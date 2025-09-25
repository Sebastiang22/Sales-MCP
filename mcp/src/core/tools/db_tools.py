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
        client_phone: str,
        client_full_name: str,
        client_document: str,
        client_address: str,
        client_city: str,
        client_email: Optional[str],
        products: Any,
    ) -> Dict[str, Any]:
        """Registra una compra con múltiples productos en una sola operación.

        Se esperan parámetros explícitos: `store_id`, datos del cliente por separado y `products`.
        `products` debe ser una lista con elementos/diccionarios con los siguientes campos: `product_id`, `quantity` y `unit_price`, por ejemplo: [{ "product_id": "123", "quantity": 1, "unit_price": 100 }, { "product_id": "456", "quantity": 2, "unit_price": 200 }].

        Args:
            store_id (str): Identificador de la tienda.
            client_phone (str): Celular del cliente.
            client_full_name (str): Nombre completo del cliente.
            client_document (str): Cédula del cliente.
            client_address (str): Dirección del cliente.
            client_city (str): Ciudad del cliente.
            client_email (Optional[str]): Correo del cliente.
            products (Any): Lista o JSON string con items a comprar.
                Cada item debe incluir: `product_id` (hash), `quantity` (>0) y `unit_price` (>=0).

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

            if not client_phone or len(client_phone.strip()) < 10:
                return {
                    "success": False,
                    "error": "El teléfono del cliente es inválido (mínimo 10 caracteres)",
                }

            if not client_address or len(client_address.strip()) < 5:
                return {
                    "success": False,
                    "error": "La dirección del cliente es inválida (mínimo 5 caracteres)",
                }

            if not client_full_name or len(client_full_name.strip()) < 3:
                return {"success": False, "error": "El nombre completo es inválido"}

            if not client_document or len(client_document.strip()) < 5:
                return {"success": False, "error": "La cédula es inválida"}

            if not client_city or len(client_city.strip()) < 2:
                return {"success": False, "error": "La ciudad es inválida"}

            # Validar estructura básica de los items sin consultar BD
            requested_items: List[Dict[str, Any]] = []
            total_amount: float = 0.0
            for i, item in enumerate(products_list):
                pid = str(item.get("product_id", "")).strip() if item and isinstance(item, dict) else ""
                qty = int(item.get("quantity", 0)) if item and isinstance(item, dict) else 0
                try:
                    unit_price = float(item.get("unit_price", None)) if item and isinstance(item, dict) else None
                except (TypeError, ValueError):
                    unit_price = None
                if not pid or qty <= 0 or unit_price is None or unit_price < 0:
                    return {"success": False, "error": f"Cada item debe incluir product_id (hash), quantity>0 y unit_price>=0. Item {i}: pid='{pid}', qty={qty}, unit_price={unit_price}"}
                requested_items.append({"product_id": pid, "quantity": qty, "unit_price": unit_price})
                total_amount += unit_price * qty

            # Persistir directamente sin validaciones de BD
            saved = purchase_service.save_purchase(
                store_id=store_id,
                purchase={
                    "total_amount": float(total_amount),
                    "client_phone": client_phone.strip(),
                    "client_full_name": client_full_name.strip(),
                    "client_document": client_document.strip(),
                    "client_address": client_address.strip(),
                    "client_city": client_city.strip(),
                    "client_email": (client_email.strip().lower() if client_email else None),
                    "products": requested_items,
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


