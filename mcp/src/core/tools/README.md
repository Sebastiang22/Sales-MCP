# Herramientas MCP - InsureGent

Este directorio contiene las herramientas de búsqueda y utilidad MCP. Los prompts y recursos se han movido a carpetas independientes para una mejor organización.

## Estructura de Archivos

```
tools/
├── __init__.py              # Paquete principal que exporta las funciones de registro
├── search_tools.py          # Herramientas de búsqueda (@server.tool)
├── utility_tools.py         # Herramientas de utilidad adicionales
├── config.py                # Configuración centralizada
└── README.md                # Este archivo
```

## Categorías de Herramientas

### 1. Search Tools (`search_tools.py`)
- **search**: Búsqueda general en la base de conocimientos
- **search_by_category**: Búsqueda filtrada por categoría

### 2. Utility Tools (`utility_tools.py`)
- **get_server_info**: Información del servidor MCP
- **health_check**: Verificación de estado del servidor

## Otras Categorías (en carpetas independientes)

### 3. Prompt Tools (`prompts/prompt_tools.py`)
- **greet_user**: Genera prompts de saludo personalizados
- **generate_insurance_recommendation**: Genera prompts para recomendaciones de seguros
- **explain_coverage**: Genera prompts para explicar coberturas

### 4. Resource Tools (`resources/resource_tools.py`)
- **get_greeting**: Recurso para saludos personalizados
- **get_coverage_details**: Detalles de coberturas específicas
- **get_category_faqs**: Preguntas frecuentes por categoría
- **get_insurance_products**: Lista de productos por categoría

## Cómo Agregar Nuevas Herramientas

### Para Tools (@server.tool)
1. Agrega la función en el archivo correspondiente
2. Usa el decorador `@server.tool()`
3. Asegúrate de que esté dentro de la función de registro

### Para Prompts (@server.prompt)
1. Agrega la función en `prompts/prompt_tools.py`
2. Usa el decorador `@server.prompt()`
3. La función debe retornar un string

### Para Resources (@server.resource)
1. Agrega la función en `resources/resource_tools.py`
2. Usa el decorador `@server.resource("uri://{param}")`
3. Define el patrón URI apropiado

## Patrón de Registro

Cada archivo de herramientas tiene una función de registro que se llama desde `server.py`:

```python
def register_[category]_tools(server: FastMCP) -> None:
    # Aquí van las herramientas con sus decoradores
    pass
```

## Ventajas de esta Estructura

1. **Separación de responsabilidades**: Cada archivo maneja un tipo específico de herramienta
2. **Mantenibilidad**: Fácil encontrar y modificar herramientas específicas
3. **Escalabilidad**: Fácil agregar nuevas herramientas sin contaminar el archivo principal
4. **Testabilidad**: Cada módulo puede ser probado independientemente
5. **Reutilización**: Las funciones de registro pueden ser usadas en otros servidores MCP

## Ejemplo de Uso

```python
# En server.py
from tools import (
    register_search_tools,
    register_utility_tools
)
from prompts import register_prompt_tools
from resources import register_resource_tools

# Registrar todas las herramientas
register_search_tools(server)
register_prompt_tools(server)
register_resource_tools(server)
register_utility_tools(server)
```
