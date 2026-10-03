def get_veterinaria_activa(request):
    """Devuelve la veterinaria (tenant) del usuario autenticado, o None si no tiene una asignada.

    TenantMiddleware ya resuelve `request.veterinaria` a partir del perfil del usuario para
    toda request autenticada; esta función expone esa única fuente de verdad. No debe agregarse
    un fallback a "la primera veterinaria de la base" (Veterinaria.objects.first()): eso filtraría
    datos de otro tenant a cualquier usuario sin perfil asignado.
    """
    return getattr(request, 'veterinaria', None)


def es_veterinaria_demo(veterinaria):
    """True si `veterinaria` es el tenant compartido de la demo pública (ver seed_demo).
    Se usa para apagar acciones que no tiene sentido -o es riesgoso- dejar disponibles
    a cualquier visitante que entra a probar el sistema (ej. mandar WhatsApp real)."""
    from .management.commands.seed_demo import DEMO_VET_NOMBRE
    return bool(veterinaria and veterinaria.nombre == DEMO_VET_NOMBRE)
