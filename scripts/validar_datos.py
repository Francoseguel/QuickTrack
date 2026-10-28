import os
import sys

from pymongo.errors import DuplicateKeyError

# Agregar la carpeta raíz del proyecto al sys.path para reconocer 'config'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import get_database

# Solo lectura: el único intento de escritura es un insert duplicado que MongoDB rechaza.

COMENTARIOS_POSITIVOS = ["Entrega a tiempo", "Excelente atención", "Muy buen servicio", "Recomendaría"]
COMENTARIOS_NEGATIVOS = ["Producto en mal estado", "Tuvo retraso"]

def contar(coleccion, pipeline):
    resultado = list(coleccion.aggregate(pipeline + [{"$count": "n"}]))
    return resultado[0]["n"] if resultado else 0

def controles_de_integridad(db):
    print("--- 1. Controles de integridad de la implementación ---")
    controles = []

    # Duplicación: insertar una orden con un _id que ya existe
    orden_existente = db.ordenes_entrega.find_one({}, sort=[("_id", 1)])
    try:
        db.ordenes_entrega.insert_one(orden_existente)
        controles.append(("Orden con _id repetido", "aceptada", False))
        db.ordenes_entrega.delete_one({"_id": orden_existente["_id"]})  # no debería llegar aquí
    except DuplicateKeyError:
        controles.append(("Orden con _id repetido", "rechazada", True))

    max_seg = list(db.seguimiento.aggregate([
        {"$group": {"_id": "$orden_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 1}]))
    max_seg = max_seg[0]["n"] if max_seg else 0
    controles.append(("Máximo de seguimientos por orden (índice único)", max_seg, max_seg == 1))

    n = contar(db.ordenes_entrega, [
        {"$lookup": {"from": "rutas", "localField": "ruta_id", "foreignField": "_id", "as": "r"}},
        {"$match": {"r": {"$size": 0}}}])
    controles.append(("Órdenes con ruta inexistente", n, n == 0))

    n = contar(db.valoraciones, [
        {"$lookup": {"from": "ordenes_entrega", "localField": "orden_id", "foreignField": "_id", "as": "o"}},
        {"$match": {"o": {"$size": 0}}}])
    controles.append(("Valoraciones de órdenes inexistentes", n, n == 0))

    huerfanos = contar(db.seguimiento, [
        {"$lookup": {"from": "ordenes_entrega", "localField": "orden_id", "foreignField": "_id", "as": "o"}},
        {"$match": {"o": {"$size": 0}}}])
    sin_seg = contar(db.ordenes_entrega, [
        {"$lookup": {"from": "seguimiento", "localField": "_id", "foreignField": "orden_id", "as": "s"}},
        {"$match": {"s": {"$size": 0}}}])
    controles.append(("Seguimientos huérfanos / órdenes sin seguimiento", f"{huerfanos} / {sin_seg}", huerfanos == 0 and sin_seg == 0))

    restos = sum(db[c].count_documents({"orden_id": {"$regex": "^orden_test_"}}) for c in ["seguimiento", "valoraciones"])
    restos += db.ordenes_entrega.count_documents({"_id": {"$regex": "^orden_test_"}})
    controles.append(("Restos de pruebas CRUD tras el borrado en cascada", restos, restos == 0))

    n = db.valoraciones.count_documents({"$or": [{"puntaje": {"$lt": 1}}, {"puntaje": {"$gt": 5}}]})
    controles.append(("Puntajes fuera del rango 1-5", n, n == 0))

    n = contar(db.clientes, [{"$group": {"_id": "$correo", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}])
    controles.append(("Clientes con correo duplicado", n, n == 0))

    # Pérdida de contexto: la referencia orden -> cliente viene como texto ("cli_73") y el _id del cliente es entero
    por_texto = contar(db.ordenes_entrega, [
        {"$lookup": {"from": "clientes", "localField": "cliente_id", "foreignField": "_id", "as": "c"}},
        {"$match": {"c": {"$ne": []}}}])
    por_num = contar(db.ordenes_entrega, [
        {"$lookup": {"from": "clientes", "localField": "cliente_num_id", "foreignField": "_id", "as": "c"}},
        {"$match": {"c": {"$ne": []}}}])
    controles.append(("Órdenes unidas a su cliente: por texto -> por cliente_num_id", f"{por_texto} -> {por_num}", por_num > por_texto))

    for nombre, resultado, ok in controles:
        print(f"  [{'OK' if ok else 'REVISAR'}] {nombre}: {resultado}")
    print()

def inconsistencias_de_origen(db):
    print("--- 2. Inconsistencias que vienen en los datos de origen ---")

    estado_distinto = contar(db.ordenes_entrega, [
        {"$lookup": {"from": "seguimiento", "localField": "_id", "foreignField": "orden_id", "as": "seg"}},
        {"$unwind": "$seg"},
        {"$match": {"$expr": {"$ne": ["$estado", "$seg.estado_actual"]}}}])

    ultimo_evento_distinto = contar(db.seguimiento, [
        {"$match": {"$expr": {"$ne": ["$estado_actual", {"$arrayElemAt": ["$historial.estado", -1]}]}}}])

    # Las fechas son texto ISO (AAAA-MM-DDTHH:MM:SS), por eso se pueden comparar directamente
    historial_previo = contar(db.ordenes_entrega, [
        {"$lookup": {"from": "seguimiento", "localField": "_id", "foreignField": "orden_id", "as": "seg"}},
        {"$unwind": "$seg"},
        {"$match": {"$expr": {"$lt": [{"$arrayElemAt": ["$seg.historial.fecha", 0]}, "$fecha_envio"]}}}])

    positivo_bajo = db.valoraciones.count_documents({"comentario": {"$in": COMENTARIOS_POSITIVOS}, "puntaje": {"$lte": 2}})
    negativo_alto = db.valoraciones.count_documents({"comentario": {"$in": COMENTARIOS_NEGATIVOS}, "puntaje": {"$gte": 4}})

    canceladas = db.ordenes_entrega.count_documents({"estado": "Cancelado"})
    canceladas_valoradas = contar(db.ordenes_entrega, [
        {"$match": {"estado": "Cancelado"}},
        {"$lookup": {"from": "valoraciones", "localField": "_id", "foreignField": "orden_id", "as": "v"}},
        {"$match": {"v": {"$ne": []}}}])

    print(f"  Estado de la orden distinto al estado del seguimiento: {estado_distinto}")
    print(f"  estado_actual distinto del último evento del historial: {ultimo_evento_distinto}")
    print(f"  Historial que comienza antes de fecha_envio: {historial_previo}")
    print(f"  Comentario que contradice el puntaje: {positivo_bajo + negativo_alto} "
          f"(positivo con puntaje <= 2: {positivo_bajo} | negativo con puntaje >= 4: {negativo_alto})")
    print(f"  Órdenes canceladas con valoración: {canceladas_valoradas} de {canceladas}")
    print()

def ejecutar_validaciones():
    try:
        db = get_database()
        controles_de_integridad(db)
        inconsistencias_de_origen(db)
        print(" Validaciones completadas.")
    except Exception as e:
        print(f" Error en las validaciones: {e}")

if __name__ == "__main__":
    ejecutar_validaciones()
