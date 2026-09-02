"""Tests del advisory lock entre procesos (`health_ai/locks.py`).

**Cómo se prueba un lock entre procesos sin levantar dos procesos.** Lo que el
lock protege de verdad es que dos *conexiones* distintas a Postgres no puedan
tenerlo a la vez. La conexión de Django es thread-local —cada hilo abre la
suya—, así que un segundo hilo es una segunda conexión: exactamente la misma
situación que el bot y la API en dos procesos, pero comprobable en un test.

Eso hace además que estos tests cubran el error más fácil de cometer con esta
API: coger el lock en un hilo y soltarlo en otro.

Se usa una clave centinela propia, no `LOCK_ANALISIS_DIARIO`, para que un test
no pueda bloquear un análisis real que estuviera corriendo en paralelo.
"""

import os
import threading
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.db import connections

from health_ai.locks import LockOcupado, advisory_lock

CLAVE_TEST = 987099


class ErrorPropio(LockOcupado):
    """Para comprobar que `advisory_lock` lanza la clase que se le pasa."""


def _coger_en_otro_hilo(clave: int) -> bool:
    """¿Consigue el lock una conexión distinta? True/False, sin propagar.

    El hilo cierra su conexión al terminar: si no, quedaría abierta y con ella
    cualquier lock que hubiera cogido, contaminando los tests siguientes.
    """
    conseguido: list[bool] = []

    def _worker():
        try:
            with advisory_lock(clave):
                conseguido.append(True)
        except LockOcupado:
            conseguido.append(False)
        finally:
            connections.close_all()

    hilo = threading.Thread(target=_worker)
    hilo.start()
    hilo.join()
    return conseguido[0]


class AdvisoryLockTests(unittest.TestCase):
    def test_otra_conexion_no_puede_cogerlo_mientras_esta_tomado(self):
        """El caso que motiva todo esto: el bot analizando y la web pidiendo
        otro análisis a la vez."""
        with advisory_lock(CLAVE_TEST):
            self.assertFalse(_coger_en_otro_hilo(CLAVE_TEST))

    def test_se_libera_al_salir_del_bloque(self):
        with advisory_lock(CLAVE_TEST):
            pass
        self.assertTrue(_coger_en_otro_hilo(CLAVE_TEST))

    def test_se_libera_aunque_el_cuerpo_reviente(self):
        """Sin el `finally`, un fallo de Gemini dejaría bloqueados todos los
        análisis siguientes hasta reiniciar el proceso."""
        with self.assertRaises(ZeroDivisionError), advisory_lock(CLAVE_TEST):
            raise ZeroDivisionError("fallo simulado dentro del bloque")
        self.assertTrue(_coger_en_otro_hilo(CLAVE_TEST))

    def test_lanza_la_excepcion_que_se_le_indica(self):
        """Cada llamador traduce el conflicto a su medio (409 en la API,
        mensaje en el bot), así que la clase la elige quien llama."""
        conflicto: list[bool] = []

        def _worker():
            try:
                with advisory_lock(CLAVE_TEST, ErrorPropio):
                    conflicto.append(False)
            except ErrorPropio:
                conflicto.append(True)
            finally:
                connections.close_all()

        with advisory_lock(CLAVE_TEST):
            hilo = threading.Thread(target=_worker)
            hilo.start()
            hilo.join()

        self.assertTrue(conflicto[0])

    def test_claves_distintas_no_se_estorban(self):
        """Postgres no da significado a la clave: dos operaciones sin relación
        solo chocan si alguien repite el número por accidente."""
        with advisory_lock(CLAVE_TEST):
            self.assertTrue(_coger_en_otro_hilo(CLAVE_TEST + 1))


if __name__ == "__main__":
    unittest.main()
