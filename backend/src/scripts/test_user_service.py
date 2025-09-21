"""
Script de prueba para el servicio de usuarios y la conexión a la base de datos.

Este script verifica la conexión, crea un usuario, lo consulta y lo elimina.
"""

from services.user_service import user_service
from database.connection import database_service
from sqlmodel import SQLModel
from core.config import settings

def test_database_connection():
    """
    Prueba la conexión a la base de datos.
    """
    print("Verificando conexión a la base de datos...")
    if database_service.health_check():
        print("Conexión exitosa.")
    else:
        print("Fallo en la conexión.")

def test_create_user():
    """
    Prueba la creación de un usuario.
    """
    print("Creando usuario de prueba...")
    user_data = {
        "name": "Test User",
        "phone": "999888777",
        "email": "test.user@example.com",
        "is_active": True
    }
    try:
        user = user_service.create_user(user_data)
        print(f"Usuario creado: {user.id} - {user.name}")
        return user
    except Exception as e:
        print(f"Error al crear usuario: {e}")
        return None

def test_get_user(user_id):
    """
    Prueba la consulta de un usuario por ID.
    """
    print(f"Consultando usuario con ID: {user_id}")
    user = user_service.get_user_by_id(user_id)
    if user:
        print(f"Usuario encontrado: {user.name} - {user.email}")
    else:
        print("Usuario no encontrado.")

def test_delete_user(user_id):
    """
    Prueba la eliminación de un usuario.
    """
    print(f"Eliminando usuario con ID: {user_id}")
    if user_service.delete_user(user_id):
        print("Usuario eliminado correctamente.")
    else:
        print("No se pudo eliminar el usuario.")

if __name__ == "__main__":
    test_database_connection()
    user = test_create_user()
    if user:
        test_get_user(user.id)
        test_delete_user(user.id) 