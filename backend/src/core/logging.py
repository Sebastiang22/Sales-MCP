"""Logging configuration and setup for the application.

This module provides structured logging configuration using structlog,
with environment-specific formatters and handlers. It supports both
console-friendly development logging and JSON-formatted production logging.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
)

import structlog
import warnings

from core.config import (
    Environment,
    settings,
)

def current_colombian_time() -> str:
    """Obtiene el timestamp actual en hora de Colombia.

    Returns:
        str: Timestamp en formato ISO con zona horaria de Colombia.
    """
    try:
        # Intentar usar zona horaria real de América/Bogotá si está disponible
        from zoneinfo import ZoneInfo  # Python 3.9+
        tz = ZoneInfo("America/Bogota")
        return datetime.now(tz).isoformat()
    except Exception:
        # Fallback a offset fijo UTC-5 si zoneinfo no está disponible
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=-5))
        return datetime.now(tz).isoformat()

# Ensure log directory exists
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_log_file_path() -> Path:
    """Get the current log file path based on date and environment.

    Returns:
        Path: The path to the log file
    """
    env_prefix = settings.ENVIRONMENT.value
    # Extraer solo la fecha del timestamp completo de Colombia
    date_part = current_colombian_time().split(' ')[0]
    return settings.LOG_DIR / f"{env_prefix}-{date_part}.jsonl"


class JsonlFileHandler(logging.Handler):
    """Custom handler for writing JSONL logs to daily files."""

    def __init__(self, file_path: Path):
        """Initialize the JSONL file handler.

        Args:
            file_path: Path to the log file where entries will be written.
        """
        super().__init__()
        self.file_path = file_path

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record to the JSONL file."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "filename": record.pathname,
                "line": record.lineno,
                "environment": settings.ENVIRONMENT.value,
            }
            if hasattr(record, "extra"):
                log_entry.update(record.extra)

            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """Close the handler."""
        super().close()


class DatabaseHandler(logging.Handler):
    """Custom handler for writing logs to database."""

    def __init__(self):
        """Initialize the database handler."""
        super().__init__()
        # Import here to avoid circular imports
        from models.logs import Log, LogLevel
        from sqlmodel import Session, create_engine
        
        self.Log = Log
        self.LogLevel = LogLevel
        self.engine = create_engine(settings.POSTGRES_URL)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record to the database."""
        try:
            from sqlmodel import Session  # Import here to avoid circular imports
            
            # Map Python logging levels to our LogLevel enum
            level_mapping = {
                logging.DEBUG: self.LogLevel.DEBUG,
                logging.INFO: self.LogLevel.INFO,
                logging.WARNING: self.LogLevel.WARNING,
                logging.ERROR: self.LogLevel.ERROR,
                logging.CRITICAL: self.LogLevel.CRITICAL,
            }
            
            log_level = level_mapping.get(record.levelno, self.LogLevel.INFO)
            
            # Extract user_id and session_id if available
            user_id = None
            session_id = None
            additional_data = {}
            
            # Standard excluded fields for logging records
            excluded_fields = {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                'filename', 'module', 'lineno', 'funcName', 'created', 
                'msecs', 'relativeCreated', 'thread', 'threadName', 
                'processName', 'process', 'stack_info', 'exc_info', 'exc_text',
                'user_id', 'session_id'  # Extract these separately
            }
            
            # Check for structlog data in the record
            if hasattr(record, '__dict__'):
                for key, value in record.__dict__.items():
                    if key == 'user_id':
                        user_id = value
                    elif key == 'session_id':
                        session_id = value
                    elif key not in excluded_fields:
                        # Convert datetime objects to string for JSON serialization
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        additional_data[key] = value
            
            # Check for extra data
            if hasattr(record, 'extra') and record.extra:
                if 'user_id' in record.extra:
                    user_id = record.extra['user_id']
                if 'session_id' in record.extra:
                    session_id = record.extra['session_id']
                
                for key, value in record.extra.items():
                    if key not in ['user_id', 'session_id']:
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        additional_data[key] = value
            
            # Check for structlog-specific data
            if hasattr(record, '_structlog_data'):
                if 'user_id' in record._structlog_data:
                    user_id = record._structlog_data['user_id']
                if 'session_id' in record._structlog_data:
                    session_id = record._structlog_data['session_id']
                    
                for key, value in record._structlog_data.items():
                    if key not in ['user_id', 'session_id']:
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        additional_data[key] = value
            
            # Remove empty additional_data
            if not additional_data:
                additional_data = None

            # Create log entry with proper user_id and session_id
            log_entry = self.Log(
                level=log_level,
                message=record.getMessage(),
                module=record.module,
                function_name=record.funcName,
                user_id=user_id,
                session_id=session_id,
                additional_data=additional_data
            )
            
            # Save to database
            with Session(self.engine) as session:
                session.add(log_entry)
                session.commit()
                
        except Exception as e:
            # If database logging fails, don't crash the app
            # Just print to stderr as fallback
            print(f"Error saving log to database: {e}", file=sys.stderr)
            print(f"Original log: [{record.levelname}] {record.getMessage()}", file=sys.stderr)

    def close(self) -> None:
        """Close the handler."""
        super().close()


class StructlogToDatabaseProcessor:
    """
    Procesador que envía logs de structlog directamente a la base de datos.
    """
    
    def __init__(self):
        """Inicializa el procesador con conexión a la base de datos."""
        try:
            from models.logs import Log, LogLevel
            from sqlmodel import Session, create_engine
            
            self.Log = Log
            self.LogLevel = LogLevel
            self.Session = Session  # Store Session class
            self.engine = create_engine(settings.POSTGRES_URL)
            self.enabled = True
        except Exception as e:
            print(f"Warning: Database processor disabled due to error: {e}", file=sys.stderr)
            self.enabled = False
    
    def __call__(self, logger, method_name, event_dict):
        """
        Procesa un evento de structlog y lo guarda en la base de datos.
        """
        if not self.enabled:
            return event_dict
            
        try:
            # Map structlog level to our LogLevel enum
            level_mapping = {
                'debug': self.LogLevel.DEBUG,
                'info': self.LogLevel.INFO,
                'warning': self.LogLevel.WARNING,
                'error': self.LogLevel.ERROR,
                'critical': self.LogLevel.CRITICAL,
            }
            
            log_level = level_mapping.get(method_name.lower(), self.LogLevel.INFO)
            
            # Extract message
            message = event_dict.get('event', str(event_dict))
            
            # Extract module and function info - prioritize the real source
            module = event_dict.get('module', event_dict.get('filename', 'unknown'))
            if module and module.endswith('.py'):
                module = module[:-3]  # Remove .py extension
            
            function_name = event_dict.get('func_name', event_dict.get('function', None))
            
            # Extract user_id and session_id specifically
            user_id = event_dict.get('user_id', None)
            session_id = event_dict.get('session_id', None)
            
            # Prepare additional data (exclude standard fields and user/session info)
            additional_data = {}
            excluded_fields = {
                'event', 'timestamp', 'level', 'logger', 'module', 'func_name', 
                'function', 'filename', 'lineno', 'pathname', 'user_id', 'session_id',
                'environment'  # This is added automatically by the system
            }
            
            for key, value in event_dict.items():
                if key not in excluded_fields:
                    # Convert datetime objects to string for JSON serialization
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    additional_data[key] = value
            
            # Remove empty additional_data
            if not additional_data:
                additional_data = None
            
            # Create log entry with proper user_id and session_id
            log_entry = self.Log(
                level=log_level,
                message=message,
                module=module,
                function_name=function_name,
                user_id=user_id,
                session_id=session_id,
                additional_data=additional_data
            )
            
            # Save to database
            try:
                with self.Session(self.engine) as session:
                    session.add(log_entry)
                    session.commit()
            except Exception as db_error:
                # Don't crash if database logging fails
                print(f"Database logging error: {db_error}", file=sys.stderr)
                
        except Exception as e:
            # Don't crash the logging pipeline
            print(f"Structlog database processor error: {e}", file=sys.stderr)
        
        return event_dict


# Create a global instance
# DISABLED: Database processor to avoid table creation issues
# _database_processor = StructlogToDatabaseProcessor()


def get_structlog_processors(include_file_info: bool = True) -> List[Any]:
    """Get the structlog processors based on configuration.

    Args:
        include_file_info: Whether to include file information in the logs

    Returns:
        List[Any]: List of structlog processors
    """
    # Set up processors that are common to both outputs
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # DISABLED: Database processor to avoid table creation issues
        # _database_processor,  # Add our custom database processor
    ]

    # Add callsite parameters if file info is requested
    if include_file_info:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.PATHNAME,
                }
            )
        )

    # Add environment info
    processors.append(lambda _, __, event_dict: {**event_dict, "environment": settings.ENVIRONMENT.value})

    return processors


def suppress_external_library_logs() -> None:
    """Suppress verbose logs from external libraries and SDKs.
    
    This function configures logging levels for external libraries to reduce noise
    from internal SDK operations like HTTP requests, responses, and verbose debugging.
    """
    # Azure SDK loggers
    azure_loggers = [
        'azure.core',
        'azure.core.pipeline',
        'azure.core.pipeline.policies',
        'azure.core.pipeline.policies.http_logging_policy',
        'azure.search.documents',
        'azure.search.documents._generated',
        'azure.search.documents.indexes',
        'azure.identity',
        'azure.storage',
        'uamqp',
        'azure.servicebus',
        'azure.eventhub'
    ]
    
    # OpenAI loggers
    openai_loggers = [
        'openai',
        'openai._base_client',
        'openai._client',
        'httpx',
        'httpcore'
    ]
    
    # HTTP and networking loggers
    http_loggers = [
        'urllib3',
        'urllib3.connectionpool',
        'urllib3.util.retry',
        'requests',
        'requests.packages.urllib3',
        'requests.packages.urllib3.connectionpool',
        'asyncio',
        'aiohttp',
        'aiohttp.access'
    ]
    
    # Database and ORM loggers
    db_loggers = [
        'sqlalchemy.engine',
        'sqlalchemy.pool',
        'sqlalchemy.dialects',
        'alembic'
    ]
    
    # Other third-party loggers
    other_loggers = [
        'langfuse',
        'langsmith',
        'langchain',
        'langgraph',
        'pydantic',
        'uvicorn.access',
        'fastapi'
    ]
    
    # Combine all external loggers
    all_external_loggers = azure_loggers + openai_loggers + http_loggers + db_loggers + other_loggers
    
    # Set log level based on environment
    if settings.ENVIRONMENT in [Environment.DEVELOPMENT, Environment.TEST]:
        # In development and test, show warnings and errors from external libraries
        external_log_level = logging.WARNING
    else:
        # In production/staging, only show errors from external libraries
        external_log_level = logging.ERROR
    
    # Configure each external logger
    for logger_name in all_external_loggers:
        logging.getLogger(logger_name).setLevel(external_log_level)
    
    # Special handling for very verbose loggers - always set to ERROR
    very_verbose_loggers = [
        'azure.core.pipeline.policies.http_logging_policy',
        'urllib3.connectionpool',
        'requests.packages.urllib3.connectionpool',
        'httpx._client',
        'httpcore.http11',
        'httpx._transports'
    ]
    
    for logger_name in very_verbose_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def suppress_warnings():
    """Suprimir warnings de librerías externas como Pydantic y otros."""
    # Suprimir todos los warnings de Pydantic
    warnings.filterwarnings("ignore", category=UserWarning, module=r"pydantic.*")
    # Suprimir otros warnings si es necesario
    warnings.filterwarnings("ignore")


def setup_logging() -> None:
    """Configure structlog with different formatters based on environment.

    In development: pretty console output
    In staging/production: structured JSON logs
    For MCP servers: file-only logging to avoid STDIO conflicts
    """
    # Suprimir warnings
    suppress_warnings()
    
    # Determinar el nivel de logging basado en LOG_LEVEL y DEBUG
    log_level_str = settings.LOG_LEVEL.upper()
    debug_mode = settings.DEBUG
    
    # Mapear string a nivel de logging
    level_mapping = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    log_level = level_mapping.get(log_level_str, logging.INFO)
    
    # Si DEBUG=true, forzar nivel DEBUG independientemente de LOG_LEVEL
    if debug_mode:
        log_level = logging.DEBUG
    
    # Detectar si estamos ejecutando como servidor MCP
    # Los servidores MCP usan STDIO para comunicación, así que no podemos usar stdout
    is_mcp_server = any('server.py' in arg for arg in sys.argv) or 'MCP' in str(sys.argv)
    
    handlers = []
    
    # Solo usar console handler si NO es servidor MCP
    if not is_mcp_server:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        handlers.append(console_handler)
    
    # Siempre incluir file handler para servidores MCP
    if is_mcp_server:
        try:
            file_handler = JsonlFileHandler(get_log_file_path())
            file_handler.setLevel(log_level)
            handlers.append(file_handler)
        except Exception as e:
            # Si falla el file handler, usar stderr como fallback
            stderr_handler = logging.StreamHandler(sys.stderr)
            stderr_handler.setLevel(log_level)
            handlers.append(stderr_handler)

    # Create database handler for saving logs to DB
    # DISABLED: Database logging to avoid table creation issues
    # try:
    #     database_handler = DatabaseHandler()
    #     database_handler.setLevel(log_level)
    #     handlers.append(database_handler)
    # except Exception as e:
    #     # If database handler fails to initialize, log to stderr instead of stdout
    #     if is_mcp_server:
    #         print(f"Warning: Database logging disabled due to error: {e}", file=sys.stderr)
    #     else:
    #         print(f"Warning: Database logging disabled due to error: {e}", file=sys.stderr)

    # Get shared processors
    shared_processors = get_structlog_processors(
        # Include detailed file info only in development and test
        include_file_info=settings.ENVIRONMENT in [Environment.DEVELOPMENT, Environment.TEST]
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=handlers,
        force=True
    )

    # Suppress external library logs AFTER basic config
    suppress_external_library_logs()

    # Configure structlog based on environment
    if settings.LOG_FORMAT == "console":
        # Development-friendly console logging
        structlog.configure(
            processors=[
                *shared_processors,
                # Use ConsoleRenderer for pretty output to the console
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Production JSON logging
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


# Initialize logging
setup_logging()

# Filtrar logs de dependencias externas para solo mostrar WARNING o superior
for ext_logger in [
    "openai",
    "httpx",
    "langgraph",
    "asyncio",
    "urllib3",
    "requests",
]:
    logging.getLogger(ext_logger).setLevel(logging.WARNING)

# Create logger instance
logger = structlog.get_logger()


def get_logger():
    """Obtener la instancia del logger."""
    return logger


# Log de inicialización
logger.info(
    "logging_initialized",
    environment=settings.ENVIRONMENT.value,
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
)


# -----------------------------------------
# region: Helper Functions for Detailed Logging
# -----------------------------------------

def log_agent_execution(agent_name: str, action: str, **kwargs) -> None:
    """Log información detallada de ejecución de agentes.
    
    Args:
        agent_name: Nombre del agente que se está ejecutando
        action: Acción que está realizando el agente
        **kwargs: Información adicional para incluir en el log
    """
    logger = get_logger()
    logger.debug(
        "agent_execution",
        agent_name=agent_name,
        action=action,
        **kwargs
    )


def log_tool_execution(tool_name: str, parameters: Dict[str, Any], result: Any = None, error: str = None) -> None:
    """Log información detallada de ejecución de tools.
    
    Args:
        tool_name: Nombre de la tool que se está ejecutando
        parameters: Parámetros pasados a la tool
        result: Resultado de la ejecución (opcional)
        error: Error si la ejecución falló (opcional)
    """
    logger = get_logger()
    
    log_data = {
        "tool_name": tool_name,
        "parameters": parameters,
    }
    
    if result is not None:
        log_data["result"] = result
        logger.debug("tool_execution_success", **log_data)
    elif error:
        log_data["error"] = error
        logger.error("tool_execution_error", **log_data)
    else:
        logger.debug("tool_execution_start", **log_data)


def log_node_transition(from_node: str, to_node: str, context: Dict[str, Any] = None) -> None:
    """Log transiciones entre nodos del sistema.
    
    Args:
        from_node: Nodo de origen
        to_node: Nodo de destino
        context: Contexto adicional de la transición
    """
    logger = get_logger()
    logger.debug(
        "node_transition",
        from_node=from_node,
        to_node=to_node,
        context=context or {}
    )


def log_system_event(event_type: str, description: str, **kwargs) -> None:
    """Log eventos importantes del sistema.
    
    Args:
        event_type: Tipo de evento (ej: "startup", "shutdown", "error")
        description: Descripción del evento
        **kwargs: Información adicional del evento
    """
    logger = get_logger()
    
    if event_type.lower() == "error":
        logger.error("system_event", event_type=event_type, description=description, **kwargs)
    else:
        logger.info("system_event", event_type=event_type, description=description, **kwargs)
