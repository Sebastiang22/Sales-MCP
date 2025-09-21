"""
Herramientas de prompts MCP para InsureGent
"""

from mcp.server.fastmcp import FastMCP

def register_prompt_tools(server: FastMCP) -> None:
    """
    Registra las herramientas de prompts en el servidor MCP
    
    Args:
        server (FastMCP): Instancia del servidor MCP donde registrar las herramientas
    """
    
    @server.prompt()
    def greet_user(name: str, style: str = "friendly") -> str:
        """Genera un prompt de saludo"""
        styles = {
            "friendly": "Por favor escribe un saludo cálido y amigable",
            "formal": "Por favor escribe un saludo formal y profesional", 
            "casual": "Por favor escribe un saludo casual y relajado",
        }

        return f"{styles.get(style, styles['friendly'])} para alguien llamado {name}."

    @server.prompt()
    def generate_insurance_recommendation(client_profile: str, needs: str, style: str = "professional") -> str:
        """Genera un prompt para recomendar seguros basado en el perfil del cliente"""
        styles = {
            "professional": "Como asesor profesional de seguros",
            "friendly": "De manera amigable y cercana",
            "detailed": "Con explicación detallada y técnica"
        }
        
        return f"""{styles.get(style, styles['professional'])}, 
        analiza el siguiente perfil de cliente:
        {client_profile}
        
        Considerando estas necesidades específicas:
        {needs}
        
        Genera una recomendación personalizada de productos de seguros Sura."""

    @server.prompt()
    def explain_coverage(coverage_type: str, detail_level: str = "basic") -> str:
        """Genera un prompt para explicar coberturas de seguros"""
        levels = {
            "basic": "de manera simple y fácil de entender",
            "detailed": "con detalles técnicos y casos de uso",
            "comparative": "comparando con otras opciones similares"
        }
        
        return f"""Explica la cobertura de seguro '{coverage_type}' 
        {levels.get(detail_level, levels['basic'])}, 
        incluyendo beneficios principales y limitaciones."""
