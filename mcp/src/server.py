"""
InsureGent MCP
Este servidor proporciona diferentes herramientas de busqueda de información en la base de conocimientos de Sura.
"""

import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent.parent.parent
print(project_root)
sys.path.insert(0, str(project_root))

import json
import random
from typing import Optional
from mcp.server.fastmcp import FastMCP
from datetime import datetime
# Imports de autenticación comentados temporalmente
# from auth.jwt_verifier import JWTVerifier
# from config.settings import settings
# from mcp.server.auth.settings import AuthSettings
# from pydantic import AnyHttpUrl

# Configurar logging para filtrar logs de librerías externas
import logging

# Configurar el nivel de logging para las librerías externas
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("azure.search").setLevel(logging.WARNING)
logging.getLogger("azure.search.documents").setLevel(logging.WARNING)
logging.getLogger("azure.search.documents.indexes").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)

# Configurar logging solo para tu aplicación
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Logger principal de la aplicación
logger = logging.getLogger("colombiang-mcp")
logger.setLevel(logging.INFO)

# Initialize FastMCP server
server = FastMCP(
    name="MCP ColombianG",
    instructions= """
        Servidor MCP con herramientas para:
    
        1. Buscar información en la base de conocimientos de Audios e Imagenes con sus respectivos URLs para Conversaciones Realistas

        2. Envío de audios, videos e imagenes al Whatsapp de un cliente a partir de URLs
        
        """,
    host="0.0.0.0",
    port=8050,
    stateless_http=True,
    # Autenticación comentada temporalmente
    # token_verifier=JWTVerifier(secret=settings.jwt.secret_key),
    # auth=AuthSettings(
    #     issuer_url=AnyHttpUrl(settings.jwt.issuer_url or "http://localhost:8000"),  # URL base de tu Authorization Server
    #     resource_server_url=AnyHttpUrl(settings.jwt.resource_server_url or "http://localhost:8050"),  # URL de este MCP server
    #     required_scopes=["mcp:read"],  # Ajusta según tus necesidades
    #     
    #     # //////////////////////////////////////////////////////////////
    #     #  Ejemplos de scopes comunes en MCP
    #     # Aunque los scopes pueden variar según la implementación, algunos ejemplos típicos son:
    #     # mcp:read: Permite leer información de los recursos MCP.
    #     # mcp:write: Permite modificar o crear recursos en MCP.
    #     # mcp:admin: Permite realizar acciones administrativas, como gestionar usuarios o configuraciones.
    #     # mcp:delete: Permite eliminar recursos.
    #     # Scopes personalizados: Puedes definir scopes específicos para tu aplicación, como mcp:search, mcp:export, etc.
    #     # //////////////////////////////////////////////////////////////
    #     #  ¿Cómo puedes usarlos?
    #     # 1. Definir scopes en tu servidor:
    #     #   Al crear endpoints o recursos, especifica qué scopes son necesarios para acceder a cada uno.
    #     # 2. Solicitar scopes al autenticar:
    #     #   Cuando una aplicación o usuario se autentica, debe solicitar los scopes que necesita. El servidor solo otorgará los permisos autorizados.
    #     # 3. Validar scopes en cada petición:
    #     #   Antes de procesar una solicitud, verifica que el token de acceso incluya los scopes requeridos.
    #     # //////////////////////////////////////////////////////////////
    # ),
)

# Registrar todas las herramientas desde los módulos organizados
from core.tools import (
    register_search_tools,
    register_db_tools,
    # register_utility_tools
)
from core.prompts import register_prompt_tools
from core.resources import register_resource_tools
from core.tools import register_whatsapp_tools
# Registrar todas las herramientas en el servidor
register_search_tools(server)
register_db_tools(server)
register_prompt_tools(server)
register_resource_tools(server)
# register_utility_tools(server)
register_whatsapp_tools(server)
# Las herramientas ahora están organizadas en módulos separados
# y se registran automáticamente arriba


if __name__ == "__main__":
    server.run(transport="streamable-http")
    
    
# Para Levantar inspector en local:
#npx @modelcontextprotocol/inspector mcp run server.py