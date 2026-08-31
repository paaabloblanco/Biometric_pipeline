import unittest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from bot import handlers


def _fake_update(chat_id=1, args=None):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_chat.send_action = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args or []
    return update, context


class AnadirFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        handlers._pending_altas.clear()
        patcher = patch("bot.handlers.is_authorized", return_value=True)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self):
        handlers._pending_altas.clear()

    @patch("nevera.parsing.parse_compra_text")
    async def test_anadir_sin_texto_pide_uso(self, mock_parse):
        update, context = _fake_update(args=[])
        await handlers.añadir(update, context)
        update.effective_message.reply_text.assert_awaited_once()
        self.assertIn("Uso", update.effective_message.reply_text.call_args[0][0])
        mock_parse.assert_not_called()

    @patch("nevera.parsing.parse_compra_text")
    async def test_anadir_guarda_pendiente_y_pide_confirmacion(self, mock_parse):
        mock_parse.return_value = [
            {
                "nombre": "leche",
                "cantidad": 1,
                "unidad": "l",
                "categoria": "lacteo",
                "fecha_caducidad": None,
            }
        ]
        update, context = _fake_update(chat_id=42, args=["1", "leche"])
        await handlers.añadir(update, context)

        self.assertIn(42, handlers._pending_altas)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("leche", texto)
        self.assertIn("/confirmar", texto)

    @patch("nevera.parsing.parse_compra_text")
    async def test_anadir_unidad_desconocida_no_guarda_pendiente(self, mock_parse):
        mock_parse.return_value = [
            {
                "nombre": "misterio",
                "cantidad": 1,
                "unidad": "bolsas",
                "categoria": None,
                "fecha_caducidad": None,
            }
        ]
        update, context = _fake_update(chat_id=7, args=["misterio"])
        await handlers.añadir(update, context)

        self.assertNotIn(7, handlers._pending_altas)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("No se pudo interpretar", texto)

    async def test_confirmar_sin_pendiente(self):
        update, context = _fake_update(chat_id=99)
        await handlers.confirmar(update, context)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("No hay ninguna alta pendiente", texto)

    @patch("nevera.services.add_items")
    async def test_confirmar_con_pendiente_llama_add_items(self, mock_add):
        handlers._pending_altas[5] = [{"nombre": "leche", "cantidad": 1, "unidad": "ml"}]
        update, context = _fake_update(chat_id=5)
        await handlers.confirmar(update, context)

        mock_add.assert_called_once()
        self.assertNotIn(5, handlers._pending_altas)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("Añadido", texto)

    async def test_cancelar_sin_pendiente(self):
        update, context = _fake_update(chat_id=1)
        await handlers.cancelar(update, context)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("No había ninguna alta pendiente", texto)

    async def test_cancelar_con_pendiente(self):
        handlers._pending_altas[1] = [{"nombre": "x"}]
        update, context = _fake_update(chat_id=1)
        await handlers.cancelar(update, context)
        self.assertNotIn(1, handlers._pending_altas)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("cancelada", texto)


class BorrarEditarTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch("bot.handlers.is_authorized", return_value=True)
        self.addCleanup(patcher.stop)
        patcher.start()

    async def test_borrar_sin_args(self):
        update, context = _fake_update(args=[])
        await handlers.borrar(update, context)
        self.assertIn("Uso", update.effective_message.reply_text.call_args[0][0])

    async def test_borrar_id_no_numerico(self):
        update, context = _fake_update(args=["abc"])
        await handlers.borrar(update, context)
        self.assertIn("número", update.effective_message.reply_text.call_args[0][0])

    @patch("nevera.services.delete_item", return_value=True)
    async def test_borrar_ok(self, mock_delete):
        update, context = _fake_update(args=["3"])
        await handlers.borrar(update, context)
        mock_delete.assert_called_once_with(3)
        self.assertIn("Borrado", update.effective_message.reply_text.call_args[0][0])

    async def test_editar_argumentos_insuficientes(self):
        update, context = _fake_update(args=["3"])
        await handlers.editar(update, context)
        self.assertIn("Uso", update.effective_message.reply_text.call_args[0][0])

    async def test_editar_id_no_numerico(self):
        update, context = _fake_update(args=["abc", "cantidad=1"])
        await handlers.editar(update, context)
        self.assertIn("número", update.effective_message.reply_text.call_args[0][0])

    async def test_editar_campo_desconocido(self):
        update, context = _fake_update(args=["3", "color=rojo"])
        await handlers.editar(update, context)
        self.assertIn("desconocido", update.effective_message.reply_text.call_args[0][0])

    async def test_editar_fecha_invalida(self):
        update, context = _fake_update(args=["3", "fecha_caducidad=mañana"])
        await handlers.editar(update, context)
        self.assertIn("inválida", update.effective_message.reply_text.call_args[0][0])

    @patch("nevera.services.edit_item")
    async def test_editar_ok(self, mock_edit):
        mock_edit.return_value = MagicMock()
        update, context = _fake_update(
            args=["3", "cantidad=1", "unidad=kg", "fecha_caducidad=2026-09-01"]
        )
        await handlers.editar(update, context)
        mock_edit.assert_called_once_with(
            3, cantidad=1.0, unidad="kg", fecha_caducidad=date(2026, 9, 1)
        )
        self.assertIn("Actualizado", update.effective_message.reply_text.call_args[0][0])

    @patch("nevera.services.edit_item", return_value=None)
    async def test_editar_item_inexistente(self, mock_edit):
        update, context = _fake_update(args=["999", "cantidad=1"])
        await handlers.editar(update, context)
        self.assertIn("No existe", update.effective_message.reply_text.call_args[0][0])


class NeveraListTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch("bot.handlers.is_authorized", return_value=True)
        self.addCleanup(patcher.stop)
        patcher.start()

    @patch("nevera.services.list_all", return_value=[])
    async def test_nevera_vacia(self, mock_list):
        update, context = _fake_update()
        await handlers.nevera_cmd(update, context)
        self.assertIn("vacía", update.effective_message.reply_text.call_args[0][0])

    @patch("nevera.services.list_all")
    async def test_nevera_con_items(self, mock_list):
        item = MagicMock(
            id=1,
            nombre="leche",
            categoria="lacteo",
            cantidad=1000,
            unidad="ml",
            fecha_caducidad=None,
        )
        mock_list.return_value = [item]
        update, context = _fake_update()
        await handlers.nevera_cmd(update, context)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("lacteo", texto)
        self.assertIn("leche", texto)
        self.assertIn("1 L", texto)


class FormatoNeveraTests(unittest.TestCase):
    def test_agrupa_por_categoria_y_alerta_caducidad_proxima(self):
        proximo = MagicMock(
            id=1,
            nombre="yogur",
            categoria="lacteo",
            cantidad=4,
            unidad="ud",
            fecha_caducidad=date.today(),
        )
        lejano = MagicMock(
            id=2,
            nombre="arroz",
            categoria="cereal",
            cantidad=1000,
            unidad="g",
            fecha_caducidad=date(2027, 1, 1),
        )
        texto = handlers._formato_nevera([proximo, lejano])
        self.assertIn("caduca pronto", texto)
        self.assertNotIn("arroz ⚠️", texto)
        self.assertIn("1 kg", texto)


class ComerHechoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        handlers._pending_recetas.clear()
        patcher = patch("bot.handlers.is_authorized", return_value=True)
        self.addCleanup(patcher.stop)
        patcher.start()

    def tearDown(self):
        handlers._pending_recetas.clear()

    @patch("nevera.services.get_items_by_expiry", return_value=[])
    async def test_comer_nevera_vacia(self, mock_items):
        update, context = _fake_update()
        await handlers.comer(update, context)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("vacía", texto)

    @patch("supabase_data.services.get_recent_analyses")
    @patch("nevera.suggestions.suggest_recipes")
    @patch("nevera.services.get_items_by_expiry")
    async def test_comer_guarda_pendiente_y_responde(self, mock_items, mock_suggest, mock_analyses):
        mock_items.return_value = [MagicMock(nombre="pollo")]
        mock_analyses.return_value = [{"analysis_date": date(2026, 8, 29), "analysis_text": "ok"}]
        mock_suggest.return_value = [
            {
                "nombre": "Pollo al horno",
                "descripcion": "Fácil",
                "ingredientes": [{"nombre": "pollo", "cantidad": 200, "unidad": "g"}],
            }
        ]
        update, context = _fake_update(chat_id=11)
        await handlers.comer(update, context)

        self.assertIn(11, handlers._pending_recetas)
        texto = update.effective_message.reply_text.call_args_list[0][0][0]
        self.assertIn("Pollo al horno", texto)
        self.assertIn("/hecho", texto)

    async def test_hecho_sin_args(self):
        update, context = _fake_update()
        await handlers.hecho(update, context)
        self.assertIn("Uso", update.effective_message.reply_text.call_args[0][0])

    async def test_hecho_sin_sugerencia_pendiente(self):
        update, context = _fake_update(chat_id=20, args=["1"])
        await handlers.hecho(update, context)
        self.assertIn(
            "No hay ninguna sugerencia", update.effective_message.reply_text.call_args[0][0]
        )

    async def test_hecho_indice_fuera_de_rango(self):
        handlers._pending_recetas[21] = [{"nombre": "x", "ingredientes": []}]
        update, context = _fake_update(chat_id=21, args=["5"])
        await handlers.hecho(update, context)
        self.assertIn("entre 1 y 1", update.effective_message.reply_text.call_args[0][0])

    @patch("nevera.services.consume_items")
    async def test_hecho_ok_consume_y_limpia_pendiente(self, mock_consume):
        mock_consume.return_value = {
            "aplicados": [{"nombre": "pollo", "unidad": "g", "restante": 300.0}],
            "no_encontrados": [],
        }
        handlers._pending_recetas[22] = [
            {
                "nombre": "Pollo",
                "ingredientes": [{"nombre": "pollo", "cantidad": 200, "unidad": "g"}],
            }
        ]
        update, context = _fake_update(chat_id=22, args=["1"])
        await handlers.hecho(update, context)

        mock_consume.assert_called_once_with([{"nombre": "pollo", "cantidad": 200, "unidad": "g"}])
        self.assertNotIn(22, handlers._pending_recetas)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("Pollo", texto)
        self.assertIn("300.0 g", texto)

    @patch("nevera.services.consume_items")
    async def test_hecho_avisa_ingredientes_no_encontrados(self, mock_consume):
        mock_consume.return_value = {
            "aplicados": [],
            "no_encontrados": [{"nombre": "pollo", "unidad": "g", "cantidad": 200}],
        }
        handlers._pending_recetas[23] = [
            {
                "nombre": "Pollo",
                "ingredientes": [{"nombre": "pollo", "cantidad": 200, "unidad": "g"}],
            }
        ]
        update, context = _fake_update(chat_id=23, args=["1"])
        await handlers.hecho(update, context)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("No encontrados", texto)


class ComprarTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch("bot.handlers.is_authorized", return_value=True)
        self.addCleanup(patcher.stop)
        patcher.start()

    async def test_comprar_sin_texto_pide_uso(self):
        update, context = _fake_update(args=[])
        await handlers.comprar(update, context)
        self.assertIn("Uso", update.effective_message.reply_text.call_args[0][0])

    @patch("nevera.ofertas.analizar_ofertas")
    @patch("nevera.services.list_all", return_value=[])
    async def test_comprar_sin_recomendaciones(self, mock_list, mock_analizar):
        mock_analizar.return_value = []
        update, context = _fake_update(args=["pollo", "5,99", "zl"])
        await handlers.comprar(update, context)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("Ninguna oferta", texto)

    @patch("nevera.ofertas.analizar_ofertas")
    @patch("nevera.services.list_all", return_value=[])
    async def test_comprar_con_recomendaciones(self, mock_list, mock_analizar):
        mock_analizar.return_value = [
            {
                "nombre": "Pechuga de pollo",
                "motivo": "Se te acaba la proteína.",
                "precio": "5,99 zl",
            }
        ]
        update, context = _fake_update(args=["pechuga", "5,99", "zl"])
        await handlers.comprar(update, context)
        texto = update.effective_message.reply_text.call_args_list[0][0][0]
        self.assertIn("Pechuga de pollo", texto)
        self.assertIn("5,99 zl", texto)

    @patch(
        "nevera.ofertas.analizar_ofertas", side_effect=ValueError("Gemini no devolvió JSON válido")
    )
    @patch("nevera.services.list_all", return_value=[])
    async def test_comprar_error_en_analisis(self, mock_list, mock_analizar):
        update, context = _fake_update(args=["texto", "raro"])
        await handlers.comprar(update, context)
        texto = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("No se pudo analizar", texto)


if __name__ == "__main__":
    unittest.main()
