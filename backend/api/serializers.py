"""Formas de entrada/salida de la API web.

Solo serialización: nada de lógica de negocio (SDD-web §3.1). Los servicios de
`nevera/` y `supabase_data/` devuelven modelos o dicts y aquí se les da forma
JSON estable para el frontend.
"""

from rest_framework import serializers

from nevera.models import NeveraItem


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
