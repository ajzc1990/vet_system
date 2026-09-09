def get_veterinaria_activa(request):
    """Devuelve la veterinaria (tenant) del usuario autenticado, o None si no tiene una asignada.

    TenantMiddleware ya resuelve `request.veterinaria` a partir del perfil del usuario para
    toda request autenticada; esta función expone esa única fuente de verdad. No debe agregarse
    un fallback a "la primera veterinaria de la base" (Veterinaria.objects.first()): eso filtraría
    datos de otro tenant a cualquier usuario sin perfil asignado.
    """
    return getattr(request, 'veterinaria', None)
