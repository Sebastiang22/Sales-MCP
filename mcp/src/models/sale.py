"""
Modelo de ventas por producto.

Este módulo define la tabla para registrar ventas por producto,
incluyendo la dirección del cliente y datos de precio/cantidad.
"""

from decimal import Decimal
from sqlmodel import Field
from pydantic import validator

from .base import BaseModel


class ProductSale(BaseModel, table=True):
    """
    Modelo para la tabla de ventas por producto.

    Attributes:
        product_id: ID del producto vendido (FK a products.id)
        quantity: Cantidad vendida
        unit_price: Precio unitario al momento de la venta
        total_amount: Total de la venta (quantity * unit_price)
        customer_address: Dirección del cliente
    """

    __tablename__ = "product_sales"

    product_id: int = Field(
        foreign_key="products.id",
        index=True,
        description="ID del producto vendido"
    )
    quantity: int = Field(
        gt=0,
        description="Cantidad vendida"
    )
    unit_price: float = Field(
        gt=0,
        description="Precio unitario al momento de la venta"
    )
    total_amount: float = Field(
        ge=0,
        description="Total de la venta"
    )
    customer_address: str = Field(
        min_length=5,
        max_length=255,
        description="Dirección del cliente"
    )

    @validator('unit_price', 'total_amount')
    def validate_price_fields(cls, v):
        """
        Valida que los campos de precio tengan máximo 2 decimales.

        Args:
            v: Valor monetario a validar

        Returns:
            float: Valor con dos decimales
        """
        decimal_value = Decimal(str(v))
        if decimal_value.as_tuple().exponent < -2:
            raise ValueError('Los valores monetarios deben tener máximo 2 decimales')
        return float(decimal_value.quantize(Decimal('0.01')))

    def calculate_total(self) -> float:
        """
        Calcula el total de la venta (quantity * unit_price).

        Returns:
            float: Total calculado de la venta
        """
        total = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        return float(total.quantize(Decimal('0.01')))

    def update_total(self) -> None:
        """
        Actualiza el campo total_amount con el cálculo actual.
        """
        self.total_amount = self.calculate_total()
        self.update_timestamp()

    def __repr__(self) -> str:
        """
        Representación string de la venta por producto.

        Returns:
            str: Representación de la venta
        """
        return (
            f"<ProductSale(product_id={self.product_id}, quantity={self.quantity}, "
            f"total={self.total_amount})>"
        )


