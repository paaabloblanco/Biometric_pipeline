import unittest
from decimal import Decimal

from nevera.units import format_cantidad, to_base


class ToBaseTests(unittest.TestCase):
    def test_masa(self):
        self.assertEqual(to_base(1, "kg"), (Decimal(1000), "g"))
        self.assertEqual(to_base(500, "g"), (Decimal(500), "g"))
        self.assertEqual(to_base(1, "Kg"), (Decimal(1000), "g"))

    def test_volumen(self):
        self.assertEqual(to_base(1, "L"), (Decimal(1000), "ml"))
        self.assertEqual(to_base(250, "ml"), (Decimal(250), "ml"))

    def test_unidad(self):
        self.assertEqual(to_base(4, "uds"), (Decimal(4), "ud"))

    def test_unidad_desconocida(self):
        with self.assertRaises(ValueError):
            to_base(1, "bolsas")


class FormatCantidadTests(unittest.TestCase):
    def test_masa_pequena_se_muestra_en_gramos(self):
        self.assertEqual(format_cantidad(500, "g"), "500 g")

    def test_masa_grande_se_muestra_en_kg(self):
        self.assertEqual(format_cantidad(1500, "g"), "1.5 kg")

    def test_volumen_grande_se_muestra_en_litros(self):
        self.assertEqual(format_cantidad(2000, "ml"), "2 L")

    def test_unidad_se_muestra_tal_cual(self):
        self.assertEqual(format_cantidad(3, "ud"), "3 ud")


if __name__ == "__main__":
    unittest.main()
