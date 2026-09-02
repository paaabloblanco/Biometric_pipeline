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
    AnalysisSerializer,
    DayDetailSerializer,
    ErrorDetailSerializer,
    LastDaySerializer,
    NeveraItemSerializer,
    NeveraItemUpdateSerializer,
    SeriesSerializer,
    SleepNightSerializer,
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
