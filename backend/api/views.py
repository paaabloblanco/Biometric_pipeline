"""Views de la API web.

Capa fina (SDD-web §3.1): cada view valida la entrada, llama a la misma función
de `services.py` que usa el handler de Telegram equivalente y devuelve JSON.
Cero lógica de negocio aquí.

Iteración 1 = solo lectura (SDD-web §7-E); la fase 4 añade la escritura
sobre la nevera.

Sobre los `@extend_schema`: estas views heredan de `APIView` pelado y construyen
la respuesta dentro de `get()`, así que `drf-spectacular` —que inspecciona la
clase, no la ejecución— no puede adivinar qué devuelven. El decorador es la
forma de declararlo explícitamente. Es el contrato de la API escrito al lado
del código que lo cumple.
"""

from django.db import IntegrityError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    AnalysisRequestSerializer,
    AnalysisSerializer,
    CompraParseRequestSerializer,
    ConsumeRequestSerializer,
    ConsumeResponseSerializer,
    DayDetailSerializer,
    ErrorDetailSerializer,
    ItemPropuestoSerializer,
    LastDaySerializer,
    NeveraItemsCreateSerializer,
    NeveraItemSerializer,
    NeveraItemUpdateSerializer,
    SeriesSerializer,
    SleepNightSerializer,
    SuggestionsRequestSerializer,
    SuggestionsResponseSerializer,
)
from supabase_data.services import SERIES_METRICS

# Tope defensivo para ?limit= en /api/analyses (evita traer toda la tabla).
MAX_ANALYSES = 366


def _primer_error(errores) -> str:
    """Aplana los errores de un serializer al primer mensaje legible."""
    if isinstance(errores, dict):
        for campo, detalle in errores.items():
            mensaje = _primer_error(detalle)
            return mensaje if campo == "non_field_errors" else f"{campo}: {mensaje}"
        return "Petición inválida."
    if isinstance(errores, list):
        return _primer_error(errores[0]) if errores else "Petición inválida."
    return str(errores)


@extend_schema(
    tags=["Salud"],
    summary="Datos crudos del último día",
    description=(
        "Todos los registros del último día con datos, sin agregar ni promediar. "
        "Equivale al comando `/hoy` del bot de Telegram."
    ),
    responses={200: LastDaySerializer},
)
class HealthLastDayView(APIView):
    """GET /api/health/last-day — datos crudos del último día. Equivale a /hoy."""

    def get(self, request):
        from supabase_data.services import get_last_day_data

        return Response(get_last_day_data())


@extend_schema(
    tags=["Salud"],
    summary="Serie diaria agregada (para gráficas)",
    description=(
        "Agrega las muestras por día. Las métricas de muestras devuelven "
        "`min`/`max`/`avg`/`count`; `sleep` devuelve `minutes` (suma de las fases "
        "de sueño, excluyendo las de vigilia). Sin rango, los últimos 30 días "
        "hasta el último día con datos."
    ),
    parameters=[
        OpenApiParameter(
            "metric",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            required=True,
            enum=list(SERIES_METRICS),
            description="Métrica a agregar.",
        ),
        OpenApiParameter(
            "from",
            OpenApiTypes.DATE,
            OpenApiParameter.QUERY,
            description="Primer día incluido (`YYYY-MM-DD`).",
        ),
        OpenApiParameter(
            "to",
            OpenApiTypes.DATE,
            OpenApiParameter.QUERY,
            description="Último día incluido (`YYYY-MM-DD`).",
        ),
    ],
    responses={200: SeriesSerializer, 400: ErrorDetailSerializer},
)
class HealthSeriesView(APIView):
    """GET /api/health/series?metric=&from=&to= — serie agregada por día (gráficas)."""

    def get(self, request):
        from supabase_data.services import get_series

        metric = request.query_params.get("metric")
        if not metric:
            return Response({"detail": "Falta el parámetro 'metric'."}, status=400)
        try:
            puntos = get_series(
                metric,
                request.query_params.get("from"),
                request.query_params.get("to"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"metric": metric, "points": puntos})


@extend_schema(
    tags=["Salud"],
    summary="Detalle de un día",
    description=(
        "Todo lo que pinta la página de un día: el resumen, las series intradía de "
        "frecuencia cardíaca y SpO₂ (instante local + valor), y los días **con datos** "
        "anterior y siguiente para navegar sin caer en pantallas vacías. El hipnograma "
        "se pide aparte a `/health/sleep-night`, porque su unidad es la noche y no el "
        "día natural."
    ),
    parameters=[
        OpenApiParameter(
            "date",
            OpenApiTypes.DATE,
            OpenApiParameter.QUERY,
            description="Día a consultar (`YYYY-MM-DD`). Por defecto, el último con datos.",
        ),
    ],
    responses={200: DayDetailSerializer, 400: ErrorDetailSerializer},
)
class HealthDayView(APIView):
    """GET /api/health/day?date= — detalle de un día para la web."""

    def get(self, request):
        from supabase_data.services import get_day_detail

        try:
            return Response(get_day_detail(request.query_params.get("date")))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)


@extend_schema(
    tags=["Salud"],
    summary="Fases de la última noche (hipnograma)",
    description=(
        "Los tramos de la sesión de sueño principal que termina en `date`, en hora "
        'local, para dibujar un hipnograma. "La noche" es la sesión más larga que '
        "acaba ese día: las siestas quedan fuera. Las sesiones duplicadas que escribe "
        "el sync se descartan al leer."
    ),
    parameters=[
        OpenApiParameter(
            "date",
            OpenApiTypes.DATE,
            OpenApiParameter.QUERY,
            description="Día del despertar (`YYYY-MM-DD`). Por defecto, el último con datos.",
        ),
    ],
    responses={200: SleepNightSerializer, 400: ErrorDetailSerializer},
)
class HealthSleepNightView(APIView):
    """GET /api/health/sleep-night?date= — fases de una noche, para el hipnograma."""

    def get(self, request):
        from supabase_data.services import get_sleep_night

        try:
            noche = get_sleep_night(request.query_params.get("date"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(noche)


@extend_schema(
    tags=["Análisis"],
    summary="Histórico de análisis de Gemini",
    description="Equivale al comando `/historial` del bot de Telegram.",
    parameters=[
        OpenApiParameter(
            "limit",
            OpenApiTypes.INT,
            OpenApiParameter.QUERY,
            description=f"Cuántos análisis devolver. Por defecto 7, máximo {MAX_ANALYSES}.",
        ),
    ],
    responses={200: AnalysisSerializer(many=True), 400: ErrorDetailSerializer},
)
class AnalysesView(APIView):
    """GET /api/analyses?limit= — histórico de análisis. Equivale a /historial."""

    def get(self, request):
        from supabase_data.services import get_recent_analyses

        crudo = request.query_params.get("limit")
        if crudo is None:
            limit = 7
        else:
            try:
                limit = int(crudo)
            except ValueError:
                return Response({"detail": "'limit' debe ser un entero."}, status=400)
            limit = max(1, min(MAX_ANALYSES, limit))
        analyses = get_recent_analyses(limit)
        return Response(AnalysisSerializer(analyses, many=True).data)

    @extend_schema(
        tags=["Análisis"],
        summary="Lanza un análisis nuevo con Gemini",
        description=(
            "Equivale al comando `/analisis` del bot. **Tarda 15-30 s**: la respuesta "
            "no llega hasta que Gemini contesta. Sobrescribe el análisis del día si ya "
            "existía. "
            "Devuelve **409** si el bot o esta misma API ya están analizando. La "
            "exclusión se hace con un *advisory lock* de Postgres, así que vale entre "
            "procesos distintos (ver `health_ai/locks.py`)."
        ),
        request=AnalysisRequestSerializer,
        responses={
            200: AnalysisSerializer,
            400: ErrorDetailSerializer,
            409: OpenApiResponse(
                response=ErrorDetailSerializer,
                description="Ya hay un análisis en curso en otro proceso.",
            ),
        },
    )
    def post(self, request):
        from health_ai.config import DEFAULT_INSTRUCTION
        from health_ai.pruebas import AnalysisInProgress, run_analysis

        entrada = AnalysisRequestSerializer(data=request.data)
        if not entrada.is_valid():
            return Response({"detail": _primer_error(entrada.errors)}, status=400)

        # Sin instrucción (o en blanco) se usa la de por defecto, igual que
        # `/analisis` sin argumentos en Telegram: las dos interfaces tienen que
        # producir el mismo análisis ante la misma petición vacía.
        instruccion = entrada.validated_data.get("instruction", "").strip() or DEFAULT_INSTRUCTION

        try:
            resultado = run_analysis(instruccion, send_to_api=True)
        except AnalysisInProgress:
            # 409 Conflict y no 429: el cliente no ha hecho nada mal ni se ha
            # pasado de cuota, es que el estado actual del sistema es
            # incompatible con lo que pide. Puede que el conflicto ni siquiera
            # lo haya causado él, sino el bot.
            return Response(
                {"detail": "Ya hay un análisis en curso, espera a que termine."},
                status=409,
            )

        # 200 y no 201: llamar dos veces el mismo día no crea dos análisis,
        # sobrescribe el mismo. Un 201 prometería un recurso nuevo cada vez,
        # con su propia URL, y aquí no lo hay.
        return Response(
            AnalysisSerializer(
                {
                    "analysis_date": resultado["date"],
                    "user_instruction": instruccion,
                    "analysis_text": resultado["response"],
                }
            ).data
        )


@extend_schema(
    tags=["Nevera"],
    summary="Inventario completo de la nevera",
    description="Equivale al comando `/nevera` del bot de Telegram.",
    responses={200: NeveraItemSerializer(many=True)},
)
class NeveraView(APIView):
    """GET /api/nevera — inventario completo. Equivale a /nevera."""

    def get(self, request):
        from nevera.services import list_all

        return Response(NeveraItemSerializer(list_all(), many=True).data)


@extend_schema(tags=["Nevera"])
class NeveraItemView(APIView):
    """PATCH/DELETE /api/nevera/items/{id} — edita o borra un item.

    Equivale a `/editar` y `/borrar` del bot. La lógica ya vive en
    `nevera.services`; aquí solo se traduce HTTP a esa llamada y se eligen los
    códigos de estado (SDD-web fase 4).
    """

    @extend_schema(
        summary="Edita un item de la nevera",
        description=(
            "Actualización **parcial**: solo se modifican los campos presentes en el "
            "cuerpo. Para cambiar la unidad hay que enviar también la cantidad, porque "
            "el servicio las convierte juntas a la unidad base. Equivale a `/editar`."
        ),
        request=NeveraItemUpdateSerializer,
        responses={
            200: NeveraItemSerializer,
            400: ErrorDetailSerializer,
            404: ErrorDetailSerializer,
            409: OpenApiResponse(
                response=ErrorDetailSerializer,
                description="Ya existe otro item con ese nombre y esa unidad.",
            ),
        },
    )
    def patch(self, request, item_id: int):
        from nevera.services import edit_item

        entrada = NeveraItemUpdateSerializer(data=request.data)
        if not entrada.is_valid():
            # `raise_exception=True` devolvería el diccionario de errores de DRF
            # (`{"cantidad": ["..."]}`), que rompe la forma `{"detail": "..."}`
            # que usa el resto de la API y que el cliente del frontend lee para
            # enseñar el mensaje. Se aplana aquí para no tener dos formas de
            # error distintas según el endpoint.
            return Response({"detail": _primer_error(entrada.errors)}, status=400)

        try:
            item = edit_item(item_id, **entrada.validated_data)
        except IntegrityError:
            # La constraint `unique_nombre_unidad` del modelo. Renombrar "pollo"
            # a "pavo" cuando ya hay un "pavo" en la misma unidad es un conflicto
            # con el estado actual del recurso, no una petición mal formada: por
            # eso 409 y no 400. Sin capturarla, Django devolvería un 500 y esto
            # parecería un fallo del servidor en vez de una decisión del usuario.
            return Response(
                {"detail": "Ya existe otro item con ese nombre y esa unidad."},
                status=409,
            )

        if item is None:
            return Response({"detail": "No existe ese item."}, status=404)
        return Response(NeveraItemSerializer(item).data)

    @extend_schema(
        summary="Borra un item de la nevera",
        description="Equivale a `/borrar` del bot. Devuelve 204 sin cuerpo.",
        responses={204: None, 404: ErrorDetailSerializer},
    )
    def delete(self, request, item_id: int):
        from nevera.services import delete_item

        if not delete_item(item_id):
            return Response({"detail": "No existe ese item."}, status=404)
        return Response(status=204)


@extend_schema(
    tags=["Nevera"],
    summary="Interpreta un texto de compra con Gemini (no guarda nada)",
    description=(
        "Primer paso del alta en dos tiempos. Equivale a `/anadir` en Telegram, con "
        "una diferencia importante: **no guarda nada ni recuerda nada**. Devuelve los "
        "items que entendió Gemini para que el cliente los enseñe, deje corregirlos y "
        "los mande de vuelta a `POST /api/nevera/items`. "
        "Tarda lo que tarde Gemini (unos segundos)."
    ),
    request=CompraParseRequestSerializer,
    responses={
        200: ItemPropuestoSerializer(many=True),
        400: ErrorDetailSerializer,
        502: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="Gemini no devolvió algo interpretable.",
        ),
    },
)
class NeveraParseView(APIView):
    """POST /api/nevera/parse — texto libre -> items propuestos, sin escribir en BD.

    Aquí está la diferencia de fondo con el bot (SDD-web §6). `/anadir` guarda
    lo entendido en `_pending_altas`, un diccionario en memoria del proceso,
    y espera un `/confirmar` posterior. Esta view **no guarda estado**: el
    resultado se lo lleva el cliente y vuelve en la siguiente petición. Así el
    servidor no tiene sesiones que caducar ni altas huérfanas si nadie confirma,
    y dos pestañas del navegador no se pisan la una a la otra.
    """

    def post(self, request):
        from nevera.parsing import parse_compra_text

        entrada = CompraParseRequestSerializer(data=request.data)
        if not entrada.is_valid():
            return Response({"detail": _primer_error(entrada.errors)}, status=400)

        try:
            items = parse_compra_text(entrada.validated_data["text"])
        except ValueError as exc:
            # 502 y no 400: la petición del cliente era correcta; quien ha
            # contestado mal es el servicio de terceros que hay detrás.
            return Response({"detail": f"No se pudo interpretar el texto: {exc}"}, status=502)

        # Se pasan por el serializer de salida para que el cliente reciba
        # exactamente la misma forma que luego tiene que devolver, incluidas
        # las fechas como ISO. La unidad se valida ya aquí: si Gemini inventa
        # una que `to_base` no conoce, mejor saberlo antes de enseñar la
        # pantalla de confirmación que al intentar guardar.
        salida = ItemPropuestoSerializer(data=items, many=True)
        if not salida.is_valid():
            return Response(
                {"detail": f"Gemini devolvió items no válidos: {_primer_error(salida.errors)}"},
                status=502,
            )
        return Response(salida.validated_data)


@extend_schema(
    tags=["Nevera"],
    summary="Da de alta los items confirmados",
    description=(
        "Segundo paso del alta. Equivale a `/confirmar` en Telegram, pero recibe los "
        "items en el cuerpo en vez de leerlos de la memoria del proceso. Si un item ya "
        "existe con el mismo nombre normalizado y la misma unidad base, **suma** la "
        "cantidad en vez de duplicar la fila (`nevera.services.add_items`)."
    ),
    request=NeveraItemsCreateSerializer,
    responses={201: NeveraItemSerializer(many=True), 400: ErrorDetailSerializer},
)
class NeveraItemsView(APIView):
    """POST /api/nevera/items — alta en lote de items ya confirmados."""

    def post(self, request):
        from nevera.services import add_items

        entrada = NeveraItemsCreateSerializer(data=request.data)
        if not entrada.is_valid():
            return Response({"detail": _primer_error(entrada.errors)}, status=400)

        # `origen="compra"` igual que /confirmar en el bot: el origen dice de
        # dónde salió el dato (de un texto de compra parseado, no de un alta a
        # mano), no por qué interfaz entró.
        creados = add_items(entrada.validated_data["items"], origen="compra")

        # 201 y no 200: esta petición sí añade recursos a la colección. No hay
        # cabecera `Location` porque no se crea *un* recurso sino varios, y
        # algunos puede que ni se creen (los que ya existían suman cantidad);
        # por eso la respuesta son las filas resultantes, que es lo que el
        # cliente necesita para pintar la tabla ya normalizada.
        return Response(NeveraItemSerializer(creados, many=True).data, status=201)


@extend_schema(
    tags=["Nevera"],
    summary="Sugiere recetas con lo que hay en la nevera",
    description=(
        "Equivale a `/comer` del bot. Cruza el inventario ordenado por caducidad con "
        "el último análisis de recuperación y pide recetas a Gemini. **No guarda "
        "nada**: las recetas solo existen en la respuesta. "
        "Es `POST` y no `GET` aunque sea una consulta: cada llamada gasta una "
        "petición a Gemini, no es idempotente en coste y no debe cachearse."
    ),
    request=SuggestionsRequestSerializer,
    responses={
        200: SuggestionsResponseSerializer,
        400: ErrorDetailSerializer,
        409: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="La nevera está vacía, o al excluir no queda nada.",
        ),
        502: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="Gemini no devolvió algo interpretable.",
        ),
    },
)
class NeveraSuggestionsView(APIView):
    """POST /api/nevera/suggestions — recetas propuestas, sin escribir en BD."""

    def post(self, request):
        from nevera.services import excluir_por_nombre, get_items_by_expiry
        from nevera.suggestions import suggest_recipes
        from supabase_data.services import get_recent_analyses

        entrada = SuggestionsRequestSerializer(data=request.data)
        if not entrada.is_valid():
            return Response({"detail": _primer_error(entrada.errors)}, status=400)

        items = get_items_by_expiry()
        if not items:
            # 409 y no 404: la nevera existe, es su estado el que impide
            # atender la petición. Tampoco es un 400: la petición era correcta.
            return Response({"detail": "La nevera está vacía."}, status=409)

        excluidos: list = []
        sin_coincidencia: list = []
        terminos = entrada.validated_data["exclude"]
        if terminos:
            items, excluidos, sin_coincidencia = excluir_por_nombre(items, terminos)
            if not items:
                return Response(
                    {"detail": "Al excluir eso no queda nada en la nevera."}, status=409
                )

        analyses = get_recent_analyses(1)
        ultimo_analisis = analyses[0] if analyses else None

        try:
            recetas = suggest_recipes(items, ultimo_analisis)
        except ValueError as exc:
            return Response({"detail": f"No se pudo generar una sugerencia: {exc}"}, status=502)

        salida = SuggestionsResponseSerializer(
            {
                "recipes": recetas,
                "excluded": [i.nombre for i in excluidos],
                # Un término que no casa con nada suele ser una errata. Se
                # devuelve para avisar, en vez de ignorarlo en silencio: si no,
                # la receta llegaría con el ingrediente que se quería evitar y
                # parecería que la web no ha hecho caso.
                "not_found": sin_coincidencia,
                "analysis_date": ultimo_analisis["analysis_date"] if ultimo_analisis else None,
            }
        )
        return Response(salida.data)


@extend_schema(
    tags=["Nevera"],
    summary="Descuenta del inventario los ingredientes de una comida",
    description=(
        "Equivale a `/hecho <n>` del bot, pero recibe los ingredientes en el cuerpo en "
        "vez de un número que apunte a una sugerencia recordada por el servidor. "
        "Los básicos de despensa no se descuentan (se gestionan por presencia) y los "
        "ingredientes que ya no estén se devuelven en `no_encontrados`. Ninguna de las "
        "dos cosas es un error: por eso la respuesta es 200 con el detalle de lo que "
        "pasó con cada ingrediente."
    ),
    request=ConsumeRequestSerializer,
    responses={200: ConsumeResponseSerializer, 400: ErrorDetailSerializer},
)
class NeveraConsumeView(APIView):
    """POST /api/nevera/consume — resta cantidades del inventario.

    El cliente manda los ingredientes, no "la receta número 2": el servidor no
    guardó las sugerencias en ningún sitio (misma decisión que el alta, SDD-web
    §6). No es un agujero de seguridad: quien llega aquí está autenticado como
    el dueño y ya puede poner cualquier cantidad en cualquier item con el
    `PATCH` de la fase 4. Este endpoint no le da ningún poder nuevo.
    """

    def post(self, request):
        from nevera.services import consume_items

        entrada = ConsumeRequestSerializer(data=request.data)
        if not entrada.is_valid():
            return Response({"detail": _primer_error(entrada.errors)}, status=400)

        resultado = consume_items(entrada.validated_data["ingredients"])
        return Response(ConsumeResponseSerializer(resultado).data)
