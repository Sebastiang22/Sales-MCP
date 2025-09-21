"""
Modelo para el sistema de logging de la aplicación.

Este módulo define los modelos de base de datos para almacenar logs
de la aplicación, incluyendo diferentes niveles de log y metadatos asociados.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Enum as SQLEnum, Integer, String, Text, JSON
from sqlmodel import Field, SQLModel


class LogLevel(str, Enum):
    """Niveles de log disponibles para el sistema de logging."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Log(SQLModel, table=True):
    """
    Modelo para almacenar logs en la base de datos.
    
    Este modelo permite almacenar logs estructurados con información
    sobre el nivel, mensaje, módulo, función y metadatos adicionales.
    """
    
    __tablename__ = "logs"
    
    # Campos principales
    id: Optional[int] = Field(default=None, primary_key=True)
    level: LogLevel = Field(sa_column=Column(SQLEnum(LogLevel), nullable=False))
    message: str = Field(sa_column=Column(Text, nullable=False))
    module: Optional[str] = Field(sa_column=Column(String(255), nullable=True))
    function_name: Optional[str] = Field(sa_column=Column(String(255), nullable=True))
    
    # Campos de contexto
    user_id: Optional[str] = Field(sa_column=Column(String(255), nullable=True))
    session_id: Optional[str] = Field(sa_column=Column(String(255), nullable=True))
    additional_data: Optional[Dict[str, Any]] = Field(sa_column=Column(JSON, nullable=True))
    
    # Campos de timestamp
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow)
    )
    
    class Config:
        """Configuración del modelo."""
        arbitrary_types_allowed = True 