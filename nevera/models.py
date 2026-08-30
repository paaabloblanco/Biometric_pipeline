from typing import ClassVar

from django.db import models


class NeveraItem(models.Model):
    ORIGEN_CHOICES: ClassVar = [
        ('compra', 'Compra'),
        ('manual', 'Manual'),
    ]

    nombre = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    unidad = models.CharField(max_length=20)
    categoria = models.CharField(max_length=50, null=True, blank=True)
    fecha_caducidad = models.DateField(null=True, blank=True)
    fecha_añadido = models.DateTimeField(auto_now_add=True)
    origen = models.CharField(max_length=10, choices=ORIGEN_CHOICES, default='manual')

    class Meta:
        db_table = 'nevera_items'
        constraints: ClassVar = [
            models.UniqueConstraint(fields=['nombre', 'unidad'], name='unique_nombre_unidad'),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.cantidad} {self.unidad})"
