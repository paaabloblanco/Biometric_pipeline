"""Formas de entrada/salida de la API web.

Solo serialización: nada de lógica de negocio (SDD-web §3.1). Los servicios de
`nevera/` y `supabase_data/` devuelven modelos o dicts y aquí se les da forma
JSON estable para el frontend.
"""

from rest_framework import serializers

from health_ai.config import MAX_INSTRUCTION_CHARS
from nevera.models import NeveraItem
from nevera.ofertas import MAX_OFERTAS_CHARS
from nevera.parsing import MAX_COMPRA_CHARS
from nevera.units import to_base


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


class CompraParseRequestSerializer(serializers.Serializer):
    """Cuerpo de `POST /api/nevera/parse`: el texto libre de la compra."""

    text = serializers.CharField(
        max_length=MAX_COMPRA_CHARS,
        trim_whitespace=True,
        help_text="Lista de la compra en texto libre, tal cual se copia del ticket.",
    )


class ItemPropuestoSerializer(serializers.Serializer):
    """Un item tal y como lo entendió Gemini, **antes** de guardarse.

    Sirve a la vez de salida de `/nevera/parse` y de entrada de
    `/nevera/items`: es literalmente el mismo objeto, que sale al cliente,
    se deja editar en pantalla y vuelve confirmado. Tenerlo declarado una
    sola vez es lo que garantiza que las dos mitades del flujo no se
    desincronicen.

    Ojo: aquí `cantidad`/`unidad` van **como las dijo el usuario** (1 kg), no
    en la unidad base (1000 g). La conversión la hace `services.add_items` con
    `to_base`, igual que para el bot; si la hiciéramos aquí, la pantalla de
    confirmación enseñaría números que el usuario no reconoce.
    """

    nombre = serializers.CharField(max_length=200)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    unidad = serializers.CharField(max_length=20)
    categoria = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True, default=None
    )
    fecha_caducidad = serializers.DateField(required=False, allow_null=True, default=None)
    es_basico = serializers.BooleanField(required=False, default=False)

    def validate_unidad(self, valor):
        # Se valida aquí y no al guardar para que el 400 señale la unidad mala
        # antes de tocar la BD: `add_items` da de alta item por item, así que
        # una unidad inválida en el cuarto dejaría los tres primeros escritos.
        try:
            to_base(1, valor)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return valor

    def validate(self, attrs):
        if attrs.get("categoria") == "":
            attrs["categoria"] = None
        return attrs


class NeveraItemsCreateSerializer(serializers.Serializer):
    """Cuerpo de `POST /api/nevera/items`: los items ya confirmados por el usuario.

    El cliente manda la lista entera, no un identificador de "lo que parseé
    antes": el servidor no guardó nada en el paso anterior (SDD-web §6).
    """

    items = ItemPropuestoSerializer(many=True, allow_empty=False)


class SuggestionsRequestSerializer(serializers.Serializer):
    """Cuerpo de `POST /api/nevera/suggestions`.

    `exclude` son los términos de `/comer sin pollo, huevos`. Van en el cuerpo
    y no en la query string porque son texto libre del usuario y pueden ser
    varios; y el verbo es POST y no GET aunque sea una consulta, porque cada
    llamada gasta una petición a Gemini: no es una lectura idempotente ni algo
    que un proxy deba cachear.
    """

    exclude = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
        max_length=20,
        help_text="Ingredientes a excluir, como en `/comer sin pollo, huevos`.",
    )


class IngredienteSerializer(serializers.Serializer):
    """Un ingrediente de receta: lo que `consume_items` espera descontar.

    Igual que en el alta, este serializer es a la vez salida (dentro de las
    recetas propuestas) y entrada (lo que se confirma al marcar hecho).
    """

    nombre = serializers.CharField(max_length=200)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    unidad = serializers.CharField(max_length=20)

    def validate_unidad(self, valor):
        try:
            to_base(1, valor)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return valor


class RecetaSerializer(serializers.Serializer):
    """Una receta propuesta por Gemini. No se guarda en ningún sitio."""

    nombre = serializers.CharField()
    descripcion = serializers.CharField(allow_blank=True)
    ingredientes = IngredienteSerializer(many=True)


class SuggestionsResponseSerializer(serializers.Serializer):
    """Respuesta de `/nevera/suggestions`.

    Incluye los avisos que el bot imprime encima de las recetas: qué se excluyó
    de verdad y qué término no casó con nada (que casi siempre es una errata, y
    callarlo haría parecer que la exclusión se ignoró).
    """

    recipes = RecetaSerializer(many=True)
    excluded = serializers.ListField(child=serializers.CharField())
    not_found = serializers.ListField(child=serializers.CharField())
    analysis_date = serializers.DateField(allow_null=True)


class ConsumeRequestSerializer(serializers.Serializer):
    """Cuerpo de `POST /api/nevera/consume`: lo que se descuenta del inventario."""

    ingredients = IngredienteSerializer(many=True, allow_empty=False)


class ConsumoAplicadoSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    unidad = serializers.CharField()
    restante = serializers.FloatField()


class ConsumeResponseSerializer(serializers.Serializer):
    """Respuesta de `/nevera/consume`, tal cual la devuelve `consume_items`.

    Los tres bloques son informativos y ninguno es un error: los básicos de
    despensa no se descuentan a propósito (se gestionan por presencia), y un
    "no encontrado" solo significa que ese ingrediente ya no estaba.
    """

    aplicados = ConsumoAplicadoSerializer(many=True)
    basicos = serializers.ListField(child=serializers.DictField())
    no_encontrados = serializers.ListField(child=serializers.DictField())


class OfertasRequestSerializer(serializers.Serializer):
    """Cuerpo de `POST /api/ofertas/analyze`: la gazetka transcrita."""

    text = serializers.CharField(
        max_length=MAX_OFERTAS_CHARS,
        trim_whitespace=True,
        help_text="Texto de las ofertas, tal cual se copia de la app del supermercado.",
    )


class RecomendacionSerializer(serializers.Serializer):
    """Una oferta que merece la pena, según Gemini. No se guarda en ningún sitio."""

    nombre = serializers.CharField()
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
    # `precio` es texto y no un número a propósito: llega tal cual aparece en
    # la oferta ("5,99 zł", "2x1", "-30%"), y convertirlo a decimal obligaría a
    # decidir divisa, formato y qué hacer con las promociones que no son un
    # precio. Aquí solo se enseña.
    precio = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class AnalysisSerializer(serializers.Serializer):
    """`supabase_data.services.get_recent_analyses` devuelve dicts, no modelos."""

    analysis_date = serializers.DateField()
    user_instruction = serializers.CharField(allow_null=True)
    analysis_text = serializers.CharField()


class AnalysisRequestSerializer(serializers.Serializer):
    """Cuerpo de `POST /api/analyses`.

    `instruction` es opcional: sin ella se usa la de por defecto, igual que
    `/analisis` sin argumentos en Telegram. Va acotada en longitud porque el
    texto se incrusta en el prompt que se manda a Gemini.
    """

    instruction = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MAX_INSTRUCTION_CHARS,
        help_text="Qué quieres que analice. Si se omite, se usa la instrucción por defecto.",
    )


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
