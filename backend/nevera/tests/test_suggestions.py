import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from nevera.suggestions import format_inventario, suggest_recipes


def _item(nombre, cantidad, unidad, fecha_caducidad=None, es_basico=False):
    # `es_basico` se pasa explícito: un MagicMock devuelve un atributo truthy
    # para lo que no se le declara, y todo el inventario acabaría en despensa.
    return MagicMock(
        nombre=nombre,
        cantidad=cantidad,
        unidad=unidad,
        fecha_caducidad=fecha_caducidad,
        es_basico=es_basico,
    )


class SuggestRecipesTests(unittest.TestCase):
    def test_nevera_vacia_lanza_error(self):
        with self.assertRaises(ValueError):
            suggest_recipes([], None)

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_json_limpio(self, mock_send):
        mock_send.return_value = (
            '[{"nombre": "Pollo con arroz", "descripcion": "Rico en proteína.", '
            '"ingredientes": [{"nombre": "pollo", "cantidad": 200, "unidad": "g"}, '
            '{"nombre": "arroz", "cantidad": 100, "unidad": "g"}]}]'
        )
        items = [_item("pollo", 500, "g"), _item("arroz", 1000, "g")]
        recetas = suggest_recipes(
            items, {"analysis_date": date(2026, 8, 29), "analysis_text": "buena recuperación"}
        )

        self.assertEqual(len(recetas), 1)
        self.assertEqual(recetas[0]["nombre"], "Pollo con arroz")
        self.assertEqual(len(recetas[0]["ingredientes"]), 2)

        prompt_usado = mock_send.call_args[0][0]
        self.assertIn("pollo", prompt_usado)
        self.assertIn("buena recuperación", prompt_usado)
        self.assertIn("fútbol sala", prompt_usado)
        self.assertIn("antiinflamatorias", prompt_usado)
        self.assertIn("comida real", prompt_usado)

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_prompt_acota_raciones_y_equipamiento(self, mock_send):
        """Sin esto Gemini vacía el stock en un plato (5 plátanos en una
        frittata) y propone recetas al horno que no se pueden cocinar."""
        mock_send.return_value = (
            '[{"nombre": "x", "descripcion": "d", "ingredientes": '
            '[{"nombre": "pollo", "cantidad": 150, "unidad": "g"}]}]'
        )
        suggest_recipes([_item("pollo", 700, "g")], None)
        prompt_usado = mock_send.call_args[0][0]

        self.assertIn("UNA sola persona y UNA sola comida", prompt_usado)
        self.assertIn("STOCK TOTAL disponible", prompt_usado)
        self.assertIn("microondas, sartén y olla", prompt_usado)
        self.assertIn("NO tiene horno", prompt_usado)
        self.assertIn("MISMA unidad", prompt_usado)

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_sin_analisis_previo_usa_texto_por_defecto(self, mock_send):
        mock_send.return_value = '[{"nombre": "x", "descripcion": "d", "ingredientes": [{"nombre": "pollo", "cantidad": 1, "unidad": "ud"}]}]'
        suggest_recipes([_item("pollo", 1, "ud")], None)
        prompt_usado = mock_send.call_args[0][0]
        self.assertIn("sin análisis previo", prompt_usado)

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_con_fences_markdown(self, mock_send):
        mock_send.return_value = (
            '```json\n[{"nombre": "x", "descripcion": "d", '
            '"ingredientes": [{"nombre": "pollo", "cantidad": 1, "unidad": "ud"}]}]\n```'
        )
        recetas = suggest_recipes([_item("pollo", 1, "ud")], None)
        self.assertEqual(recetas[0]["nombre"], "x")

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_respuesta_no_lista_lanza_error(self, mock_send):
        mock_send.return_value = '{"nombre": "x"}'
        with self.assertRaises(ValueError):
            suggest_recipes([_item("pollo", 1, "ud")], None)

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_json_invalido_lanza_error(self, mock_send):
        mock_send.return_value = "no json"
        with self.assertRaises(ValueError):
            suggest_recipes([_item("pollo", 1, "ud")], None)

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_receta_incompleta_lanza_error(self, mock_send):
        mock_send.return_value = '[{"descripcion": "d"}]'
        with self.assertRaises(ValueError):
            suggest_recipes([_item("pollo", 1, "ud")], None)

    @patch("nevera.suggestions.send_prompt_to_gemini")
    def test_ingrediente_incompleto_lanza_error(self, mock_send):
        mock_send.return_value = '[{"nombre": "x", "ingredientes": [{"cantidad": 1}]}]'
        with self.assertRaises(ValueError):
            suggest_recipes([_item("pollo", 1, "ud")], None)


class FormatInventarioTests(unittest.TestCase):
    def test_separa_perecederos_de_despensa(self):
        texto = format_inventario(
            [
                _item("pollo", 500, "g", fecha_caducidad=date(2026, 9, 3)),
                _item("sal", 1, "ud", es_basico=True),
            ]
        )

        self.assertIn("PERECEDEROS", texto)
        self.assertIn("- pollo: 500 g, caduca 2026-09-03", texto)
        self.assertIn("DESPENSA", texto)
        # El básico aparece (hace falta para cocinar) pero sin cantidad ni
        # caducidad: su cantidad es un valor testigo, no un dato real.
        self.assertIn("- sal", texto)
        self.assertNotIn("sal: 1 ud", texto)
        self.assertLess(texto.index("PERECEDEROS"), texto.index("DESPENSA"))

    def test_sin_basicos_no_pone_bloque_de_despensa(self):
        texto = format_inventario([_item("pollo", 500, "g")])
        self.assertIn("PERECEDEROS", texto)
        self.assertNotIn("DESPENSA", texto)


if __name__ == "__main__":
    unittest.main()
