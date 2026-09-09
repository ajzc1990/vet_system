from django.utils.deprecation import MiddlewareMixin

class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                request.veterinaria = request.user.perfil.veterinaria
            except AttributeError:
                # Caso para superusuarios creados desde la consola que aún no tienen perfil asignado
                request.veterinaria = None
        else:
            request.veterinaria = None