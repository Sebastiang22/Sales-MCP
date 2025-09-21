"""
Modelo de usuario para la aplicación.

Este módulo contiene el modelo de usuario que gestiona
las cuentas de usuarios del sistema de restaurante.
"""

from typing import List, Optional
from sqlmodel import Field, Relationship
from sqlalchemy import Column, JSON
from pydantic import validator
from .base import BaseModel


class User(BaseModel, table=True):
    """
    Modelo de usuario para almacenar cuentas de usuarios.

    Attributes:
        name: Nombre completo del usuario
        phone: Número de teléfono del usuario (único)
        email: Correo electrónico del usuario (opcional)
        is_active: Indica si el usuario está activo
    """
    
    __tablename__ = "users"

    name: str = Field(
        min_length=2, 
        max_length=100, 
        index=True,
        description="Nombre completo del usuario"
    )
    phone: str = Field(
        unique=True, 
        index=True,
        min_length=10,
        max_length=15,
        description="Número de teléfono del usuario"
    )
    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Correo electrónico del usuario"
    )
    is_active: bool = Field(
        default=True,
        description="Indica si el usuario está activo"
    )
    checkpointer: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Datos de checkpointer del usuario en formato JSON"
    )


    @validator('phone')
    def validate_phone(cls, v):
        """
        Valida el formato del número de teléfono.
        
        Args:
            v: Valor del teléfono a validar
            
        Returns:
            str: Teléfono validado
            
        Raises:
            ValueError: Si el formato del teléfono es inválido
        """
        if not v.isdigit():
            raise ValueError('El teléfono debe contener solo números')
        if len(v) < 10:
            raise ValueError('El teléfono debe tener al menos 10 dígitos')
        return v

    @validator('email')
    def validate_email(cls, v):
        """
        Valida el formato del correo electrónico.
        
        Args:
            v: Valor del email a validar
            
        Returns:
            str: Email validado o None
            
        Raises:
            ValueError: Si el formato del email es inválido
        """
        if v is None:
            return v
        if '@' not in v or '.' not in v:
            raise ValueError('Formato de email inválido')
        return v.lower()

    def get_name_and_email(self) -> dict:
        """
        Retorna un diccionario con el nombre y el correo electrónico del usuario.
        
        Returns:
            dict: Diccionario con las claves 'name' y 'email'.
        """
        return {
            "name": self.name,
            "email": self.email
        }

    def __repr__(self) -> str:
        """
        Representación string del usuario.
        
        Returns:
            str: Representación del usuario
        """
        return f"<User(name='{self.name}', phone='{self.phone}')>"
