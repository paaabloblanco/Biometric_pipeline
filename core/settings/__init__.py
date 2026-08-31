"""Selector de settings por entorno.

Todo el proyecto usa `DJANGO_SETTINGS_MODULE=core.settings` (manage.py, wsgi,
asgi, bot, servicios). El entorno concreto se elige con la variable de entorno
`DJANGO_ENV`:

- `dev` (por defecto): DEBUG on, hosts locales, CORS a localhost:5173.
- `prod`: DEBUG off, hosts y CORS obligatorios por env, cabeceras de seguridad.
"""

import os

_env = os.getenv("DJANGO_ENV", "dev").lower()

if _env == "prod":
    from core.settings.prod import *  # noqa: F401,F403
else:
    from core.settings.dev import *  # noqa: F401,F403
