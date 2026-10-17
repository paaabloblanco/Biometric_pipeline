"""Tests de sugerencias y consumo (SDD-web fase 6.c).

`POST /api/nevera/suggestions` (inventario -> recetas, sin escribir) y
`POST /api/nevera/consume` (ingredientes -> descuento en la BD).

Como en el alta, Gemini se sustituye por un doble: lo que se prueba es el
contrato HTTP, no la calidad de las recetas.

Prefijo centinela + limpieza en `tearDown`, como el resto del proyecto. Ojo:
`get_items_by_expiry` lee la nevera **entera**, así que estos tests conviven
con los items reales del usuario; por eso ninguno afirma nada sobre el número
total de items, solo sobre los suyos.
"""

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nevera.models import NeveraItem

User = get_user_model()

PREFIJO = "__test_api_comer__"
PASSWORD = "una-clave-de-test-larga-123"

SUGGESTIONS = "/api/nevera/suggestions"
CONSUME = "/api/nevera/consume"


def receta(*ingredientes):
    return {
        "nombre": "Receta de prueba",
        "descripcion": "Una descripción breve.",
        "ingredientes": list(ingredientes),
    }


class NeveraComerTests(unittest.TestCase):
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

        self.pollo = NeveraItem.objects.create(
            nombre=f"{PREFIJO}pollo", cantidad=Decimal("1000"), unidad="g"
        )
        self.sal = NeveraItem.objects.create(
            nombre=f"{PREFIJO}sal", cantidad=Decimal("1"), unidad="ud", es_basico=True
        )

    def tearDown(self):
        User.objects.filter(username__startswith=PREFIJO).delete()
        NeveraItem.objects.filter(nombre__startswith=PREFIJO).delete()

    # --- auth ---

    def test_exige_token(self):
        sin_auth = APIClient()
        self.assertEqual(sin_auth.post(SUGGESTIONS, {}, format="json").status_code, 401)
        self.assertEqual(sin_auth.post(CONSUME, {}, format="json").status_code, 401)

    # --- POST /api/nevera/suggestions ---

    @patch("nevera.suggestions.suggest_recipes")
    def test_suggestions_devuelve_recetas_sin_tocar_la_nevera(self, fake):
        fake.return_value = [receta({"nombre": f"{PREFIJO}pollo", "cantidad": 200, "unidad": "g"})]

        resp = self.client.post(SUGGESTIONS, {}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["recipes"]), 1)
        self.assertEqual(resp.data["recipes"][0]["nombre"], "Receta de prueba")
        # Sugerir no descuenta: eso es lo que hace /consume.
        self.pollo.refresh_from_db()
        self.assertEqual(self.pollo.cantidad, Decimal("1000"))

    @patch("nevera.suggestions.suggest_recipes")
    def test_suggestions_avisa_del_termino_excluido_que_no_existe(self, fake):
        fake.return_value = [receta({"nombre": f"{PREFIJO}pollo", "cantidad": 200, "unidad": "g"})]

        resp = self.client.post(
            SUGGESTIONS, {"exclude": ["no_existe_en_la_nevera_xyz"]}, format="json"
        )

        self.assertEqual(resp.status_code, 200)
        # Callarlo haría parecer que la exclusión se ignoró; casi siempre es
        # una errata al escribir el nombre.
        self.assertIn("no_existe_en_la_nevera_xyz", resp.data["not_found"])

    @patch("nevera.suggestions.suggest_recipes")
    def test_suggestions_devuelve_502_si_gemini_falla(self, fake):
        fake.side_effect = ValueError("Gemini no devolvió JSON válido")

        resp = self.client.post(SUGGESTIONS, {}, format="json")

        self.assertEqual(resp.status_code, 502)

    def test_suggestions_rechaza_exclude_mal_formado(self):
        resp = self.client.post(SUGGESTIONS, {"exclude": "pollo"}, format="json")
        self.assertEqual(resp.status_code, 400)

    # --- POST /api/nevera/consume ---

    def test_consume_descuenta_la_cantidad(self):
        resp = self.client.post(
            CONSUME,
            {"ingredients": [{"nombre": f"{PREFIJO}pollo", "cantidad": 200, "unidad": "g"}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.pollo.refresh_from_db()
        self.assertEqual(self.pollo.cantidad, Decimal("800"))
        self.assertEqual(resp.data["aplicados"][0]["restante"], 800)

    def test_consume_convierte_la_unidad_antes_de_restar(self):
        item = NeveraItem.objects.create(
            nombre=f"{PREFIJO}leche", cantidad=Decimal("2000"), unidad="ml"
        )

        resp = self.client.post(
            CONSUME,
            {"ingredients": [{"nombre": f"{PREFIJO}leche", "cantidad": 1, "unidad": "l"}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.cantidad, Decimal("1000"))

    def test_consume_borra_el_item_si_se_agota(self):
        resp = self.client.post(
            CONSUME,
            {"ingredients": [{"nombre": f"{PREFIJO}pollo", "cantidad": 1000, "unidad": "g"}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(NeveraItem.objects.filter(id=self.pollo.id).exists())
        self.assertEqual(resp.data["aplicados"][0]["restante"], 0)

    def test_consume_no_descuenta_los_basicos(self):
        resp = self.client.post(
            CONSUME,
            {"ingredients": [{"nombre": f"{PREFIJO}sal", "cantidad": 3, "unidad": "g"}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        # Un básico se gestiona por presencia, no por cantidad: sin esto, una
        # receta con "sal: 1 ud" borraría la sal del inventario.
        self.sal.refresh_from_db()
        self.assertEqual(self.sal.cantidad, Decimal("1"))
        self.assertEqual(resp.data["basicos"][0]["nombre"], f"{PREFIJO}sal")
        self.assertEqual(resp.data["aplicados"], [])

    def test_consume_informa_de_lo_que_ya_no_estaba(self):
        resp = self.client.post(
            CONSUME,
            {
                "ingredients": [
                    {"nombre": f"{PREFIJO}pollo", "cantidad": 100, "unidad": "g"},
                    {"nombre": f"{PREFIJO}fantasma", "cantidad": 1, "unidad": "ud"},
                ]
            },
            format="json",
        )

        # 200 y no 404: que falte un ingrediente no invalida la comida, y lo
        # que sí estaba se ha descontado. El detalle va en el cuerpo.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["aplicados"]), 1)
        self.assertEqual(resp.data["no_encontrados"][0]["nombre"], f"{PREFIJO}fantasma")

    def test_consume_rechaza_lista_vacia(self):
        resp = self.client.post(CONSUME, {"ingredients": []}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_consume_rechaza_unidad_desconocida_sin_tocar_nada(self):
        resp = self.client.post(
            CONSUME,
            {
                "ingredients": [
                    {"nombre": f"{PREFIJO}pollo", "cantidad": 100, "unidad": "g"},
                    {"nombre": f"{PREFIJO}otro", "cantidad": 1, "unidad": "lonchas"},
                ]
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        # Se valida antes de tocar la BD: el ingrediente bueno tampoco se resta.
        self.pollo.refresh_from_db()
        self.assertEqual(self.pollo.cantidad, Decimal("1000"))


if __name__ == "__main__":
    unittest.main()
