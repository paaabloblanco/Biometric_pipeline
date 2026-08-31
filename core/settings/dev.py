"""Entorno de desarrollo local."""

import os

from core.settings.base import *  # noqa: F401,F403

DEBUG = True

# "testserver" es el host que usa el cliente de tests de Django/DRF.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Vite sirve el frontend en 5173 durante el desarrollo.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Extras para pruebas puntuales (p. ej. un túnel cloudflared apuntando a un
# frontend ya desplegado en Vercel). Solo en dev y solo si se piden por env:
# DEV_EXTRA_ALLOWED_HOSTS="algo.trycloudflare.com,.trycloudflare.com"
# DEV_EXTRA_CORS_ORIGINS="https://mi-app.vercel.app"
ALLOWED_HOSTS += [
    h.strip() for h in os.getenv("DEV_EXTRA_ALLOWED_HOSTS", "").split(",") if h.strip()
]
CORS_ALLOWED_ORIGINS += [
    o.strip() for o in os.getenv("DEV_EXTRA_CORS_ORIGINS", "").split(",") if o.strip()
]
