from .models import RegistroAuditoria


def _get_client_ip(request):
    if not request:
        return None
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def registrar_auditoria(request, accion, modelo='', objeto_id='', descripcion='', veterinaria=None):
    """Registra una acción relevante en el log de auditoría. Nunca debe interrumpir
    el flujo principal de la vista: cualquier error al auditar se descarta en silencio."""
    try:
        usuario = getattr(request, 'user', None)
        if usuario is not None and not usuario.is_authenticated:
            usuario = None

        if veterinaria is None:
            veterinaria = getattr(request, 'veterinaria', None)

        RegistroAuditoria.objects.create(
            veterinaria=veterinaria,
            usuario=usuario,
            accion=accion,
            modelo=modelo,
            objeto_id=str(objeto_id) if objeto_id else '',
            descripcion=descripcion,
            ip_address=_get_client_ip(request),
        )
    except Exception:
        pass
