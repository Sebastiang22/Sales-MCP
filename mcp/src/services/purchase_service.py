"""
Servicio para gestionar compras por tienda.

Este módulo permite guardar y leer compras desde tablas específicas
dependiendo del `store_id`, mapeado a nombres reales de tablas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy import text

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
            purchase: Datos de la compra (product_id, quantity, unit_price, total_amount, customer_address).

        Returns:
            Diccionario con confirmación y datos persistidos.
        """
        table = self.resolve_table_name(store_id)

        required = ["total_amount", "customer_phone", "customer_address", "products"]

        missing = [k for k in required if k not in purchase]
        if missing:
            raise PurchaseServiceError(f"Faltan campos requeridos: {', '.join(missing)}", status_code=422)

        with database_service.get_session_context() as session:
            # Inserción; se asume que la tabla existe con las columnas esperadas
            insert_sql = text(
                f"""
                INSERT INTO {table} (total_amount, customer_phone, customer_address, products, created_at)
                VALUES (:total_amount, :customer_phone, :customer_address, :products, NOW())
                """
            ).bindparams(bindparam("products", type_=JSONB()))

            session.exec(insert_sql, params={
                "total_amount": purchase["total_amount"],
                "customer_phone": purchase["customer_phone"].strip(),
                "customer_address": purchase["customer_address"].strip(),
                "products": purchase["products"],
            })
            session.commit()

            # Recuperar último registro persistido (heurística portable)
            select_sql = text(
                f"""
                SELECT id, total_amount, customer_phone, customer_address, products, created_at, updated_at
                FROM {table}
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = session.exec(select_sql).first()
            if not row:
                raise PurchaseServiceError("No fue posible leer la compra recién guardada", status_code=500)

            result = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
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
                SELECT id, total_amount, customer_phone, customer_address, products, created_at, updated_at
                FROM {table}
                ORDER BY id DESC
                LIMIT :limit OFFSET :offset
                """
            )
            rows = session.exec(sql, params={"limit": limit, "offset": offset}).all()
            results: List[Dict[str, Any]] = []
            for row in rows:
                data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
                data["table"] = table
                results.append(data)
            return results


purchase_service = PurchaseService()

__all__ = [
    "PurchaseServiceError",
    "PurchaseService",
    "purchase_service",
]


