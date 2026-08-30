import unittest
from unittest.mock import MagicMock, patch

from nevera.ofertas import analizar_ofertas


def _item(nombre, cantidad, unidad, fecha_caducidad=None):
    return MagicMock(nombre=nombre, cantidad=cantidad, unidad=unidad, fecha_caducidad=fecha_caducidad)


class AnalizarOfertasTests(unittest.TestCase):
    @patch("nevera.ofertas.send_prompt_to_gemini")
    def test_json_limpio(self, mock_send):
        mock_send.return_value = (
            '[{"nombre": "Pechuga de pollo", "motivo": "Ya casi no te queda proteína.", "precio": "5,99 zl"}]'
        )
        items = [_item("pollo", 100, "g")]
        recomendaciones = analizar_ofertas("Pechuga de pollo 5,99 zl", items)

        self.assertEqual(len(recomendaciones), 1)
        self.assertEqual(recomendaciones[0]["nombre"], "Pechuga de pollo")

        prompt_usado = mock_send.call_args[0][0]
        self.assertIn("Pechuga de pollo", prompt_usado)
        self.assertIn("pollo", prompt_usado)  # inventario incluido en el prompt

    @patch("nevera.ofertas.send_prompt_to_gemini")
    def test_nevera_vacia_usa_texto_por_defecto(self, mock_send):
        mock_send.return_value = "[]"
        recomendaciones = analizar_ofertas("algo", [])
        self.assertEqual(recomendaciones, [])
        prompt_usado = mock_send.call_args[0][0]
        self.assertIn("La nevera está vacía", prompt_usado)

    @patch("nevera.ofertas.send_prompt_to_gemini")
    def test_lista_vacia_es_valida(self, mock_send):
        mock_send.return_value = "[]"
        recomendaciones = analizar_ofertas("nada interesante", [_item("pollo", 100, "g")])
        self.assertEqual(recomendaciones, [])

    @patch("nevera.ofertas.send_prompt_to_gemini")
    def test_con_fences_markdown(self, mock_send):
        mock_send.return_value = '```json\n[{"nombre": "x", "motivo": "m", "precio": null}]\n```'
        recomendaciones = analizar_ofertas("x", [_item("pollo", 100, "g")])
        self.assertEqual(recomendaciones[0]["nombre"], "x")

    @patch("nevera.ofertas.send_prompt_to_gemini")
    def test_respuesta_no_lista_lanza_error(self, mock_send):
        mock_send.return_value = '{"nombre": "x"}'
        with self.assertRaises(ValueError):
            analizar_ofertas("x", [_item("pollo", 100, "g")])

    @patch("nevera.ofertas.send_prompt_to_gemini")
    def test_json_invalido_lanza_error(self, mock_send):
        mock_send.return_value = "no json"
        with self.assertRaises(ValueError):
            analizar_ofertas("x", [_item("pollo", 100, "g")])

    @patch("nevera.ofertas.send_prompt_to_gemini")
    def test_recomendacion_incompleta_lanza_error(self, mock_send):
        mock_send.return_value = '[{"motivo": "m"}]'
        with self.assertRaises(ValueError):
            analizar_ofertas("x", [_item("pollo", 100, "g")])


if __name__ == "__main__":
    unittest.main()
