"""
Herramientas MCP para envío de medios por WhatsApp

Registra tres tools:
- send_whatsapp_image: Envía una imagen por WhatsApp
- send_whatsapp_audio: Envía un audio por WhatsApp (opcional PTT)
- send_whatsapp_video: Envía un video por WhatsApp
"""

from typing import Dict, Any, Optional

from mcp.server.fastmcp import FastMCP

from services import whatsapp_service, WhatsAppServiceError


def register_whatsapp_tools(server: FastMCP) -> None:
    """Registra tools para enviar medios por WhatsApp."""
    # TODO Registrar identificador de imagen y session_id para no repetir imágenes
    @server.tool()
    async def send_whatsapp_image(phone: str, image_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía una imagen por WhatsApp a partir de una URL pública.

        Args:
            phone (str): Número del destinatario en formato internacional sin símbolos
            image_url (str): URL pública de la imagen a enviar
            port (int): Puerto del servidor WhatsApp a usar (por defecto 3001)
            caption (str, opcional): Texto descriptivo para acompañar la imagen (opcional)

        Returns:
            Dict[str, Any]: Respuesta del servidor con estado y datos

        Ejemplo de payload:
            {
                "phone": "+573204259649",
                "imageUrl": "https://drive.google.com/file/d/...",
                "caption": "¡Imagen de prueba!" # opcional
            }
        """
        try:
            # Validar número de teléfono
            if not phone.startswith("+"):
                phone = f"+{phone}"

            # Enviar imagen
            result = whatsapp_service.send_image(
                phone=phone,
                image_url=image_url,
                port=port,
                caption=caption
            )
            return {"status": "success", "data": result}
        except WhatsAppServiceError as e:
            return {"status": "error", "message": e.message, "status_code": e.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e), "status_code": 500}

    # TODO Registrar identificador de audio y session_id para no repetir audios, y que no se repitan
    @server.tool()
    async def send_whatsapp_audio(phone: str, audio_url: str, port: int = 3001, session: str = "Demo") -> Dict[str, Any]:
        """
        Envía un audio por WhatsApp a partir de una URL pública. 
        Los audios enviados como notas de voz no incluyen caption.

        Args:
            phone (str): Número del destinatario en formato internacional sin símbolos
            audio_url (str): URL pública del audio (mp3/ogg)
            port (int): Puerto del servidor WhatsApp a usar (por defecto 3001)
            session (str): Identificador de la sesión (por defecto "Demo")

        Returns:
            Dict[str, Any]: Respuesta del servidor con estado y datos
        """
        try:
            result = whatsapp_service.send_audio(
                phone=phone,
                audio_url=audio_url,
                port=port,
                session=session
            )
            return {"status": "success", "data": result}
        except WhatsAppServiceError as e:
            return {"status": "error", "message": e.message, "status_code": e.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e), "status_code": 500}

    # TODO Registrar identificador de video y session_id para no repetir videos
    @server.tool()
    async def send_whatsapp_video(phone: str, video_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un video por WhatsApp a partir de una URL pública.

        Args:
            phone (str): Número del destinatario en formato internacional sin símbolos
            video_url (str): URL pública del video (mp4/contenido compatible)
            port (int): Puerto del servidor WhatsApp a usar (por defecto 3001)
            caption (str, opcional): Texto descriptivo opcional

        Returns:
            Dict[str, Any]: Respuesta del servidor con estado y datos
        """
        try:
            result = whatsapp_service.send_video(
                phone=phone,
                video_url=video_url,
                port=port,
                caption=caption
            )
            return {"status": "success", "data": result}
        except WhatsAppServiceError as e:
            return {"status": "error", "message": e.message, "status_code": e.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e), "status_code": 500}


    @server.tool()
    async def send_whatsapp_pdf(phone: str, pdf_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un documento PDF por WhatsApp a partir de una URL pública.

        Args:
            phone (str): Número del destinatario en formato internacional sin símbolos
            pdf_url (str): URL pública del documento PDF a enviar
            port (int): Puerto del servidor WhatsApp a usar (por defecto 3001)
            caption (str, opcional): Texto descriptivo que acompaña el documento

        Returns:
            Dict[str, Any]: Respuesta del servidor con estado y datos
        """
        try:
            if not phone.startswith("+"):
                phone = f"+{phone}"

            result = whatsapp_service.send_pdf(
                phone=phone,
                pdf_url=pdf_url,
                port=port,
                caption=caption
            )
            return {"status": "success", "data": result}
        except WhatsAppServiceError as e:
            return {"status": "error", "message": e.message, "status_code": e.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e), "status_code": 500}


