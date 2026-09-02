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

from contextlib import contextmanager

from django.db import connection

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
    conexión que lo pidió. Si se cogiera en un hilo y se soltara en otro, el
    `unlock` no encontraría nada que soltar y el lock quedaría retenido hasta
    que muriera el proceso. Por eso este gestor de contexto se usa **dentro**
    de la función que hace el trabajo, no alrededor del `asyncio.to_thread`
    que la lanza.

    Tampoco es reentrante de forma segura: `pg_try_advisory_lock` sobre una
    clave que la propia sesión ya tiene vuelve a decir que sí y exige otro
    `unlock` más. Anidar dos veces la misma clave dejaría una a medio soltar,
    así que no se anida.
    """
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
            # se cogió en otra conexión (¿otro hilo?) o que se perdió la
            # conexión a media operación. Se avisa en vez de callar, porque el
            # síntoma sería un lock colgado imposible de diagnosticar después.
            import logging

            logging.getLogger(__name__).warning(
                "pg_advisory_unlock(%s) devolvió false: la conexión no tenía el lock.", clave
            )
