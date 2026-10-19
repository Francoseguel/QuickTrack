import os
import pymongo
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "quicktrack_db")

def get_database():
    """
    Establece la conexión con MongoDB Atlas y retorna la instancia de la base de datos.
    """
    if not MONGO_URI:
        raise ValueError("Error: La variable MONGO_URI no está configurada en el archivo .env")
    
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]

def test_connection():
    """
    Realiza una prueba de 'ping' para verificar la conectividad con el clúster.
    """
    try:
        db = get_database()
        db.command("ping")
        print(" Conexión exitosa a la base de datos 'quicktrack_db' en MongoDB Atlas.")
        return True
    except Exception as e:
        print(f" Error de conexión con MongoDB Atlas: {e}")
        return False

if __name__ == "__main__":
    test_connection()