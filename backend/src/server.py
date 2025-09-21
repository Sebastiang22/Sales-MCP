from typing import Any, Dict, Optional
from uuid import UUID
import json
import sys
import os
from starlette.applications import Starlette
from starlette.routing import Mount, Host,Route
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from schemas.user import UserCreateData, UserUpdateData
from schemas.order import OrderCreateData, OrderItemCreateData
from schemas.order import OrderItemUpdateData
from schemas.product import ProductCreateData
import datetime

# Configurar el path para las importaciones
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Imports con manejo de errores
try:
    from services.user_service import user_service, UserServiceError
    from services.order_service import order_service, OrderServiceError
    from services.product_service import product_service, ProductServiceError
    from core.logging import logger
    SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Services not available: {e}", file=sys.stderr)
    SERVICES_AVAILABLE = False
    # Mock objects para permitir que el servidor se ejecute sin servicios
    class MockUserService:
        def create_user(self, data): raise Exception("Services not initialized")
        def get_user_by_id(self, user_id): raise Exception("Services not initialized")
        def get_user_by_phone(self, phone): raise Exception("Services not initialized")
        def update_user(self, user_id, data): raise Exception("Services not initialized")
        def delete_user(self, user_id): raise Exception("Services not initialized")

    class MockOrderService:
        def create_order(self, data): raise Exception("Services not initialized")
        def get_orders_by_phone(self, phone): raise Exception("Services not initialized")
        def get_latest_order_by_phone(self, phone): raise Exception("Services not initialized")

    class MockProductService:
        def get_all_products(self): raise Exception("Services not initialized")
        def add_products(self, products): raise Exception("Services not initialized")

    class MockLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass

    user_service = MockUserService()
    order_service = MockOrderService()
    product_service = MockProductService()
    logger = MockLogger()
    UserServiceError = Exception
    OrderServiceError = Exception
    ProductServiceError = Exception

# Initialize FastMCP server
mcp = FastMCP(
    name="restaurant-users-server",
    instructions="""
    Este servidor MCP proporciona herramientas para gestionar un restaurante.
    
    HERRAMIENTAS DISPONIBLES:
    - get_menu_products: Obtener el catálogo completo del menú
    - get_user_profile: Obtener perfil completo de usuario por teléfono
    - get_latest_order: Obtener la última orden de un cliente
    - get_system_status: Obtener el estado del sistema
    - create_user: Crear nuevo usuario
    - update_user: Actualizar datos de usuario existente
    - create_order: Crear nueva orden
    - add_item_to_order: Añadir productos a orden existente
    - remove_item_from_order: Eliminar productos de orden existente
    - update_item_in_order: Modificar productos en orden existente
    
    Todas las operaciones están integradas con el sistema de logging para auditoria.
    
    NOTA IMPORTANTE: Todas las herramientas relacionadas con usuarios requieren el número de teléfono (phone) como identificador único del usuario.
    """,
    host="0.0.0.0",
    port=8050 
)

def format_user_response(user: Any) -> str:
    """
    Formatea la respuesta de un usuario para una presentación legible.

    Args:
        user: Objeto usuario a formatear

    Returns:
        str: Representación formateada del usuario
    """
    if not user:
        return "Usuario no encontrado"

    # Formatear fechas de manera segura
    created_at = str(user.created_at) if user.created_at else "No disponible"
    updated_at = str(user.updated_at) if user.updated_at else "No disponible"

    return f"""Usuario ID: {user.id}
Nombre: {user.name}
Teléfono: {user.phone}
Email: {user.email}
Estado: {'Activo' if user.is_active else 'Inactivo'}
Creado: {created_at}
Actualizado: {updated_at}"""

#---------- TOOLS FOR INFORMATION RETRIEVAL ----------

@mcp.tool()
async def get_menu_products() -> str:
    """
    Obtiene el menú completo del restaurante con todos los productos disponibles.
    
    Esta herramienta permite a los LLMs acceder al catálogo completo de productos
    para facilitar la toma de pedidos y consultas sobre productos disponibles.
    
    Returns:
        str: Catálogo completo del menú formateado o mensaje de error
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles"
    
    try:
        products = product_service.get_all_products()
        if products:
            logger.info("mcp_menu_products_accessed")
            
            menu_text = "🍽️ MENÚ DEL RESTAURANTE\n\n"
            for product in products:
                menu_text += f"📋 {product.name}\n"
                menu_text += f"   Descripción: {product.description}\n"
                menu_text += f"   Precio: ${product.price:.2f}\n"
                menu_text += f"   Categoría: {product.category}\n"
                menu_text += f"   ID: {product.id}\n\n"
            
            menu_text += f"Total de productos: {len(products)}"
            return menu_text
        else:
            return "No hay productos disponibles en el menú"
    except Exception as e:
        logger.error("mcp_menu_products_error", error=str(e))
        return f"Error al obtener el menú: {str(e)}"

@mcp.tool()
async def get_user_profile(phone: str) -> str:
    """
    Obtiene el perfil completo de un usuario por su número de teléfono.
    
    Args:
        phone: Número de teléfono del usuario (mínimo 10 dígitos)
    
    Returns:
        str: Perfil del usuario formateado o mensaje de error
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles"
    
    try:
        if not phone.isdigit() or len(phone) < 10:
            return "Error: El teléfono debe contener solo números y tener al menos 10 dígitos"
        
        user = user_service.get_user_by_phone(phone)
        if user:
            logger.info("mcp_user_profile_accessed", phone=phone)
            return format_user_response(user)
        else:
            return f"Usuario con teléfono {phone} no encontrado"
    except Exception as e:
        logger.error("mcp_user_profile_error", error=str(e), phone=phone)
        return f"Error al obtener perfil de usuario: {str(e)}"

@mcp.tool()
async def get_latest_order(phone: str) -> str:
    """
    Obtiene la información de la última orden de un cliente.
    
    Args:
        phone: Número de teléfono del cliente (mínimo 10 dígitos)
    
    Returns:
        str: Información de la última orden formateada o mensaje de error
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles"
    
    try:
        if not phone.isdigit() or len(phone) < 10:
            return "Error: El teléfono debe contener solo números y tener al menos 10 dígitos"
        
        order = order_service.get_latest_order_by_phone(phone)
        if order:
            logger.info("mcp_latest_order_accessed", phone=phone)
            return format_order_response(order)
        else:
            return f"No se encontró ninguna orden para el teléfono {phone}"
    except Exception as e:
        logger.error("mcp_latest_order_error", error=str(e), phone=phone)
        return f"Error al obtener la última orden: {str(e)}"


#---------- TOOLS USER ----------

@mcp.tool()
async def create_user(user_data: UserCreateData) -> str:
    """
    Crea un nuevo usuario en el sistema del restaurante.

    Args:
        user_data (UserCreateData): Objeto con los datos del usuario. Campos requeridos:
            - name (str): Nombre completo del usuario. Ejemplo: "Juan Perez"
            - phone (str): Número de teléfono del usuario. Ejemplo: "1234567890"
            - email (str): Dirección de correo electrónico del usuario. Ejemplo: "juan@correo.com"
            - is_active (bool, opcional): Estado activo del usuario. Por defecto es True.

    Returns:
        str: Información del usuario creado o mensaje de error
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles. Verifica la configuración de la base de datos."
    try:
        user_dict = user_data.model_dump()
        # Validar el teléfono
        phone = user_dict.get("phone")
        if not phone or not phone.isdigit() or len(phone) < 10:
            return "Error: El teléfono debe contener solo números y tener al menos 10 dígitos."
        new_user = user_service.create_user(user_dict)
        logger.info("mcp_user_created", phone=phone, user_id=str(new_user.id))
        return format_user_response(new_user)
    except UserServiceError as e:
        logger.error("mcp_create_user_error", error=e.message)
        return f"Error al crear usuario: {e.message}"
    except Exception as e:
        logger.error("mcp_create_user_unexpected_error", error=str(e))
        return f"Error inesperado al crear usuario: {str(e)}"

@mcp.tool()
async def update_user(phone: str, user_data: UserUpdateData) -> str:
    """
    Actualiza los datos de un usuario existente usando su número de teléfono.

    Args:
        phone (str): Número de teléfono del usuario (mínimo 10 dígitos). Ejemplo: "1234567890"
        user_data (UserUpdateData): Objeto con los campos a actualizar (en inglés). Campos válidos:
            - name (str, opcional): Nuevo nombre. Ejemplo: "Juan Perez"
            - phone (str, opcional): Nuevo teléfono. Ejemplo: "123456789"
            - email (str, opcional): Nuevo email. Ejemplo: "juan@correo.com"
            - is_active (bool, opcional): Estado activo. Ejemplo: false
    
    Ejemplo de uso:
        {
            "phone": "1234567890",
            "user_data": {
                "name": "Juan Perez",
                "is_active": false
            }
        }

    Returns:
        str: Información del usuario actualizado o mensaje de error
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles. Verifica la configuración de la base de datos."
    
    try:
        # Validar el teléfono
        if not phone.isdigit() or len(phone) < 10:
            return "Error: El teléfono debe contener solo números y tener al menos 10 dígitos."

        # Convertir modelo Pydantic a diccionario, excluyendo valores None
        user_dict = user_data.model_dump(exclude_none=True)

        if not user_dict:
            return "No se proporcionaron datos para actualizar"

        # Actualizar usuario por teléfono
        updated_user = user_service.update_user_by_phone(phone, user_dict)

        if updated_user:
            logger.info("mcp_user_updated", phone=phone)
            return format_user_response(updated_user)
        else:
            return f"Usuario con teléfono {phone} no encontrado"

    except UserServiceError as e:
        logger.error("mcp_update_user_error", error=e.message, phone=phone)
        return f"Error al actualizar usuario: {e.message}"
    except Exception as e:
        logger.error("mcp_update_user_unexpected_error", error=str(e), phone=phone)
        return f"Error inesperado al actualizar usuario: {str(e)}"

def format_order_response(order: Any) -> str:
    """
    Formatea la respuesta de una orden para una presentación legible.

    Args:
        order: Objeto orden a formatear

    Returns:
        str: Representación formateada de la orden
    """
    if not order:
        return "Orden no encontrada"

    created_at = str(order.created_at) if hasattr(order, 'created_at') and order.created_at else "No disponible"
    updated_at = str(order.updated_at) if hasattr(order, 'updated_at') and order.updated_at else "No disponible"

    items_str = "\n".join([
        f"  - {item.product_name} (x{item.quantity}): ${item.subtotal:.2f}" for item in getattr(order, 'items', [])
    ])

    return f"""Orden ID: {order.id}\nCliente: {order.customer_name}\nTeléfono: {order.customer_phone}\nTotal: ${order.total_amount:.2f}\nEstado: {getattr(order, 'status', 'N/A')}\nDirección: {getattr(order, 'delivery_address', 'N/A')}\nNotas: {getattr(order, 'notes', '')}\nCreado: {created_at}\nActualizado: {updated_at}\nItems:\n{items_str}"""

#---------- TOOLS ORDER ----------

@mcp.tool()
async def create_order(order_data: OrderCreateData) -> str:
    """
    Crea una nueva orden en el sistema del restaurante.
    
    IMPORTANTE: El agente NO debe pasar el customer_id. Este se obtiene automáticamente usando el teléfono del cliente antes de crear la orden.

    Args:
        order_data (OrderCreateData): Objeto con los datos de la orden. Campos requeridos:
            - customer_name (str): Nombre del cliente. Ejemplo: "Juan Perez"
            - customer_phone (str): Teléfono del cliente. Ejemplo: "123456789"
            - delivery_address (str): Dirección de entrega. Ejemplo: "Calle 123"
            - notes (str, opcional): Notas adicionales. Ejemplo: "Sin cebolla"
            - items (list): Lista de productos. Cada item debe tener:
                - product_name (str): Nombre del producto
                - quantity (int): Cantidad
                - unit_price (float): Precio unitario
                - subtotal (float): Subtotal del item
                - notes (str, opcional): Notas del item
    
    Ejemplo de uso:
        {
            "order_data": {
                "customer_name": "Juan Perez",
                "customer_phone": "123456789",
                "delivery_address": "Calle 123",
                "notes": "Sin cebolla",
                "items": [
                    {
                        "product_name": "Pizza Margarita",
                        "quantity": 2,
                        "unit_price": 8.99,
                        "subtotal": 17.98,
                        "notes": "Extra queso"
                    }
                ]
            }
        }

    Returns:
        str: Información de la orden creada o mensaje de error
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles. Verifica la configuración de la base de datos."
    try:
        order_dict = order_data.model_dump()
        
        # Obtener y actualizar datos del cliente antes de crear la orden
        customer_phone = order_dict.get("customer_phone")
        customer_name = order_dict.get("customer_name")
        if not customer_phone:
            return "Error: El teléfono del cliente es obligatorio para crear la orden."
        update_data = {}
        if customer_name and customer_name.strip() != "Cliente Temporal":
            update_data["name"] = customer_name
        # Actualizar usuario por teléfono antes de crear la orden
        updated_user = user_service.update_user_by_phone(customer_phone, update_data)
        if not updated_user:
            return "Error: No se pudo encontrar o actualizar el usuario para crear la orden."
        logger.info("mcp_customer_updated_before_order", phone=customer_phone, name=customer_name, user_id=str(updated_user.id))
        
        # Convertir items de Pydantic a dict
        order_dict["items"] = [item.model_dump() for item in order_data.items]
        new_order = order_service.create_order(order_dict)
        logger.info("mcp_order_created", order_id=str(new_order.id))
        return format_order_response(new_order)
    except OrderServiceError as e:
        logger.error("mcp_create_order_error", error=e.message)
        return f"Error al crear orden: {e.message}"
    except Exception as e:
        logger.error("mcp_create_order_unexpected_error", error=str(e))
        return f"Error inesperado al crear orden: {str(e)}"

@mcp.tool()
async def add_item_to_order(customer_phone: str, item_data: OrderItemCreateData) -> str:
    """
    Añade un nuevo item a la última orden activa de un cliente.

    Esta herramienta permite al agente agregar productos adicionales al pedido más reciente del cliente (que no haya sido entregado ni cancelado). Es útil cuando el cliente desea añadir más productos a su orden actual.

    IMPORTANTE: Solo se pueden modificar órdenes en estado 'confirmed' o 'preparing'.

    Args:
        customer_phone (str): Teléfono del cliente. Ejemplo: "1234567890"
        item_data (OrderItemCreateData): Datos del nuevo item.

    Returns:
        str: Orden actualizada con el nuevo item o mensaje de error.
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles. Verifica la configuración de la base de datos."
    try:
        order = order_service.get_latest_order_by_phone(customer_phone)
        if not order:
            return f"No se encontró ninguna orden activa para el teléfono {customer_phone}"
        if order.status not in ["confirmed", "preparing", "CONFIRMED", "PREPARING"]:
            return f"La última orden está en estado '{order.status}' y no puede ser modificada."
        item_dict = item_data.model_dump()
        updated_order = order_service.add_item_to_order(order.id, item_dict)
        logger.info("mcp_item_added_to_order", order_id=order.id, product_name=item_dict.get("product_name"))
        return format_order_response(updated_order)
    except OrderServiceError as e:
        logger.error("mcp_add_item_to_order_error", error=e.message, phone=customer_phone)
        return f"Error al añadir item a la orden: {e.message}"
    except Exception as e:
        logger.error("mcp_add_item_to_order_unexpected_error", error=str(e), phone=customer_phone)
        return f"Error inesperado al añadir item: {str(e)}"

@mcp.tool()
async def remove_item_from_order(customer_phone: str, product_name: str) -> str:
    """
    Elimina un item específico de la última orden activa de un cliente.

    Args:
        customer_phone (str): Teléfono del cliente. Ejemplo: "1234567890"
        product_name (str): Nombre exacto del producto a eliminar.

    Returns:
        str: Orden actualizada sin el item eliminado o mensaje de error.
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles. Verifica la configuración de la base de datos."
    try:
        order = order_service.get_latest_order_by_phone(customer_phone)
        if not order:
            return f"No se encontró ninguna orden activa para el teléfono {customer_phone}"
        if order.status not in ["confirmed", "preparing", "CONFIRMED", "PREPARING"]:
            return f"La última orden está en estado '{order.status}' y no puede ser modificada."
        updated_order = order_service.remove_item_from_order(order.id, product_name)
        logger.info("mcp_item_removed_from_order", order_id=order.id, product_name=product_name)
        return format_order_response(updated_order)
    except OrderServiceError as e:
        logger.error("mcp_remove_item_from_order_error", error=e.message, phone=customer_phone)
        return f"Error al eliminar item de la orden: {e.message}"
    except Exception as e:
        logger.error("mcp_remove_item_from_order_unexpected_error", error=str(e), phone=customer_phone)
        return f"Error inesperado al eliminar item: {str(e)}"

@mcp.tool()
async def update_item_in_order(customer_phone: str, product_name: str, item_data: OrderItemUpdateData) -> str:
    """
    Actualiza un item específico en la última orden activa de un cliente.

    Args:
        customer_phone (str): Teléfono del cliente. Ejemplo: "1234567890"
        product_name (str): Nombre exacto del producto a actualizar.
        item_data (OrderItemUpdateData): Nuevos datos del item (todos opcionales).

    Returns:
        str: Orden actualizada con el item modificado o mensaje de error.
    """
    if not SERVICES_AVAILABLE:
        return "Error: Los servicios de base de datos no están disponibles. Verifica la configuración de la base de datos."
    try:
        order = order_service.get_latest_order_by_phone(customer_phone)
        if not order:
            return f"No se encontró ninguna orden activa para el teléfono {customer_phone}"
        if order.status not in ["confirmed", "preparing", "CONFIRMED", "PREPARING"]:
            return f"La última orden está en estado '{order.status}' y no puede ser modificada."
        item_dict = {k: v for k, v in item_data.model_dump().items() if v is not None}
        if not item_dict:
            return "Error: No se proporcionaron datos para actualizar"
        updated_order = order_service.update_item_in_order(order.id, product_name, item_dict)
        logger.info("mcp_item_updated_in_order", order_id=order.id, product_name=product_name)
        return format_order_response(updated_order)
    except OrderServiceError as e:
        logger.error("mcp_update_item_in_order_error", error=e.message, phone=customer_phone)
        return f"Error al actualizar item en la orden: {e.message}"
    except Exception as e:
        logger.error("mcp_update_item_in_order_unexpected_error", error=str(e), phone=customer_phone)
        return f"Error inesperado al actualizar item: {str(e)}"

# Run the server
if __name__ == "__main__":
    # Para usar Server-Sent Events (SSE)
    mcp.run(transport="stdio")
    
    # Para usar stdio (comunicación estándar)
    # mcp.run(transport="stdio")