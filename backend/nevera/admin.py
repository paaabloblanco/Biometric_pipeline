"""Registro de la nevera en el admin de Django.

El admin es la herramienta de *back-office*: sirve para corregir el inventario
a mano cuando el bot o la web se quedan cortos (un item mal parseado, una
cantidad que no cuadra, una caducidad que falta). No es la interfaz de uso
diario — para eso están Telegram y la web, que pasan por `services.py`.

`nevera` es `managed = True` (tablas propias de Django), así que aquí sí tiene
sentido editar. Compárese con `supabase_data/admin.py`, que va en solo lectura.
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from nevera.models import NeveraItem


@admin.register(NeveraItem)
class NeveraItemAdmin(admin.ModelAdmin):
    """Vista de tabla de la nevera con aviso de caducidad."""

    list_display = (
        "nombre",
        "cantidad",
        "unidad",
        "categoria",
        "caducidad",
        "origen",
        "fecha_añadido",
    )
    list_filter = ("origen", "categoria")
    search_fields = ("nombre",)
    ordering = ("nombre",)
    list_per_page = 50

    # `fecha_añadido` es auto_now_add: lo pone Django al crear y no debe
    # tocarse. Sin esto el admin ni siquiera lo mostraría en el formulario.
    readonly_fields = ("fecha_añadido",)

    @admin.display(description="Caducidad", ordering="fecha_caducidad")
    def caducidad(self, obj: NeveraItem) -> str:
        """Columna calculada: la fecha más los días que quedan, con color.

        `format_html` escapa los argumentos que interpola, así que un nombre
        con HTML dentro no puede inyectar nada en la página del admin.
        """
        if obj.fecha_caducidad is None:
            return "—"
        dias = (obj.fecha_caducidad - timezone.localdate()).days
        if dias < 0:
            color, nota = "#b00020", "caducado"
        elif dias <= 3:
            color, nota = "#c77700", f"quedan {dias} d"
        else:
            color, nota = "#1b7f3b", f"quedan {dias} d"
        return format_html('{} <b style="color:{}">({})</b>', obj.fecha_caducidad, color, nota)
