"""
Herramientas de búsqueda MCP para productos

Este módulo registra herramientas MCP enfocadas exclusivamente en la búsqueda de
productos (por texto vectorial/híbrido y por SKU exacto).
"""

import os
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from services.azure_ai_search import (
    get_azure_search_service,
    # check_azure_search_health
)

def register_search_tools(server: FastMCP) -> None:
    """
    Registra las herramientas de búsqueda en el servidor MCP
    
    Args:
        server (FastMCP): Instancia del servidor MCP donde registrar las herramientas
    """
    

    
    # @server.tool()
    # async def search_multi_vector(
    #     query: str, 
    #     top: int = 5,
    #     content_weight: float = 0.6,
    #     use_case_weight: float = 0.4,
    #     model_name: Optional[str] = None
    # ) -> Dict[str, Any]:
    #     """
    #     Búsqueda multi-vectorial usando ambos campos con pesos personalizables.
        
    #     Esta herramienta combina búsquedas en content_vector y when_to_use_vector,
    #     permitiendo ajustar la importancia de cada campo según la necesidad.
        
    #     Args:
    #         query (str): Texto de búsqueda general
    #         top (int, optional): Número máximo de resultados. Por defecto 5
    #         content_weight (float, optional): Peso para content_vector (0.0 a 1.0). Por defecto 0.6
    #         use_case_weight (float, optional): Peso para when_to_use_vector (0.0 a 1.0). Por defecto 0.4
    #         model_name (str, optional): Filtra resultados por el campo model_name
            
    #     Returns:
    #         dict: Resultados de búsqueda con la siguiente estructura:
    #             {
    #                 "count": int,           # Número de resultados
    #                 "results": List[dict],  # Lista de audios encontrados
    #                 "query": str,           # Consulta original
    #                 "search_type": str,     # Tipo de búsqueda realizada
    #                 "fields_used": List[str], # Campos vectoriales utilizados
    #                 "weights_applied": dict  # Pesos aplicados a cada campo
    #             }
    #     """
    #     try:
    #         print(f"🔀 Búsqueda multi-vectorial: '{query}' | model_name={model_name}")
    #         print(f"   - Peso contenido: {content_weight:.2f}")
    #         print(f"   - Peso caso de uso: {use_case_weight:.2f}")
            
    #         # Obtener el servicio de búsqueda
    #         search_service = get_azure_search_service()
            
    #         # Verificar si OpenAI está configurado
    #         if not search_service.openai_client:
    #             print("⚠️ OpenAI no está configurado - las búsquedas vectoriales no funcionarán")
    #             print("💡 Para habilitar búsquedas vectoriales, configura:")
    #             print("   1. OPENAI_API_KEY en tu archivo .env")
    #             print("   2. OPENAI_ENDPOINT en tu archivo .env")
                
    #             return {
    #                 "count": 0,
    #                 "results": [],
    #                 "query": query,
    #                 "search_type": "error_openai_not_configured",
    #                 "fields_used": ["content_vector", "when_to_use_vector"],
    #                 "weights_applied": {"content_vector": content_weight, "when_to_use_vector": use_case_weight},
    #                 "error": "OpenAI no configurado para embeddings",
    #                 "solution": "Configura OPENAI_API_KEY y OPENAI_ENDPOINT en tu archivo .env",
    #                 "debug_info": {
    #                     "openai_configured": False,
    #                     "config_loaded": bool(search_service.config),
    #                     "search_service_name": getattr(search_service.config, 'search_service_name', 'N/A'),
    #                     "index_name": getattr(search_service.config, 'index_name', 'N/A')
    #                 }
    #             }
            
    #         # Realizar búsqueda multi-vectorial (modo híbrido hardcodeado)
    #         results = await search_service.multi_vector_search(
    #             query=query,
    #             top=top,
    #             content_weight=content_weight,
    #             use_case_weight=use_case_weight,
    #             use_hybrid=True,
    #             model_name=model_name
    #         )
            
    #         if results.get('error'):
    #             return {
    #                 "count": 0,
    #                 "results": [],
    #                 "query": query,
    #                 "search_type": "error",
    #                 "fields_used": ["content_vector", "when_to_use_vector"],
    #                 "weights_applied": {"content_vector": content_weight, "when_to_use_vector": use_case_weight},
    #                 "error": results['error']
    #             }
            
    #         print(f"✅ Encontrados {results['total_count']} audios con búsqueda multi-vectorial")
            
    #         return {
    #             "count": results['total_count'],
    #             "results": results['documents'],
    #             "query": query,
    #             "search_type": results['search_type'],
    #             "fields_used": ["content_vector", "when_to_use_vector"],
    #             "weights_applied": {"content_vector": content_weight, "when_to_use_vector": use_case_weight}
    #         }
            
    #     except Exception as e:
    #         print(f"❌ Error en búsqueda multi-vectorial: {str(e)}")
    #         return {
    #             "count": 0,
    #             "results": [],
    #             "query": query,
    #             "search_type": "error",
    #             "fields_used": ["content_vector", "when_to_use_vector"],
    #             "weights_applied": {"content_weight": content_weight, "use_case_weight": use_case_weight},
    #             "error": str(e)
    #         }
    
    @server.tool()
    async def search_product_by_text(
        query: str,
        top: int = 5,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Busca productos por texto utilizando búsqueda híbrida y/o vectorial.

        Combina nombre y descripción del producto para calcular similitud semántica
        en un índice de productos. Aplica filtros opcionales de precio, stock y categoría.

        Args:
            query (str): Texto de búsqueda del producto
            top (int, optional): Número máximo de resultados. Por defecto 5
            min_price (float, optional): Precio mínimo de filtro
            max_price (float, optional): Precio máximo de filtro
            in_stock (bool, optional): Filtra productos con stock disponible
            category (str, optional): Filtra por categoría

        Returns:
            dict: Resultados de búsqueda con estructura:
                {
                    "count": int,
                    "results": List[{"name", "sku", "price", "description"}],
                    "query": str,
                    "search_type": str,
                    "field_used": str
                }
        """
        try:
            print(f"🛒 Búsqueda de productos por texto: '{query}' | top={top}")
            search_service = get_azure_search_service()

            filters: Dict[str, Any] = {}
            if min_price is not None:
                filters["min_price"] = min_price
            if max_price is not None:
                filters["max_price"] = max_price
            if in_stock is not None:
                filters["in_stock"] = in_stock
            if category is not None:
                filters["category"] = category

            # Verificar si OpenAI está configurado para búsqueda vectorial
            if not search_service.openai_client:
                print("⚠️ OpenAI no está configurado - la búsqueda vectorial de productos funcionará en modo stub")
                result = await search_service.search_products_by_text(
                    query=query,
                    top=top,
                    use_hybrid=True,
                    filters=filters or None,
                )
                return {
                    "count": result.get("total_count", 0),
                    "results": result.get("documents", []),
                    "query": query,
                    "search_type": result.get("search_type", "product_vector_stub"),
                    "field_used": "product_vector",
                    "warning": "OpenAI no configurado; resultados vacíos hasta integrar embeddings"
                }

            result = await search_service.search_products_by_text(
                query=query,
                top=top,
                use_hybrid=True,
                filters=filters or None,
            )

            if result.get("error"):
                return {
                    "count": 0,
                    "results": [],
                    "query": query,
                    "search_type": "error",
                    "field_used": "product_vector",
                    "error": result["error"],
                }

            docs = result.get("documents", [])
            simplified = [
                {
                    "name": d.get("name"),
                    "sku": d.get("sku"),
                    "price": d.get("price"),
                    "description": d.get("description"),
                }
                for d in docs
            ]

            print(f"✅ Encontrados {result.get('total_count', 0)} productos por texto")
            return {
                "count": result.get("total_count", len(simplified)),
                "results": simplified,
                "query": query,
                "search_type": result.get("search_type", "product_vector"),
                "field_used": "product_vector",
            }

        except Exception as e:
            print(f"❌ Error en búsqueda de productos por texto: {str(e)}")
            return {
                "count": 0,
                "results": [],
                "query": query,
                "search_type": "error",
                "field_used": "product_vector",
                "error": str(e),
            }

    @server.tool()
    async def search_product_by_sku(sku: str) -> Dict[str, Any]:
        """
        Busca un producto por su SKU exacto.

        Args:
            sku (str): Código de referencia único del producto

        Returns:
            dict: Resultado con el producto si existe
                {
                    "found": bool,
                    "product": {"name", "sku", "price", "description"} | None,
                    "search_type": str
                }
        """
        try:
            print(f"🔎 Búsqueda de producto por SKU: {sku}")
            search_service = get_azure_search_service()

            result = await search_service.search_product_by_sku(sku=sku)

            if result.get("error"):
                return {
                    "found": False,
                    "product": None,
                    "search_type": "error",
                    "error": result["error"],
                }

            docs = result.get("documents", [])
            product = None
            if docs:
                d = docs[0]
                product = {
                    "name": d.get("name"),
                    "sku": d.get("sku"),
                    "price": d.get("price"),
                    "description": d.get("description"),
                }

            found = product is not None
            print("✅ Producto encontrado" if found else "ℹ️ Producto no encontrado")
            return {
                "found": found,
                "product": product,
                "search_type": result.get("search_type", "sku_filter_stub"),
            }

        except Exception as e:
            print(f"❌ Error en búsqueda por SKU: {str(e)}")
            return {
                "found": False,
                "product": None,
                "search_type": "error",
                "error": str(e),
            }

    print("🔧 Herramientas de búsqueda registradas en el servidor MCP")
    print("   - search_product_by_text: Búsqueda de productos por texto (product_vector)")
    print("   - search_product_by_sku: Búsqueda de producto por SKU exacto")
    print("   - Las herramientas soportan modo híbrido (texto + vector) donde aplique")

