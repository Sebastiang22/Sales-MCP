"""
Servicio mínimo para Azure AI Search (stub).

Este módulo provee una implementación mínima para permitir que el servidor
arranque aun cuando no exista la integración real con Azure o OpenAI.
Las funciones retornan estructuras controladas o errores descriptivos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple

import json
import httpx

from core.config import settings


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

    # --------------- Utilidades internas ---------------
    async def _get_embeddings(self, text: str) -> Tuple[Optional[List[float]], Optional[str]]:
        """Obtiene embeddings usando Azure OpenAI u OpenAI estándar.

        Returns:
            tuple: (vector, error). Si hay error, vector será None.
        """
        try:
            # Preferir Azure OpenAI si está configurado
            if (
                settings.AZURE_OPENAI_API_KEY
                and settings.AZURE_OPENAI_ENDPOINT
                and settings.AZURE_OPENAI_API_VERSION
                and settings.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
            ):
                url = (
                    f"{settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/"
                    f"{settings.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT}/embeddings?api-version="
                    f"{settings.AZURE_OPENAI_API_VERSION}"
                )
                headers = {
                    "api-key": settings.AZURE_OPENAI_API_KEY,
                    "Content-Type": "application/json",
                }
                payload = {"input": text}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    return None, f"Azure OpenAI error {resp.status_code}: {resp.text}"
                data = resp.json()
                vector = data.get("data", [{}])[0].get("embedding")
                if not isinstance(vector, list):
                    return None, "Respuesta de embeddings inválida (Azure OpenAI)"
                return vector, None

            # Fallback a OpenAI estándar
            api_key = settings.OPENAI_API_KEY or settings.LLM_API_KEY
            if api_key:
                url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/embeddings"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": settings.OPENAI_EMBEDDINGS_MODEL,
                    "input": text,
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    return None, f"OpenAI error {resp.status_code}: {resp.text}"
                data = resp.json()
                vector = data.get("data", [{}])[0].get("embedding")
                if not isinstance(vector, list):
                    return None, "Respuesta de embeddings inválida (OpenAI)"
                return vector, None

            return None, "No hay configuración de embeddings (Azure/OpenAI)"
        except Exception as e:
            return None, str(e)

    def _build_odata_filter(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        """Construye filtro OData para Azure Search a partir de filtros simples."""
        if not filters:
            return None
        parts: List[str] = []
        if "min_price" in filters:
            parts.append(f"price ge {filters['min_price']}")
        if "max_price" in filters:
            parts.append(f"price le {filters['max_price']}")
        if "category" in filters:
            # Si existiera un campo 'category' en el índice
            parts.append(f"category eq '{str(filters['category']).replace("'", "''")}'")
        if "in_stock" in filters:
            # Si existiera 'stock_quantity' en el índice
            if filters["in_stock"]:
                parts.append("stock_quantity gt 0")
            else:
                parts.append("stock_quantity eq 0")
        return " and ".join(parts) if parts else None

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
        """Realiza una búsqueda de productos por texto/embeddings contra Azure Search.

        Si hay configuración de embeddings, usa vector search; con `use_hybrid=True`
        añade búsqueda lexical simultánea. Si no hay configuración de Azure Search,
        retorna resultados vacíos con error descriptivo.
        """
        # Validar Azure Search
        if not settings.AZURE_SEARCH_ENDPOINT or not settings.AZURE_SEARCH_API_KEY or not (self.config and self.config.index_name):
            return {
                "error": "Azure Search no configurado (endpoint/api_key/index)",
                "total_count": 0,
                "documents": [],
                "search_type": "product_vector_stub",
            }

        # Intentar embeddings (si hay proveedor configurado)
        embeddings: Optional[List[float]] = None
        embeddings_error: Optional[str] = None
        if self.openai_client:
            embeddings, embeddings_error = await self._get_embeddings(query)

        # Construir request de búsqueda
        api_version = "2023-11-01"
        # Construir endpoint a partir de SERVICE_NAME si no hay ENDPOINT completo
        if settings.AZURE_SEARCH_ENDPOINT:
            base = settings.AZURE_SEARCH_ENDPOINT.rstrip("/")
        elif settings.AZURE_SEARCH_SERVICE_NAME:
            base = f"https://{settings.AZURE_SEARCH_SERVICE_NAME}.search.windows.net"
        else:
            base = ""

        if not base:
            return {
                "error": "Azure Search no configurado (endpoint/service_name)",
                "total_count": 0,
                "documents": [],
                "search_type": "product_vector_stub",
            }

        url = (
            f"{base}/indexes/{self.config.index_name}/docs/search?api-version={api_version}"
        )
        headers = {
            "api-key": settings.AZURE_SEARCH_API_KEY,
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "count": True,
            "top": top,
        }

        odata_filter = self._build_odata_filter(filters)
        if odata_filter:
            payload["filter"] = odata_filter

        # Vector query si hay embeddings (usar 'vectors' en api-version 2023-11-01)
        vector_field = settings.AZURE_SEARCH_VECTOR_FIELD
        search_type = "lexical"
        if embeddings and isinstance(embeddings, list):
            payload["vectors"] = [
                {
                    "value": embeddings,
                    "fields": vector_field,
                    "k": top,
                }
            ]
            search_type = "product_vector"

        # Híbrido: agregar término lexical además de vector
        if use_hybrid:
            payload["queryType"] = "simple"
            payload["search"] = query

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return {
                    "error": f"Azure Search error {resp.status_code}: {resp.text}",
                    "total_count": 0,
                    "documents": [],
                    "search_type": search_type,
                }

            data = resp.json()
            docs = data.get("value", [])
            total = data.get("@odata.count", len(docs))
            return {
                "error": None,
                "total_count": total or len(docs),
                "documents": docs,
                "search_type": search_type,
            }
        except Exception as e:
            return {
                "error": str(e),
                "total_count": 0,
                "documents": [],
                "search_type": search_type,
                "embeddings_error": embeddings_error,
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
    instancia con un cliente de embeddings mínimo si hay claves presentes en
    variables de entorno. Si no, retorna `openai_client=None` para modo stub.
    """
    # Construir configuración básica del índice desde envs si existen
    index_name = settings.AZURE_SEARCH_INDEX_NAME or "stub-index"
    search_service_name = (
        settings.AZURE_SEARCH_ENDPOINT or "stub-search-service"
    )
    config = AzureSearchConfig(
        search_service_name=search_service_name,
        index_name=index_name,
    )

    # Inicialización mínima del cliente de embeddings según envs disponibles
    openai_client: Optional[Dict[str, Any]] = None

    # Preferir Azure OpenAI si está configurado
    if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
        openai_client = {
            "provider": "azure-openai",
            "endpoint": settings.AZURE_OPENAI_ENDPOINT,
            "api_key_present": True,
            "api_version": settings.AZURE_OPENAI_API_VERSION,
            "embeddings_deployment": settings.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        }
    # Fallback a OpenAI estándar (o LLM_API_KEY) si está presente
    elif settings.OPENAI_API_KEY or settings.LLM_API_KEY:
        api_key_present = bool(settings.OPENAI_API_KEY or settings.LLM_API_KEY)
        openai_client = {
            "provider": "openai",
            "base_url": settings.OPENAI_BASE_URL,
            "api_key_present": api_key_present,
            "embeddings_model": settings.OPENAI_EMBEDDINGS_MODEL,
        }

    return AzureAISearchService(openai_client=openai_client, config=config)


__all__ = [
    "AzureAISearchService",
    "AzureSearchConfig",
    "get_azure_search_service",
]


