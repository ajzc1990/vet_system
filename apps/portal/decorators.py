from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def requerir_cliente_portal(view_func):
    """Protege las vistas del Portal del Cliente: solo usuarios con un Cliente vinculado
    (creado por el staff de la veterinaria desde la ficha del cliente) pueden entrar."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if not hasattr(request.user, 'cliente_portal'):
            messages.error(request, "Esta sección es exclusiva para clientes con acceso al portal.")
            return redirect('dashboard:index')

        return view_func(request, *args, **kwargs)

    return _wrapped_view
