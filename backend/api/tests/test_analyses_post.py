"""Tests de `POST /api/analyses` (SDD-web fase 6).

Mismo patrón que el resto: sin BD de test, usuario con prefijo centinela y
limpieza en `tearDown`.

**Gemini se sustituye por un doble (`mock`) en todos los tests.** Llamarlo de
verdad gastaría cuota, tardaría 30 s por test y daría un resultado distinto
cada vez, así que el test dependería de un servicio externo para comprobar algo
que no es suyo. Lo que se prueba aquí es la **capa HTTP**: que se exige token,
que la instrucción por defecto se aplica, que el 409 sale cuando toca y que el
texto de Gemini llega al cliente. Que Gemini responda bien no es competencia de
este test.
"""

import os
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import connections
from rest_framework.test import APIClient

from health_ai.config import DEFAULT_INSTRUCTION
from health_ai.locks import LOCK_ANALISIS_DIARIO, advisory_lock
from supabase_data.models import AiAnalysisLog

User = get_user_model()

PREFIJO = "__test_api_analyses__"
PASSWORD = "una-clave-de-test-larga-123"
RESPUESTA_FALSA = "Análisis de prueba: todo en orden."


class AnalysesPostTests(unittest.TestCase):
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
        # Qué análisis había antes, para no borrar en tearDown uno real.
        self.previos = set(AiAnalysisLog.objects.values_list("id", flat=True))

    def tearDown(self):
        User.objects.filter(username__startswith=PREFIJO).delete()
        AiAnalysisLog.objects.exclude(id__in=self.previos).delete()

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    # --- auth ---

    def test_exige_token(self):
        with patch("health_ai.pruebas.send_prompt_to_gemini") as gemini:
            self.assertEqual(self.client.post("/api/analyses", {}, format="json").status_code, 401)
        # Y no ha llegado a llamar a Gemini: el permiso se evalúa antes.
        gemini.assert_not_called()

    # --- camino feliz ---

    def test_devuelve_el_analisis_generado(self):
        self._auth()
        with patch("health_ai.pruebas.send_prompt_to_gemini", return_value=RESPUESTA_FALSA):
            resp = self.client.post("/api/analyses", {"instruction": "Analiza el sueño."})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["analysis_text"], RESPUESTA_FALSA)
        self.assertEqual(resp.data["user_instruction"], "Analiza el sueño.")
        self.assertIn("analysis_date", resp.data)

    def test_sin_instruccion_usa_la_de_por_defecto(self):
        """La web y `/analisis` sin argumentos en Telegram tienen que pedir lo
        mismo: si no, el mismo botón daría análisis distintos según el canal."""
        self._auth()
        with patch(
            "health_ai.pruebas.send_prompt_to_gemini", return_value=RESPUESTA_FALSA
        ) as gemini:
            resp = self.client.post("/api/analyses", {}, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["user_instruction"], DEFAULT_INSTRUCTION)
        # La instrucción viaja dentro del prompt que se le manda a Gemini.
        self.assertIn(DEFAULT_INSTRUCTION, gemini.call_args.args[0])

    def test_el_analisis_queda_guardado(self):
        self._auth()
        with patch("health_ai.pruebas.send_prompt_to_gemini", return_value=RESPUESTA_FALSA):
            self.client.post("/api/analyses", {}, format="json")

        self.assertTrue(AiAnalysisLog.objects.filter(analysis_text=RESPUESTA_FALSA).exists())

    # --- validación ---

    def test_instruccion_demasiado_larga_da_400(self):
        """El texto se incrusta en el prompt de Gemini, así que va acotado."""
        self._auth()
        with patch("health_ai.pruebas.send_prompt_to_gemini") as gemini:
            resp = self.client.post("/api/analyses", {"instruction": "x" * 5000}, format="json")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.data)
        gemini.assert_not_called()

    # --- el lock ---

    def test_devuelve_409_si_otro_proceso_esta_analizando(self):
        """El caso que motiva el advisory lock: el bot analizando y la web
        pidiendo otro a la vez.

        El lock se coge desde otro hilo porque la conexión de Django es
        thread-local, y un hilo distinto es una conexión distinta: la misma
        situación que dos procesos, pero comprobable en un test.
        """
        self._auth()
        cogido = threading.Event()
        soltar = threading.Event()

        def _ocupar_el_lock():
            try:
                with advisory_lock(LOCK_ANALISIS_DIARIO):
                    cogido.set()
                    soltar.wait(timeout=10)
            finally:
                connections.close_all()

        hilo = threading.Thread(target=_ocupar_el_lock)
        hilo.start()
        try:
            self.assertTrue(cogido.wait(timeout=10), "el hilo no llegó a coger el lock")
            with patch("health_ai.pruebas.send_prompt_to_gemini") as gemini:
                resp = self.client.post("/api/analyses", {}, format="json")
        finally:
            soltar.set()
            hilo.join(timeout=10)

        self.assertEqual(resp.status_code, 409)
        self.assertIn("detail", resp.data)
        # Lo importante: no se gastó cuota de Gemini.
        gemini.assert_not_called()

    def test_el_lock_queda_libre_despues(self):
        """Si un análisis dejara el lock cogido, todos los siguientes darían
        409 para siempre."""
        self._auth()
        with patch("health_ai.pruebas.send_prompt_to_gemini", return_value=RESPUESTA_FALSA):
            self.client.post("/api/analyses", {}, format="json")
            segunda = self.client.post("/api/analyses", {}, format="json")

        self.assertEqual(segunda.status_code, 200)


if __name__ == "__main__":
    unittest.main()
