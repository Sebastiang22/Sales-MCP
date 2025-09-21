# Prompts MCP - InsureGent

Este directorio contiene todas las herramientas de prompts MCP para InsureGent.

## Estructura de Archivos

```
prompts/
├── __init__.py              # Paquete principal que exporta las funciones de registro
├── prompt_tools.py          # Herramientas de prompts (@server.prompt)
└── README.md                # Este archivo
```

## Herramientas de Prompts Disponibles

### 1. greet_user
Genera prompts de saludo personalizados con diferentes estilos.

**Parámetros:**
- `name` (str): Nombre de la persona a saludar
- `style` (str): Estilo del saludo ("friendly", "formal", "casual")

**Ejemplo de uso:**
```python
@server.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    # Retorna un prompt personalizado para generar un saludo
```

### 2. generate_insurance_recommendation
Genera prompts para crear recomendaciones de seguros personalizadas.

**Parámetros:**
- `client_profile` (str): Perfil del cliente
- `needs` (str): Necesidades específicas del cliente
- `style` (str): Estilo de la recomendación ("professional", "friendly", "detailed")

### 3. explain_coverage
Genera prompts para explicar coberturas de seguros.

**Parámetros:**
- `coverage_type` (str): Tipo de cobertura a explicar
- `detail_level` (str): Nivel de detalle ("basic", "detailed", "comparative")

## Cómo Agregar Nuevos Prompts

1. **Agregar la función** en `prompt_tools.py`
2. **Usar el decorador** `@server.prompt()`
3. **Definir parámetros** claros y documentados
4. **Retornar un string** que sea el prompt generado
5. **Asegurar** que esté dentro de la función `register_prompt_tools`

### Ejemplo de Nuevo Prompt

```python
@server.prompt()
def explain_policy_terms(term: str, complexity: str = "simple") -> str:
    """Genera un prompt para explicar términos de póliza"""
    levels = {
        "simple": "de manera simple y fácil de entender",
        "detailed": "con explicación técnica detallada"
    }
    
    return f"""Explica el término de póliza '{term}' 
    {levels.get(complexity, levels['simple'])}, 
    incluyendo ejemplos prácticos."""
```

## Patrón de Registro

```python
def register_prompt_tools(server: FastMCP) -> None:
    """
    Registra las herramientas de prompts en el servidor MCP
    """
    # Aquí van todos los prompts con sus decoradores
    pass
```

## Ventajas de esta Organización

1. **Separación clara**: Los prompts están en su propia carpeta
2. **Fácil mantenimiento**: Todos los prompts están centralizados
3. **Escalabilidad**: Fácil agregar nuevos prompts sin afectar otras funcionalidades
4. **Reutilización**: Los prompts pueden ser usados en diferentes contextos
5. **Testabilidad**: Cada prompt puede ser probado independientemente
