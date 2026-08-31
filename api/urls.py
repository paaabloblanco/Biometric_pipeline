"""Rutas de la API web. Montadas en core/urls.py bajo /api/.

Esta capa es al navegador lo que bot/ es a Telegram: interfaz fina, sin lógica
de negocio. Los endpoints de datos (salud, nevera, análisis) se añaden en la
fase 2 del plan (docs/SDD-web.md §8).
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from api.auth import OwnerTokenObtainPairView

app_name = "api"

urlpatterns = [
    path("auth/login", OwnerTokenObtainPairView.as_view(), name="login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="refresh"),
]
