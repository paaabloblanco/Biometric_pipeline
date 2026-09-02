"""Tests de los endpoints de escritura de la nevera (SDD-web fase 4).

Mismo patrón que el resto del proyecto: no hay BD de test, así que los datos se
siembran con un prefijo centinela y se limpian en `tearDown`.
"""

import os
import unittest
from datetime import date
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from nevera.models import NeveraItem

User = get_user_model()

PREFIJO = "__test_api_write__"
PASSWORD = "una-clave-de-test-larga-123"


class NeveraWriteEndpointsTests(unittest.TestCase):
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
        self.item = NeveraItem.objects.create(
            nombre=f"{PREFIJO}pollo",
            cantidad=Decimal("500"),
            unidad="g",
            categoria="proteina",
            fecha_caducidad=date(2030, 1, 1),
        )

    def tearDown(self):
        User.objects.filter(username__startswith=PREFIJO).delete()
        NeveraItem.objects.filter(nombre__startswith=PREFIJO).delete()

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def _ruta(self, item_id=None):
        return f"/api/nevera/items/{item_id or self.item.id}"

    # --- auth ---

    def test_escritura_exige_token(self):
        for metodo in (self.client.patch, self.client.delete):
            with self.subTest(metodo=metodo.__name__):
                self.assertEqual(metodo(self._ruta()).status_code, 401)
        # Y no ha tocado nada.
        self.assertTrue(NeveraItem.objects.filter(id=self.item.id).exists())

    # --- PATCH ---

    def test_patch_actualiza_solo_los_campos_enviados(self):
        self._auth()
        resp = self.client.patch(self._ruta(), {"cantidad": "300"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, Decimal("300"))
        # Lo no enviado sigue igual: eso es lo que distingue PATCH de PUT.
        self.assertEqual(self.item.unidad, "g")
        self.assertEqual(self.item.categoria, "proteina")
        self.assertEqual(self.item.fecha_caducidad, date(2030, 1, 1))

    def test_patch_normaliza_el_nombre_como_el_bot(self):
        self._auth()
        resp = self.client.patch(
            self._ruta(), {"nombre": f"  {PREFIJO}POLLO  Asado "}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.nombre, f"{PREFIJO.lower()}pollo asado")

    def test_patch_convierte_cantidad_y_unidad_a_la_unidad_base(self):
        self._auth()
        resp = self.client.patch(self._ruta(), {"cantidad": "1.5", "unidad": "kg"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.unidad, "g")
        self.assertEqual(self.item.cantidad, Decimal("1500"))

    def test_patch_permite_quitar_la_caducidad_y_la_categoria(self):
        self._auth()
        resp = self.client.patch(
            self._ruta(), {"fecha_caducidad": None, "categoria": ""}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.fecha_caducidad)
        self.assertIsNone(self.item.categoria)

    def test_patch_marca_basico(self):
        self._auth()
        resp = self.client.patch(self._ruta(), {"es_basico": True}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.es_basico)

    def test_patch_rechaza_unidad_sin_cantidad(self):
        self._auth()
        resp = self.client.patch(self._ruta(), {"unidad": "kg"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cantidad", resp.data["detail"])
        self.item.refresh_from_db()
        self.assertEqual(self.item.unidad, "g")

    def test_patch_rechaza_cuerpo_vacio(self):
        self._auth()
        resp = self.client.patch(self._ruta(), {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_patch_rechaza_cantidad_negativa(self):
        self._auth()
        resp = self.client.patch(self._ruta(), {"cantidad": "-5"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, Decimal("500"))

    def test_patch_devuelve_409_si_choca_con_la_constraint(self):
        NeveraItem.objects.create(nombre=f"{PREFIJO}pavo", cantidad=Decimal("200"), unidad="g")
        self._auth()
        resp = self.client.patch(self._ruta(), {"nombre": f"{PREFIJO}pavo"}, format="json")
        self.assertEqual(resp.status_code, 409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.nombre, f"{PREFIJO}pollo")

    def test_patch_de_item_inexistente_da_404(self):
        self._auth()
        resp = self.client.patch(self._ruta(item_id=99_999_999), {"cantidad": "1"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_patch_devuelve_el_item_actualizado(self):
        self._auth()
        resp = self.client.patch(self._ruta(), {"cantidad": "250"}, format="json")
        self.assertEqual(resp.data["id"], self.item.id)
        self.assertEqual(resp.data["cantidad"], "250.00")
        self.assertEqual(resp.data["unidad"], "g")

    # --- DELETE ---

    def test_delete_borra_el_item(self):
        self._auth()
        resp = self.client.delete(self._ruta())
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(NeveraItem.objects.filter(id=self.item.id).exists())

    def test_delete_de_item_inexistente_da_404(self):
        self._auth()
        resp = self.client.delete(self._ruta(item_id=99_999_999))
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
