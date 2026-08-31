"""Tests de los endpoints de solo lectura (SDD-web fase 2), contra la BD real.

Mismo patrón que el resto del proyecto: sin BD de test, datos sembrados con un
centinela propio y limpieza en tearDown. Para las tablas de salud
(`managed = False`) se usa un `parent_key` / fecha centinela que no colisiona
con datos reales; para la nevera y los análisis, un prefijo/fecha de test.
"""

import os
import unittest
from datetime import UTC, date, datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nevera.models import NeveraItem
from supabase_data.models import AiAnalysisLog, HeartRateSamples, SleepStages

User = get_user_model()

PREFIJO = "__test_api_read__"
PASSWORD = "una-clave-de-test-larga-123"

# Centinelas fuera del rango de datos reales.
SENTINEL_PARENT = 987654321
DIA_A = date(2001, 1, 1)
DIA_B = date(2001, 1, 2)


def _dt(dia, hora):
    return datetime(dia.year, dia.month, dia.day, hora, 0, tzinfo=UTC)


class ReadEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username=f"{PREFIJO}dueno",
            password=PASSWORD,
            is_staff=True,
            is_superuser=True,
        )
        resp = self.client.post(
            "/api/auth/login",
            {"username": self.user.username, "password": PASSWORD},
            format="json",
        )
        self.access = resp.data["access"]

    def tearDown(self):
        User.objects.filter(username__startswith=PREFIJO).delete()
        NeveraItem.objects.filter(nombre__startswith=PREFIJO).delete()
        HeartRateSamples.objects.filter(parent_key=SENTINEL_PARENT).delete()
        SleepStages.objects.filter(parent_key=SENTINEL_PARENT).delete()
        AiAnalysisLog.objects.filter(analysis_date__in=[DIA_A, DIA_B]).delete()

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    # --- auth ---

    def test_todos_los_endpoints_exigen_token(self):
        for ruta in (
            "/api/health/last-day",
            "/api/health/series?metric=heart_rate",
            "/api/analyses",
            "/api/nevera",
        ):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 401)

    # --- /api/health/series ---

    def test_series_heart_rate_agrega_por_dia(self):
        HeartRateSamples.objects.bulk_create(
            [
                HeartRateSamples(parent_key=SENTINEL_PARENT, bpm=60, recorded_at=_dt(DIA_A, 8)),
                HeartRateSamples(parent_key=SENTINEL_PARENT, bpm=80, recorded_at=_dt(DIA_A, 9)),
                HeartRateSamples(parent_key=SENTINEL_PARENT, bpm=70, recorded_at=_dt(DIA_B, 8)),
            ]
        )
        self._auth()
        resp = self.client.get(f"/api/health/series?metric=heart_rate&from={DIA_A}&to={DIA_B}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["metric"], "heart_rate")
        puntos = {p["date"]: p for p in resp.data["points"]}
        self.assertEqual(puntos[DIA_A.isoformat()]["min"], 60)
        self.assertEqual(puntos[DIA_A.isoformat()]["max"], 80)
        self.assertEqual(puntos[DIA_A.isoformat()]["avg"], 70.0)
        self.assertEqual(puntos[DIA_A.isoformat()]["count"], 2)
        self.assertEqual(puntos[DIA_B.isoformat()]["count"], 1)

    def test_series_sleep_suma_minutos_sin_vigilia(self):
        SleepStages.objects.bulk_create(
            [
                SleepStages(
                    parent_key=SENTINEL_PARENT,
                    stage_type=4,
                    stage_start=_dt(DIA_A, 0),
                    stage_end=_dt(DIA_A, 2),
                ),
                SleepStages(
                    parent_key=SENTINEL_PARENT,
                    stage_type=1,  # vigilia: se excluye
                    stage_start=_dt(DIA_A, 2),
                    stage_end=_dt(DIA_A, 3),
                ),
            ]
        )
        self._auth()
        resp = self.client.get(f"/api/health/series?metric=sleep&from={DIA_A}&to={DIA_A}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["points"], [{"date": DIA_A.isoformat(), "minutes": 120}])

    def test_series_metrica_desconocida_400(self):
        self._auth()
        resp = self.client.get("/api/health/series?metric=inventada")
        self.assertEqual(resp.status_code, 400)

    def test_series_sin_metric_400(self):
        self._auth()
        self.assertEqual(self.client.get("/api/health/series").status_code, 400)

    # --- /api/analyses ---

    def test_analyses_devuelve_lista_y_respeta_limit(self):
        AiAnalysisLog.objects.create(analysis_date=DIA_A, analysis_text="viejo A")
        AiAnalysisLog.objects.create(analysis_date=DIA_B, analysis_text="viejo B")
        self._auth()
        resp = self.client.get("/api/analyses?limit=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertIn("analysis_text", resp.data[0])

    def test_analyses_limit_no_entero_400(self):
        self._auth()
        self.assertEqual(self.client.get("/api/analyses?limit=abc").status_code, 400)

    # --- /api/nevera ---

    def test_nevera_lista_items(self):
        NeveraItem.objects.create(
            nombre=f"{PREFIJO}leche", cantidad=1000, unidad="ml", origen="manual"
        )
        self._auth()
        resp = self.client.get("/api/nevera")
        self.assertEqual(resp.status_code, 200)
        nombres = [i["nombre"] for i in resp.data]
        self.assertIn(f"{PREFIJO}leche", nombres)

    # --- /api/health/last-day ---

    def test_last_day_ok_contra_datos_reales(self):
        from supabase_data.services import get_latest_written_day

        try:
            get_latest_written_day()
        except ValueError:
            self.skipTest("No hay datos de salud en la BD para probar /health/last-day.")

        self._auth()
        resp = self.client.get("/api/health/last-day")
        self.assertEqual(resp.status_code, 200)
        for clave in (
            "date",
            "heart_rate_samples",
            "oxygen_saturation_samples",
            "resting_heart_rate_samples",
            "sleep_stages",
        ):
            self.assertIn(clave, resp.data)


if __name__ == "__main__":
    unittest.main()
