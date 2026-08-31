"""Documentación OpenAPI de la API (esquema + Swagger UI).

`drf-spectacular` genera el esquema **leyendo las views y los serializers**, no
de un fichero escrito a mano: es documentación derivada del código, así que no
puede quedarse desactualizada. Efecto secundario buscado: solo puede describir
bien lo que está tipado, así que empuja a que toda respuesta declare su forma.

Detalle de autenticación, que es el motivo de que estas dos views no usen la
configuración por defecto del proyecto: estas rutas **se abren en el
navegador**, y el navegador no lleva el JWT (lo guarda el JavaScript de la SPA
y lo pone a mano en la cabecera de cada petición). Con la autenticación por
defecto —solo JWT—, abrir `/api/docs/` devolvería `401` siempre. Por eso aquí
se autentica **por sesión**: basta con haber entrado antes en `/admin/`. El
permiso sigue siendo el mismo del resto de la API (`IsTheOwner`), así que la
documentación no queda expuesta a cualquiera.

Los atributos se repiten en las dos clases a propósito: sacarlos a un mixin
obliga a mypy a reconciliar dos bases que declaran lo mismo y no compensa para
dos clases.
"""

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication

from api.permissions import IsTheOwner


class SchemaView(SpectacularAPIView):
    """GET /api/schema/ — el contrato en sí, en YAML (OpenAPI 3)."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsTheOwner,)


class SwaggerView(SpectacularSwaggerView):
    """GET /api/docs/ — el mismo contrato, navegable (Swagger UI)."""

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsTheOwner,)

    # La página pide el esquema por AJAX; hay que darle la ruta con el
    # namespace de la app (`app_name = "api"` en api/urls.py).
    url_name = "api:schema"
