"""Views de la API web.

Capa fina (SDD-web §3.1): cada view valida la entrada, llama a la misma función
de `services.py` que usa el handler de Telegram equivalente y devuelve JSON.
Cero lógica de negocio aquí.

Iteración 1 = solo lectura (SDD-web §7-E).

Sobre los `@extend_schema`: estas views heredan de `APIView` pelado y construyen
la respuesta dentro de `get()`, así que `drf-spectacular` —que inspecciona la
clase, no la ejecución— no puede adivinar qué devuelven. El decorador es la
forma de declararlo explícitamente. Es el contrato de la API escrito al lado
del código que lo cumple.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    AnalysisSerializer,
    ErrorDetailSerializer,
    LastDaySerializer,
    NeveraItemSerializer,
    SeriesSerializer,
)
from supabase_data.services import SERIES_METRICS

# Tope defensivo para ?limit= en /api/analyses (evita traer toda la tabla).
MAX_ANALYSES = 366


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
