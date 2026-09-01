from typing import ClassVar

from django.db import models


class NeveraItem(models.Model):
    ORIGEN_CHOICES: ClassVar = [
        ("compra", "Compra"),
        ("manual", "Manual"),
    ]

    nombre = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    unidad = models.CharField(max_length=20)
    categoria = models.CharField(max_length=50, null=True, blank=True)
    fecha_caducidad = models.DateField(null=True, blank=True)
    fecha_añadido = models.DateTimeField(auto_now_add=True)
    origen = models.CharField(max_length=10, choices=ORIGEN_CHOICES, default="manual")

    # Discriminador de *cómo se gestiona el stock*, no de qué tipo de alimento
    # es (para eso está `categoria`). Un básico de despensa —sal, especias,
    # aceite, vinagre— se gestiona por presencia (hay / no hay), no por
    # cantidad: su `cantidad` es un valor testigo sin significado real.
    #
    # Al existir este campo, `fecha_caducidad = NULL` recupera un único
    # significado: "perecedero cuyo caducidad no anoté". Antes estaba
    # sobrecargado y valía también para "no caduca en la práctica".
    es_basico = models.BooleanField(
        default=False,
        verbose_name="básico de despensa",
        help_text=(
            "Si está marcado: no entra en el ranking de caducidad y /hecho no "
            "le descuenta cantidad. Solo sale del inventario al borrarlo a mano."
        ),
    )

    class Meta:
        db_table = "nevera_items"
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["nombre", "unidad"], name="unique_nombre_unidad"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.cantidad} {self.unidad})"
