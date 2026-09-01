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
        "fecha_caducidad",
        "estado",
        "es_basico",
        "origen",
        "fecha_añadido",
    )
    list_filter = ("es_basico", "origen", "categoria")
    search_fields = ("nombre",)
    ordering = ("nombre",)
    list_per_page = 50

    # Editables desde la propia tabla: rellenar caducidades y reclasificar
    # básicos son correcciones en lote, justo para lo que existe el admin.
    # Sin esto habría que abrir el detalle de cada item, guardar y volver.
    # `estado` no puede ir aquí: es una columna calculada, no un campo.
    list_editable = ("fecha_caducidad", "es_basico")
    actions = ("marcar_como_basico", "marcar_como_perecedero")

    # `fecha_añadido` es auto_now_add: lo pone Django al crear y no debe
    # tocarse. Sin esto el admin ni siquiera lo mostraría en el formulario.
    readonly_fields = ("fecha_añadido",)

    @admin.display(description="Estado", ordering="fecha_caducidad")
    def estado(self, obj: NeveraItem) -> str:
        """Columna calculada: los días que quedan, con color.

        No repite la fecha, que ya tiene su propia columna editable al lado.

        `format_html` escapa los argumentos que interpola, así que un nombre
        con HTML dentro no puede inyectar nada en la página del admin.
        """
        if obj.es_basico:
            return "despensa"
        if obj.fecha_caducidad is None:
            return "—"
        dias = (obj.fecha_caducidad - timezone.localdate()).days
        if dias < 0:
            color, nota = "#b00020", "caducado"
        elif dias <= 3:
            color, nota = "#c77700", f"quedan {dias} d"
        else:
            color, nota = "#1b7f3b", f"quedan {dias} d"
        return format_html('<b style="color:{}">{}</b>', color, nota)

    # Las "acciones" del admin operan sobre la selección de la lista. Usan
    # `queryset.update()`: un solo UPDATE en SQL para las N filas marcadas, en
    # vez de N `save()` en un bucle de Python.
    @admin.action(description="Marcar como básico de despensa")
    def marcar_como_basico(self, request, queryset):
        actualizados = queryset.update(es_basico=True)
        self.message_user(request, f"{actualizados} item(s) marcados como básico.")

    @admin.action(description="Marcar como perecedero")
    def marcar_como_perecedero(self, request, queryset):
        actualizados = queryset.update(es_basico=False)
        self.message_user(request, f"{actualizados} item(s) marcados como perecedero.")
