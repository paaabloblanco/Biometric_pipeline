"""Punto de entrada del bot de Telegram (modo long polling).

Uso:
    python -m bot.main

Pensado para correr como proceso permanente (tarea programada de Windows con
reinicio automático, o NSSM como servicio). Un solo proceso a la vez: Telegram
devuelve 409 si hay dos haciendo polling con el mismo token.
"""

import logging
import sys

from bot.config import BASE_DIR, require_token, setup_django

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "telegram_bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
# httpx es muy verboso a nivel INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)

log = logging.getLogger("bot.main")


def build_application():
    from telegram import BotCommand
    from telegram.ext import Application, CommandHandler

    from bot import handlers

    token = require_token()
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("hoy", handlers.hoy))
    app.add_handler(CommandHandler("historial", handlers.historial))
    app.add_handler(CommandHandler("analisis", handlers.analisis))
    app.add_handler(CommandHandler("anadir", handlers.añadir))
    app.add_handler(CommandHandler("confirmar", handlers.confirmar))
    app.add_handler(CommandHandler("cancelar", handlers.cancelar))
    app.add_handler(CommandHandler("nevera", handlers.nevera_cmd))
    app.add_handler(CommandHandler("borrar", handlers.borrar))
    app.add_handler(CommandHandler("editar", handlers.editar))
    app.add_handler(CommandHandler("comer", handlers.comer))
    app.add_handler(CommandHandler("hecho", handlers.hecho))
    app.add_handler(CommandHandler("comprar", handlers.comprar))

    async def _post_init(application):
        await application.bot.set_my_commands(
            [
                BotCommand("analisis", "Análisis del último día con Gemini"),
                BotCommand("hoy", "Resumen de datos crudos del último día"),
                BotCommand("historial", "Últimos análisis guardados"),
                BotCommand("anadir", "Da de alta una compra transcrita"),
                BotCommand("confirmar", "Confirma la alta pendiente"),
                BotCommand("cancelar", "Cancela la alta pendiente"),
                BotCommand("nevera", "Lista el inventario"),
                BotCommand("borrar", "Borra un item de la nevera"),
                BotCommand("editar", "Edita un item de la nevera"),
                BotCommand("comer", "Sugerencia de qué cocinar"),
                BotCommand("hecho", "Confirma una receta sugerida"),
                BotCommand("comprar", "Analiza ofertas transcritas contra la nevera"),
                BotCommand("help", "Ayuda"),
            ]
        )

    app.post_init = _post_init
    return app


def main():
    log.info("Arrancando bot de Telegram…")
    setup_django()
    app = build_application()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
