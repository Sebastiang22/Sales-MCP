"""
Servicio mínimo para envío de medios por WhatsApp (stub).

Este módulo define las funciones necesarias consumidas por las tools de WhatsApp.
Las implementaciones realizan validaciones básicas y retornan estructuras simples,
levantando `WhatsAppServiceError` en casos esperables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


class WhatsAppServiceError(Exception):
    """Error controlado para el servicio de WhatsApp.

    Contiene un mensaje y un código de estado HTTP para propagar a las tools.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Inicializa el error con mensaje y código de estado.

        Args:
            message (str): Descripción del error para el cliente.
            status_code (int): Código HTTP asociado al error.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _validate_public_url(url: str) -> None:
    """Valida que la URL sea no vacía y parezca pública.

    Args:
        url (str): URL a validar.

    Raises:
        WhatsAppServiceError: Si la URL es inválida.
    """
    if not url or not isinstance(url, str):
        raise WhatsAppServiceError("Invalid URL", status_code=422)
    if url.startswith("file:") or url.startswith("data:"):
        raise WhatsAppServiceError("Unsupported URL scheme", status_code=415)


def _normalize_phone(phone: str) -> str:
    """Normaliza el número a formato internacional con prefijo '+'.

    Args:
        phone (str): Número telefónico ingresado por el usuario.

    Returns:
        str: Número normalizado con '+' al inicio.
    """
    if not phone:
        raise WhatsAppServiceError("Phone number is required", status_code=422)
    return phone if phone.startswith("+") else f"+{phone}"


def send_image(phone: str, image_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
    """Envía una imagen a través del servicio de WhatsApp (stub).

    Realiza validaciones y retorna una respuesta simulada de éxito.
    """
    normalized_phone = _normalize_phone(phone)
    _validate_public_url(image_url)
    return {
        "phone": normalized_phone,
        "port": port,
        "type": "image",
        "caption": caption,
        "url": image_url,
        "delivered": True,
    }


def send_audio(phone: str, audio_url: str, port: int = 3001, session: str = "Demo") -> Dict[str, Any]:
    """Envía un audio a través del servicio de WhatsApp (stub)."""
    normalized_phone = _normalize_phone(phone)
    _validate_public_url(audio_url)
    return {
        "phone": normalized_phone,
        "port": port,
        "type": "audio",
        "session": session,
        "url": audio_url,
        "delivered": True,
    }


def send_video(phone: str, video_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
    """Envía un video a través del servicio de WhatsApp (stub)."""
    normalized_phone = _normalize_phone(phone)
    _validate_public_url(video_url)
    return {
        "phone": normalized_phone,
        "port": port,
        "type": "video",
        "caption": caption,
        "url": video_url,
        "delivered": True,
    }


def send_pdf(phone: str, pdf_url: str, port: int = 3001, caption: Optional[str] = None) -> Dict[str, Any]:
    """Envía un documento PDF a través del servicio de WhatsApp (stub)."""
    normalized_phone = _normalize_phone(phone)
    _validate_public_url(pdf_url)
    return {
        "phone": normalized_phone,
        "port": port,
        "type": "document",
        "mime": "application/pdf",
        "caption": caption,
        "url": pdf_url,
        "delivered": True,
    }


__all__ = [
    "WhatsAppServiceError",
    "send_image",
    "send_audio",
    "send_video",
    "send_pdf",
]



