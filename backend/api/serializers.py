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
            "es_basico",
        ]


class NeveraItemUpdateSerializer(serializers.Serializer):
    """Entrada de `PATCH /api/nevera/items/{id}` (SDD-web fase 4).

    Es un `Serializer` pelado y no un `ModelSerializer` a propósito. Un
    `ModelSerializer` sabría guardar solo, y guardar es justo lo que esta capa
    no debe hacer: la escritura pasa por `nevera.services.edit_item`, que
    normaliza el nombre y convierte `cantidad`/`unidad` a la unidad base. Si
    aquí escribiéramos el modelo directamente, la web metería en la BD datos
    con una forma distinta a la que mete el bot, y se acabó la única fuente de
    verdad.

    Todos los campos son opcionales: PATCH es una actualización *parcial*, así
    que solo se toca lo que venga. `validated_data` trae únicamente las claves
    presentes en el cuerpo, que es lo que `edit_item(**cambios)` espera.
    """

    nombre = serializers.CharField(max_length=200)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    unidad = serializers.CharField(max_length=20)
    categoria = serializers.CharField(max_length=50, allow_null=True, allow_blank=True)
    fecha_caducidad = serializers.DateField(allow_null=True)
    es_basico = serializers.BooleanField()

    def __init__(self, *args, **kwargs):
        # Opcionalidad de todos los campos en un único sitio, en vez de repetir
        # `required=False` seis veces y arriesgarse a olvidarlo en el séptimo.
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.required = False

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("No hay ningún campo que actualizar.")
        # `cantidad` sin `unidad` significa "ya viene en la unidad base actual"
        # (contrato de `edit_item`). Cambiar solo la unidad, en cambio, dejaría
        # la cantidad interpretada en una escala que no le corresponde: 500 g
        # pasarían a ser 500 kg sin que nadie lo pidiera.
        if "unidad" in attrs and "cantidad" not in attrs:
            raise serializers.ValidationError(
                "Para cambiar la unidad hay que enviar también la cantidad."
            )
        # Un <input> vacío del formulario llega como "", pero en la BD la
        # ausencia de categoría es NULL. Sin esta traducción tendríamos dos
        # representaciones para lo mismo y los filtros por categoría fallarían
        # en una de ellas.
        if attrs.get("categoria") == "":
            attrs["categoria"] = None
        return attrs


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


class DaySummarySerializer(serializers.Serializer):
    """Bloque `summary` de `GET /api/health/last-day`: los KPIs ya calculados.

    Se calcula en `supabase_data.services.build_day_summary` y no en el cliente
    para que la web y el bot no puedan divergir en el mismo número.
    """

    heart_rate_avg = serializers.FloatField(allow_null=True)
    heart_rate_min = serializers.IntegerField(allow_null=True)
    heart_rate_max = serializers.IntegerField(allow_null=True)
    resting_heart_rate = serializers.FloatField(allow_null=True)
    oxygen_saturation_avg = serializers.FloatField(allow_null=True)
    oxygen_saturation_min = serializers.FloatField(allow_null=True)
    sleep_minutes = serializers.IntegerField(
        allow_null=True, help_text="Minutos dormidos en la noche que termina ese día."
    )


class LastDaySerializer(serializers.Serializer):
    """Respuesta de `GET /api/health/last-day`: el día crudo, más un resumen."""

    date = serializers.DateField()
    heart_rate_samples = HeartRateSampleSerializer(many=True)
    oxygen_saturation_samples = OxygenSaturationSampleSerializer(many=True)
    resting_heart_rate_samples = RestingHeartRateSampleSerializer(many=True)
    sleep_stages = SleepStageSerializer(many=True)
    summary = DaySummarySerializer()


class SleepSegmentSerializer(serializers.Serializer):
    """Un tramo continuo de una fase dentro de la noche (una barra del hipnograma)."""

    stage = serializers.CharField(help_text="ligero | profundo | rem | despierto | …")
    start = serializers.DateTimeField(help_text="Hora local de inicio.")
    end = serializers.DateTimeField(help_text="Hora local de fin.")
    minutes = serializers.IntegerField()


class SleepStageTotalSerializer(serializers.Serializer):
    stage = serializers.CharField()
    minutes = serializers.IntegerField()


class SleepNightSerializer(serializers.Serializer):
    """Respuesta de `GET /api/health/sleep-night`: la noche para el hipnograma."""

    date = serializers.DateField(help_text="Día del despertar.")
    start = serializers.DateTimeField(allow_null=True)
    end = serializers.DateTimeField(allow_null=True)
    total_minutes = serializers.IntegerField()
    segments = SleepSegmentSerializer(many=True)
    totals = SleepStageTotalSerializer(many=True, help_text="Minutos por fase, de mayor a menor.")


class IntradayPointSerializer(serializers.Serializer):
    """Una muestra dentro del día: instante local y valor."""

    t = serializers.DateTimeField(help_text="Hora local de la muestra.")
    v = serializers.FloatField()


class DayDetailSerializer(serializers.Serializer):
    """Respuesta de `GET /api/health/day`: todo lo de la página de un día.

    `prev_date`/`next_date` son días **con datos**, no el día natural anterior:
    el sync tiene huecos de semanas y navegar día a día llevaría a pantallas
    vacías.
    """

    date = serializers.DateField()
    prev_date = serializers.DateField(allow_null=True)
    next_date = serializers.DateField(allow_null=True)
    summary = DaySummarySerializer()
    heart_rate = IntradayPointSerializer(many=True)
    oxygen_saturation = IntradayPointSerializer(many=True)


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
