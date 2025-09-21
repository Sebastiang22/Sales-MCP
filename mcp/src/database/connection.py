"""
Módulo para gestionar la conexión con la base de datos.

Este archivo contiene el servicio de base de datos para la aplicación,
proporcionando métodos para gestionar conexiones, sesiones y operaciones básicas.
"""

from typing import (
    Optional,
    Generator,
    Any,
)
from contextlib import contextmanager
import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from sqlalchemy import text  # <-- Agregado para consultas SQL directas
from sqlmodel import (
    Session,
    SQLModel,
    create_engine,
)

from core.config import (
    Environment,
    settings,
)
logger = logging.getLogger("database")


class DatabaseError(Exception):
    """
    Excepción personalizada para errores de base de datos.
    
    Attributes:
        message: Mensaje descriptivo del error
        status_code: Código de estado HTTP sugerido
    """
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseService:
    """
    Servicio para gestionar las operaciones de base de datos.

    Esta clase maneja todas las operaciones de base de datos incluyendo
    la gestión de conexiones, sesiones y proporciona métodos para que
    los servicios de la aplicación puedan realizar consultas.
    """

    def __init__(self):
        """
        Inicializa el servicio de base de datos con pool de conexiones.
        
        Configura el engine de SQLAlchemy con configuraciones específicas
        para el entorno y establece el pool de conexiones.
        """
        self.engine = None
        self._initialize_database()

    def _initialize_database(self) -> None:
        """
        Inicializa la conexión a la base de datos.
        
        Configura el engine de SQLAlchemy con las configuraciones apropiadas
        según el entorno de ejecución.
        """
        try:
            # Determinar URL de base de datos: fallback a SQLite si no hay POSTGRES_URL
            db_url = (settings.POSTGRES_URL or "").strip()

            # Configuración del engine según el backend
            if not db_url:
                # Fallback para desarrollo: SQLite en archivo local
                # Nota: check_same_thread=False permite acceso desde diferentes hilos
                db_url = "sqlite:////home/agents/Agent-Sales/Sales-MCP/mcp/dev.db"
                engine_kwargs = {
                    "echo": settings.DEBUG,
                    "connect_args": {"check_same_thread": False},
                }
            elif db_url.startswith("sqlite:"):
                engine_kwargs = {
                    "echo": settings.DEBUG,
                    "connect_args": {"check_same_thread": False},
                }
            else:
                # Configuración para Postgres u otros backends con pool
                engine_kwargs = {
                    "echo": settings.DEBUG,
                    "pool_pre_ping": True,
                    "poolclass": QueuePool,
                    "pool_size": settings.POSTGRES_POOL_SIZE,
                    "max_overflow": settings.POSTGRES_MAX_OVERFLOW,
                    "pool_recycle": 3600,
                }

            # Crear el engine con la URL determinada
            self.engine = create_engine(db_url, **engine_kwargs)
            
            logger.info(
                "database_engine_initialized pool_size=%s max_overflow=%s",
                settings.POSTGRES_POOL_SIZE,
                settings.POSTGRES_MAX_OVERFLOW,
            )

        except Exception as e:
            logger.exception("database_initialization_error: %s", str(e))
            raise

    def get_session(self) -> Session:
        """
        Obtiene una nueva sesión de base de datos.
        
        Returns:
            Session: Nueva sesión de SQLModel para operaciones de base de datos
            
        Raises:
            DatabaseError: Si no se puede crear la sesión
        """
        if not self.engine:
            logger.error("database_engine_not_initialized")
            raise DatabaseError(
                message="Database engine not initialized",
                status_code=500
            )
        
        try:
            return Session(self.engine)
        except SQLAlchemyError as e:
            logger.exception("session_creation_error: %s", str(e))
            raise DatabaseError(
                message="Could not create database session",
                status_code=500
            )

    @contextmanager
    def get_session_context(self) -> Generator[Session, None, None]:
        """
        Proporciona un contexto de sesión que se cierra automáticamente.
        
        Yields:
            Session: Sesión de base de datos que se cierra automáticamente
            
        Example:
            with database_service.get_session_context() as session:
                # Realizar operaciones con la sesión
                pass
        """
        session = self.get_session()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.exception("session_context_error: %s", str(e))
            raise
        finally:
            session.close()

    def create_tables(self) -> None:
        """
        Crea todas las tablas definidas en los modelos.
        
        Este método debe ser llamado durante la inicialización de la aplicación
        para asegurar que todas las tablas existan en la base de datos.
        """
        if not self.engine:
            logger.error("database_engine_not_initialized")
            raise RuntimeError("Database engine not initialized")
        
        try:
            SQLModel.metadata.create_all(self.engine)
            logger.info("database_tables_created")
        except SQLAlchemyError as e:
            logger.exception("table_creation_error: %s", str(e))
            raise

    def drop_tables(self) -> None:
        """
        Elimina todas las tablas de la base de datos.
        
        ¡CUIDADO! Este método elimina todas las tablas y datos.
        Solo debe usarse en desarrollo o para pruebas.
        """
        if not self.engine:
            logger.error("database_engine_not_initialized")
            raise RuntimeError("Database engine not initialized")
        
        if settings.ENVIRONMENT == Environment.PRODUCTION:
            logger.error("drop_tables_blocked_in_production")
            raise RuntimeError("Cannot drop tables in production environment")
        
        try:
            SQLModel.metadata.drop_all(self.engine)
            logger.info("database_tables_dropped")
        except SQLAlchemyError as e:
            logger.exception("table_drop_error: %s", str(e))
            raise

    def health_check(self) -> bool:
        """
        Verifica el estado de la conexión a la base de datos.
        
        Returns:
            bool: True si la conexión está funcionando, False en caso contrario
        """
        if not self.engine:
            return False
        
        try:
            with self.get_session_context() as session:
                # Ejecutar una consulta simple para verificar la conexión
                session.exec(text("SELECT 1"))  # <-- Usar text() para SQLAlchemy
                return True
        except Exception as e:
            logger.exception("database_health_check_failed: %s", str(e))
            return False

    def close_connections(self) -> None:
        """
        Cierra todas las conexiones del pool.
        
        Este método debe ser llamado durante el cierre de la aplicación
        para liberar recursos de manera apropiada.
        """
        if self.engine:
            try:
                self.engine.dispose()
                logger.info("database_connections_closed")
            except Exception as e:
                logger.exception("connection_close_error: %s", str(e))


# Crear una instancia singleton del servicio de base de datos
database_service = DatabaseService()
