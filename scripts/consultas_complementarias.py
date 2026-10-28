import os
import sys

# Agregar la carpeta raíz del proyecto al sys.path para reconocer 'config'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import get_database

def consulta_4_satisfaccion_por_zona(db):
    """C4: ¿dónde está la insatisfacción? (valoraciones -> órdenes -> rutas)"""
    print("--- Consulta 4: Satisfacción por Zona ---")
    pipeline = [
        {"$lookup": {"from": "ordenes_entrega", "localField": "orden_id", "foreignField": "_id", "as": "o"}},
        {"$unwind": "$o"},
        {"$lookup": {"from": "rutas", "localField": "o.ruta_id", "foreignField": "_id", "as": "r"}},
        {"$unwind": "$r"},
        {"$group": {
            "_id": "$r.zona",
            "valoraciones": {"$sum": 1},
            "puntaje_prom": {"$avg": "$puntaje"},
            "criticas": {"$sum": {"$cond": [{"$lte": ["$puntaje", 2]}, 1, 0]}}
        }},
        {"$sort": {"puntaje_prom": 1}}
    ]
    for r in db.valoraciones.aggregate(pipeline):
        pct = r['criticas'] / r['valoraciones'] * 100
        print(f"  Zona: {r['_id']} | Valoraciones: {r['valoraciones']} | Puntaje prom.: {r['puntaje_prom']:.2f}/5 | Críticas (<= 2): {r['criticas']} ({pct:.1f} %)")
    print()

def consulta_5_cumplimiento_por_zona(db):
    """C5: ¿qué zonas cumplen peor? (canceladas, entregadas y abiertas por zona)"""
    print("--- Consulta 5: Cumplimiento por Zona ---")
    pipeline = [
        {"$lookup": {"from": "rutas", "localField": "ruta_id", "foreignField": "_id", "as": "r"}},
        {"$unwind": "$r"},
        {"$group": {
            "_id": "$r.zona",
            "ordenes": {"$sum": 1},
            "canceladas": {"$sum": {"$cond": [{"$eq": ["$estado", "Cancelado"]}, 1, 0]}},
            "entregadas": {"$sum": {"$cond": [{"$eq": ["$estado", "Entregado"]}, 1, 0]}},
            "abiertas": {"$sum": {"$cond": [{"$in": ["$estado", ["En preparación", "En tránsito"]]}, 1, 0]}}
        }},
        {"$project": {
            "zona": "$_id", "ordenes": 1, "canceladas": 1, "entregadas": 1, "abiertas": 1,
            "pct_cancelacion": {"$round": [{"$multiply": [{"$divide": ["$canceladas", "$ordenes"]}, 100]}, 1]}
        }},
        {"$sort": {"pct_cancelacion": -1}}
    ]
    for r in db.ordenes_entrega.aggregate(pipeline):
        print(f"  Zona: {r['zona']} | Órdenes: {r['ordenes']} | Canceladas: {r['canceladas']} ({r['pct_cancelacion']} %) | Entregadas: {r['entregadas']} | Abiertas: {r['abiertas']}")
    print()

def ejecutar_consultas():
    try:
        db = get_database()
        consulta_4_satisfaccion_por_zona(db)
        consulta_5_cumplimiento_por_zona(db)
        print(" Consultas complementarias ejecutadas correctamente.")
    except Exception as e:
        print(f" Error en ejecución de consultas: {e}")

if __name__ == "__main__":
    ejecutar_consultas()
