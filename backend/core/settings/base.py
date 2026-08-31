"""
Ajustes comunes a todos los entornos.

`DJANGO_SETTINGS_MODULE` sigue siendo `core.settings` en todo el proyecto; el
entorno concreto (dev/prod) lo elige `core/settings/__init__.py` según la
variable `DJANGO_ENV`. Lo que cambia entre entornos (DEBUG, ALLOWED_HOSTS,
CORS, cabeceras de seguridad) vive en `dev.py` / `prod.py`, no aquí.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# core/settings/base.py -> core/settings -> core -> raíz del repo
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "supabase_data",
    "nevera",
    "api",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Europe/Warsaw"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# Django REST Framework + JWT (interfaz web, ver docs/SDD-web.md §5)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("api.permissions.IsTheOwner",),
    # Generador del esquema OpenAPI (drf-spectacular). Sustituye al generador
    # propio de DRF, que está obsoleto y produce OpenAPI 2.
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
}


# OpenAPI / Swagger UI (docs/SDD-web.md). El esquema se genera leyendo las
# views y los serializers: es documentación derivada del código, no escrita a
# mano, así que no puede quedarse desactualizada.
SPECTACULAR_SETTINGS = {
    "TITLE": "API de Proyecto Salud",
    "DESCRIPTION": (
        "API REST de un pipeline biométrico personal de un solo usuario. "
        "Misma lógica de negocio (`*/services.py`) que el bot de Telegram; "
        "esta es la interfaz que consume la SPA de React."
    ),
    "VERSION": "1.0.0",
    # El esquema se sirve en su propia ruta (/api/schema/), no incrustado como
    # un endpoint más dentro de la propia documentación.
    "SERVE_INCLUDE_SCHEMA": False,
    # Recorta el prefijo común de las rutas en los nombres autogenerados.
    "SCHEMA_PATH_PREFIX": "/api",
    "SERVERS": [{"url": "/", "description": "Este servidor"}],
}
