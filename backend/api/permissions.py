from rest_framework.permissions import BasePermission


class IsTheOwner(BasePermission):
    """Solo el dueño del proyecto puede usar la API.

    App de un solo usuario (ver docs/SDD-web.md §5): el "dueño" es el
    superusuario. Aunque solo exista una cuenta, esto es defensa en
    profundidad si algún día se crea otro usuario sin querer.
    """

    message = "No autorizado."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)
