import os
import statistics
import sys
import time

import bson
import pymongo

# Agregar la carpeta raíz del proyecto al sys.path para reconocer 'config'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import get_database, MONGO_URI

# Solo lectura: no modifica ningún documento. Requiere haber ejecutado antes
# scripts/consultas_nosql.py, que crea los índices.

def etapas_del_plan(plan):
    """Recorre el plan ganador de explain() y devuelve sus etapas (de la última a la primera)."""
    plan = plan.get("queryPlan", plan)
    etapas = [plan.get("stage")]
    if "inputStage" in plan:
        etapas += etapas_del_plan(plan["inputStage"])
    for sub in plan.get("inputStages", []):
        etapas += etapas_del_plan(sub)
    return etapas

def mostrar_explain(nombre, cursor):
    exp = cursor.explain()
    stats = exp["executionStats"]
    etapas = " <- ".join(e for e in etapas_del_plan(exp["queryPlanner"]["winningPlan"]) if e)
    print(f"  {nombre}")
    print(f"     Plan: {etapas}")
    print(f"     Claves examinadas: {stats['totalKeysExamined']} | Documentos examinados: {stats['totalDocsExamined']} "
          f"| Devueltos: {stats['nReturned']} | Tiempo: {stats['executionTimeMillis']} ms")

def evaluar_planes(db):
    print("--- 1. Planes de ejecución con explain(): con índice vs. recorrido completo forzado ---")
    filtro_c1 = {"estado": "Entregado", "total": {"$gt": 100000}}
    proy_c1 = {"_id": 1, "cliente_id": 1, "medio_pago": 1, "total": 1, "fecha_envio": 1}

    mostrar_explain("C1 con índice compuesto {estado, fecha_envio}",
                    db.ordenes_entrega.find(filtro_c1, proy_c1).sort("total", -1).limit(5))
    mostrar_explain("C1 sin índice (hint $natural)",
                    db.ordenes_entrega.find(filtro_c1, proy_c1).sort("total", -1).limit(5).hint([("$natural", 1)]))
    mostrar_explain("Órdenes 'En tránsito' por fecha, con índice",
                    db.ordenes_entrega.find({"estado": "En tránsito"}).sort("fecha_envio", -1))
    mostrar_explain("Ídem sin índice (hint $natural)",
                    db.ordenes_entrega.find({"estado": "En tránsito"}).sort("fecha_envio", -1).hint([("$natural", 1)]))
    mostrar_explain("Seguimiento de una orden (índice único orden_id)",
                    db.seguimiento.find({"orden_id": "orden_1"}))
    mostrar_explain("C3: valoraciones <= 2 (sin índice en puntaje)",
                    db.valoraciones.find({"puntaje": {"$lte": 2}}))
    print()

def evaluar_volumen(db):
    print("--- 2. Volumen de datos retornado por C1 (tamaño BSON) ---")
    filtro_c1 = {"estado": "Entregado", "total": {"$gt": 100000}}
    proy_c1 = {"_id": 1, "cliente_id": 1, "medio_pago": 1, "total": 1, "fecha_envio": 1}
    variantes = [
        ("Sin proyección ni límite", db.ordenes_entrega.find(filtro_c1)),
        ("Con proyección (5 campos)", db.ordenes_entrega.find(filtro_c1, proy_c1)),
        ("Proyección + limit(5)", db.ordenes_entrega.find(filtro_c1, proy_c1).sort("total", -1).limit(5)),
    ]
    base = None
    for nombre, cursor in variantes:
        docs = list(cursor)
        total_bytes = sum(len(bson.encode(d)) for d in docs)
        base = base or total_bytes
        ahorro = "" if total_bytes == base else f" ({(total_bytes - base) / base * 100:+.0f} %)"
        print(f"  {nombre}: {len(docs)} documentos | {total_bytes:,} bytes{ahorro}")
    print()

def evaluar_latencia(db, repeticiones_reutilizado=30, repeticiones_nuevo=8):
    print("--- 3. Latencia de una lectura por _id (milisegundos) ---")
    nombre_db = db.name

    db.ordenes_entrega.find_one({"_id": "orden_1"})  # calentamiento: la primera conexión incluye DNS y TLS
    tiempos = []
    for _ in range(repeticiones_reutilizado):
        t0 = time.perf_counter()
        db.ordenes_entrega.find_one({"_id": "orden_1"})
        tiempos.append((time.perf_counter() - t0) * 1000)
    mediana_reutilizado = statistics.median(tiempos)
    print(f"  Cliente reutilizado (n = {repeticiones_reutilizado}): mediana {mediana_reutilizado:.0f} ms")

    tiempos = []
    for _ in range(repeticiones_nuevo):
        t0 = time.perf_counter()
        cliente = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        cliente[nombre_db].ordenes_entrega.find_one({"_id": "orden_1"})
        tiempos.append((time.perf_counter() - t0) * 1000)
        cliente.close()
    mediana_nuevo = statistics.median(tiempos)
    print(f"  Cliente nuevo por operación, como hace la API (n = {repeticiones_nuevo}): mediana {mediana_nuevo:.0f} ms")
    print(f"  -> Crear un MongoClient por operación es ~{mediana_nuevo / mediana_reutilizado:.0f} veces más lento.")
    print()

def ejecutar_evaluacion():
    try:
        db = get_database()
        evaluar_planes(db)
        evaluar_volumen(db)
        evaluar_latencia(db)
        print(" Evaluación de eficiencia completada.")
    except Exception as e:
        print(f" Error en la evaluación de eficiencia: {e}")

if __name__ == "__main__":
    ejecutar_evaluacion()
