"""Locks entre procesos, apoyados en los *advisory locks* de Postgres.

**Qué problema resuelve.** El bot de Telegram y la API web son dos procesos
distintos que llaman a los mismos servicios. Un `asyncio.Lock` (o cualquier
lock de Python) vive en la memoria de un proceso: el del bot no se entera de lo
que hace el de la API, así que no impide que los dos disparen a la vez la misma
llamada cara a Gemini. Para que dos procesos se coordinen, el lock tiene que
vivir **fuera de los dos**, en algo que ya comparten. Aquí eso es Postgres.

**Qué es un advisory lock.** Una función nativa de Postgres a la que le pides
que te reserve un número entero cualquiera. Se llama *advisory* ("consultivo")
porque el servidor no lo asocia a ninguna tabla ni fila: no protege datos,
protege un **acuerdo entre nuestros procesos**. El significado del número nos
lo inventamos nosotros (ver las constantes de abajo). No necesita tabla ni
migración, y Postgres lo libera solo si la conexión se cae, así que un proceso
que muera a mitad no deja el lock colgado para siempre.

**Alternativas descartadas** (decisión C del SDD-web, 2026-08-31):
- *Redis* (`SET NX`): lo más común en producción, pero añade un servicio más
  que desplegar y vigilar para un proyecto de un solo usuario.
- *Fila de control + `SELECT FOR UPDATE`*: portable a cualquier SQL, pero
  exige tabla y migración a cambio de ninguna ventaja aquí.
- *Cola de trabajos* (Celery, RQ): la solución de verdad cuando la tarea es
  larga —no bloqueas, encolas—, pero es una pieza de infraestructura entera
  para un análisis al día.

⚠️ **Depende del modo del pooler.** Un advisory lock de sesión pertenece a la
*conexión* que lo pidió. Supabase expone el pooler en dos puertos: el 5432 en
modo *session* (la conexión queda atada mientras dure) y el 6543 en modo
*transaction* (te la devuelve al montón al acabar cada transacción). Con el
6543 este lock deja de proteger nada **sin dar ningún error**: otra conexión
del pool se lo encontraría libre. `DB_PORT` tiene que seguir siendo 5432.
"""

import logging
from contextlib import contextmanager

from django.conf import settings
from django.db import connection

log = logging.getLogger(__name__)

# Claves de advisory lock en uso. Postgres no les da ningún significado: son
# enteros arbitrarios y el acuerdo es solo entre nuestros procesos. Se listan
# aquí juntas para que nadie repita una por accidente, que es el único modo de
# que dos operaciones sin relación se bloqueen entre sí.
LOCK_ANALISIS_DIARIO = 987001


class LockOcupado(RuntimeError):
    """Otro proceso tiene el lock. No es un fallo: es un estado esperable."""


@contextmanager
def advisory_lock(clave: int, error: type[LockOcupado] = LockOcupado):
    """Coge el advisory lock `clave` o lanza `error` si ya lo tiene otro.

    No espera: usa `pg_try_advisory_lock`, que responde al instante con si lo
    consiguió o no. La variante que espera (`pg_advisory_lock`) dejaría colgada
    una petición HTTP hasta que el otro proceso terminase —30 s en el caso del
    análisis—, y el navegador o el proxy la cortarían antes.

    Es un lock **de sesión**, no de transacción. `pg_advisory_xact_lock` se
    libera solo al cerrar la transacción, lo que es más cómodo, pero obligaría
    a mantener una transacción abierta durante toda la llamada a Gemini: una
    transacción larga bloquea el `VACUUM` de Postgres y retiene una conexión
    para no hacer nada. Regla: nunca tengas una transacción abierta esperando a
    una red ajena.

    ⚠️ **Coger y soltar tienen que ocurrir en el mismo hilo.** La conexión de
    Django es *thread-local*: cada hilo tiene la suya, y el lock pertenece a la
    conexión que lo pidió. El `with` de un solo bloque ya lo garantiza; el
    riesgo aparece si alguien parte el lock en dos pasos y los reparte entre
    dos `asyncio.to_thread`, porque el pool de hilos puede darle uno distinto
    en cada llamada: serían dos conexiones, el `unlock` no encontraría nada
    que soltar y el lock quedaría retenido hasta que muriera el proceso.

    Tampoco es reentrante de forma segura: `pg_try_advisory_lock` sobre una
    clave que la propia sesión ya tiene vuelve a decir que sí y exige otro
    `unlock` más. Anidar dos veces la misma clave dejaría una a medio soltar,
    así que no se anida.
    """
    _avisar_si_el_pooler_no_sirve()

    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", [clave])
        (conseguido,) = cur.fetchone()

    if not conseguido:
        raise error(f"El lock {clave} ya está cogido por otro proceso.")

    try:
        yield
    finally:
        # `finally` y no un simple `unlock` al final: si el cuerpo revienta
        # (Gemini devuelve un error, se cae la red), el lock se suelta igual.
        # Sin esto, un fallo dejaría bloqueados todos los análisis siguientes
        # hasta reiniciar el proceso.
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", [clave])
            (soltado,) = cur.fetchone()
        if not soltado:
            # Postgres dice que esta conexión no tenía el lock. Si pasa, es que
            # se cogió en otra conexión (¿otro hilo?, ¿el pooler en modo
            # transaction?) o que se perdió la conexión a media operación. Se
            # avisa en vez de callar: comprobar el valor de retorno de un
            # `unlock` no es habitual, pero es la ÚNICA prueba que quedará de
            # que el mecanismo dejó de funcionar.
            log.warning(
                "pg_advisory_unlock(%s) devolvió false: la conexión no tenía el lock.", clave
            )


def _avisar_si_el_pooler_no_sirve() -> None:
    """Grita si la conexión va por el pooler en modo transaction.

    Duplica la comprobación de `health_ai/checks.py` a propósito: aquella es un
    *system check* de Django y solo corre con `manage.py check` o al arrancar
    `runserver`. El bot y el CLI hacen `django.setup()` a secas y nunca la
    pasarían, así que la comprobación de verdad —la que cubre todos los
    procesos— es esta. Se ejecuta al coger el lock, que es una vez cada 30 s en
    el peor caso: el coste es irrelevante.
    """
    from health_ai.checks import PUERTO_TRANSACTION_MODE

    if str(settings.DATABASES["default"].get("PORT") or "") == PUERTO_TRANSACTION_MODE:
        log.error(
            "DB_PORT=%s (pooler en modo transaction): este advisory lock de sesión "
            "NO protege nada. Ver health_ai/locks.py.",
            PUERTO_TRANSACTION_MODE,
        )
