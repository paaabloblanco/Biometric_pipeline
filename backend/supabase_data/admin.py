"""Registro de solo lectura de las tablas del sync en el admin de Django.

Estas tablas son `managed = False`: las crea y las llena el pipeline externo
(`extractor.py` / Health Connect), no Django. Exponerlas como editables
invitaría a corregir a mano datos que **el siguiente sync sobrescribe**, así
que aquí el admin actúa como *visor*: se consultan, se filtran y se buscan,
pero no se tocan. El dueño del dato es el sync.
"""

from django.contrib import admin
from django.utils.html import format_html

from supabase_data.models import (
    AiAnalysisLog,
    HeartRateSamples,
    OxygenSaturationSamples,
    RestingHeartRateSamples,
    SleepStages,
)


class SoloLecturaAdmin(admin.ModelAdmin):
    """Base para las tablas del sync: se ven, no se editan.

    Los tres `has_*_permission` cortan alta, edición y borrado de verdad (el
    admin los consulta también al resolver la URL), no solo escondiendo los
    botones de la plantilla.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # Las tablas de muestras crecen sin techo (varias lecturas por minuto). El
    # `COUNT(*)` que el admin lanza para pintar "N resultados" recorre la tabla
    # entera y se vuelve carísimo; se desactiva y se pagina sin total.
    show_full_result_count = False
    list_per_page = 50


@admin.register(HeartRateSamples)
class HeartRateSamplesAdmin(SoloLecturaAdmin):
    list_display = ("recorded_at", "bpm", "parent_key")
    ordering = ("-recorded_at",)


@admin.register(RestingHeartRateSamples)
class RestingHeartRateSamplesAdmin(SoloLecturaAdmin):
    list_display = ("recorded_at", "resting_bpm")
    ordering = ("-recorded_at",)


@admin.register(OxygenSaturationSamples)
class OxygenSaturationSamplesAdmin(SoloLecturaAdmin):
    list_display = ("recorded_at", "percentage")
    ordering = ("-recorded_at",)


@admin.register(SleepStages)
class SleepStagesAdmin(SoloLecturaAdmin):
    list_display = ("stage_start", "stage_end", "stage_type", "parent_key")
    ordering = ("-stage_start",)


@admin.register(AiAnalysisLog)
class AiAnalysisLogAdmin(SoloLecturaAdmin):
    """Historial de análisis de Gemini. Una fila por día, tabla pequeña."""

    list_display = ("analysis_date", "created_at", "extracto")
    search_fields = ("analysis_text", "user_instruction")
    ordering = ("-analysis_date",)

    # Navegador por fechas: aquí sí compensa (una fila al día, no millones).
    date_hierarchy = "analysis_date"

    @admin.display(description="Extracto")
    def extracto(self, obj: AiAnalysisLog) -> str:
        """Primeras líneas del análisis, para poder ojear la lista."""
        texto = " ".join(obj.analysis_text.split())
        return format_html("{}", texto[:160] + ("…" if len(texto) > 160 else ""))
