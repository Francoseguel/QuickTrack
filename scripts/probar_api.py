import os
import sys

from fastapi.testclient import TestClient

# Agregar la carpeta raíz del proyecto al sys.path para reconocer 'api' y 'config'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.main import app
from config.database import get_database

# Prueba la API sin levantar el servidor: TestClient llama a los endpoints igual que lo haría
# Swagger o Postman, y cada respuesta se verifica después leyendo directo en la base con PyMongo.
# Usa la orden de prueba 'orden_test_api' y la borra al final.

ORDEN_PRUEBA = "orden_test_api"

def verificar(nombre, respuesta, codigo_esperado):
    ok = respuesta.status_code == codigo_esperado
    tiempo = respuesta.headers.get("X-Process-Time", "-")
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}: {respuesta.status_code} (esperado {codigo_esperado}) | X-Process-Time: {tiempo}")
    return ok

def flujo_lectura_escritura(cliente, db):
    print("--- 1. Lectura y escritura en tiempo real (API -> MongoDB) ---")
    resultados = []

    resultados.append(verificar("GET / (salud del servicio)", cliente.get("/"), 200))

    r = cliente.post("/ordenes", json={"_id": ORDEN_PRUEBA, "cliente_id": "cli_10", "ruta_id": "ruta_5",
                                       "medio_pago": "Tarjeta", "total": 185000})
    resultados.append(verificar("POST /ordenes (crear)", r, 201))
    print(f"     En la base: orden={db.ordenes_entrega.count_documents({'_id': ORDEN_PRUEBA})} | "
          f"seguimiento={db.seguimiento.count_documents({'orden_id': ORDEN_PRUEBA})}")

    r = cliente.get(f"/ordenes/{ORDEN_PRUEBA}")
    resultados.append(verificar("GET /ordenes/{id} (leer con $lookup)", r, 200))
    if r.status_code == 200:
        print(f"     Estado leído: {r.json()['estado']} | eventos en el historial: {len(r.json()['seguimiento'][0]['historial'])}")

    r = cliente.put(f"/ordenes/{ORDEN_PRUEBA}/estado", json={"nuevo_estado": "En tránsito", "fecha_evento": "2026-03-30T14:00:00"})
    resultados.append(verificar("PUT /ordenes/{id}/estado (actualizar)", r, 200))
    seg = db.seguimiento.find_one({"orden_id": ORDEN_PRUEBA}) or {}
    print(f"     En la base: estado_actual={seg.get('estado_actual')} | eventos en el historial: {len(seg.get('historial', []))}")

    r = cliente.get("/analitica/rendimiento-zonas")
    resultados.append(verificar("GET /analitica/rendimiento-zonas (agregación)", r, 200))
    if r.status_code == 200:
        print(f"     Zonas devueltas: {', '.join(z['_id'] for z in r.json())}")

    r = cliente.delete(f"/ordenes/{ORDEN_PRUEBA}")
    resultados.append(verificar("DELETE /ordenes/{id} (borrado en cascada)", r, 200))
    restos = (db.ordenes_entrega.count_documents({"_id": ORDEN_PRUEBA})
              + db.seguimiento.count_documents({"orden_id": ORDEN_PRUEBA})
              + db.valoraciones.count_documents({"orden_id": ORDEN_PRUEBA}))
    print(f"     Documentos residuales en la base: {restos}")
    print()
    return resultados

def errores_controlados(cliente, db):
    print("--- 2. Control de errores y validación de entradas ---")
    resultados = []
    existente = db.ordenes_entrega.find_one({}, sort=[("_id", 1)])["_id"]

    resultados.append(verificar(f"POST con _id existente ('{existente}')",
                                cliente.post("/ordenes", json={"_id": existente, "cliente_id": "cli_1", "ruta_id": "ruta_1",
                                                               "medio_pago": "Tarjeta", "total": 1000}), 400))
    resultados.append(verificar("POST con total = -5",
                                cliente.post("/ordenes", json={"_id": "orden_test_neg", "cliente_id": "cli_1", "ruta_id": "ruta_1",
                                                               "medio_pago": "Tarjeta", "total": -5}), 422))
    resultados.append(verificar("POST sin ruta_id",
                                cliente.post("/ordenes", json={"_id": "orden_test_sin_ruta", "cliente_id": "cli_1",
                                                               "medio_pago": "Tarjeta", "total": 1000}), 422))
    resultados.append(verificar("GET de una orden inexistente", cliente.get("/ordenes/orden_que_no_existe"), 404))
    resultados.append(verificar("PUT a una orden inexistente",
                                cliente.put("/ordenes/orden_que_no_existe/estado",
                                            json={"nuevo_estado": "Entregado", "fecha_evento": "2026-03-30T14:00:00"}), 404))
    resultados.append(verificar("DELETE de una orden inexistente", cliente.delete("/ordenes/orden_que_no_existe"), 404))
    print()
    return resultados

def ejecutar_pruebas():
    db = get_database()
    cliente = TestClient(app)
    try:
        resultados = flujo_lectura_escritura(cliente, db) + errores_controlados(cliente, db)
        print(f" {sum(resultados)} de {len(resultados)} pruebas correctas.")
    finally:
        # Limpieza por si alguna prueba falló a mitad de camino
        db.valoraciones.delete_many({"orden_id": ORDEN_PRUEBA})
        db.seguimiento.delete_many({"orden_id": ORDEN_PRUEBA})
        db.ordenes_entrega.delete_one({"_id": ORDEN_PRUEBA})

if __name__ == "__main__":
    ejecutar_pruebas()
