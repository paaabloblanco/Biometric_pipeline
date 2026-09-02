"""Tests de `POST /api/ofertas/analyze` (SDD-web fase 6.d).

Gemini se sustituye por un doble, como en el resto de endpoints con IA: lo que
se prueba es el contrato HTTP, no la calidad de las recomendaciones (eso ya lo
cubre `nevera/tests/test_ofertas.py`).
"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

PREFIJO = "__test_api_ofertas__"
PASSWORD = "una-clave-de-test-larga-123"
RUTA = "/api/ofertas/analyze"


class OfertasEndpointTests(unittest.TestCase):
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
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")

    def tearDown(self):
        User.objects.filter(username__startswith=PREFIJO).delete()

    def test_exige_token(self):
        self.assertEqual(APIClient().post(RUTA, {"text": "x"}, format="json").status_code, 401)

    @patch("nevera.ofertas.analizar_ofertas")
    def test_devuelve_las_recomendaciones(self, fake):
        fake.return_value = [
            {"nombre": "Pechuga de pollo", "motivo": "Te queda poca.", "precio": "5,99 zł"}
        ]

        resp = self.client.post(RUTA, {"text": "Pechuga de pollo 5,99 zl"}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data[0]["nombre"], "Pechuga de pollo")
        # El precio viaja como texto, tal cual aparece en la oferta: puede ser
        # "2x1" o "-30%", que no son un número.
        self.assertEqual(resp.data[0]["precio"], "5,99 zł")

    @patch("nevera.ofertas.analizar_ofertas")
    def test_lista_vacia_es_una_respuesta_valida(self, fake):
        fake.return_value = []

        resp = self.client.post(RUTA, {"text": "solo ultraprocesados"}, format="json")

        # 200 con lista vacía, no 404: "ninguna oferta compensa" es una
        # respuesta, no la ausencia de un recurso.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    @patch("nevera.ofertas.analizar_ofertas")
    def test_recomendacion_sin_precio(self, fake):
        fake.return_value = [{"nombre": "Aceite de oliva", "motivo": "Básico."}]

        resp = self.client.post(RUTA, {"text": "aceite"}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data[0]["precio"])

    def test_rechaza_texto_vacio(self):
        resp = self.client.post(RUTA, {"text": "   "}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_rechaza_texto_demasiado_largo(self):
        from nevera.ofertas import MAX_OFERTAS_CHARS

        resp = self.client.post(RUTA, {"text": "x" * (MAX_OFERTAS_CHARS + 1)}, format="json")
        self.assertEqual(resp.status_code, 400)

    @patch("nevera.ofertas.analizar_ofertas")
    def test_devuelve_502_si_gemini_falla(self, fake):
        fake.side_effect = ValueError("Gemini no devolvió JSON válido")

        resp = self.client.post(RUTA, {"text": "lo que sea"}, format="json")

        self.assertEqual(resp.status_code, 502)


if __name__ == "__main__":
    unittest.main()
