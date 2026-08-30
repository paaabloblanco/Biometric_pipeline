"""Configuración del bot de Telegram: carga de .env, allowlist y arranque de Django.

Todas las variables se leen de la raíz del repo (`.env`). Ver `.env.example`.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

# La consola de Windows por defecto usa cp1252; los textos llevan emojis/acentos.
# stdout puede no soportar reconfigure() si ha sido reemplazado (p.ej. al
# redirigir la salida a un proceso que no expone un TextIOWrapper real).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    log.debug("No se pudo forzar UTF-8 en stdout; puede que fallen emojis en consola.")

load_dotenv(BASE_DIR / ".env")


def _parse_chat_ids(raw: str | None) -> frozenset[int]:
    """'123, 456' -> {123, 456}. Vacío o None -> conjunto vacío."""
    if not raw:
        return frozenset()
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise ValueError(
                f"TELEGRAM_ALLOWED_CHAT_IDS contiene un valor no numérico: {part!r}"
            )
    return frozenset(ids)


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_IDS = _parse_chat_ids(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS"))
DEFAULT_INSTRUCTION = os.getenv(
    "TELEGRAM_DEFAULT_INSTRUCTION",
    "Dame el análisis de recuperación del día.",
)

# Límite duro de la API de Telegram por mensaje.
TELEGRAM_MAX_MESSAGE = 4096


def require_token() -> str:
    """Devuelve el token o aborta con un mensaje claro si falta."""
    if not BOT_TOKEN:
        raise RuntimeError(
            "Falta TELEGRAM_BOT_TOKEN en .env. Créalo con @BotFather y añádelo al .env."
        )
    return BOT_TOKEN


def is_authorized(chat_id: int) -> bool:
    return chat_id in ALLOWED_CHAT_IDS


def setup_django() -> None:
    """Inicializa Django para poder importar modelos y servicios.

    Mismo patrón que health_ai/pruebas.py. Idempotente.
    """
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django

    django.setup()  # idempotente: no-op si ya está inicializado (ver apps.registry.populate)
