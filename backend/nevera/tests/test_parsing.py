import unittest
from datetime import date
from unittest.mock import patch

from nevera.parsing import parse_compra_text


class ParseCompraTextTests(unittest.TestCase):
    @patch("nevera.parsing.send_prompt_to_gemini")
    def test_json_limpio(self, mock_send):
        mock_send.return_value = (
            '[{"nombre": "leche", "cantidad": 1, "unidad": "l", '
            '"categoria": "lacteo", "fecha_caducidad": "2026-09-05"}]'
        )
        items = parse_compra_text("1 leche")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["nombre"], "leche")
        self.assertEqual(items[0]["cantidad"], 1)
        self.assertEqual(items[0]["unidad"], "l")
        self.assertEqual(items[0]["categoria"], "lacteo")
        self.assertEqual(items[0]["fecha_caducidad"], date(2026, 9, 5))
        self.assertFalse(items[0]["es_basico"])

    @patch("nevera.parsing.send_prompt_to_gemini")
    def test_es_basico_se_respeta_y_por_defecto_es_falso(self, mock_send):
        mock_send.return_value = (
            '[{"nombre": "sal", "cantidad": 1, "unidad": "ud", "es_basico": true},'
            ' {"nombre": "pollo", "cantidad": 500, "unidad": "g"}]'
        )
        sal, pollo = parse_compra_text("sal, 500g pollo")
        self.assertTrue(sal["es_basico"])
        # Ausente en la respuesta -> perecedero: es el lado seguro.
        self.assertFalse(pollo["es_basico"])

    @patch("nevera.parsing.send_prompt_to_gemini")
    def test_json_con_fences_markdown(self, mock_send):
        mock_send.return_value = (
            '```json\n[{"nombre": "pollo", "cantidad": 500, "unidad": "g"}]\n```'
        )
        items = parse_compra_text("500g pollo")
        self.assertEqual(items[0]["nombre"], "pollo")
        self.assertIsNone(items[0]["fecha_caducidad"])
        self.assertIsNone(items[0]["categoria"])

    @patch("nevera.parsing.send_prompt_to_gemini")
    def test_respuesta_no_es_lista_lanza_error(self, mock_send):
        mock_send.return_value = '{"nombre": "pollo"}'
        with self.assertRaises(ValueError):
            parse_compra_text("pollo")

    @patch("nevera.parsing.send_prompt_to_gemini")
    def test_json_invalido_lanza_error(self, mock_send):
        mock_send.return_value = "esto no es json"
        with self.assertRaises(ValueError):
            parse_compra_text("algo")

    @patch("nevera.parsing.send_prompt_to_gemini")
    def test_item_incompleto_lanza_error(self, mock_send):
        mock_send.return_value = '[{"cantidad": 1}]'
        with self.assertRaises(ValueError):
            parse_compra_text("algo")

    @patch("nevera.parsing.send_prompt_to_gemini")
    def test_fecha_caducidad_invalida_se_ignora(self, mock_send):
        mock_send.return_value = (
            '[{"nombre": "queso", "cantidad": 1, "unidad": "ud", "fecha_caducidad": "no-es-fecha"}]'
        )
        items = parse_compra_text("queso")
        self.assertIsNone(items[0]["fecha_caducidad"])


if __name__ == "__main__":
    unittest.main()
