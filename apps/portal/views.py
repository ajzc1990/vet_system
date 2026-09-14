from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from .decorators import requerir_cliente_portal
from apps.clientes.models import Mascota
from apps.turnos.models import Turno
from apps.historia_clinica.models import (
    ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico, Internacion,
)


@login_required
@requerir_cliente_portal
def portal_home(request):
    """Panel principal del tutor: sus mascotas y próximos turnos."""
    cliente = request.user.cliente_portal
    mascotas = cliente.mascotas.all()

    proximos_turnos = Turno.objects.filter(
        mascota__cliente=cliente, fecha_hora__gte=timezone.now()
    ).exclude(estado='CANCELADO').select_related('mascota', 'veterinario').order_by('fecha_hora')[:5]

    return render(request, 'portal/home.html', {
        'cliente': cliente,
        'mascotas': mascotas,
        'proximos_turnos': proximos_turnos,
    })


@login_required
@requerir_cliente_portal
def portal_mascota_detalle(request, mascota_id):
    """Expediente de solo lectura de una mascota propia: consultas, vacunas, estudios e internaciones."""
    cliente = request.user.cliente_portal
    mascota = get_object_or_404(Mascota, pk=mascota_id, cliente=cliente)

    consultas = ConsultaMedica.objects.filter(mascota=mascota).select_related('veterinario').order_by('-fecha_hora')
    vacunas = RegistroVacuna.objects.filter(mascota=mascota).order_by('-fecha_aplicacion')
    desparasitaciones = RegistroDesparasitacion.objects.filter(mascota=mascota).order_by('-fecha_aplicacion')
    estudios = EstudioMedico.objects.filter(mascota=mascota).order_by('-fecha_estudio')
    internaciones = Internacion.objects.filter(mascota=mascota).order_by('-fecha_ingreso')

    return render(request, 'portal/mascota_detalle.html', {
        'mascota': mascota,
        'consultas': consultas,
        'vacunas': vacunas,
        'desparasitaciones': desparasitaciones,
        'estudios': estudios,
        'internaciones': internaciones,
    })


@login_required
@requerir_cliente_portal
def portal_turnos(request):
    """Historial completo de turnos (pasados y futuros) del tutor."""
    cliente = request.user.cliente_portal
    turnos = Turno.objects.filter(mascota__cliente=cliente).select_related('mascota', 'veterinario').order_by('-fecha_hora')

    return render(request, 'portal/turnos.html', {'turnos': turnos, 'cliente': cliente})
