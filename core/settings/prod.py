"""Entorno de producción.

Las variables obligatorias fallan alto si faltan (mismo criterio que
`DJANGO_SECRET_KEY` en base.py): es preferible no arrancar a arrancar inseguro.
El despliegue real (dominio, HTTPS, dónde vive esto) es el siguiente SDD.
"""

import os

from core.settings.base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = [h.strip() for h in os.environ["DJANGO_ALLOWED_HOSTS"].split(",") if h.strip()]

# Dominio(s) del frontend en Vercel, separados por comas.
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ["CORS_ALLOWED_ORIGINS"].split(",") if o.strip()
]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Detrás de un proxy que termina TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
