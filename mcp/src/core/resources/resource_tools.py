"""
Herramientas de recursos MCP para InsureGent
"""

from mcp.server.fastmcp import FastMCP

def register_resource_tools(server: FastMCP) -> None:
    """
    Registra las herramientas de recursos en el servidor MCP
    
    Args:
        server (FastMCP): Instancia del servidor MCP donde registrar las herramientas
    """
    
    @server.resource("greeting://{name}")
    def get_greeting(name: str) -> str:
        """Obtiene un saludo personalizado"""
        return f"Hola, {name}!"

    @server.resource("coverage://{insurance_type}/{coverage_id}")
    def get_coverage_details(insurance_type: str, coverage_id: str) -> dict:
        """Obtiene detalles específicos de una cobertura"""
        # Aquí podrías implementar la lógica para obtener los detalles
        return {
            "type": insurance_type,
            "coverage_id": coverage_id,
            "details": "Detalles de la cobertura..."
        }

    @server.resource("faq://{category}")
    def get_category_faqs(category: str) -> list:
        """Obtiene preguntas frecuentes por categoría"""
        return [
            {"question": "Pregunta 1...", "answer": "Respuesta 1..."},
            {"question": "Pregunta 2...", "answer": "Respuesta 2..."}
        ]

    @server.resource("products://{category}")
    def get_insurance_products(category: str) -> list:
        """Obtiene lista de productos de seguro por categoría"""
        return [
            {"id": "1", "name": "Producto 1", "description": "..."},
            {"id": "2", "name": "Producto 2", "description": "..."}
        ]
