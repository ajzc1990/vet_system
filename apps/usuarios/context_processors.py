def suscripcion_activa(request):
    """Expone la suscripción de la veterinaria activa (si existe) a todos los templates,
    para poder mostrar el banner de vencimiento sin repetir la consulta en cada vista.
    Los tenants sin una Suscripcion asociada (ej. datos históricos/demo) simplemente no
    muestran el banner: la falta de registro de facturación nunca bloquea el acceso.

    También expone es_demo_publica, para avisar en cualquier pantalla que el usuario está
    en el entorno de demo compartido (ver usuarios.views.entrar_a_demo)."""
    veterinaria = getattr(request, 'veterinaria', None)
    if not veterinaria:
        return {'suscripcion': None, 'es_demo_publica': False}

    from .management.commands.seed_demo import DEMO_VET_NOMBRE

    suscripcion = getattr(veterinaria, 'suscripcion', None)
    return {'suscripcion': suscripcion, 'es_demo_publica': veterinaria.nombre == DEMO_VET_NOMBRE}


def recordatorios_pendientes(request):
    """Cantidad de recordatorios de hoy (turnos de mañana + vacunas/desparasitaciones
    vencidas o por vencer en 7 días) para la campanita del nav, que lleva al Centro de
    Recordatorios (dashboard:centro_recordatorios). No aplica a clientes del Portal:
    ellos no le recuerdan nada a nadie."""
    if not request.user.is_authenticated or hasattr(request.user, 'cliente_portal'):
        return {'recordatorios_pendientes_count': 0}

    from datetime import timedelta
    from django.utils import timezone
    from apps.turnos.models import Turno
    from apps.historia_clinica.models import RegistroVacuna, RegistroDesparasitacion

    veterinaria = getattr(request, 'veterinaria', None)
    es_superuser_global = request.user.is_superuser and not veterinaria

    hoy = timezone.now().date()
    manana = hoy + timedelta(days=1)
    limite = hoy + timedelta(days=7)

    filtro_tenant = {} if es_superuser_global else {'veterinaria': veterinaria}
    if not es_superuser_global and not veterinaria:
        return {'recordatorios_pendientes_count': 0}

    turnos_manana = Turno.objects.filter(
        fecha_hora__date=manana, estado__in=['PENDIENTE', 'CONFIRMADO'], **filtro_tenant,
    ).count()
    vacunas = RegistroVacuna.objects.filter(
        fecha_proxima_dosis__isnull=False, fecha_proxima_dosis__lte=limite, **filtro_tenant,
    ).count()
    despara = RegistroDesparasitacion.objects.filter(
        fecha_proxima_dosis__isnull=False, fecha_proxima_dosis__lte=limite, **filtro_tenant,
    ).count()

    return {'recordatorios_pendientes_count': turnos_manana + vacunas + despara}
