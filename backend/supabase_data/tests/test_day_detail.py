"""Tests del detalle de un día (`get_day_detail`, página /dia/:fecha de la web).

Mismo patrón que el resto: sin BD de test, centinelas fuera del rango real y
limpieza en `tearDown`.
"""

import os
import unittest
from datetime import UTC, date, datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from supabase_data.models import HeartRateSamples
from supabase_data.services import get_day_detail

SENTINEL_PARENT = 987654321
# Tres días con datos separados por huecos: lo que hace interesante a prev/next.
DIA_1 = date(2001, 2, 1)
DIA_2 = date(2001, 2, 10)
DIA_3 = date(2001, 2, 20)


def _muestra(dia, hora, bpm):
    return HeartRateSamples(
        parent_key=SENTINEL_PARENT,
        bpm=bpm,
        recorded_at=datetime(dia.year, dia.month, dia.day, hora, 0, tzinfo=UTC),
    )


class DayDetailTests(unittest.TestCase):
    def setUp(self):
        HeartRateSamples.objects.bulk_create(
            [
                _muestra(DIA_1, 10, 60),
                _muestra(DIA_2, 10, 70),
                _muestra(DIA_2, 11, 80),
                _muestra(DIA_3, 10, 90),
            ]
        )

    def tearDown(self):
        HeartRateSamples.objects.filter(parent_key=SENTINEL_PARENT).delete()

    def test_los_vecinos_saltan_los_huecos_sin_datos(self):
        """Del 10 de febrero se va al 1 y al 20, no al 9 y al 11: navegar por
        días naturales llevaría a pantallas vacías, porque el sync tiene huecos
        de semanas."""
        detalle = get_day_detail(DIA_2)
        self.assertEqual(detalle["prev_date"], DIA_1.isoformat())
        self.assertEqual(detalle["next_date"], DIA_3.isoformat())

    def test_el_primer_dia_no_tiene_anterior(self):
        detalle = get_day_detail(DIA_1)
        self.assertIsNone(detalle["prev_date"])
        self.assertEqual(detalle["next_date"], DIA_2.isoformat())

    def test_la_serie_intradia_trae_instante_local_y_valor(self):
        detalle = get_day_detail(DIA_2)
        self.assertEqual(len(detalle["heart_rate"]), 2)
        punto = detalle["heart_rate"][0]
        self.assertEqual(set(punto), {"t", "v"})
        self.assertEqual(punto["v"], 70.0)
        # El instante llega con offset explícito, no en UTC pelado: así el
        # navegador no lo reinterpreta en su propia zona horaria.
        self.assertRegex(punto["t"], r"^2001-02-10T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

    def test_el_resumen_del_dia_viene_calculado(self):
        detalle = get_day_detail(DIA_2)
        self.assertEqual(detalle["summary"]["heart_rate_avg"], 75)
        self.assertEqual(detalle["summary"]["heart_rate_min"], 70)
        self.assertEqual(detalle["summary"]["heart_rate_max"], 80)


if __name__ == "__main__":
    unittest.main()
