"""
Inicializa el paquete de servicios.

Expone clases y funciones comunes para que otros módulos puedan importar
desde `services` directamente.
"""

from .whatsapp_service import WhatsAppServiceError  # re-export
from .azure_ai_search import (
    AzureAISearchService,
    AzureSearchConfig,
    get_azure_search_service,
)

__all__ = [
    "WhatsAppServiceError",
    "AzureAISearchService",
    "AzureSearchConfig",
    "get_azure_search_service",
]



