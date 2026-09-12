from rest_framework.permissions import BasePermission


class EsUsuarioAprobadoDeLaVeterinaria(BasePermission):
    """Sólo deja pasar a superusuarios o usuarios con un PerfilUsuario aprobado y con
    veterinaria asignada. Replica la misma condición que ya aplica CustomLoginView al
    autenticarse por sesión, para que un token de API no sea una puerta trasera para
    una cuenta que el login normal rechazaría (por ejemplo, si le revocaron la aprobación
    después de haber emitido el token)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        perfil = getattr(user, 'perfil', None)
        return bool(perfil and perfil.is_approved and perfil.veterinaria_id)
