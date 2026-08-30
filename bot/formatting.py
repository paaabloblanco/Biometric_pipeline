"""Utilidades de formato para mensajes de Telegram.

Telegram rechaza mensajes de más de 4096 caracteres, así que los análisis de
Gemini largos hay que trocearlos. El troceo intenta cortar por fronteras
"naturales" (párrafo > línea > espacio) y solo parte a lo bruto si un fragmento
sin espacios supera el límite.
"""

from bot.config import TELEGRAM_MAX_MESSAGE

# Fronteras por las que preferimos cortar, de más a menos deseable.
_SEPARATORS = ["\n\n", "\n", " "]


def split_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE) -> list[str]:
    """Trocea `text` en partes de longitud <= `limit`.

    - Corta por la mejor frontera disponible dentro del límite.
    - Cada parte se devuelve sin espacios en blanco sobrantes al principio/final.
    - Un `text` vacío o solo espacios devuelve `[]`.
    """
    if limit <= 0:
        raise ValueError("limit debe ser positivo")

    text = text.strip()
    if not text:
        return []

    parts: list[str] = []
    rest = text

    while len(rest) > limit:
        window = rest[:limit]
        cut = _best_cut(window)
        if cut is None:
            # Sin fronteras: corte duro en el límite.
            cut = limit
        chunk = rest[:cut].strip()
        if chunk:
            parts.append(chunk)
        rest = rest[cut:].lstrip()

    if rest:
        parts.append(rest)

    return parts


def _best_cut(window: str) -> int | None:
    """Índice donde cortar `window` según la mejor frontera. None si no hay."""
    for sep in _SEPARATORS:
        idx = window.rfind(sep)
        if idx > 0:
            return idx + len(sep)
    return None
