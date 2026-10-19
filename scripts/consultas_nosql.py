import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config.database import get_database

def crear_indices(db):
    print("--- 1. Creación de Índices Estratégicos ---")
    # Índice compuesto para acelerar búsquedas por estado y ordenamiento de fecha
    idx_1 = db.ordenes_entrega.create_index([("estado", 1), ("fecha_envio", -1)])
    # Índice para optimizar los $lookup entre ordenes y rutas
    idx_2 = db.ordenes_entrega.create_index([("ruta_id", 1)])
    # Índice único en seguimiento
    idx_3 = db.seguimiento.create_index([("orden_id", 1)], unique=True)
    
    print(f" Índice creado en ordenes_entrega: {idx_1}")
    print(f" Índice creado en ordenes_entrega: {idx_2}")
    print(f" Índice creado en seguimiento: {idx_3}\n")

def consulta_1_ordenes_alto_valor(db):
    print("--- Consulta 1: Órdenes Entregadas con Total > $100.000 ---")
    query = {
        "estado": "Entregado",
        "total": {"$gt": 100000}
    }
    proyeccion = {
        "_id": 1,
        "cliente_id": 1,
        "medio_pago": 1,
        "total": 1,
        "fecha_envio": 1
    }
    resultados = list(db.ordenes_entrega.find(query, proyeccion).sort("total", -1).limit(5))
    for r in resultados:
        print(f"  ID: {r['_id']} | Cliente: {r.get('cliente_id')} | Pago: {r.get('medio_pago')} | Total: ${r.get('total'):,.2f}")
    print()

def consulta_2_rendimiento_por_zona(db):
    print("--- Consulta 2: Rendimiento Logístico por Zona y Medio de Pago (Agregación) ---")
    pipeline = [
        {
            "$lookup": {
                "from": "rutas",
                "localField": "ruta_id",
                "foreignField": "_id",
                "as": "info_ruta"
            }
        },
        {"$unwind": "$info_ruta"},
        {
            "$group": {
                "_id": {
                    "zona": "$info_ruta.zona",
                    "medio_pago": "$medio_pago"
                },
                "total_ordenes": {"$sum": 1},
                "monto_acumulado": {"$sum": "$total"},
                "monto_promedio": {"$avg": "$total"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "zona": "$_id.zona",
                "medio_pago": "$_id.medio_pago",
                "total_ordenes": 1,
                "monto_acumulado": {"$round": ["$monto_acumulado", 2]},
                "monto_promedio": {"$round": ["$monto_promedio", 2]}
            }
        },
        {"$sort": {"zona": 1, "monto_acumulado": -1}}
    ]
    resultados = list(db.ordenes_entrega.aggregate(pipeline))
    for r in resultados[:6]:
        print(f"  Zona: {r['zona']} | Pago: {r['medio_pago']} | Órdenes: {r['total_ordenes']} | Total: ${r['monto_acumulado']:,.2f}")
    print()

def consulta_3_valoraciones_criticas(db):
    print("--- Consulta 3: Análisis de Valoraciones Bajas (<= 2 puntos) ---")
    pipeline = [
        {"$match": {"puntaje": {"$lte": 2}}},
        {
            "$lookup": {
                "from": "ordenes_entrega",
                "localField": "orden_id",
                "foreignField": "_id",
                "as": "detalle_orden"
            }
        },
        {"$unwind": "$detalle_orden"},
        {
            "$project": {
                "_id": 0,
                "orden_id": 1,
                "puntaje": 1,
                "comentario": 1,
                "estado_orden": "$detalle_orden.estado",
                "monto_total": "$detalle_orden.total"
            }
        },
        {"$sort": {"puntaje": 1}}
    ]
    resultados = list(db.valoraciones.aggregate(pipeline))
    for r in resultados[:5]:
        print(f"  Orden: {r['orden_id']} | Puntaje: {r['puntaje']}/5 | Comentario: '{r['comentario']}' | Estado: {r['estado_orden']}")
    print()

def ejecutar_consultas():
    try:
        db = get_database()
        crear_indices(db)
        consulta_1_ordenes_alto_valor(db)
        consulta_2_rendimiento_por_zona(db)
        consulta_3_valoraciones_criticas(db)
        print(" Consultas ejecutadas correctamente.")
    except Exception as e:
        print(f" Error en ejecución de consultas: {e}")

if __name__ == "__main__":
    ejecutar_consultas()