# apps/usuarios/decorators.py
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def es_veterinario_o_admin(user):
    """
    Auxiliar que determina si un usuario tiene rango médico/administrativo.
    Soporta superusuarios, grupos de Django o perfil con rol.
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    # Verificación por grupos
    if user.groups.filter(name='Veterinarios').exists():
        return True

    # Verificación por perfil de usuario
    if hasattr(user, 'perfil') and getattr(user.perfil, 'rol', None) in ['VET', 'ADMIN']:
        return True

    return False


def requerir_rol_veterinario(view_func):
    """
    Decorador para proteger vistas médicas críticas (Consultas, Medicación, Adjuntos).
    Si un recepcionista intenta acceder, es reorientado con un mensaje de advertencia.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if es_veterinario_o_admin(request.user):
            return view_func(request, *args, **kwargs)

        messages.error(
            request, 
            "Acceso denegado: Esta función requiere permisos de Médico Veterinario."
        )
        return redirect('dashboard:index')

    return _wrapped_view