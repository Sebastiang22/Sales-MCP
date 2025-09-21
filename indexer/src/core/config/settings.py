from __future__ import annotations

"""Gestión de configuración mínima para el indexador.

Carga variables de entorno necesarias para `ai_search_service.py`, con soporte
para archivos .env por entorno. Limita la configuración a los secretos
estrictamente requeridos por el servicio de Azure AI Search.
"""

import os
from enum import Enum
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore


class Environment(str, Enum):
    """Tipos de entorno de la aplicación.

    Define los posibles entornos: development, staging, production y test.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


def get_environment() -> Environment:
    """Obtiene el entorno actual de ejecución.

    Returns:
        Environment: Entorno actual (development, staging, production o test)
    """
    match os.getenv("APP_ENV", "development").lower():
        case "production" | "prod":
            return Environment.PRODUCTION
        case "staging" | "stage":
            return Environment.STAGING
        case "test":
            return Environment.TEST
        case _:
            return Environment.DEVELOPMENT


def _possible_env_paths() -> List[Path]:
    """Obtiene rutas candidatas donde buscar archivos .env por entorno.

    Returns:
        list[Path]: Rutas base donde pueden existir archivos .env.*
    """
    here = Path(__file__).resolve()
    # Estructura: indexer/src/core/config/settings.py
    src_root = here.parents[2]      # .../indexer/src
    indexer_root = here.parents[3]  # .../indexer
    repo_root = here.parents[4] if len(here.parents) >= 5 else indexer_root
    return [src_root, indexer_root, repo_root]


def load_env_file() -> None:
    """Carga el archivo .env correspondiente al entorno si existe.

    Busca en múltiples directorios base para compatibilidad con ejecución local
    y contenedores. No falla si `python-dotenv` no está instalado.
    """
    if load_dotenv is None:
        return

    env = get_environment()
    for base in _possible_env_paths():
        env_file = {
            Environment.DEVELOPMENT: base / ".env.development",
            Environment.PRODUCTION: base / ".env.production",
            Environment.STAGING: base / ".env.staging",
            Environment.TEST: base / ".env.test",
        }.get(env)
        if env_file and env_file.exists():
            load_dotenv(dotenv_path=env_file, override=True)
            return


# Cargar variables de entorno al importar el módulo
load_env_file()


class Settings:
    """Configuración mínima para el indexador.

    Expone solo los secretos requeridos por `ai_search_service.py`.
    """

    def __init__(self) -> None:
        """Inicializa configuración desde variables de entorno."""
        self.ENVIRONMENT = get_environment()

        # Azure AI Search
        self.AZURE_SEARCH_SERVICE_NAME: str = os.getenv("AZURE_SEARCH_SERVICE_NAME", "")
        self.AZURE_SEARCH_API_KEY: str = os.getenv("AZURE_SEARCH_API_KEY", "")
        self.AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.AZURE_SEARCH_INDEX_NAME: str = os.getenv("AZURE_SEARCH_INDEX_NAME", "products-index")

        # Embeddings (OpenAI/Azure OpenAI compatible a través de SDK de OpenAI)
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


# Instancia única
settings = Settings()
