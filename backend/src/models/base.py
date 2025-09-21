"""
Modelos base y imports comunes para todos los modelos.

Este módulo contiene la clase base que comparten todos los modelos
de la aplicación, proporcionando campos y funcionalidades comunes.
"""

from datetime import datetime, UTC
from typing import Optional
from sqlmodel import Field, SQLModel
from uuid import UUID, uuid4


class BaseModel(SQLModel):
    """
    Modelo base con campos comunes para todos los modelos.
    
    Proporciona campos de auditoría y funcionalidades comunes
    que todos los modelos de la aplicación deben tener.
    """
    
    id: int = Field(default=None, primary_key=True, description="Identificador incremental del registro")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), 
        description="Fecha y hora de creación del registro"
    )
    updated_at: Optional[datetime] = Field(
        default=None, 
        description="Fecha y hora de última actualización del registro"
    )
    
    def update_timestamp(self) -> None:
        """
        Actualiza el timestamp de modificación.
        
        Este método debe ser llamado antes de guardar cambios
        en un registro existente.
        """
        self.updated_at = datetime.now(UTC)
    
    class Config:
        """Configuración del modelo base."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
