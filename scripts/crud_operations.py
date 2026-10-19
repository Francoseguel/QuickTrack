import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config.database import get_database

def crear_orden(db, orden_id, cliente_id, ruta_id, medio_pago, total):
    """CREATE: Inserta una orden y genera su primer registro en seguimiento"""
    try:
        if db.ordenes_entrega.find_one({"_id": orden_id}):
            print(f" Advertencia: La orden '{orden_id}' ya existe.")
            return False

        nueva_orden = {
            "_id": orden_id,
            "cliente_id": cliente_id,
            "ruta_id": ruta_id,
            "fecha_envio": "2026-03-30T10:00:00",
            "estado": "En preparación",
            "medio_pago": medio_pago,
            "total": float(total)
        }
        db.ordenes_entrega.insert_one(nueva_orden)

        nuevo_seguimiento = {
            "_id": f"seg_{orden_id}",
            "orden_id": orden_id,
            "estado_actual": "En preparación",
            "historial": [
                {"estado": "En preparación", "fecha": "2026-03-30T10:00:00"}
            ]
        }
        db.seguimiento.insert_one(nuevo_seguimiento)
        print(f" [CREATE] Orden '{orden_id}' registrada correctamente con su seguimiento inicial.")
        return True
    except Exception as e:
        print(f" Error al crear orden: {e}")
        return False

def leer_orden(db, orden_id):
    """READ: Consulta el detalle completo de una orden con su seguimiento"""
    pipeline = [
        {"$match": {"_id": orden_id}},
        {
            "$lookup": {
                "from": "seguimiento",
                "localField": "_id",
                "foreignField": "orden_id",
                "as": "seguimiento_info"
            }
        }
    ]
    res = list(db.ordenes_entrega.aggregate(pipeline))
    if res:
        doc = res[0]
        print(f" [READ] Detalle de '{orden_id}': Estado={doc['estado']} | Total=${doc['total']:,.2f}")
        return doc
    print(f" [READ] No se encontró la orden '{orden_id}'.")
    return None

def actualizar_estado_orden(db, orden_id, nuevo_estado, fecha_evento):
    """UPDATE: Actualiza atómicamente el estado y agrega entrada al array de historial"""
    try:
        res = db.ordenes_entrega.update_one(
            {"_id": orden_id},
            {"$set": {"estado": nuevo_estado}}
        )
        if res.matched_count == 0:
            print(f" [UPDATE] No existe la orden '{orden_id}'.")
            return False

        db.seguimiento.update_one(
            {"orden_id": orden_id},
            {
                "$set": {"estado_actual": nuevo_estado},
                "$push": {
                    "historial": {"estado": nuevo_estado, "fecha": fecha_evento}
                }
            }
        )
        print(f" [UPDATE] Estado de la orden '{orden_id}' actualizado a '{nuevo_estado}'.")
        return True
    except Exception as e:
        print(f" Error al actualizar orden: {e}")
        return False

def eliminar_orden_cascada(db, orden_id):
    """DELETE: Elimina una orden y sus registros vinculados en seguimiento y valoraciones"""
    try:
        db.valoraciones.delete_many({"orden_id": orden_id})
        db.seguimiento.delete_many({"orden_id": orden_id})
        res = db.ordenes_entrega.delete_one({"_id": orden_id})
        
        if res.deleted_count > 0:
            print(f" [DELETE] Orden '{orden_id}' y registros relacionados eliminados.")
            return True
        print(f" [DELETE] La orden '{orden_id}' no existía.")
        return False
    except Exception as e:
        print(f" Error al eliminar orden: {e}")
        return False

def probar_flujo_crud():
    print("--- Probando Ciclo de Vida CRUD Completo ---\n")
    db = get_database()
    test_id = "orden_test_999"

    # 1. CREATE
    crear_orden(db, test_id, "cli_10", "ruta_5", "Tarjeta", 185000.0)

    # 2. READ
    leer_orden(db, test_id)

    # 3. UPDATE
    actualizar_estado_orden(db, test_id, "En tránsito", "2026-03-30T14:00:00")
    leer_orden(db, test_id)

    # 4. DELETE
    eliminar_orden_cascada(db, test_id)
    leer_orden(db, test_id)

if __name__ == "__main__":
    probar_flujo_crud()