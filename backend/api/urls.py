"""Rutas de la API web. Montadas en core/urls.py bajo /api/.

Esta capa es al navegador lo que bot/ es a Telegram: interfaz fina, sin lógica
de negocio. Iteración 1 (solo lectura): auth + endpoints de consulta de salud,
nevera y análisis (docs/SDD-web.md §4 y §8).
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from api.auth import OwnerTokenObtainPairView
from api.views import AnalysesView, HealthLastDayView, HealthSeriesView, NeveraView

app_name = "api"

urlpatterns = [
    path("auth/login", OwnerTokenObtainPairView.as_view(), name="login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("health/last-day", HealthLastDayView.as_view(), name="health-last-day"),
    path("health/series", HealthSeriesView.as_view(), name="health-series"),
    path("analyses", AnalysesView.as_view(), name="analyses"),
    path("nevera", NeveraView.as_view(), name="nevera"),
]
