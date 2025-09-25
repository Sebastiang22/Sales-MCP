"""
Servicio para gestionar compras por tienda.

Este módulo permite guardar y leer compras desde tablas específicas
dependiendo del `store_id`, mapeado a nombres reales de tablas.

Esquema esperado de tabla de ventas:

(
    id integer NOT NULL,
    client_phone varchar(30) NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL,
    total_amount double precision NOT NULL,
    products json NOT NULL,
    client_json json NOT NULL
)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from sqlalchemy import bindparam
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from datetime import datetime

from database.connection import database_service


logger = logging.getLogger("purchase-service")


class PurchaseServiceError(Exception):
    """Error de alto nivel para operaciones de compras."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class PurchaseService:
    """Servicio para guardar y leer compras por tienda."""

    # Mapa de store_id -> nombre de tabla real
    STORE_TABLE_MAP: Dict[str, str] = {
        # Ejemplos; reemplazar/expandir según despliegue real
        "4f22df54942898f1": "ventas_mauricio"
    }

    def resolve_table_name(self, store_id: str) -> str:
        """
        Resuelve el nombre de la tabla a partir del store_id.

        Args:
            store_id: Identificador de la tienda.

        Returns:
            Nombre real de la tabla donde se guardan/leen compras.
        """
        key = (store_id or "").strip().lower()
        table_name = self.STORE_TABLE_MAP.get(key) or self.STORE_TABLE_MAP.get("default")

        if not table_name:
            raise PurchaseServiceError("No hay tabla configurada para el store_id dado", status_code=400)
        return table_name

    def save_purchase(self, store_id: str, purchase: Dict[str, Any]) -> Dict[str, Any]:
        """
        Guarda una compra en la tabla correspondiente al store.

        Args:
            store_id: Identificador de la tienda para mapear la tabla.
            purchase: Datos de la compra incluyendo `total_amount`, `client_phone`,
                datos del cliente por separado para construir `client_json` y `products`.

        Returns:
            Diccionario con confirmación y datos persistidos.
        """
        table = self.resolve_table_name(store_id)

        # Campos requeridos para cumplir el nuevo esquema
        required = [
            "total_amount",
            "client_phone",
            "client_full_name",
            "client_document",
            "client_address",
            "client_city",
            "client_email",
            "products",
        ]

        missing = [k for k in required if k not in purchase]
        if missing:
            raise PurchaseServiceError(f"Faltan campos requeridos: {', '.join(missing)}", status_code=422)

        with database_service.get_session_context() as session:
            # Construir JSON del cliente según requerimiento
            client_json: Dict[str, Any] = {
                "direccion": str(purchase["client_address"]).strip(),
                "ciudad": str(purchase["client_city"]).strip(),
                "cedula": str(purchase["client_document"]).strip(),
                "nombre_completo": str(purchase["client_full_name"]).strip(),
                "celular": str(purchase["client_phone"]).strip(),
                "correo": (str(purchase["client_email"]).strip().lower() if purchase.get("client_email") else None),
            }

            # Inserción; se asume que la tabla existe con las columnas esperadas
            insert_sql = text(
                f"""
                INSERT INTO {table} (client_phone, created_at, updated_at, total_amount, products, client_json)
                VALUES (:client_phone, NOW(), NOW(), :total_amount, :products, :client_json)
                """
            ).bindparams(
                bindparam("products", type_=PG_JSON()),
                bindparam("client_json", type_=PG_JSON()),
            )

            session.exec(insert_sql, params={
                "total_amount": float(purchase["total_amount"]),
                "client_phone": str(purchase["client_phone"]).strip(),
                "products": purchase["products"],
                "client_json": client_json,
            })
            session.commit()

            # Recuperar último registro persistido (heurística portable)
            select_sql = text(
                f"""
                SELECT id, client_phone, created_at, updated_at, total_amount, products, client_json
                FROM {table}
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = session.exec(select_sql).first()
            if not row:
                raise PurchaseServiceError("No fue posible leer la compra recién guardada", status_code=500)

            result = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
            # Normalizar datetimes a ISO8601 para facilitar serialización JSON
            for key in ("created_at", "updated_at"):
                value = result.get(key)
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
            result["table"] = table
            return result

    def get_purchases(self, store_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Lee compras desde la tabla correspondiente al store.

        Args:
            store_id: Identificador de la tienda para mapear la tabla.
            limit: Límite de registros a recuperar.
            offset: Desplazamiento de registros.

        Returns:
            Lista de compras serializadas.
        """
        table = self.resolve_table_name(store_id)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        with database_service.get_session_context() as session:
            sql = text(
                f"""
                SELECT id, client_phone, created_at, updated_at, total_amount, products, client_json
                FROM {table}
                ORDER BY id DESC
                LIMIT :limit OFFSET :offset
                """
            )
            rows = session.exec(sql, params={"limit": limit, "offset": offset}).all()
            results: List[Dict[str, Any]] = []
            for row in rows:
                data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
                for key in ("created_at", "updated_at"):
                    value = data.get(key)
                    if isinstance(value, datetime):
                        data[key] = value.isoformat()
                data["table"] = table
                results.append(data)
            return results


purchase_service = PurchaseService()

__all__ = [
    "PurchaseServiceError",
    "PurchaseService",
    "purchase_service",
]


