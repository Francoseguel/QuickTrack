"""
Auditoría empírica RICE sobre las 5 colecciones reales de QuickTrack.

Calcula la cobertura real (R en escala 0-1: proporción de documentos donde el
campo existe y no es nulo ni vacío) directamente desde MongoDB Atlas o desde
los archivos locales data/*.json, y genera las 3 matrices RICE por eje
analítico (Preguntas 1, 2 y 3).

Escalas RICE (Actividad 3.1.1 / EP3 BDY0101):
- R (Alcance / Cobertura empírica): 0,00 a 1,00
- I (Impacto analítico): 0,25 · 0,5 · 1 · 2 · 3
- C (Confianza en calidad del dato): 0,00 a 1,00
- E (Esfuerzo técnico de limpieza/modelado): 1 (bajo) a 5 (alto)
- Puntaje = (R * I * C) / E
- Regla: >= 1,00 Conservar | 0,50 a < 1,00 Evaluar | < 0,50 Descartar
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = DATA_DIR / "export"


def cargar_colecciones_local():
    """Lee las 5 colecciones desde data/*.json."""
    with open(DATA_DIR / "clientes.json", "r", encoding="utf-8") as f:
        clientes = json.load(f)

    def leer_jsonl(nombre):
        docs = []
        with open(DATA_DIR / nombre, "r", encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    docs.append(json.loads(linea))
        return docs

    return {
        "clientes": clientes,
        "ordenes_entrega": leer_jsonl("ordenes_entrega.json"),
        "rutas": leer_jsonl("rutas.json"),
        "seguimiento": leer_jsonl("seguimiento.json"),
        "valoraciones": leer_jsonl("valoraciones.json"),
    }


def cargar_colecciones_atlas():
    """Lee las 5 colecciones en modo solo lectura desde MongoDB Atlas."""
    from config.database import get_database

    db = get_database()
    db.command("ping")
    return {
        nombre: list(db[nombre].find({}))
        for nombre in [
            "clientes",
            "ordenes_entrega",
            "rutas",
            "seguimiento",
            "valoraciones",
        ]
    }


def obtener_colecciones(source: str):
    """Carga colecciones según el modo solicitado (auto, atlas o local)."""
    if source == "local":
        return cargar_colecciones_local(), "local"

    if source == "atlas":
        return cargar_colecciones_atlas(), "atlas"

    # Modo auto: intenta Atlas si hay MONGO_URI válida, sino fallback a local
    mongo_uri = os.getenv("MONGO_URI", "")
    if mongo_uri and "<password>" not in mongo_uri and "<usuario>" not in mongo_uri:
        try:
            return cargar_colecciones_atlas(), "atlas"
        except Exception as exc:
            print(f"[AVISO] No se pudo conectar a Atlas ({exc}). Usando modo local.")
    return cargar_colecciones_local(), "local"


def calcular_cobertura(docs, campo):
    """Calcula R empírico (0-1) para un campo plano o anidado en lista (historial[].x)."""
    total = len(docs)
    if total == 0:
        return 0.0, 0, 0

    if "[]." in campo:
        arr_field, sub_field = campo.split("[].", 1)
        validos = 0
        for doc in docs:
            arr = doc.get(arr_field)
            if isinstance(arr, list) and len(arr) > 0:
                if all(
                    isinstance(item, dict)
                    and item.get(sub_field) is not None
                    and str(item.get(sub_field)).strip() != ""
                    for item in arr
                ):
                    validos += 1
        return round(validos / total, 4), validos, total

    validos = 0
    for doc in docs:
        val = doc.get(campo)
        if val is not None and str(val).strip() != "":
            validos += 1
    return round(validos / total, 4), validos, total


def decidir_rice(puntaje: float) -> str:
    if puntaje >= 1.0:
        return "Conservar"
    if puntaje >= 0.5:
        return "Evaluar"
    return "Descartar"


# Definición de criterios I, C, E y justificación por eje analítico.
# R se calcula empíricamente desde los datos en tiempo de ejecución.
MATRIZ_DEFINICION = [
    # --- Eje 1: Táctico (Temporal y Geográfico — Pregunta 1) ---
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "rutas",
        "campo": "zona",
        "I": 3.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Agrupador geográfico principal para comparar volumen de despachos y facturación por zona logística.",
    },
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "ordenes_entrega",
        "campo": "fecha_envio",
        "I": 3.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Eje temporal indispensable para consolidar series mensuales/anuales y detectar estacionalidad.",
    },
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "rutas",
        "campo": "ciudad_origen",
        "I": 1.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Permite desglosar los tramos logísticos por nodo de despacho en la dimensión de rutas.",
    },
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "rutas",
        "campo": "ciudad_destino",
        "I": 1.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Identifica ciudades receptoras de alta demanda para planificación de rutas.",
    },
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "rutas",
        "campo": "distancia_km",
        "I": 2.0,
        "C": 0.9,
        "E": 2,
        "justificacion": "Métrica operativa secundaria; útil para correlacionar extensión de ruta con cumplimiento y costos (incluida en dim_rutas).",
    },
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "clientes",
        "campo": "pais",
        "I": 1.0,
        "C": 0.8,
        "E": 1,
        "justificacion": "Segmentación geográfica complementaria del maestro de clientes (incluida en dim_clientes).",
    },
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "clientes",
        "campo": "correo",
        "I": 0.25,
        "C": 1.0,
        "E": 2,
        "justificacion": "Dato personal identificable (PII) de contacto; sin valor en agregaciones analíticas y se excluye por privacidad.",
    },
    {
        "eje": "Pregunta 1 — Eje Táctico (Temporal y Geográfico)",
        "coleccion": "clientes",
        "campo": "nombre",
        "I": 0.25,
        "C": 1.0,
        "E": 2,
        "justificacion": "Atributo nominal PII sin valor para agregación por zonas ni KPIs ejecutivos; se excluye del modelo BI.",
    },
    # --- Eje 2: Estratégico (Financiero — Pregunta 2) ---
    {
        "eje": "Pregunta 2 — Eje Estratégico (Financiero)",
        "coleccion": "ordenes_entrega",
        "campo": "total",
        "I": 3.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Métrica monetaria central para calcular Facturación Total (KPI 1) y Ticket Promedio.",
    },
    {
        "eje": "Pregunta 2 — Eje Estratégico (Financiero)",
        "coleccion": "ordenes_entrega",
        "campo": "medio_pago",
        "I": 2.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Clasifica el canal de recaudación (Efectivo, Transferencia, Tarjeta) para decisiones comerciales.",
    },
    {
        "eje": "Pregunta 2 — Eje Estratégico (Financiero)",
        "coleccion": "rutas",
        "campo": "zona",
        "I": 3.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Segmenta la recaudación y los medios de pago por sector logístico.",
    },
    {
        "eje": "Pregunta 2 — Eje Estratégico (Financiero)",
        "coleccion": "ordenes_entrega",
        "campo": "fecha_envio",
        "I": 3.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Habilita el cierre de facturación por mes, trimestre y año.",
    },
    {
        "eje": "Pregunta 2 — Eje Estratégico (Financiero)",
        "coleccion": "clientes",
        "campo": "fecha_registro",
        "I": 0.5,
        "C": 0.8,
        "E": 2,
        "justificacion": "Fecha administrativa de alta del cliente; no explica la distribución de ingresos por zona ni medio de pago.",
    },
    # --- Eje 3: Operacional y Calidad de Servicio (Pregunta 3) ---
    {
        "eje": "Pregunta 3 — Eje Operacional (Cumplimiento y Satisfacción)",
        "coleccion": "ordenes_entrega",
        "campo": "estado",
        "I": 3.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Estado oficial de la orden; base del KPI Tasa de Cumplimiento (% Entregado) y control de cancelaciones.",
    },
    {
        "eje": "Pregunta 3 — Eje Operacional (Cumplimiento y Satisfacción)",
        "coleccion": "valoraciones",
        "campo": "puntaje",
        "I": 3.0,
        "C": 1.0,
        "E": 1,
        "justificacion": "Calificación cuantitativa (1–5); base del KPI Satisfacción Promedio y detección de casos críticos (<= 2).",
    },
    {
        "eje": "Pregunta 3 — Eje Operacional (Cumplimiento y Satisfacción)",
        "coleccion": "seguimiento",
        "campo": "historial[].estado",
        "I": 3.0,
        "C": 0.9,
        "E": 2,
        "justificacion": "Arreglo anidado de hitos logísticos; requiere $unwind para auditar transiciones de etapa y cuellos de botella.",
    },
    {
        "eje": "Pregunta 3 — Eje Operacional (Cumplimiento y Satisfacción)",
        "coleccion": "seguimiento",
        "campo": "historial[].fecha",
        "I": 3.0,
        "C": 0.9,
        "E": 2,
        "justificacion": "Marcas temporales del historial; permite derivar días en seguimiento y días hasta hito Entregado.",
    },
    {
        "eje": "Pregunta 3 — Eje Operacional (Cumplimiento y Satisfacción)",
        "coleccion": "seguimiento",
        "campo": "estado_actual",
        "I": 1.0,
        "C": 0.7,
        "E": 1,
        "justificacion": "Menor confianza (C=0,7) por desfase detectado en 82% de órdenes respecto a ordenes_entrega.estado; se usa solo como auditoría de consistencia.",
    },
    {
        "eje": "Pregunta 3 — Eje Operacional (Cumplimiento y Satisfacción)",
        "coleccion": "valoraciones",
        "campo": "comentario",
        "I": 0.5,
        "C": 0.8,
        "E": 2,
        "justificacion": "Texto cualitativo no agregable directamente en fórmulas DAX numéricas; descartado del modelo tabular principal (requeriría NLP).",
    },
]


def ejecutar_auditoria(source: str = "auto"):
    colecciones, modo_usado = obtener_colecciones(source)
    print(f"=== AUDITORÍA EMPÍRICA RICE — QUICKTRACK [MODO: {modo_usado.upper()}] ===\n")

    # 1. Cobertura general de todos los campos de las 5 colecciones
    resumen_cobertura = {}
    for col_name, docs in colecciones.items():
        campos = sorted({k for d in docs for k in d.keys()})
        resumen_cobertura[col_name] = {}
        for c in campos:
            r, validos, total = calcular_cobertura(docs, c)
            resumen_cobertura[col_name][c] = {
                "cobertura_R": r,
                "no_nulos": validos,
                "total_docs": total,
            }
        if col_name == "seguimiento":
            for sub in ["historial[].estado", "historial[].fecha"]:
                r, validos, total = calcular_cobertura(docs, sub)
                resumen_cobertura[col_name][sub] = {
                    "cobertura_R": r,
                    "no_nulos": validos,
                    "total_docs": total,
                }
            # Cobertura específica de hito "Entregado" dentro de historial
            con_entregado = sum(
                1
                for d in docs
                if any(e.get("estado") == "Entregado" for e in d.get("historial", []))
            )
            resumen_cobertura[col_name]["historial[estado=Entregado]"] = {
                "cobertura_R": round(con_entregado / len(docs), 4) if docs else 0.0,
                "no_nulos": con_entregado,
                "total_docs": len(docs),
            }

    # 2. Evaluación RICE por eje
    resultados = []
    for item in MATRIZ_DEFINICION:
        col = item["coleccion"]
        campo = item["campo"]
        r_val, validos, total = calcular_cobertura(colecciones[col], campo)
        puntaje = round((r_val * item["I"] * item["C"]) / item["E"], 2)
        decision = decidir_rice(puntaje)
        fila = {
            "eje": item["eje"],
            "atributo": f"{col}.{campo}",
            "coleccion": col,
            "campo": campo,
            "no_nulos": validos,
            "total_docs": total,
            "R": r_val,
            "I": item["I"],
            "C": item["C"],
            "E": item["E"],
            "puntaje": puntaje,
            "decision": decision,
            "justificacion": item["justificacion"],
        }
        resultados.append(fila)

    # Imprimir resumen por eje
    ejes_orden = list(dict.fromkeys(r["eje"] for r in resultados))
    for eje in ejes_orden:
        print(f"--- {eje} ---")
        print(
            f"{'Atributo':34s} | {'R':5s} | {'I':4s} | {'C':4s} | {'E':2s} | {'Score':5s} | {'Decisión':10s}"
        )
        print("-" * 80)
        for r in [x for x in resultados if x["eje"] == eje]:
            print(
                f"{r['atributo']:34s} | {r['R']:5.2f} | {r['I']:4.2f} | {r['C']:4.2f} | {r['E']:2d} | {r['puntaje']:5.2f} | {r['decision']:10s}"
            )
        print()

    # Exportar CSV y JSON
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = EXPORT_DIR / "rice_auditoria.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(resultados[0].keys()))
        writer.writeheader()
        writer.writerows(resultados)

    json_path = EXPORT_DIR / "rice_auditoria.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "modo_origen": modo_usado,
                "cobertura_colecciones": resumen_cobertura,
                "evaluacion_rice": resultados,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    unicos = {}
    for r in resultados:
        unicos[r["atributo"]] = r["decision"]
    conteo_dec = {
        d: sum(1 for v in unicos.values() if v == d)
        for d in ["Conservar", "Evaluar", "Descartar"]
    }
    print(f"Atributos únicos evaluados: {len(unicos)} -> {conteo_dec}")
    print(f"Nota: Claves estructurales (_id, cliente_id, ruta_id, orden_id) excluidas del puntaje RICE por ser PK/FK.")
    print(f"Exportado: {csv_path.relative_to(BASE_DIR)} y {json_path.relative_to(BASE_DIR)}")
    return resultados, modo_usado


def main():
    parser = argparse.ArgumentParser(
        description="Auditoría empírica RICE sobre las 5 colecciones de QuickTrack."
    )
    parser.add_argument(
        "--source",
        choices=["auto", "atlas", "local"],
        default="auto",
        help="Origen de datos: auto (Atlas con fallback local), atlas o local.",
    )
    args = parser.parse_args()
    ejecutar_auditoria(source=args.source)


if __name__ == "__main__":
    main()
