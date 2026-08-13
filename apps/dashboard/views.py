from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import F

from apps.turnos.models import Turno
from apps.clientes.models import Mascota, Cliente
from apps.inventario.models import Producto
from apps.historia_clinica.models import ConsultaMedica
from apps.usuarios.models import MensajeContacto


def _get_veterinaria(request):
    """Auxiliar robusto para obtener la veterinaria activa del usuario/request."""
    if hasattr(request, 'veterinaria') and request.veterinaria:
        return request.veterinaria
    if hasattr(request.user, 'perfil') and request.user.perfil and hasattr(request.user.perfil, 'veterinaria'):
        if request.user.perfil.veterinaria:
            return request.user.perfil.veterinaria
    if hasattr(request.user, 'veterinaria') and request.user.veterinaria:
        return request.user.veterinaria
    try:
        from apps.usuarios.models import Veterinaria
        return Veterinaria.objects.first()
    except (ImportError, Exception):
        pass
    return None


@login_required
def dashboard_principal(request):
    """Panel de Control con KPIs operativos, consultas de Landing Page y accesos rápidos en tiempo real."""
    vet = _get_veterinaria(request)
    hoy = timezone.now().date()
    limite_vencimiento = hoy + timedelta(days=30)

    # 1. Filtros base según Tenant
    if request.user.is_superuser and not vet:
        qs_turnos = Turno.objects.all()
        qs_mascotas = Mascota.objects.all()
        qs_productos = Producto.objects.all()
        qs_consultas = ConsultaMedica.objects.all()
    else:
        qs_turnos = Turno.objects.filter(veterinaria=vet) if vet else Turno.objects.none()
        qs_mascotas = Mascota.objects.filter(cliente__veterinaria=vet) if vet else Mascota.objects.none()
        qs_productos = Producto.objects.filter(veterinaria=vet) if vet else Producto.objects.none()
        qs_consultas = ConsultaMedica.objects.filter(veterinaria=vet) if vet else ConsultaMedica.objects.none()

    # 2. Métricas e Indicadores Clave (KPIs)
    turnos_hoy = qs_turnos.filter(fecha_hora__date=hoy).order_by('fecha_hora')
    cant_turnos_hoy = turnos_hoy.count()
    cant_turnos_pendientes = turnos_hoy.filter(estado__in=['PENDIENTE', 'CONFIRMADO', 'EN_ESPERA']).count()
    
    cant_pacientes = qs_mascotas.count()
    cant_consultas_hoy = qs_consultas.filter(fecha_hora__date=hoy).count()

    # Alertas de Inventario
    cant_bajo_stock = qs_productos.filter(stock_actual__lte=F('stock_minimo')).count()
    cant_proximo_vencer = qs_productos.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=limite_vencimiento
    ).count()
    cant_vencidos = qs_productos.filter(fecha_vencimiento__lt=hoy).count()

    # Próximos turnos del día para la tabla resumida
    proximos_turnos = turnos_hoy.filter(estado__in=['PENDIENTE', 'CONFIRMADO', 'EN_ESPERA', 'ATENDIENDO'])[:5]

    # 3. Mensajes de Contacto recibidos desde la Landing Page
    mensajes_contacto = MensajeContacto.objects.all().order_by('-fecha_envio')[:10]
    mensajes_no_leidos_count = MensajeContacto.objects.filter(leido=False).count()

    return render(request, 'dashboard/dashboard.html', {
        'cant_turnos_hoy': cant_turnos_hoy,
        'cant_turnos_pendientes': cant_turnos_pendientes,
        'cant_pacientes': cant_pacientes,
        'cant_consultas_hoy': cant_consultas_hoy,
        'cant_bajo_stock': cant_bajo_stock,
        'cant_proximo_vencer': cant_proximo_vencer,
        'cant_vencidos': cant_vencidos,
        'proximos_turnos': proximos_turnos,
        'mensajes_contacto': mensajes_contacto,
        'mensajes_no_leidos_count': mensajes_no_leidos_count,
        'hoy': hoy,
    })