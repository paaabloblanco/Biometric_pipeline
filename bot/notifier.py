"""Envío puntual de mensajes a Telegram, independiente del proceso de polling.

Se usa desde scripts desatendidos (p. ej. daily_sync.py) para hacer el push
diario. Habla directamente con la API HTTP de Telegram vía httpx (síncrono),
así no arrastra python-telegram-bot ni un event loop.

Uso manual:
    python -m bot.notifier "mensaje de prueba"
    python -m bot.notifier "solo a este chat" 123456789
"""

import logging
import sys

import httpx

from bot.config import ALLOWED_CHAT_IDS, require_token
from bot.formatting import split_message

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(
    text: str,
    chat_ids: list[int] | None = None,
    parse_mode: str | None = "Markdown",
    timeout: float = 30.0,
) -> bool:
    """Envía `text` a los chats indicados (por defecto, toda la allowlist).

    Devuelve True si todos los envíos salieron bien. No lanza excepción:
    un fallo de Telegram no debe tumbar la sync diaria.
    """
    token = require_token()
    targets = chat_ids if chat_ids is not None else sorted(ALLOWED_CHAT_IDS)
    if not targets:
        log.warning("send_message: no hay destinatarios (allowlist vacía).")
        return False

    url = _API.format(token=token)
    ok = True
    with httpx.Client(timeout=timeout) as client:
        for chat_id in targets:
            for part in split_message(text):
                payload = {"chat_id": chat_id, "text": part}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                try:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 400 and parse_mode:
                        # Markdown mal formado en el texto de Gemini: reintento en plano.
                        resp = client.post(
                            url, json={"chat_id": chat_id, "text": part}
                        )
                    resp.raise_for_status()
                except Exception as exc:  # noqa: BLE001 - un chat fallido no debe cortar el resto
                    ok = False
                    log.error(
                        "Fallo enviando a chat %s (%s: %s)",
                        chat_id,
                        exc.__class__.__name__,
                        exc,
                    )
    return ok


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if not argv:
        print('Uso: python -m bot.notifier "<mensaje>" [chat_id]')
        return 1
    text = argv[0]
    chat_ids = [int(argv[1])] if len(argv) > 1 else None
    return 0 if send_message(text, chat_ids=chat_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
