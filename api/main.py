import os
import sys
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# Asegurar importación de config
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config.database import get_database
from api.models import OrdenCrear, ActualizarEstado
from api.middlewares import ProcessTimeMiddleware, global_exception_handler

app = FastAPI(
    title="QuickTrack Logistics API",
    description="API RESTful para la gestión logística NoSQL sobre MongoDB Atlas",
    version="1.0.0"
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

# 5. ANALYTICS
@app.get("/analitica/rendimiento-zonas", tags=["Analítica"])
def obtener_rendimiento_zonas():
    db = get_database()
    pipeline = [
        {"$lookup": {"from": "rutas", "localField": "ruta_id", "foreignField": "_id", "as": "ruta"}},
        {"$unwind": "$ruta"},
        {
            "$group": {
                "_id": "$ruta.zona",
                "total_ordenes": {"$sum": 1},
                "monto_total": {"$sum": "$total"},
                "promedio_monto": {"$avg": "$total"}
            }
        },
        {"$sort": {"monto_total": -1}}
    ]
    return list(db.ordenes_entrega.aggregate(pipeline))