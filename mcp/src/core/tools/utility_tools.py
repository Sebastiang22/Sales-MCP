# """
# Herramientas de utilidad MCP para InsureGent
# """

# from mcp.server.fastmcp import FastMCP
# from typing import Dict, Any

# def register_utility_tools(server: FastMCP) -> None:
#     """
#     Registra las herramientas de utilidad en el servidor MCP
    
#     Args:
#         server (FastMCP): Instancia del servidor MCP donde registrar las herramientas
#     """
    
#     @server.tool()
#     async def get_server_info() -> Dict[str, Any]:
#         """Obtiene información del servidor MCP"""
#         return {
#             "name": "InsureGent MCP",
#             "version": "1.0.0",
#             "description": "Servidor MCP con herramientas para buscar información en la base de conocimientos de Sura",
#             "tools_count": len(server.tools),
#             "resources_count": len(server.resources),
#             "prompts_count": len(server.prompts)
#         }
    
#     @server.tool()
#     async def health_check() -> Dict[str, str]:
#         """Verifica el estado de salud del servidor"""
#         return {
#             "status": "healthy",
#             "message": "Servidor MCP funcionando correctamente"
#         }
