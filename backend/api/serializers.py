"""Formas de entrada/salida de la API web.

Solo serialización: nada de lógica de negocio (SDD-web §3.1). Los servicios de
`nevera/` y `supabase_data/` devuelven modelos o dicts y aquí se les da forma
JSON estable para el frontend.
"""

from rest_framework import serializers

from nevera.models import NeveraItem


class ErrorDetailSerializer(serializers.Serializer):
    """Forma de los errores de la API: `{"detail": "..."}`."""

    detail = serializers.CharField()


class NeveraItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = NeveraItem
        fields = [
            "id",
            "nombre",
            "cantidad",
            "unidad",
            "categoria",
            "fecha_caducidad",
            "fecha_añadido",
            "origen",
        ]


class AnalysisSerializer(serializers.Serializer):
    """`supabase_data.services.get_recent_analyses` devuelve dicts, no modelos."""

    analysis_date = serializers.DateField()
    user_instruction = serializers.CharField(allow_null=True)
    analysis_text = serializers.CharField()


# --- Formas de solo documentación ------------------------------------------
# `/health/last-day` y `/health/series` devuelven los dicts de `services.py`
# tal cual, sin pasar por un serializer. Estas clases declaran esa forma para
# el esquema OpenAPI (ver api/docs.py); no se usan para serializar, así que la
# salida real no cambia. Si algún día esas views empiezan a serializar de
# verdad, estos son los serializers a usar.


class HeartRateSampleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parent_key = serializers.IntegerField()
    bpm = serializers.IntegerField()
    recorded_at = serializers.DateTimeField()


class RestingHeartRateSampleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    uuid = serializers.CharField()
    resting_bpm = serializers.IntegerField()
    recorded_at = serializers.DateTimeField()


class OxygenSaturationSampleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    uuid = serializers.CharField()
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    recorded_at = serializers.DateTimeField()


class SleepStageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parent_key = serializers.IntegerField()
    stage_type = serializers.IntegerField()
    stage_start = serializers.DateTimeField()
    stage_end = serializers.DateTimeField()


class LastDaySerializer(serializers.Serializer):
    """Respuesta de `GET /api/health/last-day`: el día crudo, sin agregar."""

    date = serializers.DateField()
    heart_rate_samples = HeartRateSampleSerializer(many=True)
    oxygen_saturation_samples = OxygenSaturationSampleSerializer(many=True)
    resting_heart_rate_samples = RestingHeartRateSampleSerializer(many=True)
    sleep_stages = SleepStageSerializer(many=True)


class SeriesPointSerializer(serializers.Serializer):
    """Un punto de la serie diaria.

    La forma depende de la métrica: las de muestras traen `min/max/avg/count`
    y `sleep` trae `minutes`. Se declaran todos como opcionales en vez de
    partirlo en dos esquemas con `oneOf`: es menos preciso, pero mucho más
    legible en Swagger UI para solo dos variantes.
    """

    date = serializers.DateField()
    min = serializers.FloatField(required=False, help_text="Solo métricas de muestras.")
    max = serializers.FloatField(required=False, help_text="Solo métricas de muestras.")
    avg = serializers.FloatField(required=False, help_text="Solo métricas de muestras.")
    count = serializers.IntegerField(required=False, help_text="Solo métricas de muestras.")
    minutes = serializers.IntegerField(required=False, help_text="Solo métrica 'sleep'.")


class SeriesSerializer(serializers.Serializer):
    """Respuesta de `GET /api/health/series`."""

    metric = serializers.CharField()
    points = SeriesPointSerializer(many=True)
