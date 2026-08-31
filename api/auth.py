"""Login JWT que además exige que quien entra sea el dueño.

`TokenObtainPairView` de serie da tokens a cualquier usuario de Django válido.
Aquí se rechaza a quien no sea superusuario, para que la puerta de entrada
aplique la misma regla que `IsTheOwner` (SDD-web §5).
"""

from rest_framework import exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class OwnerTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # super().validate() ya ha autenticado y fijado self.user si llegamos aquí.
        assert self.user is not None
        if not self.user.is_superuser:
            raise exceptions.AuthenticationFailed(self.error_messages["no_active_account"])
        return data


class OwnerTokenObtainPairView(TokenObtainPairView):
    serializer_class = OwnerTokenObtainPairSerializer
