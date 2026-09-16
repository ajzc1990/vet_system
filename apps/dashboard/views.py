from datetime import timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import F

from apps.turnos.models import Turno
from apps.clientes.models import Mascota, Cliente
from apps.inventario.models import Producto
from apps.historia_clinica.models import ConsultaMedica, Internacion, RegistroVacuna, RegistroDesparasitacion
from apps.usuarios.models import MensajeContacto
from apps.usuarios.utils import get_veterinaria_activa


@login_required
def dashboard_principal(request):
    """Panel de Control con KPIs operativos, consultas de Landing Page y accesos rápidos en tiempo real."""
    if hasattr(request.user, 'cliente_portal'):
        return redirect('portal:home')

    vet = get_veterinaria_activa(request)
    hoy = timezone.now().date()
    limite_vencimiento = hoy + timedelta(days=30)

    # 1. Filtros base según Tenant
    if request.user.is_superuser and not vet:
        qs_turnos = Turno.objects.all()
        qs_mascotas = Mascota.objects.all()
        qs_productos = Producto.objects.all()
        qs_consultas = ConsultaMedica.objects.all()
        qs_internaciones = Internacion.objects.all()
    else:
        qs_turnos = Turno.objects.filter(veterinaria=vet) if vet else Turno.objects.none()
        qs_mascotas = Mascota.objects.filter(cliente__veterinaria=vet) if vet else Mascota.objects.none()
        qs_productos = Producto.objects.filter(veterinaria=vet) if vet else Producto.objects.none()
        qs_consultas = ConsultaMedica.objects.filter(veterinaria=vet) if vet else ConsultaMedica.objects.none()
        qs_internaciones = Internacion.objects.filter(veterinaria=vet) if vet else Internacion.objects.none()

    # 2. Métricas e Indicadores Clave (KPIs)
    turnos_hoy = qs_turnos.filter(fecha_hora__date=hoy).order_by('fecha_hora')
    cant_turnos_hoy = turnos_hoy.count()
    cant_turnos_pendientes = turnos_hoy.filter(estado__in=['PENDIENTE', 'CONFIRMADO', 'EN_ESPERA']).count()
    
    cant_pacientes = qs_mascotas.count()
    cant_consultas_hoy = qs_consultas.filter(fecha_hora__date=hoy).count()
    cant_internados = qs_internaciones.filter(estado='INTERNADO').count()

    # Alertas de Inventario
    cant_bajo_stock = qs_productos.filter(stock_actual__lte=F('stock_minimo')).count()
    cant_proximo_vencer = qs_productos.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=limite_vencimiento
    ).count()
    cant_vencidos = qs_productos.filter(fecha_vencimiento__lt=hoy).count()

    # Próximos turnos del día para la tabla resumida
    proximos_turnos = turnos_hoy.filter(estado__in=['PENDIENTE', 'CONFIRMADO', 'EN_ESPERA', 'ATENDIENDO'])[:5]

    # 3. Mensajes de Contacto recibidos desde la Landing Page: son consultas de
    # prospectos de TODO el SaaS (no pertenecen a ninguna veterinaria), así que sólo
    # el superusuario los ve. Ni se consultan para el resto del staff.
    if request.user.is_superuser:
        mensajes_contacto = MensajeContacto.objects.all().order_by('-fecha_envio')[:10]
        mensajes_no_leidos_count = MensajeContacto.objects.filter(leido=False).count()
    else:
        mensajes_contacto = MensajeContacto.objects.none()
        mensajes_no_leidos_count = 0

    return render(request, 'dashboard/dashboard.html', {
        'cant_turnos_hoy': cant_turnos_hoy,
        'cant_turnos_pendientes': cant_turnos_pendientes,
        'cant_pacientes': cant_pacientes,
        'cant_consultas_hoy': cant_consultas_hoy,
        'cant_internados': cant_internados,
        'cant_bajo_stock': cant_bajo_stock,
        'cant_proximo_vencer': cant_proximo_vencer,
        'cant_vencidos': cant_vencidos,
        'proximos_turnos': proximos_turnos,
        'mensajes_contacto': mensajes_contacto,
        'mensajes_no_leidos_count': mensajes_no_leidos_count,
        'hoy': hoy,
    })


def _mensaje_whatsapp(cliente, texto):
    telefono = (cliente.telefono or '').strip().replace(' ', '').replace('-', '')
    return {'telefono': telefono, 'texto': texto}


@login_required
def centro_recordatorios(request):
    """Centro de Recordatorios: agrupa turnos de mañana y refuerzos de vacunas/desparasitaciones
    próximos o vencidos, con un enlace directo de WhatsApp ya redactado para contactar al tutor."""
    vet = get_veterinaria_activa(request)
    hoy = timezone.now().date()
    manana = hoy + timedelta(days=1)
    limite_proximos = hoy + timedelta(days=7)

    if request.user.is_superuser and not vet:
        qs_turnos = Turno.objects.all()
        qs_vacunas = RegistroVacuna.objects.all()
        qs_despara = RegistroDesparasitacion.objects.all()
    else:
        qs_turnos = Turno.objects.filter(veterinaria=vet) if vet else Turno.objects.none()
        qs_vacunas = RegistroVacuna.objects.filter(veterinaria=vet) if vet else RegistroVacuna.objects.none()
        qs_despara = RegistroDesparasitacion.objects.filter(veterinaria=vet) if vet else RegistroDesparasitacion.objects.none()

    turnos_manana = qs_turnos.filter(
        fecha_hora__date=manana, estado__in=['PENDIENTE', 'CONFIRMADO']
    ).select_related('mascota', 'mascota__cliente').order_by('fecha_hora')

    vacunas_vencidas = qs_vacunas.filter(fecha_proxima_dosis__lt=hoy).select_related('mascota', 'mascota__cliente').order_by('fecha_proxima_dosis')
    vacunas_proximas = qs_vacunas.filter(fecha_proxima_dosis__gte=hoy, fecha_proxima_dosis__lte=limite_proximos).select_related('mascota', 'mascota__cliente').order_by('fecha_proxima_dosis')

    despara_vencidas = qs_despara.filter(fecha_proxima_dosis__lt=hoy).select_related('mascota', 'mascota__cliente').order_by('fecha_proxima_dosis')
    despara_proximas = qs_despara.filter(fecha_proxima_dosis__gte=hoy, fecha_proxima_dosis__lte=limite_proximos).select_related('mascota', 'mascota__cliente').order_by('fecha_proxima_dosis')

    def _armar(items, texto_fn):
        resultado = []
        for item in items:
            cliente = item.mascota.cliente
            resultado.append({
                'item': item,
                'whatsapp': _mensaje_whatsapp(cliente, texto_fn(item)),
            })
        return resultado

    turnos_data = _armar(turnos_manana, lambda t: (
        f"Hola {t.mascota.cliente.nombre}! Te recordamos el turno de {t.mascota.nombre} "
        f"para mañana {t.fecha_hora.strftime('%d/%m')} a las {t.fecha_hora.strftime('%H:%M')} hs."
    ))
    vacunas_vencidas_data = _armar(vacunas_vencidas, lambda v: (
        f"Hola {v.mascota.cliente.nombre}! La vacuna {v.nombre_vacuna} de {v.mascota.nombre} "
        f"venció el {v.fecha_proxima_dosis.strftime('%d/%m/%Y')}. Coordinemos un turno para regularizarla."
    ))
    vacunas_proximas_data = _armar(vacunas_proximas, lambda v: (
        f"Hola {v.mascota.cliente.nombre}! Te recordamos que la vacuna {v.nombre_vacuna} de {v.mascota.nombre} "
        f"vence el {v.fecha_proxima_dosis.strftime('%d/%m/%Y')}. ¿Coordinamos un turno?"
    ))
    despara_vencidas_data = _armar(despara_vencidas, lambda d: (
        f"Hola {d.mascota.cliente.nombre}! La desparasitación ({d.producto}) de {d.mascota.nombre} "
        f"venció el {d.fecha_proxima_dosis.strftime('%d/%m/%Y')}. Coordinemos la reposición."
    ))
    despara_proximas_data = _armar(despara_proximas, lambda d: (
        f"Hola {d.mascota.cliente.nombre}! Te recordamos que la desparasitación de {d.mascota.nombre} "
        f"vence el {d.fecha_proxima_dosis.strftime('%d/%m/%Y')}."
    ))

    return render(request, 'dashboard/centro_recordatorios.html', {
        'turnos_data': turnos_data,
        'vacunas_vencidas_data': vacunas_vencidas_data,
        'vacunas_proximas_data': vacunas_proximas_data,
        'despara_vencidas_data': despara_vencidas_data,
        'despara_proximas_data': despara_proximas_data,
        'hoy': hoy,
        'manana': manana,
    })