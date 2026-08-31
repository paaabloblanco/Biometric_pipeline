"""Tests del login JWT contra la base real (mismo patrón que nevera/tests:
sin DB de test separada, usuarios con prefijo único y limpieza en tearDown)."""

import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

PREFIJO = "__test_api__"
PASSWORD = "una-clave-de-test-larga-123"


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.client = APIClient()

    def tearDown(self):
        User.objects.filter(username__startswith=PREFIJO).delete()

    def _crear(self, sufijo, *, superuser):
        return User.objects.create_user(
            username=f"{PREFIJO}{sufijo}",
            password=PASSWORD,
            is_staff=superuser,
            is_superuser=superuser,
        )

    def test_login_ok_devuelve_tokens(self):
        u = self._crear("dueno", superuser=True)
        resp = self.client.post(
            "/api/auth/login", {"username": u.username, "password": PASSWORD}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_password_mala(self):
        u = self._crear("dueno", superuser=True)
        resp = self.client.post(
            "/api/auth/login", {"username": u.username, "password": "incorrecta"}, format="json"
        )
        self.assertEqual(resp.status_code, 401)

    def test_login_usuario_no_dueno_rechazado(self):
        u = self._crear("normal", superuser=False)
        resp = self.client.post(
            "/api/auth/login", {"username": u.username, "password": PASSWORD}, format="json"
        )
        self.assertEqual(resp.status_code, 401)

    def test_refresh_devuelve_nuevo_access(self):
        u = self._crear("dueno", superuser=True)
        login = self.client.post(
            "/api/auth/login", {"username": u.username, "password": PASSWORD}, format="json"
        )
        resp = self.client.post(
            "/api/auth/refresh", {"refresh": login.data["refresh"]}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)


if __name__ == "__main__":
    unittest.main()
