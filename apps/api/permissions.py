from rest_framework.permissions import BasePermission

from apps.usuarios.decorators import es_veterinario_o_admin


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


class EsVeterinarioOAdmin(BasePermission):
    """Para las altas médicas (consultas, vacunas, recetas): mismo criterio que el decorador
    requerir_rol_veterinario de la web, así un recepcionista no puede cargar por la API lo
    que la web no le deja cargar."""

    message = "Esta acción requiere permisos de Médico Veterinario."

    def has_permission(self, request, view):
        return es_veterinario_o_admin(request.user)
