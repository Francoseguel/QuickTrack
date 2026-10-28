"""
Extracción de datos de MongoDB Atlas para Power BI (QuickTrack).

Uso en Power BI Desktop:
  Obtener datos > Más... > Otras > Script de Python > pegar este archivo completo.
  Power BI crea una tabla por cada DataFrame: ordenes, clientes, rutas,
  seguimiento, eventos_seguimiento y valoraciones.

Requisitos: el Python configurado en Power BI (Archivo > Opciones > Scripting de Python)
debe tener instalados pymongo, pandas, matplotlib y python-dotenv.

También se puede ejecutar directo para probar: python powerbi/extraer_quicktrack.py
Plan B sin Python en Power BI: python powerbi/extraer_quicktrack.py --csv  (deja los CSV en powerbi/csv/)
"""
import os
import sys

import pandas as pd
import pymongo
from dotenv import load_dotenv

# pandas 3 usa un tipo de texto nuevo por defecto; se vuelve al de pandas 2 para que Power BI lo lea sin problemas
pd.options.future.infer_string = False

# Ejecutado como archivo, la ruta del proyecto se deduce de su ubicación.
# Pegado en Power BI no existe __file__ (corre en una carpeta temporal): se usa la variable
# de entorno QUICKTRACK_DIR o, si no está, la ruta de abajo. En el .pbip del repo esta línea
# la completa el parámetro RutaProyecto (Transformar datos > Administrar parámetros).
try:
    RUTA_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    RUTA_PROYECTO = os.getenv("QUICKTRACK_DIR", r"C:\Users\Felipe\Desktop\exp2_bdnorelacional\QuickTrack")

load_dotenv(os.path.join(RUTA_PROYECTO, ".env"))


def extraer_tablas():
    """Lee las 5 colecciones con agregaciones y las devuelve como DataFrames planos."""
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("Error: no se encontró MONGO_URI en el archivo .env del proyecto")

    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
    db = client[os.getenv("DB_NAME", "quicktrack_db")]
    try:
        # Órdenes con el estado de su seguimiento, para medir la coherencia entre ambas colecciones
        ordenes = pd.DataFrame(db.ordenes_entrega.aggregate([
            {"$lookup": {"from": "seguimiento", "localField": "_id", "foreignField": "orden_id", "as": "seg"}},
            {"$unwind": {"path": "$seg", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0, "orden_id": "$_id", "cliente_num_id": 1, "ruta_id": 1,
                "fecha_envio": 1, "estado": 1, "medio_pago": 1, "total": 1,
                "estado_seguimiento": "$seg.estado_actual",
                "ultimo_evento": {"$arrayElemAt": ["$seg.historial.estado", -1]},
            }},
        ]))
        ordenes["fecha_envio"] = pd.to_datetime(ordenes["fecha_envio"])
        ordenes["estado_coherente"] = ordenes["estado"] == ordenes["estado_seguimiento"]

        clientes = pd.DataFrame(db.clientes.find(
            {}, {"_id": 0, "cliente_num_id": "$_id", "nombre": 1, "pais": 1, "fecha_registro": 1}))
        clientes["fecha_registro"] = pd.to_datetime(clientes["fecha_registro"])

        rutas = pd.DataFrame(db.rutas.find(
            {}, {"_id": 0, "ruta_id": "$_id", "zona": 1, "ciudad_origen": 1, "ciudad_destino": 1, "distancia_km": 1}))

        seguimiento = pd.DataFrame(db.seguimiento.aggregate([
            {"$project": {
                "_id": 0, "orden_id": 1, "estado_actual": 1,
                "eventos": {"$size": "$historial"},
                "primer_evento": {"$arrayElemAt": ["$historial.fecha", 0]},
                "ultimo_evento": {"$arrayElemAt": ["$historial.estado", -1]},
                "fecha_ultimo_evento": {"$arrayElemAt": ["$historial.fecha", -1]},
            }},
        ]))
        seguimiento["primer_evento"] = pd.to_datetime(seguimiento["primer_evento"])
        seguimiento["fecha_ultimo_evento"] = pd.to_datetime(seguimiento["fecha_ultimo_evento"])

        # Historial embebido desplegado: una fila por evento
        eventos_seguimiento = pd.DataFrame(db.seguimiento.aggregate([
            {"$unwind": {"path": "$historial", "includeArrayIndex": "paso"}},
            {"$project": {"_id": 0, "orden_id": 1, "paso": {"$add": ["$paso", 1]},
                          "estado": "$historial.estado", "fecha": "$historial.fecha"}},
        ]))
        eventos_seguimiento["fecha"] = pd.to_datetime(eventos_seguimiento["fecha"])

        # Tiempo de entrega: días entre el primer evento y el evento "Entregado" (vacío si no se entregó)
        entregas = eventos_seguimiento[eventos_seguimiento["estado"] == "Entregado"].groupby("orden_id")["fecha"].min()
        seguimiento["dias_entrega"] = (seguimiento["orden_id"].map(entregas) - seguimiento["primer_evento"]).dt.days

        valoraciones = pd.DataFrame(db.valoraciones.find(
            {}, {"_id": 0, "orden_id": 1, "puntaje": 1, "comentario": 1}))
        valoraciones["critica"] = valoraciones["puntaje"] <= 2
        valoraciones["con_retraso"] = valoraciones["comentario"] == "Tuvo retraso"
    finally:
        client.close()

    return ordenes, clientes, rutas, seguimiento, eventos_seguimiento, valoraciones


# Power BI toma como tabla cada DataFrame definido en este nivel
ordenes, clientes, rutas, seguimiento, eventos_seguimiento, valoraciones = extraer_tablas()

if __name__ == "__main__":
    carpeta_csv = os.path.join(RUTA_PROYECTO, "powerbi", "csv")
    if "--csv" in sys.argv:
        os.makedirs(carpeta_csv, exist_ok=True)
    for nombre, df in [("ordenes", ordenes), ("clientes", clientes), ("rutas", rutas),
                       ("seguimiento", seguimiento), ("eventos_seguimiento", eventos_seguimiento),
                       ("valoraciones", valoraciones)]:
        print(f" {nombre}: {len(df)} filas | columnas: {', '.join(df.columns)}")
        if "--csv" in sys.argv:
            # utf-8-sig para que Power BI y Excel lean bien los tildes
            df.to_csv(os.path.join(carpeta_csv, f"{nombre}.csv"), index=False, encoding="utf-8-sig")
    if "--csv" in sys.argv:
        print(f" CSV guardados en {carpeta_csv}")
