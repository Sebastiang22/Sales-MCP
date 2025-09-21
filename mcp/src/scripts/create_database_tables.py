#!/usr/bin/env python3
"""
Script para crear todas las tablas de la base de datos.

Este script crea automáticamente todas las tablas definidas en los modelos
de SQLModel utilizando el servicio de base de datos mejorado.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional

# Agregar el directorio src al path para importar módulos
current_dir = Path(__file__).parent
src_dir = current_dir.parent
sys.path.insert(0, str(src_dir))

from sqlmodel import SQLModel, create_engine, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import re

# Importar todos los modelos para que SQLModel los registre
from models.user import User
from models.product import Product
from models.sale import ProductSale
from models.logs import Log

# Importar el servicio de base de datos
from database.connection import database_service

# Configurar salida estándar en UTF-8 para evitar problemas de codificación en Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def get_database_url_from_env() -> str:
    """
    Obtiene la URL de la base de datos desde las variables de entorno.
    
    Returns:
        str: URL de conexión a la base de datos
        
    Raises:
        ValueError: Si la URL no está configurada
    """
    db_url = os.getenv('POSTGRES_URL')
    if not db_url:
        raise ValueError("La variable de entorno POSTGRES_URL no está configurada")
    return db_url


def extract_database_name(database_url: str) -> str:
    """
    Extrae el nombre de la base de datos de una URL de PostgreSQL.
    
    Args:
        database_url: URL completa de la base de datos
        
    Returns:
        str: Nombre de la base de datos
        
    Raises:
        ValueError: Si no se puede extraer el nombre
    """
    # Patrón para extraer el nombre de la base de datos de la URL
    # postgresql://user:password@host:port/database_name
    pattern = r'postgresql://[^/]+/([^?]+)'
    match = re.search(pattern, database_url)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"No se pudo extraer el nombre de la base de datos de la URL")


def get_server_url(database_url: str) -> str:
    """
    Obtiene la URL del servidor PostgreSQL sin especificar una base de datos.
    
    Args:
        database_url: URL completa de la base de datos
        
    Returns:
        str: URL del servidor PostgreSQL (conecta a 'postgres' por defecto)
    """
    # Reemplazar el nombre de la base de datos con 'postgres'
    pattern = r'(postgresql://[^/]+)/([^?]+)'
    server_url = re.sub(pattern, r'\1/postgres', database_url)
    return server_url


def create_database_if_not_exists() -> bool:
    """
    Crea la base de datos si no existe.
    
    Returns:
        bool: True si la base de datos se creó o ya existía, False si ocurrió un error
    """
    try:
        # Obtener URLs
        database_url = get_database_url_from_env()
        server_url = get_server_url(database_url)
        database_name = extract_database_name(database_url)
        
        print(f"\n🔍 Verificando si la base de datos '{database_name}' existe...")
        
        # Conectar al servidor PostgreSQL (base de datos 'postgres')
        server_engine = create_engine(server_url, isolation_level='AUTOCOMMIT')
        
        with server_engine.connect() as connection:
            # Verificar si la base de datos existe
            check_db_query = """
                SELECT 1 FROM pg_database WHERE datname = :datname;
            """
            result = connection.execute(text(check_db_query), {"datname": database_name})
            db_exists = result.fetchone() is not None
            
            if db_exists:
                print(f"✅ La base de datos '{database_name}' ya existe")
                return True
            else:
                print(f"🆕 Creando base de datos '{database_name}'...")
                
                # Crear la base de datos
                create_db_query = f'CREATE DATABASE "{database_name}";'
                connection.execute(text(create_db_query))
                
                print(f"✅ Base de datos '{database_name}' creada exitosamente")
                return True
                
    except OperationalError as e:
        error_msg = str(e)
        if "does not exist" in error_msg:
            print(f"❌ Error: No se pudo conectar al servidor de base de datos")
            print("   Verifica que PostgreSQL esté ejecutándose y las credenciales sean correctas")
        else:
            print(f"❌ Error de conexión: {error_msg}")
        return False
        
    except Exception as e:
        print(f"❌ Error inesperado al crear la base de datos: {str(e)}")
        return False


def get_existing_tables(engine) -> set:
    """
    Obtiene la lista de tablas que ya existen en la base de datos.
    
    Args:
        engine: Engine de SQLAlchemy
        
    Returns:
        set: Conjunto de nombres de tablas existentes
    """
    with engine.connect() as connection:
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """
        result = connection.execute(text(tables_query))
        return {row[0] for row in result.fetchall()}


def get_model_tables() -> set:
    """
    Obtiene la lista de tablas definidas en los modelos SQLModel.
    
    Returns:
        set: Conjunto de nombres de tablas definidas en los modelos
    """
    return {table.name for table in SQLModel.metadata.tables.values()}


def create_tables(force: bool = False) -> bool:
    """
    Crea las tablas de la base de datos.
    
    Args:
        force: Si es True, elimina las tablas existentes antes de crearlas
        
    Returns:
        bool: True si las tablas se crearon exitosamente, False si ocurrió un error
    """
    try:
        print(f"\n🔧 Conectando a la base de datos...")
        
        # Usar el servicio de base de datos
        if not database_service.engine:
            print("❌ Error: El engine de la base de datos no está inicializado")
            return False
        
        engine = database_service.engine
        
        # Testear conexión
        if not database_service.health_check():
            print("❌ Error: No se pudo conectar a la base de datos")
            return False
        
        print("✅ Conexión exitosa a la base de datos")
        
        # Obtener tablas existentes y tablas de modelos
        existing_tables = get_existing_tables(engine)
        model_tables = get_model_tables()
        
        print(f"\n📋 Analizando tablas:")
        print(f"Tablas definidas en modelos: {len(model_tables)}")
        print(f"Tablas ya existentes: {len(existing_tables)}")
        
        if force:
            print("⚠️  Eliminando tablas existentes (modo force)...")
            database_service.drop_tables()
            print("🗑️  Tablas eliminadas")
            existing_tables = set()  # Reset después del drop
        
        # Determinar qué tablas crear
        tables_to_create = model_tables - existing_tables
        tables_already_exist = model_tables & existing_tables
        
        if tables_already_exist:
            print(f"\n✅ Tablas que ya existen ({len(tables_already_exist)}):")
            for table in sorted(tables_already_exist):
                print(f"  ✓ {table}")
        
        if tables_to_create:
            print(f"\n🆕 Creando tablas nuevas ({len(tables_to_create)}):")
            for table in sorted(tables_to_create):
                print(f"  + {table}")
            
            # Crear tablas usando el servicio
            database_service.create_tables()
            
            print(f"\n✅ Tablas creadas exitosamente")
        else:
            print(f"\n🎯 No hay tablas nuevas que crear")
        
        # Verificar estado final
        final_tables = get_existing_tables(engine)
        
        print(f"\n📊 Estado final de tablas:")
        print(f"Total de tablas: {len(final_tables)}")
        for table in sorted(final_tables):
            status = "🆕 Nueva" if table in tables_to_create else "✅ Existente"
            print(f"  {status}: {table}")
        
        return True
        
    except SQLAlchemyError as e:
        print(f"\n❌ Error de base de datos: {str(e)}")
        return False
        
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
        return False


def list_models() -> None:
    """
    Lista todos los modelos disponibles y sus tablas.
    """
    print("\n📋 Modelos disponibles:")
    print(f"  • User -> tabla: users")
    print(f"  • Product -> tabla: products")
    print(f"  • ProductSale -> tabla: product_sales")
    print(f"  • Log -> tabla: logs")

    print(f"\n📊 Resumen:")
    print(f"  Total de modelos: 4")
    print(f"  Total de tablas: {len(get_model_tables())}")


def main():
    """
    Función principal del script.
    
    Maneja los argumentos de línea de comandos y ejecuta la creación de tablas
    según los parámetros especificados.
    """
    parser = argparse.ArgumentParser(
        description="Crear base de datos y tablas para el sistema de restaurante",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python create_database_tables.py                    # Crear tablas normalmente
  python create_database_tables.py --force            # Recrear todas las tablas
  python create_database_tables.py --list-models      # Listar modelos disponibles
  python create_database_tables.py --check-health     # Verificar conexión
        """
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Eliminar tablas existentes antes de crearlas"
    )
    
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Listar todos los modelos disponibles"
    )
    
    parser.add_argument(
        "--check-health",
        action="store_true",
        help="Verificar la conexión a la base de datos"
    )
    
    args = parser.parse_args()
    
    print("🚀 Script de creación de tablas para sistema de restaurante")
    print("=" * 60)

    # Manejar argumentos especiales que no requieren conexión previa
    if args.list_models:
        list_models()
        return

    # Verificar variables de entorno
    try:
        db_url = get_database_url_from_env()
        print(f"🔗 URL de base de datos: {db_url.split('@')[0]}@[HIDDEN]")
    except ValueError as e:
        print(f"❌ Error de configuración: {e}")
        print("\nConfigura las variables de entorno necesarias:")
        print("  POSTGRES_URL=postgresql://user:password@host:port/database")
        print("  O individualmente:")
        print("  DB_HOST=localhost")
        print("  DB_PORT=5432")
        print("  DB_NAME=restaurant_db")
        print("  DB_USER=postgres")
        print("  DB_PASSWORD=your_password")
        sys.exit(1)
    if args.check_health:
        print("\n🔍 Verificando conexión a la base de datos...")
        if database_service.health_check():
            print("✅ Conexión exitosa")
        else:
            print("❌ Error de conexión")
            sys.exit(1)
        return
    
    if args.force:
        print("⚠️  ADVERTENCIA: Modo force activado - Se eliminarán las tablas existentes")
        response = input("¿Estás seguro de que quieres continuar? (sí/no): ")
        if response.lower() not in ["sí", "si", "s", "yes", "y"]:
            print("❌ Operación cancelada por el usuario")
            return
    
    # Saltar la creación de la base de datos, asumimos que ya existe
    print("🔎 Saltando la creación de la base de datos, se asume que ya existe.")
    # if not create_database_if_not_exists():
    #     print("❌ No se pudo crear/verificar la base de datos")
    #     sys.exit(1)
    
    # Crear tablas
    if create_tables(args.force):
        print("\n🎉 Todas las operaciones completadas exitosamente")
    else:
        print("\n❌ Algunas operaciones fallaron")
        sys.exit(1)


if __name__ == "__main__":
    main() 