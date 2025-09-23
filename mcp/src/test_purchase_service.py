"""
Script simple para probar la inserción de una compra usando PurchaseService.

Ajusta los valores de `store_id`, `customer_address` y `products` según tu entorno.
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
    customer_phone: str = "+573204259649"
    customer_address: str = "Calle 123 #45-67"
    products: List[Dict[str, Any]] = [
        {"product_id": 1, "quantity": 2},
        {"product_id": 5, "quantity": 1},
    ]

    # Para la prueba, asignamos un total_amount arbitrario
    # (el servicio no valida el cálculo versus los productos)
    total_amount: float = 12345.67

    try:
        result = purchase_service.save_purchase(
            store_id=store_id,
            purchase={
                "total_amount": total_amount,
                "customer_phone": customer_phone,
                "customer_address": customer_address,
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


