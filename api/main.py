import os
import sys
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

# Asegurar importación de config y scripts
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config.database import get_database
from api.models import OrdenCrear, ActualizarEstado
from api.middlewares import ProcessTimeMiddleware, global_exception_handler
from scripts.etl_analitica import (
    PIPELINE_KPI_POR_ZONA,
    PIPELINE_ORDENES_ANALITICA,
    PIPELINE_SEGUIMIENTO_EVENTOS,
    calcular_metricas_historial,
    extraer_datos,
)

app = FastAPI(
    title="QuickTrack Logistics API",
    description="API RESTful para la gestión logística NoSQL sobre MongoDB Atlas y capa analítica BI",
    version="1.1.0"
)

# Registrar Middlewares y Excepciones
app.add_middleware(ProcessTimeMiddleware)
app.add_exception_handler(Exception, global_exception_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Healthcheck"])
def root():
    return {
        "status": "online",
        "sistema": "QuickTrack NoSQL Engine",
        "base_datos": "MongoDB Atlas"
    }


# 1. CREATE
@app.post("/ordenes", status_code=status.HTTP_201_CREATED, tags=["Órdenes"])
def crear_orden(orden: OrdenCrear):
    db = get_database()
    if db.ordenes_entrega.find_one({"_id": orden.id}):
        raise HTTPException(status_code=400, detail=f"La orden '{orden.id}' ya existe.")

    doc_orden = {
        "_id": orden.id,
        "cliente_id": orden.cliente_id,
        "ruta_id": orden.ruta_id,
        "fecha_envio": "2026-03-30T10:00:00",
        "estado": "En preparación",
        "medio_pago": orden.medio_pago,
        "total": orden.total
    }
    if isinstance(orden.cliente_id, str) and orden.cliente_id.startswith("cli_"):
        try:
            doc_orden["cliente_num_id"] = int(orden.cliente_id.replace("cli_", ""))
        except ValueError:
            pass

    db.ordenes_entrega.insert_one(doc_orden)

    db.seguimiento.insert_one({
        "_id": f"seg_{orden.id}",
        "orden_id": orden.id,
        "estado_actual": "En preparación",
        "historial": [{"estado": "En preparación", "fecha": "2026-03-30T10:00:00"}]
    })

    return {"mensaje": "Orden creada exitosamente", "orden_id": orden.id}


# 2. READ (Por ID)
@app.get("/ordenes/{orden_id}", tags=["Órdenes"])
def obtener_orden(orden_id: str):
    db = get_database()
    pipeline = [
        {"$match": {"_id": orden_id}},
        {
            "$lookup": {
                "from": "seguimiento",
                "localField": "_id",
                "foreignField": "orden_id",
                "as": "seguimiento"
            }
        }
    ]
    resultado = list(db.ordenes_entrega.aggregate(pipeline))
    if not resultado:
        raise HTTPException(status_code=404, detail=f"Orden '{orden_id}' no encontrada.")
    return resultado[0]


# 3. UPDATE
@app.put("/ordenes/{orden_id}/estado", tags=["Órdenes"])
def actualizar_estado(orden_id: str, datos: ActualizarEstado):
    db = get_database()
    res = db.ordenes_entrega.update_one(
        {"_id": orden_id},
        {"$set": {"estado": datos.nuevo_estado}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Orden '{orden_id}' no encontrada.")

    db.seguimiento.update_one(
        {"orden_id": orden_id},
        {
            "$set": {"estado_actual": datos.nuevo_estado},
            "$push": {"historial": {"estado": datos.nuevo_estado, "fecha": datos.fecha_evento}}
        }
    )

    return {"mensaje": f"Estado de la orden '{orden_id}' actualizado a '{datos.nuevo_estado}'"}


# 4. DELETE
@app.delete("/ordenes/{orden_id}", tags=["Órdenes"])
def eliminar_orden(orden_id: str):
    db = get_database()
    db.valoraciones.delete_many({"orden_id": orden_id})
    db.seguimiento.delete_many({"orden_id": orden_id})
    res = db.ordenes_entrega.delete_one({"_id": orden_id})

    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Orden '{orden_id}' no encontrada.")

    return {"mensaje": f"Orden '{orden_id}' y sus datos asociados fueron eliminados."}


# 5. ANALYTICS (Fuente JSON alternativa para Power BI / Web.Contents)
@app.get("/analitica/rendimiento-zonas", tags=["Analítica"])
def obtener_rendimiento_zonas(
    source: str = Query(default="auto", pattern="^(auto|atlas|local)$")
):
    """
    Devuelve facturación, volumen, tasa de cumplimiento y satisfacción por zona.
    Compatible con el contrato previo (_id, total_ordenes, monto_total, promedio_monto).
    """
    if source == "atlas":
        db = get_database()
        return list(db.ordenes_entrega.aggregate(PIPELINE_KPI_POR_ZONA))

    (ordenes_raw, _, _, _), modo = extraer_datos(source)
    zonas = {}
    for o in ordenes_raw:
        z = o.get("zona") or "Sin zona"
        bucket = zonas.setdefault(
            z, {"_id": z, "zona": z, "total_ordenes": 0, "monto_total": 0.0, "entregadas": 0, "puntajes": []}
        )
        bucket["total_ordenes"] += 1
        bucket["monto_total"] += float(o.get("total") or 0.0)
        if o.get("estado") == "Entregado":
            bucket["entregadas"] += 1
        if o.get("puntaje") is not None:
            bucket["puntajes"].append(float(o["puntaje"]))

    resultado = []
    for b in zonas.values():
        n = b["total_ordenes"]
        resultado.append({
            "_id": b["_id"],
            "zona": b["zona"],
            "total_ordenes": n,
            "monto_total": round(b["monto_total"], 2),
            "promedio_monto": round(b["monto_total"] / n, 2) if n else 0.0,
            "tasa_cumplimiento_pct": round((b["entregadas"] / n) * 100, 2) if n else 0.0,
            "satisfaccion_promedio": round(sum(b["puntajes"]) / len(b["puntajes"]), 2) if b["puntajes"] else None,
            "modo_origen": modo,
        })
    resultado.sort(key=lambda x: x["monto_total"], reverse=True)
    return resultado


@app.get("/analitica/kpis", tags=["Analítica"])
def obtener_kpis_ejecutivos(
    source: str = Query(default="auto", pattern="^(auto|atlas|local)$")
):
    """Retorna los 4 KPIs oficiales del dashboard más indicadores secundarios."""
    (ordenes_raw, eventos_raw, _, _), modo = extraer_datos(source)
    n = len(ordenes_raw)
    facturacion = round(sum(float(o.get("total") or 0.0) for o in ordenes_raw), 2)
    entregadas = sum(1 for o in ordenes_raw if o.get("estado") == "Entregado")
    puntajes = [float(o["puntaje"]) for o in ordenes_raw if o.get("puntaje") is not None]

    return {
        "modo_origen": modo,
        "kpis_principales": {
            "facturacion_total": facturacion,
            "volumen_ordenes": n,
            "tasa_cumplimiento_pct": round((entregadas / n) * 100, 2) if n else 0.0,
            "satisfaccion_promedio": round(sum(puntajes) / len(puntajes), 2) if puntajes else None,
        },
        "indicadores_secundarios": {
            "ticket_promedio": round(facturacion / n, 2) if n else 0.0,
            "ordenes_entregadas": entregadas,
            "ordenes_canceladas": sum(1 for o in ordenes_raw if o.get("estado") == "Cancelado"),
            "valoraciones_criticas": sum(1 for p in puntajes if p <= 2),
            "total_eventos_seguimiento": len(eventos_raw),
        },
    }


@app.get("/analitica/ordenes", tags=["Analítica"])
def obtener_ordenes_analitica(
    source: str = Query(default="auto", pattern="^(auto|atlas|local)$")
):
    """
    Retorna la tabla plana de órdenes (cruce de 5 colecciones + métricas derivadas
    de seguimiento) lista para consumo directo desde Power BI (Web.Contents).
    """
    (ordenes_raw, _, _, _), _ = extraer_datos(source)
    salida = []
    for o in ordenes_raw:
        m = calcular_metricas_historial(o.get("historial"))
        dias_seg = None if m["dias_en_seguimiento"] is None or str(m["dias_en_seguimiento"]) == "<NA>" else int(m["dias_en_seguimiento"])
        dias_ent = None if m["dias_hasta_entrega_historial"] is None or str(m["dias_hasta_entrega_historial"]) == "<NA>" else int(m["dias_hasta_entrega_historial"])
        salida.append({
            "orden_id": o["orden_id"],
            "fecha_envio": str(o["fecha_envio"])[:10],
            "cliente_num_id": o["cliente_num_id"],
            "ruta_id": o["ruta_id"],
            "zona": o["zona"],
            "estado": o["estado"],
            "medio_pago": o["medio_pago"],
            "total": float(o["total"]),
            "puntaje": o["puntaje"],
            "num_eventos_seg": int(m["num_eventos_seg"]),
            "dias_en_seguimiento": dias_seg,
            "dias_hasta_entrega_historial": dias_ent,
        })
    return salida


@app.get("/analitica/seguimiento-eventos", tags=["Analítica"])
def obtener_seguimiento_eventos(
    source: str = Query(default="auto", pattern="^(auto|atlas|local)$")
):
    """Retorna los eventos desplegados ($unwind) desde seguimiento.historial."""
    (_, eventos_raw, _, _), _ = extraer_datos(source)
    return eventos_raw
