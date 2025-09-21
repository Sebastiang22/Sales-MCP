"""
Herramientas MCP para operaciones de base de datos relacionadas con ventas.

Este módulo registra herramientas MCP para crear registros de ventas de productos.
"""

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from sqlmodel import select

from database.connection import database_service
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
        sku: Optional[str] = None,
        product_id: Optional[int] = None,
        quantity: int = 1,
        unit_price: Optional[float] = None,
        customer_address: str = "",
    ) -> Dict[str, Any]:
        """Registra la venta de un producto.

        Valida la existencia del producto y crea un registro de venta con el
        precio unitario indicado o el del producto.

        Args:
            sku (Optional[str]): SKU del producto a vender. Alternativo a product_id.
            product_id (Optional[int]): ID del producto a vender. Alternativo a sku.
            quantity (int): Cantidad a vender. Debe ser > 0.
            unit_price (Optional[float]): Precio unitario. Si no se provee, usa product.price.
            customer_address (str): Dirección del cliente asociada a la venta.

        Returns:
            Dict[str, Any]: Resultado de la operación con detalles de la venta y stock.
        """
        try:
            if (sku is None and product_id is None) or (sku and product_id):
                return {
                    "success": False,
                    "error": "Debe proporcionar únicamente sku o product_id",
                }

            if quantity <= 0:
                return {
                    "success": False,
                    "error": "La cantidad debe ser mayor a 0",
                }

            if not customer_address or len(customer_address.strip()) < 5:
                return {
                    "success": False,
                    "error": "La dirección del cliente es inválida (mínimo 5 caracteres)",
                }

            with database_service.get_session_context() as session:
                product: Optional[Product] = None

                if sku is not None:
                    normalized_sku = sku.strip().upper()
                    stmt = select(Product).where(Product.sku == normalized_sku)
                    product = session.exec(stmt).first()
                else:
                    product = session.get(Product, product_id)  # type: ignore[arg-type]

                if product is None:
                    return {
                        "success": False,
                        "error": "Producto no encontrado",
                    }

                applied_unit_price = unit_price if unit_price is not None else product.price

                if not product.is_active:
                    return {
                        "success": False,
                        "error": "El producto no está activo para la venta",
                    }

                sale = ProductSale(
                    product_id=product.id,  # type: ignore[arg-type]
                    quantity=quantity,
                    unit_price=applied_unit_price,
                    total_amount=0.0,
                    customer_address=customer_address.strip(),
                )
                sale.update_total()

                session.add(sale)
                session.commit()
                session.refresh(sale)

                return {
                    "success": True,
                    "sale": {
                        "id": sale.id,
                        "product_id": sale.product_id,
                        "quantity": sale.quantity,
                        "unit_price": sale.unit_price,
                        "total_amount": sale.total_amount,
                        "customer_address": sale.customer_address,
                        "created_at": str(sale.created_at) if getattr(sale, "created_at", None) else None,
                    },
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    print("🗄️ Herramientas de base de datos registradas en el servidor MCP")
    print("   - register_product_sale: Registra venta")

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


