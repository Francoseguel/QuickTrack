import os
from pathlib import Path
import pymongo
from dotenv import load_dotenv

try:
    import certifi
except ImportError:
    certifi = None

# Cargar variables de entorno únicamente desde el .env del proyecto
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)


def get_database():
    """
    Establece la conexión con MongoDB Atlas y retorna la instancia de la base de datos.
    Lee MONGO_URI y DB_NAME dinámicamente desde variables de entorno.
    """
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME", "quicktrack_db")

    if not mongo_uri:
        raise ValueError(
            "Error: La variable MONGO_URI no está configurada en el archivo .env"
        )

    client_kwargs = {"serverSelectionTimeoutMS": 5000}
    if certifi is not None and mongo_uri.startswith("mongodb+srv://"):
        client_kwargs["tlsCAFile"] = certifi.where()

    client = pymongo.MongoClient(mongo_uri, **client_kwargs)
    return client[db_name]


def test_connection():
    """
    Realiza una prueba de 'ping' para verificar la conectividad con el clúster.
    """
    try:
        db = get_database()
        db.command("ping")
        print(
            f"Conexión exitosa a la base de datos '{db.name}' en MongoDB Atlas."
        )
        return True
    except Exception as e:
        print(f"Error de conexión con MongoDB Atlas: {e}")
        return False


if __name__ == "__main__":
    test_connection()
