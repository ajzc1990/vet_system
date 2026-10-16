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


def veterinaria_del_usuario(user):
    """Veterinaria (tenant) del dueño de un token de API: a diferencia de
    get_veterinaria_activa (que lee request.veterinaria, resuelto por TenantMiddleware
    a partir de la sesión), esto se usa donde no hay sesión/middleware de por medio
    -DRF con TokenAuthentication, o el servidor MCP- y hay que resolverlo directo
    desde el perfil del usuario autenticado por token."""
    perfil = getattr(user, 'perfil', None)
    return perfil.veterinaria if perfil else None


def usuario_habilitado_para_api(user):
    """True si un token de este usuario debe poder usarse (API REST o MCP): superusuario,
    o con PerfilUsuario aprobado y con veterinaria asignada. Replica la misma condición
    que ya aplica CustomLoginView al autenticarse por sesión, para que un token emitido
    antes no sea una puerta trasera para una cuenta a la que le revocaron el acceso
    después (ver apps.api.permissions.EsUsuarioAprobadoDeLaVeterinaria)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfil', None)
    return bool(perfil and perfil.is_approved and perfil.veterinaria_id)
