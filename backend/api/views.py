"""Views de la API web.

Capa fina (SDD-web §3.1): cada view valida la entrada, llama a la misma función
de `services.py` que usa el handler de Telegram equivalente y devuelve JSON.
Cero lógica de negocio aquí.

Iteración 1 = solo lectura (SDD-web §7-E).
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import AnalysisSerializer, NeveraItemSerializer

# Tope defensivo para ?limit= en /api/analyses (evita traer toda la tabla).
MAX_ANALYSES = 366


class HealthLastDayView(APIView):
    """GET /api/health/last-day — datos crudos del último día. Equivale a /hoy."""

    def get(self, request):
        from supabase_data.services import get_last_day_data

        return Response(get_last_day_data())


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


class NeveraView(APIView):
    """GET /api/nevera — inventario completo. Equivale a /nevera."""

    def get(self, request):
        from nevera.services import list_all

        return Response(NeveraItemSerializer(list_all(), many=True).data)
