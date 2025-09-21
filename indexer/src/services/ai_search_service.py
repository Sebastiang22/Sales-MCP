from __future__ import annotations

"""Servicio de Azure AI Search para indexar y buscar productos.

Este módulo provee una clase de servicio enfocada en un índice genérico de
productos. Crea el esquema del índice (en inglés), permite crear o
re-crear el índice, subir documentos y realizar búsquedas básicas.

Requisitos de entorno esperados (si se desean clientes reales):
- AZURE_SEARCH_SERVICE_NAME
- AZURE_SEARCH_API_KEY
- AZURE_SEARCH_INDEX_NAME (por ejemplo: products-index)
- AZURE_SEARCH_ENDPOINT (opcional; si no se define se construye con el service name)
- LLM_API_KEY (opcional; activa embeddings y búsqueda vectorial)
- OPENAI_EMBEDDING_MODEL (opcional; por defecto text-embedding-3-small)

Si no se configuran credenciales, los métodos devolverán errores controlados
para facilitar el diagnóstico.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4
import hashlib

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SimpleField,
        SearchField,
        SearchFieldDataType,
        VectorSearch,
        HnswAlgorithmConfiguration,
        VectorSearchProfile,
        SemanticConfiguration,
        SemanticPrioritizedFields,
        SemanticField,
        SemanticSearch,
        SearchIndex,
    )
except Exception:  # pragma: no cover - permite importar sin dependencias instaladas
    AzureKeyCredential = object  # type: ignore
    SearchClient = object  # type: ignore
    SearchIndexClient = object  # type: ignore
    SimpleField = SearchField = SearchFieldDataType = object  # type: ignore
    VectorSearch = HnswAlgorithmConfiguration = VectorSearchProfile = object  # type: ignore
    SemanticConfiguration = SemanticPrioritizedFields = SemanticField = object  # type: ignore
    SemanticSearch = SearchIndex = object  # type: ignore

try:  # OpenAI opcional
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore

from indexer.src.core.config.settings import settings


@dataclass
class ProductSearchConfig:
    """Configuración del servicio de búsqueda de productos.

    Esta configuración encapsula parámetros necesarios para interactuar con
    Azure AI Search y el proveedor de embeddings.
    """

    service_name: str | None = None
    api_key: str | None = None
    endpoint: str | None = None
    index_name: str | None = None
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"


def compute_store_id(store_name: str) -> str:
    """Genera un identificador hash consistente para una tienda.

    Args:
        store_name: Nombre de la tienda de origen.

    Returns:
        str: Hash estable (hex) derivado del nombre normalizado de la tienda.
    """
    normalized = (store_name or "").strip().lower()
    if not normalized:
        return ""
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


class AzureProductSearchService:
    """Servicio para gestionar el índice de productos en Azure AI Search.

    Expone utilidades para crear el índice, preparar documentos y subirlos.
    Si no hay configuración válida, retorna errores descriptivos.
    """

    def __init__(self, config: Optional[ProductSearchConfig] = None) -> None:
        """Inicializa el servicio tomando valores desde settings/env.

        Args:
            config: Configuración explícita. Si no se provee, se carga desde settings.
        """
        merged = ProductSearchConfig(
            service_name=(config.service_name if config else None) or getattr(settings, "AZURE_SEARCH_SERVICE_NAME", None),
            api_key=(config.api_key if config else None) or getattr(settings, "AZURE_SEARCH_API_KEY", None),
            endpoint=(config.endpoint if config else None)
            or getattr(settings, "AZURE_SEARCH_ENDPOINT", None)
            or (f"https://{getattr(settings, 'AZURE_SEARCH_SERVICE_NAME', '')}.search.windows.net" if getattr(settings, "AZURE_SEARCH_SERVICE_NAME", "") else None),
            index_name=(config.index_name if config else None) or getattr(settings, "AZURE_SEARCH_INDEX_NAME", None) or "products-index",
            openai_api_key=(config.openai_api_key if config else None) or getattr(settings, "LLM_API_KEY", None),
            embedding_model=(config.embedding_model if config else None) or getattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        )

        self.config = merged

        self._has_azure = all([self.config.service_name, self.config.api_key, self.config.endpoint, self.config.index_name])
        self._has_openai = bool(self.config.openai_api_key and AsyncOpenAI is not None)

        self._credential = AzureKeyCredential(self.config.api_key) if self._has_azure else None
        self._index_client = (
            SearchIndexClient(endpoint=self.config.endpoint, credential=self._credential)
            if self._has_azure
            else None
        )
        self._search_client = (
            SearchClient(endpoint=self.config.endpoint, index_name=self.config.index_name, credential=self._credential)
            if self._has_azure
            else None
        )
        self._openai = AsyncOpenAI(api_key=self.config.openai_api_key) if self._has_openai else None

    def _index_schema(self) -> Any:
        """Construye el esquema de índice para productos (campos en inglés).

        Returns:
            Any: Instancia `SearchIndex` lista para crear/actualizar el índice.
        """
        has_vectors = bool(self._openai)

        fields: List[Any] = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchField(name="name", type=SearchFieldDataType.String, searchable=True, filterable=True, sortable=True),
            SearchField(name="description", type=SearchFieldDataType.String, searchable=True),
            SimpleField(name="price", type=SearchFieldDataType.Double, filterable=True, sortable=True, facetable=True),
            # store_id es un hash consistente del nombre de la tienda
            SimpleField(name="store_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchField(name="store", type=SearchFieldDataType.String, searchable=True, filterable=True, facetable=True),
            SearchField(
                name="images",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                searchable=False,
                filterable=False,
            ),
            SearchField(name="search_text", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="tags", type=SearchFieldDataType.Collection(SearchFieldDataType.String), searchable=True, filterable=True, facetable=True),
            SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        ]

        vector_search = None
        if has_vectors:
            fields.append(
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    hidden=True,
                    vector_search_dimensions=1536,
                    vector_search_profile_name="default-vector-profile",
                )
            )
            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="default-algorithm",
                        parameters={"metric": "cosine", "m": 4, "ef_construction": 200, "ef_search": 400},
                    )
                ],
                profiles=[
                    VectorSearchProfile(name="default-vector-profile", algorithm_configuration_name="default-algorithm")
                ],
            )

        semantic_search = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name="products-semantic-config",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="name"),
                        content_fields=[SemanticField(field_name="description"), SemanticField(field_name="search_text")],
                        keywords_fields=[
                            SemanticField(field_name="store"),
                            SemanticField(field_name="store_id"),
                            SemanticField(field_name="tags"),
                        ],
                    ),
                )
            ]
        )

        return SearchIndex(name=self.config.index_name, fields=fields, vector_search=vector_search, semantic_search=semantic_search)

    async def create_index(self, force_recreate: bool = False) -> Dict[str, Any]:
        """Crea o recrea el índice de productos.

        Args:
            force_recreate: Si es True, elimina el índice antes de crearlo.

        Returns:
            dict: Resultado con `success` y `error` si aplica.
        """
        if not self._has_azure:
            return {"success": False, "error": "Azure Search no está configurado"}

        try:
            if force_recreate:
                try:
                    self._index_client.delete_index(self.config.index_name)
                except Exception:
                    pass
            # Crear índice con fallback si semantic no está disponible
            index = self._index_schema()
            try:
                self._index_client.create_or_update_index(index)
            except Exception as e:
                if "semantic" in str(e).lower():
                    # Reintento sin semantic
                    index_no_semantic = SearchIndex(
                        name=self.config.index_name, fields=index.fields, vector_search=index.vector_search
                    )
                    self._index_client.create_or_update_index(index_no_semantic)
                else:
                    raise
            return {"success": True}
        except Exception as e:  # pragma: no cover
            return {"success": False, "error": str(e)}

    async def prepare_product_document(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Transforma un producto crudo en documento listo para indexar.

        Espera llaves en español y produce campos en inglés:
        - nombre -> name
        - precio_venta -> price
        - descripcion -> description
        - tienda -> store
        - imagenes -> images (lista de URLs)
        - store_id -> store_id (opcional; si no se provee se calcula)

        Además genera `search_text` y opcionalmente `content_vector`.
        """
        doc_id = raw.get("id") or str(uuid4())
        images_value = raw.get("imagenes") or []
        if isinstance(images_value, str):
            images = [u.strip() for u in images_value.split(",") if u.strip()]
        elif isinstance(images_value, list):
            images = [str(u).strip() for u in images_value if str(u).strip()]
        else:
            images = []

        name = (raw.get("nombre") or "").strip()
        description = (raw.get("descripcion") or "").strip()
        store = (raw.get("tienda") or "").strip()
        price = raw.get("precio_venta")
        incoming_store_id = (raw.get("store_id") or "").strip()
        store_id = incoming_store_id or compute_store_id(store)

        # search_text compuesto
        search_parts: List[str] = []
        if name:
            search_parts.append(name)
        if description:
            search_parts.append(description)
        if store:
            search_parts.append(f"Store: {store}")
        if price not in (None, ""):
            try:
                search_parts.append(f"Price: {float(price):.2f}")
            except Exception:
                pass
        search_text = " | ".join(search_parts)

        prepared = {
            "id": doc_id,
            "name": name,
            "description": description,
            "price": float(price) if price not in (None, "") else None,
            "store_id": store_id,
            "store": store,
            "images": images,
            "search_text": search_text,
            "tags": [],
            "created_at": "2024-01-01T00:00:00Z",
        }

        if self._openai and search_text:
            try:
                resp = await self._openai.embeddings.create(model=self.config.embedding_model, input=search_text)
                embedding = resp.data[0].embedding  # type: ignore[attr-defined]
                prepared["content_vector"] = embedding
            except Exception:
                # Silencioso: si falla el embedding, seguimos con búsqueda lexical/semántica
                pass

        return prepared

    async def upload_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sube documentos al índice en lotes.

        Args:
            documents: Lista de documentos ya preparados con `prepare_product_document`.

        Returns:
            dict: Resultado con `success`, `uploaded`, `error` si aplica.
        """
        if not self._has_azure:
            return {"success": False, "uploaded": 0, "error": "Azure Search no está configurado"}

        if not documents:
            return {"success": True, "uploaded": 0}

        try:
            batch_size = 100
            uploaded = 0
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]
                self._search_client.upload_documents(documents=batch)
                uploaded += len(batch)
            return {"success": True, "uploaded": uploaded}
        except Exception as e:  # pragma: no cover
            return {"success": False, "uploaded": 0, "error": str(e)}


__all__ = ["AzureProductSearchService", "ProductSearchConfig", "compute_store_id"]
