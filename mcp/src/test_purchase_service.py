"""
Script simple para probar la inserción de una compra usando PurchaseService.

Ajusta los valores de `store_id` y de los campos del cliente según tu entorno.
Ejecuta: `python -m src.test_purchase_service` desde la raíz del proyecto (si tu PYTHONPATH lo permite)
o `python mcp/src/test_purchase_service.py` según tu estructura local.
"""

from __future__ import annotations

from typing import Any, Dict, List
import json

from services import purchase_service, PurchaseServiceError


def run_test_insert() -> None:
    """Ejecuta una inserción de prueba en la tabla mapeada por store_id.

    Inserta un registro de compra con un conjunto de productos de ejemplo
    y muestra por consola la respuesta del servicio.
    """
    # Valores de ejemplo: ajusta según tu mapeo en PurchaseService.STORE_TABLE_MAP
    store_id: str = "4f22df54942898f1"
    client_phone: str = "+573204259649"
    client_full_name: str = "Juan Pérez"
    client_document: str = "1234567890"
    client_address: str = "Calle 123 #45-67"
    client_city: str = "Bogotá"
    client_email: str = "juan.perez@example.com"
    products: List[Dict[str, Any]] = [
        {"product_id": "hash_producto_1", "quantity": 2, "unit_price": 150000.0},
        {"product_id": "hash_producto_2", "quantity": 1, "unit_price": 299900.0},
    ]

    # total_amount será calculado por la tool en entorno MCP, pero aquí
    # lo enviamos directamente al servicio, consistente con API del servicio.
    total_amount: float = sum(float(p["unit_price"]) * int(p["quantity"]) for p in products)

    try:
        result = purchase_service.save_purchase(
            store_id=store_id,
            purchase={
                "total_amount": total_amount,
                "client_phone": client_phone,
                "client_full_name": client_full_name,
                "client_document": client_document,
                "client_address": client_address,
                "client_city": client_city,
                "client_email": client_email,
                "products": products,
            },
        )
        print("Insert OK:\n" + json.dumps(result, ensure_ascii=False, indent=2))
    except PurchaseServiceError as e:
        print(f"Error de servicio ({e.status_code}): {e.message}")
    except Exception as e:
        print(f"Error inesperado: {str(e)}")


if __name__ == "__main__":
    run_test_insert()


