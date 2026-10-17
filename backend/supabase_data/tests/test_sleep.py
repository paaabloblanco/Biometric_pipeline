"""Tests de la lógica de sueño (deduplicación, noche y serie).

Mismo patrón que el resto del proyecto: no hay BD de test, así que se siembra
con un `parent_key` centinela fuera del rango real y se limpia en `tearDown`.

Estos tests existen por un bug real: el sync guardaba la misma noche dos veces
con dos `parent_key` distintos y la serie devolvía 17h de sueño. Son la red que
impide que vuelva.
"""

import os
import unittest
from datetime import UTC, date, datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from supabase_data.models import SleepStages
from supabase_data.services import get_series, get_sleep_night

# Centinelas: el año 2001 no colisiona con datos reales.
PK_A = 987654001
PK_B = 987654002
PK_SIESTA = 987654003
VISPERA = date(2001, 1, 5)
DIA = date(2001, 1, 6)
# Domingo del cambio a horario de invierno en España: a las 03:00 CEST se
# vuelve a las 02:00 CET, así que esa madrugada tiene dos veces las 02:xx.
CAMBIO_HORA = date(2026, 10, 25)

LIGERO, PROFUNDO, REM, DESPIERTO = 4, 5, 6, 1


def _dt(dia, hora, minuto=0):
    """Instante en UTC."""
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=UTC)


def _sembrar(parent_key, fases):
    """Siembra una sesión a partir de tuplas (stage_type, inicio, fin)."""
    SleepStages.objects.bulk_create(
        [
            SleepStages(parent_key=parent_key, stage_type=tipo, stage_start=ini, stage_end=fin)
            for tipo, ini, fin in fases
        ]
    )


class SleepDedupTests(unittest.TestCase):
    def tearDown(self):
        SleepStages.objects.filter(parent_key__in=[PK_A, PK_B, PK_SIESTA]).delete()

    def _sembrar_noche(self, parent_key, fin_hora=6):
        """Noche del 5 al 6, de 22:00 a 06:00 UTC: 8h en tres fases."""
        _sembrar(
            parent_key,
            [
                (LIGERO, _dt(VISPERA, 22), _dt(DIA, 0)),
                (PROFUNDO, _dt(DIA, 0), _dt(DIA, 2)),
                (REM, _dt(DIA, 2), _dt(DIA, fin_hora)),
            ],
        )

    def _minutos(self):
        puntos = get_series("sleep", DIA, DIA)
        return puntos[0]["minutes"] if puntos else 0

    def test_noche_que_cruza_medianoche_se_atribuye_al_despertar(self):
        """Una noche 22:00->06:00 cuenta entera en el día en que despiertas,
        no partida entre los dos días naturales que toca."""
        self._sembrar_noche(PK_A)
        self.assertEqual(self._minutos(), 8 * 60)
        self.assertEqual(get_series("sleep", VISPERA, VISPERA), [])

    def test_sesion_duplicada_identica_cuenta_una_vez(self):
        """El bug original: las mismas fases con dos parent_key -> minutos x2."""
        self._sembrar_noche(PK_A)
        solo_una = self._minutos()
        self._sembrar_noche(PK_B)
        self.assertEqual(self._minutos(), solo_una)

    def test_duplicado_parcial_conserva_la_sesion_mas_larga(self):
        """Dos pasadas del sync guardaron la misma noche con finales distintos.
        Comparar huellas exactas no lo detecta; el solapamiento sí."""
        self._sembrar_noche(PK_A, fin_hora=6)  # la completa
        self._sembrar_noche(PK_B, fin_hora=4)  # la truncada
        self.assertEqual(self._minutos(), 8 * 60)

    def test_las_fases_de_vigilia_no_cuentan_como_sueno(self):
        self._sembrar_noche(PK_A)
        _sembrar(PK_A, [(DESPIERTO, _dt(DIA, 6), _dt(DIA, 7))])
        self.assertEqual(self._minutos(), 8 * 60)

    def test_la_siesta_no_se_mezcla_con_la_noche(self):
        """`get_sleep_night` devuelve la sesión más larga del día, no todas: si
        no, el hipnograma dibujaría la siesta como parte de la noche."""
        self._sembrar_noche(PK_A)
        _sembrar(PK_SIESTA, [(LIGERO, _dt(DIA, 14), _dt(DIA, 15))])

        noche = get_sleep_night(DIA)
        self.assertEqual(noche["total_minutes"], 8 * 60)
        self.assertEqual(len(noche["segments"]), 3)
        self.assertEqual({t["stage"] for t in noche["totals"]}, {"ligero", "profundo", "rem"})

    def test_los_extremos_son_correctos_la_noche_del_cambio_de_hora(self):
        """La madrugada del cambio de hora convive con dos offsets. Si `start` y
        `end` salieran de comparar los ISO ya formateados como texto, el orden
        alfabético no coincidiría con el cronológico y la noche se leería al
        revés; por eso se calculan sobre los datetime."""
        # 25-10-2026, 03:00 CEST (+02:00) -> 02:00 CET (+01:00).
        _sembrar(
            PK_A,
            [
                # 00:30-01:00 UTC = 02:30-03:00 +02:00 (antes del salto)
                (LIGERO, _dt(CAMBIO_HORA, 0, 30), _dt(CAMBIO_HORA, 1)),
                # 01:00-02:00 UTC = 02:00-03:00 +01:00 (después del salto)
                (PROFUNDO, _dt(CAMBIO_HORA, 1), _dt(CAMBIO_HORA, 2)),
            ],
        )
        noche = get_sleep_night(CAMBIO_HORA)
        self.assertEqual(noche["total_minutes"], 90)
        self.assertTrue(noche["start"].startswith("2026-10-25T02:30:00+02:00"))
        self.assertTrue(noche["end"].startswith("2026-10-25T03:00:00+01:00"))

    def test_la_noche_sin_datos_devuelve_forma_vacia_no_error(self):
        vacia = get_sleep_night(date(2001, 1, 20))
        self.assertEqual(vacia["segments"], [])
        self.assertEqual(vacia["total_minutes"], 0)
        self.assertIsNone(vacia["start"])


if __name__ == "__main__":
    unittest.main()
