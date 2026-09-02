"""Configuración del análisis, independiente de la interfaz que lo pida.

Vivía en `bot/config.py`, pero la instrucción por defecto no es una cosa de
Telegram: es el valor con el que se llama a `run_analysis` cuando el usuario no
dice nada, y eso lo necesitan por igual el bot, la API web y `daily_sync.py`.
Si se quedara en `bot/`, la app `api/` tendría que importar del bot para
arrancar un análisis, y las dos interfaces dejarían de ser hermanas —el
principio del proyecto es que ambas son capas finas sobre los mismos
servicios, sin que ninguna dependa de la otra—.

Módulo deliberadamente ligero: sin Django ni `google-genai`, para que
`bot/config.py` (que se importa muy pronto) pueda leer de aquí sin arrastrar
medio proyecto.
"""

import os

# `ANALYSIS_DEFAULT_INSTRUCTION` es el nombre nuevo; se mantiene la lectura de
# `TELEGRAM_DEFAULT_INSTRUCTION` para no romper los `.env` que ya existen.
DEFAULT_INSTRUCTION = (
    os.getenv("ANALYSIS_DEFAULT_INSTRUCTION")
    or os.getenv("TELEGRAM_DEFAULT_INSTRUCTION")
    or "Dame el análisis de recuperación del día."
)

# Tope de longitud de la instrucción que llega por la API. El texto se
# incrusta en el prompt que va a Gemini, así que acotarlo limita tanto el
# gasto de tokens como el margen para reescribir el prompt entero desde el
# cuerpo de la petición (*prompt injection*). No sustituye a la autenticación,
# que es lo que de verdad impide que un tercero llegue hasta aquí.
MAX_INSTRUCTION_CHARS = 500
