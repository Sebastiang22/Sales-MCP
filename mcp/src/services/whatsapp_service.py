"""
Servicio para la interacción con WhatsApp.

Este módulo proporciona operaciones para enviar mensajes, imágenes,
audios y videos a través del servidor de WhatsApp.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging
import os
import secrets

import requests
from core.config import settings

logger = logging.getLogger("colombiang-mcp.whatsapp")
logger.setLevel(logging.INFO)


class WhatsAppServiceError(Exception):
    """Excepción de alto nivel para errores del servicio de WhatsApp."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


@dataclass
class WhatsAppConfig:
    """Configuración del servicio de WhatsApp cargada desde variables de entorno."""

    base_url: str
    default_timeout_seconds: float = 10.0
    long_timeout_seconds: float = 60.0
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "WhatsAppConfig":
        """Construye la configuración usando la lógica centralizada de core.config.

        Intenta obtener `BAILEYS_SERVER_URL` desde `core.config.settings` y,
        si no está definido, recurre a variables de entorno como respaldo.
        """
        try:
            # Importación perezosa para respetar el orden de carga del proyecto
              # type: ignore
            base_url = settings.BAILEYS_SERVER_URL or os.getenv("BAILEYS_SERVER_URL", "http://localhost")
        except Exception:
            # Respaldo si no es posible importar settings (p. ej., durante pruebas unitarias)
            base_url = os.getenv("BAILEYS_SERVER_URL", "http://localhost")

        api_key = os.getenv("WHATSAPP_API_KEY")
        default_timeout = float(os.getenv("WHATSAPP_TIMEOUT_SECONDS", "10"))
        long_timeout = float(os.getenv("WHATSAPP_LONG_TIMEOUT_SECONDS", "60"))
        return cls(
            base_url=base_url,
            default_timeout_seconds=default_timeout,
            long_timeout_seconds=long_timeout,
            api_key=api_key,
        )


def _normalize_phone(phone: str) -> str:
    """Normaliza el número a formato internacional con prefijo '+'."""
    if not phone:
        raise WhatsAppServiceError("Phone number is required", status_code=422)
    return phone if phone.startswith("+") else f"+{phone}"


def _validate_public_url(url: str) -> None:
    """Valida que la URL sea pública y soportada."""
    if not url or not isinstance(url, str):
        raise WhatsAppServiceError("Invalid URL", status_code=422)
    if url.startswith("file:") or url.startswith("data:"):
        raise WhatsAppServiceError("Unsupported URL scheme", status_code=415)


class WhatsAppService:
    """Servicio para gestionar operaciones de WhatsApp."""

    def __init__(self, config: Optional[WhatsAppConfig] = None):
        """Inicializa el servicio con configuración desde variables de entorno.

        Args:
            config: Configuración opcional; si no se pasa, se carga desde .env
        """
        self.config = config or WhatsAppConfig.from_env()
        self.base_url = self.config.base_url.rstrip("/")
        self.session = requests.Session()
        self.default_timeout = self.config.default_timeout_seconds
        self.long_timeout = self.config.long_timeout_seconds

        # Header de autenticación opcional
        self._auth_headers: Dict[str, str] = {}
        if self.config.api_key:
            self._auth_headers["Authorization"] = f"Bearer {self.config.api_key}"

    def _post_json(self, path: str, payload: Dict[str, Any], port: int = 3001, *, long: bool = False) -> Dict[str, Any]:
        """Realiza POST JSON con control de timeout, autenticación y manejo de errores."""
        try:
            url_with_port = f"{self.base_url}:{port}"
            response = self.session.post(
                f"{url_with_port}{path}",
                json=payload,
                headers=self._auth_headers or None,
                timeout=self.long_timeout if long else self.default_timeout,
            )
            if response.status_code == 200:
                return response.json()
            if response.headers.get("content-type", "").startswith("application/json"):
                error = response.json().get("message", response.text)
            else:
                error = response.text
            raise WhatsAppServiceError(f"HTTP {response.status_code}: {error}", status_code=response.status_code)
        except requests.exceptions.Timeout:
            raise WhatsAppServiceError("Timeout en solicitud a WhatsApp", status_code=408)
        except requests.exceptions.ConnectionError:
            raise WhatsAppServiceError("No se puede conectar con el servidor de WhatsApp", status_code=503)
        except requests.exceptions.RequestException as e:
            raise WhatsAppServiceError(f"Error de red: {str(e)}", status_code=500)

    def check_whatsapp_status(self) -> Dict[str, Any]:
        """Verifica estado del servidor de WhatsApp."""
        try:
            url_with_port = f"{self.base_url}:3001"
            response = self.session.get(f"{url_with_port}/api/status", headers=self._auth_headers or None, timeout=5)
            if response.status_code == 200:
                return response.json()
            raise WhatsAppServiceError(f"HTTP {response.status_code}: {response.text}", status_code=response.status_code)
        except requests.exceptions.Timeout:
            raise WhatsAppServiceError("Timeout al verificar estado de WhatsApp", status_code=408)
        except requests.exceptions.ConnectionError:
            raise WhatsAppServiceError("No se puede conectar con el servidor de WhatsApp", status_code=503)

    def send_image(self, phone: str, image_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía una imagen por WhatsApp a partir de una URL pública.

        Args:
            phone: Número del destinatario
            image_url: URL pública de la imagen
            port: Puerto del servidor WhatsApp a usar (por defecto 3001)
            caption: Texto opcional
        """
        phone = _normalize_phone(phone)
        _validate_public_url(image_url)
        logger.info("sending_image", extra={"phone": phone, "image_url": image_url, "port": port, "has_caption": caption is not None})
        payload: Dict[str, Any] = {"phone": phone, "imageUrl": image_url}
        if caption:
            payload["caption"] = caption
        return self._post_json("/api/send-image-url", payload, port=port)

    def send_audio(self, phone: str, audio_url: str, port: int = 3001) -> Dict[str, Any]:
        """
        Envía un audio por WhatsApp desde una URL pública.

        Args:
            phone: Número del destinatario
            audio_url: URL pública del audio (mp3/ogg)
            port: Puerto del servidor WhatsApp a usar (por defecto 3001)
        """
        phone = _normalize_phone(phone)
        _validate_public_url(audio_url)
        logger.info("sending_audio", extra={"phone": phone, "audio_url": audio_url, "port": port})
        payload: Dict[str, Any] = {"phone": phone, "audioUrl": audio_url}
        
        return self._post_json("/api/send-audio-url", payload, port=port)

    def send_video(self, phone: str, video_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un video por WhatsApp desde una URL pública.

        Args:
            phone: Número del destinatario
            video_url: URL pública del video
            port: Puerto del servidor WhatsApp a usar (por defecto 3001)
            caption: Texto opcional
        """
        phone = _normalize_phone(phone)
        _validate_public_url(video_url)
        logger.info("sending_video", extra={"phone": phone, "video_url": video_url, "port": port})
        payload: Dict[str, Any] = {"phone": phone, "videoUrl": video_url}
        if caption:
            payload["caption"] = caption
        return self._post_json("/api/send-video-url", payload, port=port, long=True)

    def _generate_hashed_filename(self, base_filename: str = "document.pdf") -> str:
        """
        Genera un nombre de archivo con un hash aleatorio y extensión .pdf.

        Args:
            base_filename: Nombre base del archivo (se ignorará su extensión)

        Returns:
            Nombre de archivo con hash aleatorio y extensión .pdf, ej: document-1a2b3c4d.pdf
        """
        name_without_ext = base_filename.rsplit(".", 1)[0] if "." in base_filename else base_filename
        random_hash = secrets.token_hex(4)
        return f"{name_without_ext}-{random_hash}.pdf"

    def send_pdf(self, phone: str, pdf_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía un documento PDF por WhatsApp a partir de una URL pública.

        Args:
            phone: Número del destinatario
            pdf_url: URL pública del documento PDF
            port: Puerto del servidor WhatsApp a usar (por defecto 3001)
            caption: Texto opcional (no enviado; reservado para compatibilidad)
        """
        phone = _normalize_phone(phone)
        _validate_public_url(pdf_url)
        logger.info("sending_pdf", extra={"phone": phone, "pdf_url": pdf_url, "port": port})
        file_name = self._generate_hashed_filename("document.pdf")
        payload: Dict[str, Any] = {"phone": phone, "pdfUrl": pdf_url, "fileName": file_name}
        if caption:
            payload["caption"] = caption
        return self._post_json("/api/send-pdf-url", payload, port=port)


# Instancia global del servicio
whatsapp_service = WhatsAppService()


__all__ = [
    "WhatsAppServiceError",
    "WhatsAppConfig",
    "WhatsAppService",
    "whatsapp_service",
]

