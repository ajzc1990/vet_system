# apps/usuarios/middleware.py

class TenantMiddleware:
    """Inyecta request.veterinaria en cada solicitud HTTP."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.veterinaria = None
        if request.user.is_authenticated:
            # Si el usuario tiene perfil con veterinaria asignada
            perfil = getattr(request.user, 'perfil', None)
            if perfil and perfil.veterinaria:
                request.veterinaria = perfil.veterinaria

        return self.get_response(request)