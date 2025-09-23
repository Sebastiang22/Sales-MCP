"""
Herramientas MCP para operaciones de base de datos relacionadas con ventas.

Este módulo registra herramientas MCP para crear registros de ventas de productos.
"""

from typing import Any, Dict, Optional, List
import json

from mcp.server.fastmcp import FastMCP
from sqlmodel import select

from database.connection import database_service
from services import purchase_service, PurchaseServiceError
from models.product import Product
from models.sale import ProductSale
from models.user import User


def register_db_tools(server: FastMCP) -> None:
    """Registra herramientas de base de datos en el servidor MCP.

    Args:
        server (FastMCP): Instancia del servidor MCP donde registrar las herramientas.
    """

    @server.tool()
    async def register_product_sale(
        store_id: str,
        customer_phone: str,
        customer_address: str,
        products: Any,
    ) -> Dict[str, Any]:
        """Registra una compra con múltiples productos en una sola operación.

        Se esperan parámetros explícitos: `store_id`, `customer_phone`, `customer_address` y `products`.
        `products` puede ser una lista o JSON string con elementos `{ "product_id": int, "quantity": int }`.

        Args:
            store_id (str): Identificador de la tienda para mapear la tabla de compras.
            customer_phone (str): Teléfono del cliente asociado a la compra.
            customer_address (str): Dirección del cliente asociada a la compra.
            products (Any): Lista de productos o JSON string con productos a comprar.

        Returns:
            Dict[str, Any]: Resultado con la compra persistida.
        """
        try:
            # Manejar tanto lista como JSON string
            if isinstance(products, str):
                try:
                    products_list = json.loads(products)
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "El campo 'products' debe ser un JSON válido",
                    }
            elif isinstance(products, list):
                products_list = products
            else:
                return {
                    "success": False,
                    "error": "El campo 'products' debe ser una lista o JSON string",
                }
            
            if not isinstance(products_list, list) or len(products_list) == 0:
                return {
                    "success": False,
                    "error": "Debe proporcionar una lista 'products' con al menos un item",
                }

            if not customer_phone or len(customer_phone.strip()) < 10:
                return {
                    "success": False,
                    "error": "El teléfono del cliente es inválido (mínimo 10 caracteres)",
                }

            if not customer_address or len(customer_address.strip()) < 5:
                return {
                    "success": False,
                    "error": "La dirección del cliente es inválida (mínimo 5 caracteres)",
                }

            # Validar estructura básica de los items sin consultar BD
            requested_items: List[Dict[str, Any]] = []
            for i, item in enumerate(products_list):
                pid = int(item.get("product_id", 0)) if item and isinstance(item, dict) else 0
                qty = int(item.get("quantity", 0)) if item and isinstance(item, dict) else 0
                if pid <= 0 or qty <= 0:
                    return {"success": False, "error": f"Cada item debe incluir product_id>0 y quantity>0. Item {i}: pid={pid}, qty={qty}"}
                requested_items.append({"product_id": pid, "quantity": qty})

            # Persistir directamente sin validaciones de BD
            saved = purchase_service.save_purchase(
                store_id=store_id,
                purchase={
                    "total_amount": 0.0,  # Total será calculado externamente si es necesario
                    "customer_phone": customer_phone.strip(),
                    "customer_address": customer_address.strip(),
                    "products": requested_items,  # Guardar tal como viene
                },
            )

            return {
                "success": True,
                "sale": saved,
            }

        except PurchaseServiceError as e:
            return {
                "success": False,
                "error": e.message,
                "status_code": e.status_code,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    print("🗄️ Herramientas de base de datos registradas en el servidor MCP")
    print("   - register_product_sale: Registra venta")

    @server.tool()
    async def get_store_purchases(store_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Obtiene compras de una tienda específica usando su tabla mapeada.

        Args:
            store_id (str): Identificador de la tienda para resolver la tabla.
            limit (int): Límite de registros a recuperar (1-200).
            offset (int): Desplazamiento de los registros.

        Returns:
            Dict[str, Any]: Resultado con la lista de compras.
        """
        try:
            purchases = purchase_service.get_purchases(store_id=store_id, limit=limit, offset=offset)
            return {"success": True, "purchases": purchases}
        except PurchaseServiceError as e:
            return {"success": False, "error": e.message, "status_code": e.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    print("   - get_store_purchases: Lista compras por tienda")

    @server.tool()
    async def update_user_by_phone(
        phone: str,
        new_name: Optional[str] = None,
        new_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Actualiza nombre o correo de un usuario por su teléfono.

        Al menos uno de los campos `new_name` o `new_email` debe ser provisto.

        Args:
            phone (str): Número de teléfono del usuario (solo dígitos).
            new_name (Optional[str]): Nuevo nombre del usuario.
            new_email (Optional[str]): Nuevo correo del usuario.

        Returns:
            Dict[str, Any]: Resultado de la operación con datos del usuario actualizado.
        """
        try:
            if not phone or not phone.isdigit() or len(phone) < 10:
                return {
                    "success": False,
                    "error": "Teléfono inválido (solo dígitos, mínimo 10)",
                }

            if new_name is None and new_email is None:
                return {
                    "success": False,
                    "error": "Debe proporcionar new_name y/o new_email",
                }

            with database_service.get_session_context() as session:
                stmt = select(User).where(User.phone == phone)
                user = session.exec(stmt).first()
                if user is None:
                    return {
                        "success": False,
                        "error": "Usuario no encontrado",
                    }

                if new_name is not None:
                    user.name = new_name.strip()
                if new_email is not None:
                    user.email = new_email.strip().lower() if new_email else None

                user.update_timestamp()
                session.add(user)
                session.commit()
                session.refresh(user)

                return {
                    "success": True,
                    "user": {
                        "id": user.id,
                        "name": user.name,
                        "phone": user.phone,
                        "email": user.email,
                        "is_active": user.is_active,
                    },
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    print("   - update_user_by_phone: Actualiza nombre/correo por teléfono")


