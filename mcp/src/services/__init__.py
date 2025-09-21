"""
Inicializa el paquete de servicios.

Expone clases y funciones comunes para que otros módulos puedan importar
desde `services` directamente.
"""

from .whatsapp_service import WhatsAppServiceError  # re-export

__all__ = [
    "WhatsAppServiceError",
]



