"""
Script de validación automatizada del ETL analítico de QuickTrack.

Verifica que las tablas exportadas en data/export/ coincidan exactamente con
la fuente original (MongoDB Atlas o data/*.json):
1. Conteos de filas por colección/tabla.
2. Ausencia de claves primarias/foráneas nulas o duplicadas.
3. Integridad referencial del modelo estrella (hechos -> dimensiones).
4. Cuadre exacto de métricas financieras y operativas (total, entregadas, puntaje).
5. Cumplimiento de depuración RICE (ausencia de campos PII/descartados).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = DATA_DIR / "export"


def cargar_fuente_local():
    with open(DATA_DIR / "clientes.json", "r", encoding="utf-8") as f:
        clientes = json.load(f)

    def leer_jsonl(nombre):
        with open(DATA_DIR / nombre, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    return {
        "clientes": clientes,
        "ordenes_entrega": leer_jsonl("ordenes_entrega.json"),
        "rutas": leer_jsonl("rutas.json"),
        "seguimiento": leer_jsonl("seguimiento.json"),
        "valoraciones": leer_jsonl("valoraciones.json"),
    }


def cargar_fuente_atlas():
    from config.database import get_database

    db = get_database()
    db.command("ping")
    return {
        col: list(db[col].find({}))
        for col in ["clientes", "ordenes_entrega", "rutas", "seguimiento", "valoraciones"]
    }


def obtener_fuente(source: str):
    if source == "local":
        return cargar_fuente_local(), "local"
    if source == "atlas":
        return cargar_fuente_atlas(), "atlas"
    mongo_uri = os.getenv("MONGO_URI", "")
    if mongo_uri and "<password>" not in mongo_uri and "<usuario>" not in mongo_uri:
        try:
            return cargar_fuente_atlas(), "atlas"
        except Exception:
            pass
    return cargar_fuente_local(), "local"


def validar_etl(source: str = "auto") -> bool:
    fuente, modo = obtener_fuente(source)
    print(f"=== VALIDACIÓN ETL QUICKTRACK [FUENTE COMPARADA: {modo.upper()}] ===\n")

    archivos_req = [
        "fact_ordenes.csv",
        "fact_seguimiento_eventos.csv",
        "dim_rutas.csv",
        "dim_clientes.csv",
        "dim_fecha.csv",
    ]
    for arch in archivos_req:
        if not (EXPORT_DIR / arch).exists():
            print(f"[FAIL] Falta archivo requerido: data/export/{arch}")
            return False

    fact_ord = pd.read_csv(EXPORT_DIR / "fact_ordenes.csv")
    fact_ev = pd.read_csv(EXPORT_DIR / "fact_seguimiento_eventos.csv")
    dim_rutas = pd.read_csv(EXPORT_DIR / "dim_rutas.csv")
    dim_cli = pd.read_csv(EXPORT_DIR / "dim_clientes.csv")
    dim_fecha = pd.read_csv(EXPORT_DIR / "dim_fecha.csv")

    checks = []

    def check(nombre: str, ok: bool, detalle: str):
        estado = "PASS" if ok else "FAIL"
        checks.append((nombre, ok, detalle))
        print(f"  [{estado}] {nombre}: {detalle}")

    # 1. Conteos exactos
    expected_ord = len(fuente["ordenes_entrega"])
    expected_rutas = len(fuente["rutas"])
    expected_cli = len(fuente["clientes"])
    expected_ev = sum(len(s.get("historial", [])) for s in fuente["seguimiento"])

    check(
        "Conteo fact_ordenes vs ordenes_entrega",
        len(fact_ord) == expected_ord,
        f"CSV={len(fact_ord)} | Fuente={expected_ord}",
    )
    check(
        "Conteo fact_seguimiento_eventos vs $unwind(historial)",
        len(fact_ev) == expected_ev,
        f"CSV={len(fact_ev)} | Fuente={expected_ev}",
    )
    check(
        "Conteo dim_rutas vs rutas",
        len(dim_rutas) == expected_rutas,
        f"CSV={len(dim_rutas)} | Fuente={expected_rutas}",
    )
    check(
        "Conteo dim_clientes vs clientes",
        len(dim_cli) == expected_cli,
        f"CSV={len(dim_cli)} | Fuente={expected_cli}",
    )
    check(
        "Cobertura dim_fecha",
        len(dim_fecha) > 0 and set(fact_ord["fecha_key"]).issubset(set(dim_fecha["fecha_key"])),
        f"Filas calendario={len(dim_fecha)} | Todas las fechas cubiertas",
    )

    # 2. Claves nulas y unicidad
    nulos_pk = (
        fact_ord[["orden_id", "ruta_id", "cliente_num_id", "fecha_key"]].isna().sum().sum()
        + fact_ev[["evento_id", "orden_id", "ruta_id"]].isna().sum().sum()
        + dim_rutas[["ruta_id", "zona"]].isna().sum().sum()
        + dim_cli[["cliente_num_id", "pais"]].isna().sum().sum()
        + dim_fecha[["fecha_key", "fecha"]].isna().sum().sum()
    )
    check("Claves primarias/foráneas sin nulos", int(nulos_pk) == 0, f"Nulos detectados={int(nulos_pk)}")

    pk_unicas = (
        fact_ord["orden_id"].is_unique
        and fact_ev["evento_id"].is_unique
        and dim_rutas["ruta_id"].is_unique
        and dim_cli["cliente_num_id"].is_unique
        and dim_fecha["fecha_key"].is_unique
    )
    check("Unicidad de claves primarias", pk_unicas, "Todas las PK son únicas")

    # 3. Integridad referencial
    huerfanos_ruta = set(fact_ord["ruta_id"]) - set(dim_rutas["ruta_id"])
    huerfanos_cli = set(fact_ord["cliente_num_id"]) - set(dim_cli["cliente_num_id"])
    huerfanos_ev = set(fact_ev["orden_id"]) - set(fact_ord["orden_id"])
    check(
        "Integridad referencial del modelo estrella",
        len(huerfanos_ruta) == 0 and len(huerfanos_cli) == 0 and len(huerfanos_ev) == 0,
        f"Huérfanos ruta={len(huerfanos_ruta)}, cliente={len(huerfanos_cli)}, eventos={len(huerfanos_ev)}",
    )

    # 4. Cuadre numérico de KPIs
    sum_fuente = round(sum(float(o["total"]) for o in fuente["ordenes_entrega"]), 2)
    sum_csv = round(float(fact_ord["total"].sum()), 2)
    diff_sum = abs(sum_fuente - sum_csv)
    check(
        "Cuadre de Facturación Total",
        diff_sum < 0.01,
        f"CSV=${sum_csv:,.2f} | Fuente=${sum_fuente:,.2f} | Dif=${diff_sum:.4f}",
    )

    ent_fuente = sum(1 for o in fuente["ordenes_entrega"] if o["estado"] == "Entregado")
    ent_csv = int(fact_ord["es_entregado"].sum())
    check(
        "Cuadre de Órdenes Entregadas",
        ent_fuente == ent_csv,
        f"CSV={ent_csv} | Fuente={ent_fuente}",
    )

    avg_val_fuente = round(
        sum(float(v["puntaje"]) for v in fuente["valoraciones"]) / len(fuente["valoraciones"]), 4
    )
    avg_val_csv = round(float(fact_ord["puntaje"].mean()), 4)
    check(
        "Cuadre de Satisfacción Promedio",
        abs(avg_val_fuente - avg_val_csv) < 0.0001,
        f"CSV={avg_val_csv:.4f} | Fuente={avg_val_fuente:.4f}",
    )

    # 5. Cumplimiento de depuración RICE (sin campos descartados ni PII)
    campos_prohibidos = {"correo", "nombre", "comentario", "fecha_registro", "foto_evidencia_url", "color_tema_app"}
    columnas_exportadas = (
        set(fact_ord.columns)
        | set(fact_ev.columns)
        | set(dim_rutas.columns)
        | set(dim_cli.columns)
        | set(dim_fecha.columns)
    )
    presentes_prohibidos = campos_prohibidos & columnas_exportadas
    check(
        "Cumplimiento de depuración RICE (exclusión PII/descartados)",
        len(presentes_prohibidos) == 0,
        f"Campos prohibidos presentes={sorted(presentes_prohibidos)}",
    )

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print(f"\nResultado global: {passed}/{total} validaciones aprobadas.")
    return passed == total


def main():
    parser = argparse.ArgumentParser(description="Valida los CSV generados por el ETL analítico.")
    parser.add_argument(
        "--source",
        choices=["auto", "atlas", "local"],
        default="auto",
        help="Fuente contra la cual contrastar las salidas CSV.",
    )
    args = parser.parse_args()
    ok = validar_etl(source=args.source)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
