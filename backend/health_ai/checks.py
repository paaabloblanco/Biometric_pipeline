"""Comprobaciones de configuración que Django ejecuta al arrancar.

**Qué es el framework de *system checks*.** Django trae un registro de
funciones de validación que corre solas antes de levantar el servidor, y
también con `manage.py check`. Sirven para cazar configuraciones que son
sintácticamente válidas pero semánticamente rotas: un `ALLOWED_HOSTS` vacío con
`DEBUG=False`, un `ForeignKey` sin `on_delete`, un middleware en el orden
equivocado. Los avisos que ves al arrancar `runserver` con forma de `W042`,
`security.W004`… salen de aquí.

Es el sitio idiomático para "esto tiene que cumplirse o el programa no
funciona como crees", y la alternativa a descubrirlo en producción.

Aquí se usa para lo que se explica en `locks.py`: el advisory lock depende de
que el pooler esté en modo *session*. Con el modo *transaction* el lock deja de
proteger **sin dar ningún error**, y un mecanismo de seguridad que falla en
silencio es peor que no tenerlo, porque dejas de mirar. Esta comprobación
convierte ese fallo silencioso en uno ruidoso.
"""

from django.conf import settings
from django.core.checks import Error

# Puerto del pooler de Supabase en modo *transaction*. En ese modo la conexión
# vuelve al montón al acabar cada transacción, así que un lock de sesión queda
# colgado en una conexión que ya no es tuya.
PUERTO_TRANSACTION_MODE = "6543"


def pooler_en_modo_session(app_configs, **kwargs):
    """`DB_PORT` no puede ser el del pooler en modo transaction.

    Es `Error` y no `Warning` a propósito: un `Warning` se imprime al arrancar
    y se pierde en el scroll, y aquí la consecuencia es que el lock del
    análisis deja de funcionar sin avisar. Un `Error` impide arrancar, que es
    la respuesta proporcionada a una configuración que rompe la corrección.

    Si algún día se pasa a `pg_advisory_xact_lock` (que sí es seguro en modo
    transaction), esta comprobación sobra: se quita de aquí, no se silencia
    con `SILENCED_SYSTEM_CHECKS`.
    """
    puerto = str(settings.DATABASES["default"].get("PORT") or "")
    if puerto != PUERTO_TRANSACTION_MODE:
        return []
    return [
        Error(
            f"DB_PORT={puerto}: el pooler está en modo transaction y los advisory "
            "locks de sesión dejan de funcionar sin dar error.",
            hint=(
                "Usa el puerto 5432 (pooler en modo session). Ver la nota del "
                "módulo health_ai/locks.py."
            ),
            id="health_ai.E001",
        )
    ]
