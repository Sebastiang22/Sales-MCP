"""
Modelo de ventas por producto.

Este módulo define la tabla para registrar ventas por producto,
incluyendo la dirección del cliente y datos de precio/cantidad.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from sqlmodel import Field, Column, JSON
from pydantic import validator

from .base import BaseModel


class ProductSale(BaseModel, table=True):
    """
    Modelo para la tabla de ventas por producto.

    Attributes:
        customer_phone: Teléfono del cliente
        total_amount: Total de la venta
        customer_address: Dirección del cliente
        products: Información JSON de los productos vendidos
    """

    __tablename__ = "ventas_mauricio"

    customer_phone: str = Field(
        description="Teléfono del cliente"
    )
    total_amount: float = Field(
        description="Total de la venta"
    )
    customer_address: str = Field(
        description="Dirección del cliente"
    )
    products: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Información JSON de los productos vendidos"
    )

    @validator('total_amount')
    def validate_price_fields(cls, v):
        """
        Valida que el campo de precio tenga máximo 2 decimales.

        Args:
            v: Valor monetario a validar

        Returns:
            float: Valor con dos decimales
        """
        decimal_value = Decimal(str(v))
        if decimal_value.as_tuple().exponent < -2:
            raise ValueError('Los valores monetarios deben tener máximo 2 decimales')
        return float(decimal_value.quantize(Decimal('0.01')))

    def __repr__(self) -> str:
        """
        Representación string de la venta por producto.

        Returns:
            str: Representación de la venta
        """
        return (
            f"<ProductSale(id={self.id}, phone={self.customer_phone}, "
            f"total={self.total_amount}, address={self.customer_address[:20]}...)>"
        )


