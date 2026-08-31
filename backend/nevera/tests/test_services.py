"""Tests contra la base real de Supabase (mismo patrón que el resto del
proyecto: sin DB de test separada). Usa nombres con prefijo único y limpia
en tearDown para no dejar basura en nevera_items."""

import os
import unittest
from datetime import date, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from nevera import services
from nevera.models import NeveraItem

PREFIJO = "__test_nevera__"


class NeveraServicesTests(unittest.TestCase):
    def tearDown(self):
        NeveraItem.objects.filter(nombre__startswith=PREFIJO).delete()

    def test_add_items_crea_nuevo(self):
        creados = services.add_items(
            [{"nombre": f"{PREFIJO} leche", "cantidad": 1, "unidad": "L", "categoria": "lacteo"}],
            origen="manual",
        )
        self.assertEqual(len(creados), 1)
        item = NeveraItem.objects.get(nombre=f"{PREFIJO} leche", unidad="ml")
        self.assertEqual(float(item.cantidad), 1000.0)
        self.assertEqual(item.categoria, "lacteo")
        self.assertEqual(item.origen, "manual")

    def test_add_items_suma_si_ya_existe(self):
        services.add_items([{"nombre": f"{PREFIJO} Leche", "cantidad": 1, "unidad": "l"}])
        services.add_items([{"nombre": f"{PREFIJO} leche", "cantidad": 200, "unidad": "ml"}])
        item = NeveraItem.objects.get(nombre=f"{PREFIJO} leche", unidad="ml")
        self.assertEqual(float(item.cantidad), 1200.0)

    def test_get_items_by_expiry_orden_y_filtro(self):
        hoy = date.today()
        services.add_items(
            [
                {
                    "nombre": f"{PREFIJO} pronto",
                    "cantidad": 1,
                    "unidad": "ud",
                    "fecha_caducidad": hoy + timedelta(days=1),
                },
                {
                    "nombre": f"{PREFIJO} lejos",
                    "cantidad": 1,
                    "unidad": "ud",
                    "fecha_caducidad": hoy + timedelta(days=30),
                },
                {"nombre": f"{PREFIJO} sin_fecha", "cantidad": 1, "unidad": "ud"},
            ]
        )

        todos = [i for i in services.get_items_by_expiry() if i.nombre.startswith(PREFIJO)]
        self.assertEqual(
            [i.nombre for i in todos],
            [f"{PREFIJO} pronto", f"{PREFIJO} lejos", f"{PREFIJO} sin_fecha"],
        )

        urgentes = [
            i for i in services.get_items_by_expiry(dias_limite=5) if i.nombre.startswith(PREFIJO)
        ]
        self.assertEqual([i.nombre for i in urgentes], [f"{PREFIJO} pronto"])

    def test_consume_items_resta_y_elimina(self):
        services.add_items([{"nombre": f"{PREFIJO} pollo", "cantidad": 500, "unidad": "g"}])

        resultado = services.consume_items(
            [{"nombre": f"{PREFIJO} pollo", "unidad": "g", "cantidad": 200}]
        )
        self.assertEqual(
            resultado["aplicados"],
            [{"nombre": f"{PREFIJO} pollo", "unidad": "g", "restante": 300.0}],
        )
        self.assertTrue(NeveraItem.objects.filter(nombre=f"{PREFIJO} pollo", unidad="g").exists())

        resultado = services.consume_items(
            [{"nombre": f"{PREFIJO} pollo", "unidad": "g", "cantidad": 300}]
        )
        self.assertEqual(resultado["aplicados"][0]["restante"], 0)
        self.assertFalse(NeveraItem.objects.filter(nombre=f"{PREFIJO} pollo", unidad="g").exists())

    def test_consume_items_no_encontrado(self):
        resultado = services.consume_items(
            [{"nombre": f"{PREFIJO} inexistente", "unidad": "g", "cantidad": 1}]
        )
        self.assertEqual(resultado["aplicados"], [])
        self.assertEqual(len(resultado["no_encontrados"]), 1)

    def test_conversion_de_unidades_unifica_items(self):
        services.add_items([{"nombre": f"{PREFIJO} arroz", "cantidad": 1, "unidad": "kg"}])
        services.add_items([{"nombre": f"{PREFIJO} arroz", "cantidad": 500, "unidad": "g"}])
        item = NeveraItem.objects.get(nombre=f"{PREFIJO} arroz", unidad="g")
        self.assertEqual(float(item.cantidad), 1500.0)

        resultado = services.consume_items(
            [{"nombre": f"{PREFIJO} arroz", "unidad": "kg", "cantidad": 0.5}]
        )
        self.assertEqual(resultado["aplicados"][0]["restante"], 1000.0)

    def test_unidad_desconocida_lanza_error(self):
        with self.assertRaises(ValueError):
            services.add_items(
                [{"nombre": f"{PREFIJO} misterio", "cantidad": 1, "unidad": "bolsas"}]
            )

    def test_delete_item(self):
        [item] = services.add_items([{"nombre": f"{PREFIJO} yogur", "cantidad": 4, "unidad": "ud"}])
        self.assertTrue(services.delete_item(item.id))
        self.assertFalse(NeveraItem.objects.filter(id=item.id).exists())
        self.assertFalse(services.delete_item(item.id))

    def test_edit_item(self):
        [item] = services.add_items(
            [{"nombre": f"{PREFIJO} queso", "cantidad": 200, "unidad": "g"}]
        )
        nueva_fecha = date.today() + timedelta(days=10)

        actualizado = services.edit_item(
            item.id, cantidad=1, unidad="kg", categoria="lacteo", fecha_caducidad=nueva_fecha
        )
        self.assertEqual(float(actualizado.cantidad), 1000.0)
        self.assertEqual(actualizado.unidad, "g")
        self.assertEqual(actualizado.categoria, "lacteo")
        self.assertEqual(actualizado.fecha_caducidad, nueva_fecha)

        self.assertIsNone(services.edit_item(999999999, cantidad=1))


if __name__ == "__main__":
    unittest.main()
