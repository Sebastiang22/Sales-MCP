"""
Modelos para la gestión de productos de inventario comercial.

Este módulo define el modelo de producto para un contexto de
venta minorista/comercial, con soporte para SKU y stock.
"""

from sqlmodel import Field
from pydantic import validator
from decimal import Decimal
from .base import BaseModel


class Product(BaseModel, table=True):
    """
    Modelo para la tabla de productos de inventario comercial.
    
    Attributes:
        name: Nombre del producto
        description: Descripción del producto
        sku: Código único de referencia del producto
        price: Precio de venta al público (PVP)
        stock_quantity: Cantidad disponible en inventario
        is_active: Indicador de si el producto está activo
    """
    
    __tablename__ = "products"
    
    name: str = Field(
        min_length=2,
        max_length=100,
        index=True,
        description="Nombre del producto"
    )
    description: str = Field(
        min_length=10,
        max_length=500,
        description="Descripción detallada del producto"
    )
    sku: str = Field(
        min_length=3,
        max_length=50,
        index=True,
        unique=True,  # type: ignore[arg-type]
        description="Código único de referencia del producto"
    )
    price: float = Field(
        gt=0,
        description="Precio de venta al público (PVP)"
    )
    stock_quantity: int = Field(
        ge=0,
        default=0,
        description="Cantidad disponible en inventario"
    )
    is_active: bool = Field(
        default=True,
        description="Indica si el producto está activo para la venta"
    )

    @validator('price')
    def validate_price(cls, v):
        """
        Valida que el precio sea positivo y tenga máximo 2 decimales.
        
        Args:
            v: Valor del precio a validar
            
        Returns:
            float: Precio validado
            
        Raises:
            ValueError: Si el precio no es válido
        """
        if v <= 0:
            raise ValueError('El precio debe ser mayor a 0')
        
        # Verificar que tenga máximo 2 decimales
        decimal_price = Decimal(str(v))
        if decimal_price.as_tuple().exponent < -2:
            raise ValueError('El precio debe tener máximo 2 decimales')
        
        return float(decimal_price.quantize(Decimal('0.01')))

    @validator('name')
    def validate_name(cls, v):
        """
        Valida y normaliza el nombre del producto.
        
        Args:
            v: Valor del nombre a validar
            
        Returns:
            str: Nombre validado y normalizado
        """
        return v.strip().title()

    @validator('sku')
    def validate_sku(cls, v):
        """
        Valida y normaliza el SKU.
        
        Args:
            v: SKU a validar
        
        Returns:
            str: SKU normalizado
        """
        normalized = v.strip().upper()
        if len(normalized) < 3:
            raise ValueError('El SKU debe tener al menos 3 caracteres')
        return normalized


    def is_in_stock(self) -> bool:
        """
        Verifica si el producto tiene stock disponible.
        
        Returns:
            bool: True si hay stock (> 0), False en caso contrario
        """
        return self.stock_quantity > 0

    def is_orderable(self) -> bool:
        """
        Verifica si el producto se puede ordenar.
        
        Returns:
            bool: True si está activo y hay stock
        """
        if not self.is_active:
            return False
        return self.is_in_stock()

    def decrease_stock(self, quantity: int) -> None:
        """
        Disminuye el stock del producto de forma segura.
        
        Args:
            quantity: Cantidad a disminuir
        
        Raises:
            ValueError: Si la cantidad es inválida o no hay suficiente stock
        """
        if quantity <= 0:
            raise ValueError('La cantidad a disminuir debe ser mayor a 0')
        if quantity > self.stock_quantity:
            raise ValueError(f'Stock insuficiente. Disponible: {self.stock_quantity}, solicitado: {quantity}')
        self.stock_quantity -= quantity
        self.update_timestamp()

    def increase_stock(self, quantity: int) -> None:
        """
        Aumenta el stock del producto.
        
        Args:
            quantity: Cantidad a aumentar
        
        Raises:
            ValueError: Si la cantidad es inválida
        """
        if quantity <= 0:
            raise ValueError('La cantidad a aumentar debe ser mayor a 0')
        self.stock_quantity += quantity
        self.update_timestamp()

    def __repr__(self) -> str:
        """
        Representación string del producto.
        
        Returns:
            str: Representación del producto
        """
        return (
            f"<Product(name='{self.name}', sku='{self.sku}', price={self.price}, "
            f"stock={self.stock_quantity})>"
        )

    # Métodos relacionados con costos internos y dropshipping fueron removidos.

    # No se manejan impuestos en este modelo simplificado.

    # No se maneja backorder ni punto de reorden en este modelo simplificado.