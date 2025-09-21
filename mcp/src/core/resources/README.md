# Recursos MCP - InsureGent

Este directorio contiene todas las herramientas de recursos MCP para InsureGent.

## Estructura de Archivos

```
resources/
├── __init__.py              # Paquete principal que exporta las funciones de registro
├── resource_tools.py        # Herramientas de recursos (@server.resource)
└── README.md                # Este archivo
```

## Herramientas de Recursos Disponibles

### 1. get_greeting
Recurso para obtener saludos personalizados.

**URI Pattern:** `greeting://{name}`
**Parámetros:**
- `name` (str): Nombre de la persona a saludar

**Ejemplo de uso:**
```python
@server.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    return f"Hola, {name}!"
```

### 2. get_coverage_details
Recurso para obtener detalles específicos de coberturas.

**URI Pattern:** `coverage://{insurance_type}/{coverage_id}`
**Parámetros:**
- `insurance_type` (str): Tipo de seguro
- `coverage_id` (str): ID de la cobertura

### 3. get_category_faqs
Recurso para obtener preguntas frecuentes por categoría.

**URI Pattern:** `faq://{category}`
**Parámetros:**
- `category` (str): Categoría de preguntas frecuentes

### 4. get_insurance_products
Recurso para obtener lista de productos por categoría.

**URI Pattern:** `products://{category}`
**Parámetros:**
- `category` (str): Categoría de productos

## Cómo Agregar Nuevos Recursos

1. **Agregar la función** en `resource_tools.py`
2. **Usar el decorador** `@server.resource("uri://{param}")`
3. **Definir el patrón URI** apropiado con parámetros
4. **Implementar la lógica** para obtener los datos
5. **Asegurar** que esté dentro de la función `register_resource_tools`

### Ejemplo de Nuevo Recurso

```python
@server.resource("policy://{policy_type}/{policy_id}")
def get_policy_details(policy_type: str, policy_id: str) -> dict:
    """Obtiene detalles de una póliza específica"""
    return {
        "policy_type": policy_type,
        "policy_id": policy_id,
        "details": "Detalles de la póliza...",
        "status": "active"
    }
```

## Patrones URI Recomendados

### Estructura General
```
scheme://{param1}/{param2}/{param3}
```

### Ejemplos de Esquemas
- `greeting://{name}` - Saludos personalizados
- `coverage://{type}/{id}` - Detalles de cobertura
- `faq://{category}` - Preguntas frecuentes
- `products://{category}` - Productos por categoría
- `policy://{type}/{id}` - Detalles de póliza
- `claim://{status}/{id}` - Estados de reclamos

## Patrón de Registro

```python
def register_resource_tools(server: FastMCP) -> None:
    """
    Registra las herramientas de recursos en el servidor MCP
    """
    # Aquí van todos los recursos con sus decoradores
    pass
```

## Ventajas de esta Organización

1. **Separación clara**: Los recursos están en su propia carpeta
2. **Fácil mantenimiento**: Todos los recursos están centralizados
3. **Escalabilidad**: Fácil agregar nuevos recursos sin afectar otras funcionalidades
4. **Reutilización**: Los recursos pueden ser accedidos desde diferentes contextos
5. **Testabilidad**: Cada recurso puede ser probado independientemente
6. **URI patterns**: Estructura clara y consistente para acceder a los recursos

## Consideraciones de Diseño

- **URIs consistentes**: Mantener un patrón consistente para todos los recursos
- **Parámetros claros**: Usar nombres de parámetros descriptivos
- **Respuestas estructuradas**: Retornar datos en formatos consistentes
- **Manejo de errores**: Implementar manejo apropiado de casos de error
- **Documentación**: Mantener docstrings claros para cada recurso
