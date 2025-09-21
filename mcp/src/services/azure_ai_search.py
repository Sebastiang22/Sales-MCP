"""
Servicio mínimo para Azure AI Search (stub).

Este módulo provee una implementación mínima para permitir que el servidor
arranque aun cuando no exista la integración real con Azure o OpenAI.
Las funciones retornan estructuras controladas o errores descriptivos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AzureSearchConfig:
    """Configuración mínima para el servicio de búsqueda.

    Esta clase representa una configuración básica necesaria para exponer
    campos utilizados por las tools, evitando fallos por atributos faltantes.
    """

    search_service_name: str = "stub-search-service"
    index_name: str = "stub-index"


class AzureAISearchService:
    """Servicio mínimo de Azure AI Search.

    Provee métodos asincrónicos utilizados por las tools de búsqueda. Si no hay
    cliente de OpenAI disponible, `openai_client` será None y los métodos
    devolverán un error informativo.
    """

    def __init__(self, openai_client: Optional[Any] = None, config: Optional[AzureSearchConfig] = None) -> None:
        """Inicializa el servicio con cliente OpenAI opcional y configuración.

        Args:
            openai_client (Optional[Any]): Cliente de OpenAI o None si no está configurado.
            config (Optional[AzureSearchConfig]): Configuración del servicio.
        """
        self.openai_client = openai_client
        self.config = config or AzureSearchConfig()

    async def search_by_content_vector(self, query: str, top: int = 5, use_hybrid: bool = True, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Realiza una búsqueda por vector de contenido (stub).

        Retorna un resultado controlado cuando no hay cliente OpenAI configurado.
        """
        if not self.openai_client:
            return {
                "error": "OpenAI client not configured",
                "total_count": 0,
                "documents": [],
                "search_type": "content_vector_stub",
            }

        # Implementación real pendiente.
        return {
            "error": None,
            "total_count": 0,
            "documents": [],
            "search_type": "content_vector",
        }

    async def search_by_use_case_vector(self, use_case: str, top: int = 5, use_hybrid: bool = True, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Realiza una búsqueda por vector de caso de uso (stub)."""
        if not self.openai_client:
            return {
                "error": "OpenAI client not configured",
                "total_count": 0,
                "documents": [],
                "search_type": "use_case_vector_stub",
            }

        # Implementación real pendiente.
        return {
            "error": None,
            "total_count": 0,
            "documents": [],
            "search_type": "use_case_vector",
        }

    async def multi_vector_search(self, query: str, top: int = 5, content_weight: float = 0.6, use_case_weight: float = 0.4, use_hybrid: bool = True, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Realiza una búsqueda multi-vector (stub)."""
        if not self.openai_client:
            return {
                "error": "OpenAI client not configured",
                "total_count": 0,
                "documents": [],
                "search_type": "multi_vector_stub",
            }

        # Implementación real pendiente.
        return {
            "error": None,
            "total_count": 0,
            "documents": [],
            "search_type": "multi_vector",
        }

    async def search_products_by_text(self, query: str, top: int = 5, use_hybrid: bool = True, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Realiza una búsqueda de productos por texto/embeddings (stub).

        Esta búsqueda asume un índice de productos con un campo vectorial
        (por ejemplo, `product_vector`) generado a partir de `name + description`.

        Args:
            query: Texto de búsqueda del producto.
            top: Número máximo de resultados.
            use_hybrid: Si combina búsqueda lexical con vectorial.
            filters: Filtros opcionales (precio, stock, categoría, etc.).

        Returns:
            dict: Estructura con `error`, `total_count`, `documents`, `search_type`.
        """
        if not self.openai_client:
            return {
                "error": "OpenAI client not configured",
                "total_count": 0,
                "documents": [],
                "search_type": "product_vector_stub",
            }

        # Implementación real pendiente.
        return {
            "error": None,
            "total_count": 0,
            "documents": [],
            "search_type": "product_vector",
        }

    async def search_product_by_sku(self, sku: str) -> Dict[str, Any]:
        """Busca un producto por SKU exacto (stub).

        Esta búsqueda no requiere embeddings; se espera un filtro exacto
        sobre el campo `sku` en el índice de productos.

        Args:
            sku: Código de referencia único del producto.

        Returns:
            dict: Estructura con `error`, `total_count`, `documents`, `search_type`.
        """
        # Implementación real pendiente. Retorna 0 resultados por defecto.
        return {
            "error": None,
            "total_count": 0,
            "documents": [],
            "search_type": "sku_filter_stub",
        }


def get_azure_search_service() -> AzureAISearchService:
    """Crea y retorna una instancia del servicio de búsqueda.

    Esta función es el punto de entrada que utilizan las tools. Devuelve una
    instancia con `openai_client=None` para indicar que no hay embeddings
    configurados, permitiendo que las tools muestren mensajes guía.
    """
    # En el futuro, inicializar aquí clientes reales (OpenAI/Azure) a partir de envs.
    return AzureAISearchService(openai_client=None, config=AzureSearchConfig())


__all__ = [
    "AzureAISearchService",
    "AzureSearchConfig",
    "get_azure_search_service",
]


