from django.apps import AppConfig
from django.core.checks import register


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        """Se ejecuta una vez, cuando Django termina de cargar las apps.

        Es el gancho donde se registran señales y comprobaciones. Se registra
        aquí la de `health_ai` porque `health_ai/` es un paquete normal, no una
        app de Django, y no tiene `AppConfig` propio desde el que hacerlo; la
        alternativa —convertirlo en app— sería crear modelos, migraciones y
        una entrada en `INSTALLED_APPS` para nada.

        Registrar no es ejecutar: las comprobaciones corren con
        `manage.py check` y al arrancar `runserver`, no en cualquier
        `django.setup()`. El proceso del bot, que solo hace `setup()`, no las
        pasa; por eso `advisory_lock` lleva además su propia comprobación en
        caliente.
        """
        from health_ai.checks import pooler_en_modo_session

        register(pooler_en_modo_session)
