import json
import os
import sys

# Agregar la carpeta raíz del proyecto al sys.path para reconocer 'config'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import get_database

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

def obtener_ruta_json(nombre_archivo):
    return os.path.join(DATA_DIR, nombre_archivo)

def cargar_coleccion_array(db, nombre_coleccion, archivo_json):
    ruta = obtener_ruta_json(archivo_json)
    if not os.path.exists(ruta):
        print(f" Advertencia: No se encontró el archivo {archivo_json}")
        return

    with open(ruta, 'r', encoding='utf-8') as f:
        documentos = json.load(f)
        db[nombre_coleccion].drop()
        if documentos:
            db[nombre_coleccion].insert_many(documentos)
            print(f" Colección '{nombre_coleccion}': {len(documentos)} documentos insertados.")

def cargar_coleccion_lineas(db, nombre_coleccion, archivo_json, es_ordenes=False):
    ruta = obtener_ruta_json(archivo_json)
    if not os.path.exists(ruta):
        print(f" Advertencia: No se encontró el archivo {archivo_json}")
        return

    documentos = []
    with open(ruta, 'r', encoding='utf-8') as f:
        for linea in f:
            linea_limpia = linea.strip()
            if linea_limpia:
                doc = json.loads(linea_limpia)
                # Normalización de cliente_id para ordenes_entrega ("cli_99" -> 99)
                if es_ordenes and isinstance(doc.get('cliente_id'), str) and doc['cliente_id'].startswith('cli_'):
                    doc['cliente_num_id'] = int(doc['cliente_id'].replace('cli_', ''))
                documentos.append(doc)

    db[nombre_coleccion].drop()
    if documentos:
        db[nombre_coleccion].insert_many(documentos)
        print(f" Colección '{nombre_coleccion}': {len(documentos)} documentos insertados.")

def ejecutar_etl():
    print("Iniciando proceso ETL e ingesta a MongoDB Atlas...\n")
    try:
        db = get_database()
        
        # 1. Clientes
        cargar_coleccion_array(db, "clientes", "clientes.json")
        
        # 2. Órdenes de Entrega
        cargar_coleccion_lineas(db, "ordenes_entrega", "ordenes_entrega.json", es_ordenes=True)
        
        # 3. Rutas
        cargar_coleccion_lineas(db, "rutas", "rutas.json")
        
        # 4. Seguimiento
        cargar_coleccion_lineas(db, "seguimiento", "seguimiento.json")
        
        # 5. Valoraciones
        cargar_coleccion_lineas(db, "valoraciones", "valoraciones.json")
        
        print("\n Proceso ETL completado con éxito.")
    except Exception as e:
        print(f"\n Error durante la ejecución del ETL: {e}")

if __name__ == "__main__":
    ejecutar_etl()