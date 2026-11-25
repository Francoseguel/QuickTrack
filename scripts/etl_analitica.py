"""
Pipeline ETL Analítico de QuickTrack (Evaluación Parcial N°3 — BDY0101).

Extrae datos desde las 5 colecciones NoSQL (ordenes_entrega, rutas, clientes,
valoraciones y seguimiento) mediante pipelines de agregación MongoDB ($lookup,
$unwind, $match, $addFields, $project), aplica limpieza, tipado y modelado
estrella con pandas, y exporta los archivos CSV (UTF-8 con BOM) a data/export/.

Modos de ejecución:
- --source auto  : Intenta conectar a MongoDB Atlas vía config/database.py; si
                   no hay .env configurado o Atlas no responde, utiliza data/*.json.
- --source atlas : Obliga la extracción en solo lectura desde MongoDB Atlas.
- --source local : Lee directamente data/*.json (reproducible sin credenciales).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = DATA_DIR / "export"

# =============================================================================
# PIPELINES DE AGREGACIÓN MONGODB (IE1 — Consultas complejas sobre 5 colecciones)
# =============================================================================

# Pipeline 1: Cruce de 5 colecciones (ordenes_entrega + rutas + clientes +
# valoraciones + seguimiento) resolviendo el cruce de tipos ("cli_N" -> int N)
# y calculando métricas derivadas desde el arreglo anidado seguimiento.historial.
PIPELINE_ORDENES_ANALITICA = [
    {
        "$match": {
            "_id": {"$ne": None},
            "total": {"$gte": 0},
        }
    },
    {
        "$addFields": {
            "cliente_num_id": {
                "$ifNull": [
                    "$cliente_num_id",
                    {
                        "$toInt": {
                            "$replaceOne": {
                                "input": "$cliente_id",
                                "find": "cli_",
                                "replacement": "",
                            }
                        }
                    },
                ]
            }
        }
    },
    {
        "$lookup": {
            "from": "rutas",
            "localField": "ruta_id",
            "foreignField": "_id",
            "as": "info_ruta",
        }
    },
    {
        "$lookup": {
            "from": "clientes",
            "localField": "cliente_num_id",
            "foreignField": "_id",
            "as": "info_cliente",
        }
    },
    {
        "$lookup": {
            "from": "valoraciones",
            "localField": "_id",
            "foreignField": "orden_id",
            "as": "info_valoracion",
        }
    },
    {
        "$lookup": {
            "from": "seguimiento",
            "localField": "_id",
            "foreignField": "orden_id",
            "as": "info_seguimiento",
        }
    },
    {"$unwind": {"path": "$info_ruta", "preserveNullAndEmptyArrays": True}},
    {"$unwind": {"path": "$info_cliente", "preserveNullAndEmptyArrays": True}},
    {"$unwind": {"path": "$info_valoracion", "preserveNullAndEmptyArrays": True}},
    {"$unwind": {"path": "$info_seguimiento", "preserveNullAndEmptyArrays": True}},
    {
        "$project": {
            "_id": 0,
            "orden_id": "$_id",
            "cliente_id_str": "$cliente_id",
            "cliente_num_id": "$cliente_num_id",
            "ruta_id": "$ruta_id",
            "fecha_envio": "$fecha_envio",
            "estado": "$estado",
            "medio_pago": "$medio_pago",
            "total": "$total",
            "zona": "$info_ruta.zona",
            "ciudad_origen": "$info_ruta.ciudad_origen",
            "ciudad_destino": "$info_ruta.ciudad_destino",
            "distancia_km": "$info_ruta.distancia_km",
            "pais_cliente": "$info_cliente.pais",
            "puntaje": "$info_valoracion.puntaje",
            "estado_actual_seg": "$info_seguimiento.estado_actual",
            "historial": "$info_seguimiento.historial",
        }
    },
]

# Pipeline 2: Despliegue ($unwind) del arreglo anidado seguimiento.historial
# cruzado con ordenes_entrega y rutas (3 colecciones) para analizar eventos y tiempos.
PIPELINE_SEGUIMIENTO_EVENTOS = [
    {"$match": {"historial": {"$exists": True, "$ne": []}}},
    {
        "$lookup": {
            "from": "ordenes_entrega",
            "localField": "orden_id",
            "foreignField": "_id",
            "as": "info_orden",
        }
    },
    {"$unwind": {"path": "$info_orden", "preserveNullAndEmptyArrays": False}},
    {
        "$lookup": {
            "from": "rutas",
            "localField": "info_orden.ruta_id",
            "foreignField": "_id",
            "as": "info_ruta",
        }
    },
    {"$unwind": {"path": "$info_ruta", "preserveNullAndEmptyArrays": True}},
    {
        "$unwind": {
            "path": "$historial",
            "includeArrayIndex": "orden_evento",
        }
    },
    {
        "$project": {
            "_id": 0,
            "seg_id": "$_id",
            "orden_id": "$orden_id",
            "ruta_id": "$info_orden.ruta_id",
            "zona": "$info_ruta.zona",
            "estado_orden": "$info_orden.estado",
            "estado_actual_seg": "$estado_actual",
            "orden_evento": {"$add": ["$orden_evento", 1]},
            "estado_evento": "$historial.estado",
            "fecha_evento": "$historial.fecha",
        }
    },
    {"$sort": {"orden_id": 1, "orden_evento": 1}},
]

# Pipeline 3: Agregación analítica directa por zona (verificación de KPIs en motor NoSQL)
PIPELINE_KPI_POR_ZONA = [
    {
        "$lookup": {
            "from": "rutas",
            "localField": "ruta_id",
            "foreignField": "_id",
            "as": "info_ruta",
        }
    },
    {"$unwind": "$info_ruta"},
    {
        "$lookup": {
            "from": "valoraciones",
            "localField": "_id",
            "foreignField": "orden_id",
            "as": "info_val",
        }
    },
    {"$unwind": {"path": "$info_val", "preserveNullAndEmptyArrays": True}},
    {
        "$group": {
            "_id": "$info_ruta.zona",
            "volumen_ordenes": {"$sum": 1},
            "facturacion_total": {"$sum": "$total"},
            "ordenes_entregadas": {
                "$sum": {"$cond": [{"$eq": ["$estado", "Entregado"]}, 1, 0]}
            },
            "satisfaccion_promedio": {"$avg": "$info_val.puntaje"},
        }
    },
    {
        "$project": {
            "_id": 0,
            "zona": "$_id",
            "volumen_ordenes": 1,
            "facturacion_total": {"$round": ["$facturacion_total", 2]},
            "tasa_cumplimiento_pct": {
                "$round": [
                    {
                        "$multiply": [
                            {"$divide": ["$ordenes_entregadas", "$volumen_ordenes"]},
                            100,
                        ]
                    },
                    2,
                ]
            },
            "satisfaccion_promedio": {"$round": ["$satisfaccion_promedio", 2]},
        }
    },
    {"$sort": {"facturacion_total": -1}},
]


# =============================================================================
# EXTRACCIÓN (ATLAS O LOCAL)
# =============================================================================

def leer_jsonl_local(ruta_archivo: Path):
    docs = []
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                docs.append(json.loads(linea))
    return docs


def extraer_desde_atlas():
    """Ejecuta los pipelines de agregación en modo solo lectura sobre MongoDB Atlas."""
    from config.database import get_database

    db = get_database()
    db.command("ping")

    ordenes_raw = list(db["ordenes_entrega"].aggregate(PIPELINE_ORDENES_ANALITICA))
    eventos_raw = list(db["seguimiento"].aggregate(PIPELINE_SEGUIMIENTO_EVENTOS))
    rutas_raw = list(
        db["rutas"].find(
            {},
            {"_id": 1, "zona": 1, "ciudad_origen": 1, "ciudad_destino": 1, "distancia_km": 1},
        )
    )
    clientes_raw = list(db["clientes"].find({}, {"_id": 1, "pais": 1}))
    return ordenes_raw, eventos_raw, rutas_raw, clientes_raw


def extraer_desde_local():
    """Replica exactamente los pipelines de agregación sobre data/*.json (modo reproducible)."""
    with open(DATA_DIR / "clientes.json", "r", encoding="utf-8") as f:
        clientes = json.load(f)
    ordenes = leer_jsonl_local(DATA_DIR / "ordenes_entrega.json")
    rutas = leer_jsonl_local(DATA_DIR / "rutas.json")
    seguimiento = leer_jsonl_local(DATA_DIR / "seguimiento.json")
    valoraciones = leer_jsonl_local(DATA_DIR / "valoraciones.json")

    rutas_idx = {r["_id"]: r for r in rutas}
    clientes_idx = {c["_id"]: c for c in clientes}
    val_idx = {v["orden_id"]: v for v in valoraciones}
    seg_idx = {s["orden_id"]: s for s in seguimiento}
    ord_idx = {o["_id"]: o for o in ordenes}

    # Equivalente exacto de PIPELINE_ORDENES_ANALITICA
    ordenes_raw = []
    for o in ordenes:
        if o.get("_id") is None or (o.get("total") is not None and o["total"] < 0):
            continue
        cli_str = o.get("cliente_id", "")
        cli_num = o.get("cliente_num_id")
        if cli_num is None and isinstance(cli_str, str) and cli_str.startswith("cli_"):
            cli_num = int(cli_str.replace("cli_", ""))
        r = rutas_idx.get(o.get("ruta_id"), {})
        c = clientes_idx.get(cli_num, {})
        v = val_idx.get(o["_id"], {})
        s = seg_idx.get(o["_id"], {})
        ordenes_raw.append(
            {
                "orden_id": o["_id"],
                "cliente_id_str": cli_str,
                "cliente_num_id": cli_num,
                "ruta_id": o.get("ruta_id"),
                "fecha_envio": o.get("fecha_envio"),
                "estado": o.get("estado"),
                "medio_pago": o.get("medio_pago"),
                "total": o.get("total"),
                "zona": r.get("zona"),
                "ciudad_origen": r.get("ciudad_origen"),
                "ciudad_destino": r.get("ciudad_destino"),
                "distancia_km": r.get("distancia_km"),
                "pais_cliente": c.get("pais"),
                "puntaje": v.get("puntaje"),
                "estado_actual_seg": s.get("estado_actual"),
                "historial": s.get("historial", []),
            }
        )

    # Equivalente exacto de PIPELINE_SEGUIMIENTO_EVENTOS ($unwind sobre historial)
    eventos_raw = []
    for s in seguimiento:
        hist = s.get("historial") or []
        if not hist:
            continue
        o = ord_idx.get(s.get("orden_id"))
        if not o:
            continue
        r = rutas_idx.get(o.get("ruta_id"), {})
        for idx, ev in enumerate(hist, start=1):
            eventos_raw.append(
                {
                    "seg_id": s["_id"],
                    "orden_id": s["orden_id"],
                    "ruta_id": o.get("ruta_id"),
                    "zona": r.get("zona"),
                    "estado_orden": o.get("estado"),
                    "estado_actual_seg": s.get("estado_actual"),
                    "orden_evento": idx,
                    "estado_evento": ev.get("estado"),
                    "fecha_evento": ev.get("fecha"),
                }
            )
    eventos_raw.sort(key=lambda x: (x["orden_id"], x["orden_evento"]))

    # Dimensiones depuradas según matriz RICE (sin PII correo/nombre ni fecha_registro)
    rutas_raw = [
        {
            "_id": r["_id"],
            "zona": r.get("zona"),
            "ciudad_origen": r.get("ciudad_origen"),
            "ciudad_destino": r.get("ciudad_destino"),
            "distancia_km": r.get("distancia_km"),
        }
        for r in rutas
    ]
    clientes_raw = [{"_id": c["_id"], "pais": c.get("pais")} for c in clientes]
    return ordenes_raw, eventos_raw, rutas_raw, clientes_raw


def extraer_datos(source: str):
    if source == "local":
        return extraer_desde_local(), "local"
    if source == "atlas":
        return extraer_desde_atlas(), "atlas"

    mongo_uri = os.getenv("MONGO_URI", "")
    if mongo_uri and "<password>" not in mongo_uri and "<usuario>" not in mongo_uri:
        try:
            return extraer_desde_atlas(), "atlas"
        except Exception as exc:
            print(f"[AVISO] Conexión a Atlas no disponible ({exc}). Usando fallback --source local.")
    return extraer_desde_local(), "local"


# =============================================================================
# TRANSFORMACIONES Y MODELO ESTRELLA
# =============================================================================

MESES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

DIAS_ES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def calcular_metricas_historial(historial):
    """Deriva duración y cumplimiento de hitos desde el arreglo anidado historial."""
    if not isinstance(historial, list) or len(historial) == 0:
        return pd.Series(
            {
                "num_eventos_seg": 0,
                "fecha_primer_evento_seg": pd.NaT,
                "fecha_ultimo_evento_seg": pd.NaT,
                "dias_en_seguimiento": pd.NA,
                "dias_hasta_entrega_historial": pd.NA,
                "tiene_entregado_historial": 0,
            }
        )

    eventos = []
    for ev in historial:
        ts = pd.to_datetime(ev.get("fecha"), errors="coerce")
        est = str(ev.get("estado", "")).strip()
        if pd.notna(ts):
            eventos.append((ts, est))

    if not eventos:
        return pd.Series(
            {
                "num_eventos_seg": 0,
                "fecha_primer_evento_seg": pd.NaT,
                "fecha_ultimo_evento_seg": pd.NaT,
                "dias_en_seguimiento": pd.NA,
                "dias_hasta_entrega_historial": pd.NA,
                "tiene_entregado_historial": 0,
            }
        )

    eventos.sort(key=lambda x: x[0])
    f_inicio = eventos[0][0]
    f_fin = eventos[-1][0]
    dias_seg = int((f_fin - f_inicio).days)

    fechas_ent = [ts for ts, est in eventos if est == "Entregado"]
    if fechas_ent:
        dias_ent = int((fechas_ent[-1] - f_inicio).days)
        tiene_ent = 1
    else:
        dias_ent = pd.NA
        tiene_ent = 0

    return pd.Series(
        {
            "num_eventos_seg": len(eventos),
            "fecha_primer_evento_seg": f_inicio,
            "fecha_ultimo_evento_seg": f_fin,
            "dias_en_seguimiento": dias_seg,
            "dias_hasta_entrega_historial": dias_ent,
            "tiene_entregado_historial": tiene_ent,
        }
    )


def normalizar_texto(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)


def clasificar_distancia(km: float) -> str:
    if pd.isna(km):
        return "Sin dato"
    if km < 600:
        return "Corta (< 600 km)"
    if km <= 1300:
        return "Media (600–1.300 km)"
    return "Larga (> 1.300 km)"


def construir_dim_fecha(fechas: pd.Series) -> pd.DataFrame:
    f_min = fechas.min().normalize()
    f_max = fechas.max().normalize()
    rango = pd.date_range(start=f_min, end=f_max, freq="D")
    df_fecha = pd.DataFrame({"fecha": rango})
    df_fecha["fecha_key"] = df_fecha["fecha"].dt.strftime("%Y%m%d").astype(int)
    df_fecha["anio"] = df_fecha["fecha"].dt.year
    df_fecha["trimestre"] = "T" + df_fecha["fecha"].dt.quarter.astype(str)
    df_fecha["mes"] = df_fecha["fecha"].dt.month
    df_fecha["nombre_mes"] = df_fecha["mes"].map(MESES_ES)
    df_fecha["anio_mes"] = df_fecha["fecha"].dt.strftime("%Y-%m")
    df_fecha["dia_semana"] = df_fecha["fecha"].dt.dayofweek.map(DIAS_ES)
    df_fecha["es_fin_de_semana"] = (df_fecha["fecha"].dt.dayofweek >= 5).astype(int)
    df_fecha["fecha"] = df_fecha["fecha"].dt.strftime("%Y-%m-%d")
    return df_fecha[
        [
            "fecha_key",
            "fecha",
            "anio",
            "trimestre",
            "mes",
            "nombre_mes",
            "anio_mes",
            "dia_semana",
            "es_fin_de_semana",
        ]
    ]


def ejecutar_etl(source: str = "auto"):
    trazabilidad = []

    def registrar(paso, antes, despues, detalle=""):
        trazabilidad.append(
            {
                "paso": paso,
                "filas_antes": int(antes),
                "filas_despues": int(despues),
                "detalle": detalle,
            }
        )
        print(f"  [{paso}] antes={antes} -> después={despues} | {detalle}")

    (ordenes_raw, eventos_raw, rutas_raw, clientes_raw), modo_usado = extraer_datos(source)
    print(f"=== ETL ANALÍTICO QUICKTRACK [MODO: {modo_usado.upper()}] ===")

    # -------------------------------------------------------------------------
    # 1. Tabla de Hechos: fact_ordenes
    # -------------------------------------------------------------------------
    df_ord = pd.DataFrame(ordenes_raw)
    n0 = len(df_ord)
    registrar("1. Extracción ordenes_entrega (5 colecciones)", n0, n0, "Cruce $lookup completado")

    # Aplanamiento de métricas derivadas desde seguimiento.historial
    metricas_hist = df_ord["historial"].apply(calcular_metricas_historial)
    df_ord = pd.concat([df_ord.drop(columns=["historial"]), metricas_hist], axis=1)
    registrar(
        "2. Aplanamiento métricas de seguimiento.historial",
        n0,
        len(df_ord),
        "Derivados dias_en_seguimiento y dias_hasta_entrega_historial",
    )

    # Tipado y normalización de categorías
    df_ord["fecha_envio_dt"] = pd.to_datetime(df_ord["fecha_envio"], errors="coerce")
    df_ord["total"] = pd.to_numeric(df_ord["total"], errors="coerce")
    df_ord["distancia_km"] = pd.to_numeric(df_ord["distancia_km"], errors="coerce")
    df_ord["puntaje"] = pd.to_numeric(df_ord["puntaje"], errors="coerce").astype("Int64")
    df_ord["cliente_num_id"] = pd.to_numeric(df_ord["cliente_num_id"], errors="coerce").astype("Int64")

    for col_txt in [
        "orden_id",
        "cliente_id_str",
        "ruta_id",
        "estado",
        "medio_pago",
        "zona",
        "ciudad_origen",
        "ciudad_destino",
        "pais_cliente",
        "estado_actual_seg",
    ]:
        df_ord[col_txt] = normalizar_texto(df_ord[col_txt])

    # Limpieza de nulos críticos y duplicados por clave primaria
    n_antes = len(df_ord)
    df_ord = df_ord.drop_duplicates(subset=["orden_id"], keep="first")
    df_ord = df_ord.dropna(subset=["orden_id", "ruta_id", "cliente_num_id", "fecha_envio_dt", "total"])
    registrar(
        "3. Limpieza de duplicados y claves nulas (fact_ordenes)",
        n_antes,
        len(df_ord),
        f"Descartadas {n_antes - len(df_ord)} filas inválidas",
    )

    # Integridad referencial (huérfanos frente a rutas y clientes)
    rutas_validas = {r["_id"] for r in rutas_raw}
    clientes_validos = {c["_id"] for c in clientes_raw}
    n_antes = len(df_ord)
    df_ord = df_ord[
        df_ord["ruta_id"].isin(rutas_validas) & df_ord["cliente_num_id"].isin(clientes_validos)
    ].copy()
    registrar(
        "4. Control de huérfanos referenciales (fact_ordenes)",
        n_antes,
        len(df_ord),
        f"Huérfanos eliminados: {n_antes - len(df_ord)}",
    )

    # Columnas analíticas derivadas
    df_ord["fecha_key"] = df_ord["fecha_envio_dt"].dt.strftime("%Y%m%d").astype(int)
    df_ord["fecha_envio"] = df_ord["fecha_envio_dt"].dt.strftime("%Y-%m-%d")
    df_ord["anio"] = df_ord["fecha_envio_dt"].dt.year
    df_ord["mes"] = df_ord["fecha_envio_dt"].dt.month
    df_ord["anio_mes"] = df_ord["fecha_envio_dt"].dt.strftime("%Y-%m")
    df_ord["es_entregado"] = (df_ord["estado"] == "Entregado").astype(int)
    df_ord["es_cancelado"] = (df_ord["estado"] == "Cancelado").astype(int)
    df_ord["es_valoracion_critica"] = (df_ord["puntaje"] <= 2).astype(int)
    df_ord["discrepancia_estado_seg"] = (
        df_ord["estado"] != df_ord["estado_actual_seg"]
    ).astype(int)
    df_ord["fecha_primer_evento_seg"] = pd.to_datetime(
        df_ord["fecha_primer_evento_seg"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    df_ord["fecha_ultimo_evento_seg"] = pd.to_datetime(
        df_ord["fecha_ultimo_evento_seg"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    fact_ordenes_cols = [
        "orden_id",
        "fecha_key",
        "fecha_envio",
        "anio",
        "mes",
        "anio_mes",
        "cliente_num_id",
        "ruta_id",
        "zona",
        "estado",
        "medio_pago",
        "total",
        "puntaje",
        "es_entregado",
        "es_cancelado",
        "es_valoracion_critica",
        "num_eventos_seg",
        "dias_en_seguimiento",
        "dias_hasta_entrega_historial",
        "tiene_entregado_historial",
        "estado_actual_seg",
        "discrepancia_estado_seg",
    ]
    fact_ordenes = df_ord[fact_ordenes_cols].copy()

    # -------------------------------------------------------------------------
    # 2. Tabla de Hechos de Eventos: fact_seguimiento_eventos ($unwind historial)
    # -------------------------------------------------------------------------
    df_ev = pd.DataFrame(eventos_raw)
    n_ev_0 = len(df_ev)
    df_ev["fecha_evento_dt"] = pd.to_datetime(df_ev["fecha_evento"], errors="coerce")
    for col_txt in ["seg_id", "orden_id", "ruta_id", "zona", "estado_orden", "estado_evento"]:
        df_ev[col_txt] = normalizar_texto(df_ev[col_txt])

    df_ev = df_ev.dropna(subset=["seg_id", "orden_id", "estado_evento", "fecha_evento_dt"]).copy()
    df_ev = df_ev.sort_values(["orden_id", "fecha_evento_dt", "orden_evento"]).reset_index(drop=True)
    df_ev["evento_id"] = df_ev["seg_id"] + "_ev" + df_ev["orden_evento"].astype(str)

    # Días acumulados y días entre etapas dentro del historial de cada orden
    df_ev["fecha_inicio_ord"] = df_ev.groupby("orden_id")["fecha_evento_dt"].transform("min")
    df_ev["dias_desde_inicio"] = (df_ev["fecha_evento_dt"] - df_ev["fecha_inicio_ord"]).dt.days
    df_ev["dias_desde_evento_anterior"] = (
        df_ev.groupby("orden_id")["fecha_evento_dt"].diff().dt.days.fillna(0).astype(int)
    )
    df_ev["fecha_evento"] = df_ev["fecha_evento_dt"].dt.strftime("%Y-%m-%d")

    fact_seguimiento = df_ev[
        [
            "evento_id",
            "seg_id",
            "orden_id",
            "ruta_id",
            "zona",
            "orden_evento",
            "estado_evento",
            "fecha_evento",
            "dias_desde_inicio",
            "dias_desde_evento_anterior",
        ]
    ].copy()
    registrar(
        "5. Despliegue de eventos ($unwind seguimiento.historial)",
        n_ev_0,
        len(fact_seguimiento),
        "Eventos individuales normalizados con cálculo de duración entre hitos",
    )

    # -------------------------------------------------------------------------
    # 3. Dimensiones: dim_rutas, dim_clientes, dim_fecha
    # -------------------------------------------------------------------------
    dim_rutas = pd.DataFrame(rutas_raw).rename(columns={"_id": "ruta_id"})
    n_r_0 = len(dim_rutas)
    for c in ["ruta_id", "zona", "ciudad_origen", "ciudad_destino"]:
        dim_rutas[c] = normalizar_texto(dim_rutas[c])
    dim_rutas["distancia_km"] = pd.to_numeric(dim_rutas["distancia_km"], errors="coerce").round(2)
    dim_rutas["tramo"] = dim_rutas["ciudad_origen"] + " → " + dim_rutas["ciudad_destino"]
    dim_rutas["rango_distancia"] = dim_rutas["distancia_km"].apply(clasificar_distancia)
    dim_rutas = dim_rutas.drop_duplicates(subset=["ruta_id"]).dropna(subset=["ruta_id", "zona"])
    registrar(
        "6. Dimensión dim_rutas",
        n_r_0,
        len(dim_rutas),
        "Atributos geográficos y distancia clasificada por rango",
    )

    dim_clientes = pd.DataFrame(clientes_raw).rename(columns={"_id": "cliente_num_id"})
    n_c_0 = len(dim_clientes)
    dim_clientes["cliente_num_id"] = pd.to_numeric(
        dim_clientes["cliente_num_id"], errors="coerce"
    ).astype("Int64")
    dim_clientes["cliente_id_str"] = "cli_" + dim_clientes["cliente_num_id"].astype(str)
    dim_clientes["pais"] = normalizar_texto(dim_clientes["pais"])
    dim_clientes = dim_clientes.drop_duplicates(subset=["cliente_num_id"]).dropna(
        subset=["cliente_num_id"]
    )
    dim_clientes = dim_clientes[["cliente_num_id", "cliente_id_str", "pais"]]
    registrar(
        "7. Dimensión dim_clientes (PII excluido por RICE)",
        n_c_0,
        len(dim_clientes),
        "Normalizado cliente_num_id (int) <-> cliente_id_str ('cli_N'); sin nombre/correo",
    )

    dim_fecha = construir_dim_fecha(df_ord["fecha_envio_dt"])
    registrar(
        "8. Dimensión dim_fecha (calendario continuo)",
        df_ord["fecha_envio_dt"].nunique(),
        len(dim_fecha),
        f"Rango {dim_fecha['fecha'].min()} a {dim_fecha['fecha'].max()}",
    )

    # -------------------------------------------------------------------------
    # 4. Exportación CSV (UTF-8 con BOM) + Metadata de ejecución
    # -------------------------------------------------------------------------
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    salidas = {
        "fact_ordenes.csv": fact_ordenes,
        "fact_seguimiento_eventos.csv": fact_seguimiento,
        "dim_rutas.csv": dim_rutas,
        "dim_clientes.csv": dim_clientes,
        "dim_fecha.csv": dim_fecha,
    }
    for nombre_archivo, df_out in salidas.items():
        ruta_out = EXPORT_DIR / nombre_archivo
        df_out.to_csv(ruta_out, index=False, encoding="utf-8-sig")

    resumen_kpis = {
        "facturacion_total": round(float(fact_ordenes["total"].sum()), 2),
        "volumen_ordenes": int(len(fact_ordenes)),
        "ordenes_entregadas": int(fact_ordenes["es_entregado"].sum()),
        "tasa_cumplimiento_pct": round(float(fact_ordenes["es_entregado"].mean() * 100), 2),
        "satisfaccion_promedio": round(float(fact_ordenes["puntaje"].mean()), 2),
        "ticket_promedio": round(float(fact_ordenes["total"].mean()), 2),
        "valoraciones_criticas": int(fact_ordenes["es_valoracion_critica"].sum()),
        "dias_seguimiento_promedio": round(
            float(fact_ordenes["dias_en_seguimiento"].dropna().mean()), 2
        ),
        "discrepancias_estado_seg": int(fact_ordenes["discrepancia_estado_seg"].sum()),
    }

    metadata = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "modo_origen": modo_usado,
        "archivos_generados": {k: int(len(v)) for k, v in salidas.items()},
        "trazabilidad_pasos": trazabilidad,
        "kpis_resumen": resumen_kpis,
    }
    with open(EXPORT_DIR / "etl_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("\n--- RESUMEN KPIs EXPORTADOS ---")
    print(f"  1. Facturación Total       : ${resumen_kpis['facturacion_total']:,.2f}")
    print(f"  2. Volumen de Órdenes      : {resumen_kpis['volumen_ordenes']}")
    print(
        f"  3. Tasa de Cumplimiento    : {resumen_kpis['tasa_cumplimiento_pct']:.2f}% "
        f"({resumen_kpis['ordenes_entregadas']}/{resumen_kpis['volumen_ordenes']})"
    )
    print(f"  4. Satisfacción Promedio   : {resumen_kpis['satisfaccion_promedio']:.2f} / 5.00")
    print(f"  *  Ticket Promedio (sec.)  : ${resumen_kpis['ticket_promedio']:,.2f}")
    print(f"\nExportación completada en: {EXPORT_DIR.relative_to(BASE_DIR)}/")
    return metadata


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline ETL analítico de QuickTrack hacia modelo estrella CSV."
    )
    parser.add_argument(
        "--source",
        choices=["auto", "atlas", "local"],
        default="auto",
        help="Origen de datos: auto (Atlas con fallback local), atlas o local.",
    )
    args = parser.parse_args()
    ejecutar_etl(source=args.source)


if __name__ == "__main__":
    main()
