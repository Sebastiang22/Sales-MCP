import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from core.config import settings


def create_database():
    """
    Crea la base de datos en el servidor PostgreSQL especificado.
    Si la base de datos ya existe, no realiza ninguna acción.
    """
    # Configuración de conexión al servidor PostgreSQL (no a una base de datos específica)
    db_config = {
        'host': settings.DB_HOST,
        'port': settings.DB_PORT,
        'user': settings.DB_USER,
        'password': settings.DB_PASSWORD,
        'dbname': settings.DB_SERVER_DB,
    }

    try:
        # Conexión al servidor PostgreSQL
        connection = psycopg2.connect(**db_config)
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()

        # Verificar si la base de datos ya existe
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (settings.DB_NAME,))
        exists = cursor.fetchone()
        if exists:
            print(f"La base de datos '{settings.DB_NAME}' ya existe.")
        else:
            # Crear la base de datos
            cursor.execute(f'CREATE DATABASE "{settings.DB_NAME}";')
            print(f"Base de datos '{settings.DB_NAME}' creada exitosamente.")

        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error al crear la base de datos: {e}")


if __name__ == "__main__":
    create_database() 