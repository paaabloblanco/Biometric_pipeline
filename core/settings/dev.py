"""Entorno de desarrollo local."""

from core.settings.base import *  # noqa: F401,F403

DEBUG = True

# "testserver" es el host que usa el cliente de tests de Django/DRF.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Vite sirve el frontend en 5173 durante el desarrollo.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
