"""Tests del alta de nevera con IA (SDD-web fase 6.b).

Cubre las dos mitades del flujo sin estado: `POST /api/nevera/parse` (texto ->
items propuestos, sin escribir) y `POST /api/nevera/items` (items confirmados
-> filas en la BD).

La llamada a Gemini se sustituye por un doble (`patch` sobre
`nevera.parsing.parse_compra_text`): lo que se prueba aquí es el contrato HTTP
—códigos, forma de la respuesta, validación— no la calidad del parseo, que ya
tiene sus propios tests en `nevera/tests/test_parsing.py`. Además un test que
llamara a Gemini de verdad sería lento, gastaría cuota y no sería determinista.

Mismo patrón que el resto del proyecto: no hay BD de test, así que los datos se
siembran con un prefijo centinela y se limpian en `tearDown`.
"""

import os
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nevera.models import NeveraItem

User = get_user_model()

PREFIJO = "__test_api_alta__"
PASSWORD = "una-clave-de-test-larga-123"

PARSE = "/api/nevera/parse"
ITEMS = "/api/nevera/items"


def item_propuesto(**cambios):
    """Un item con la forma que devuelve `parse_compra_text`."""
    base = {
        "nombre": f"{PREFIJO}leche",
        "cantidad": 1,
        "unidad": "l",
        "categoria": "lacteo",
        "fecha_caducidad": date(2030, 1, 1),
        "es_basico": False,
    }
    base.update(cambios)
    return base


class NeveraAltaTests(unittest.TestCase):
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
        NeveraItem.objects.filter(nombre__startswith=PREFIJO).delete()

    # --- auth ---

    def test_alta_exige_token(self):
        sin_auth = APIClient()
        self.assertEqual(sin_auth.post(PARSE, {"text": "leche"}, format="json").status_code, 401)
        self.assertEqual(sin_auth.post(ITEMS, {"items": []}, format="json").status_code, 401)

    # --- POST /api/nevera/parse ---

    @patch("nevera.parsing.parse_compra_text")
    def test_parse_devuelve_items_sin_guardar_nada(self, fake_parse):
        fake_parse.return_value = [item_propuesto()]

        resp = self.client.post(PARSE, {"text": "1 litro de leche"}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["nombre"], f"{PREFIJO}leche")
        # La unidad viaja como la dijo el usuario, no convertida a la base: la
        # pantalla de confirmación tiene que enseñar "1 l", no "1000 ml".
        self.assertEqual(resp.data[0]["unidad"], "l")
        self.assertEqual(resp.data[0]["cantidad"], Decimal("1.00"))
        # Lo importante de esta fase: parsear NO escribe.
        self.assertFalse(NeveraItem.objects.filter(nombre__startswith=PREFIJO).exists())

    def test_parse_rechaza_texto_vacio(self):
        resp = self.client.post(PARSE, {"text": "   "}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.data)

    def test_parse_rechaza_texto_demasiado_largo(self):
        from nevera.parsing import MAX_COMPRA_CHARS

        resp = self.client.post(PARSE, {"text": "x" * (MAX_COMPRA_CHARS + 1)}, format="json")
        self.assertEqual(resp.status_code, 400)

    @patch("nevera.parsing.parse_compra_text")
    def test_parse_devuelve_502_si_gemini_no_da_json(self, fake_parse):
        fake_parse.side_effect = ValueError("Gemini no devolvió JSON válido")

        resp = self.client.post(PARSE, {"text": "lo que sea"}, format="json")

        # 502 y no 400: la petición era correcta, quien contestó mal fue el
        # servicio de terceros que hay detrás.
        self.assertEqual(resp.status_code, 502)

    @patch("nevera.parsing.parse_compra_text")
    def test_parse_devuelve_502_si_gemini_inventa_una_unidad(self, fake_parse):
        fake_parse.return_value = [item_propuesto(unidad="lonchas")]

        resp = self.client.post(PARSE, {"text": "jamón"}, format="json")

        self.assertEqual(resp.status_code, 502)
        self.assertIn("lonchas", resp.data["detail"])

    # --- POST /api/nevera/items ---

    def test_items_da_de_alta_y_normaliza(self):
        resp = self.client.post(
            ITEMS,
            {"items": [item_propuesto(nombre=f"{PREFIJO}LECHE Entera")]},
            format="json",
        )

        self.assertEqual(resp.status_code, 201)
        creado = NeveraItem.objects.get(nombre__startswith=PREFIJO)
        # `add_items` es quien normaliza el nombre y convierte a unidad base;
        # la API no toca ninguna de las dos cosas.
        self.assertEqual(creado.nombre, f"{PREFIJO}leche entera".lower())
        self.assertEqual(creado.unidad, "ml")
        self.assertEqual(creado.cantidad, Decimal("1000"))
        self.assertEqual(creado.origen, "compra")
        # La respuesta trae las filas ya normalizadas, que es lo que el cliente
        # necesita para pintar la tabla sin volver a pedirla.
        self.assertEqual(resp.data[0]["unidad"], "ml")

    def test_items_suma_cantidad_si_ya_existe(self):
        NeveraItem.objects.create(nombre=f"{PREFIJO}leche", cantidad=Decimal("500"), unidad="ml")

        resp = self.client.post(ITEMS, {"items": [item_propuesto()]}, format="json")

        self.assertEqual(resp.status_code, 201)
        # Una sola fila: 500 ml + 1 l. No se duplica el item.
        item = NeveraItem.objects.get(nombre=f"{PREFIJO}leche", unidad="ml")
        self.assertEqual(item.cantidad, Decimal("1500"))

    def test_items_acepta_varios_de_una_vez(self):
        resp = self.client.post(
            ITEMS,
            {
                "items": [
                    item_propuesto(),
                    item_propuesto(nombre=f"{PREFIJO}pollo", cantidad=500, unidad="g"),
                ]
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(NeveraItem.objects.filter(nombre__startswith=PREFIJO).count(), 2)

    def test_items_rechaza_lista_vacia(self):
        resp = self.client.post(ITEMS, {"items": []}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_items_rechaza_unidad_desconocida_sin_escribir_nada(self):
        resp = self.client.post(
            ITEMS,
            {
                "items": [
                    item_propuesto(),
                    item_propuesto(nombre=f"{PREFIJO}jamon", unidad="lonchas"),
                ]
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        # La validación ocurre antes de tocar la BD: el item bueno de la lista
        # tampoco se guarda. Si validáramos dentro de `add_items`, el primero
        # quedaría escrito y el alta a medias.
        self.assertFalse(NeveraItem.objects.filter(nombre__startswith=PREFIJO).exists())

    def test_items_rechaza_cantidad_negativa(self):
        resp = self.client.post(ITEMS, {"items": [item_propuesto(cantidad=-1)]}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_items_acepta_campos_opcionales_ausentes(self):
        # El cliente puede mandar lo mínimo: el resto tiene defaults.
        resp = self.client.post(
            ITEMS,
            {"items": [{"nombre": f"{PREFIJO}sal", "cantidad": 1, "unidad": "ud"}]},
            format="json",
        )

        self.assertEqual(resp.status_code, 201)
        item = NeveraItem.objects.get(nombre=f"{PREFIJO}sal")
        self.assertIsNone(item.categoria)
        self.assertIsNone(item.fecha_caducidad)
        self.assertFalse(item.es_basico)


if __name__ == "__main__":
    unittest.main()
