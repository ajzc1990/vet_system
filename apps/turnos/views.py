import os
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Turno, Veterinario, SolicitudTurnoWeb
from .forms import TurnoForm, VeterinarioForm
from apps.usuarios.models import Veterinaria
from apps.usuarios.utils import get_veterinaria_activa


@login_required
def lista_turnos(request):
    """Muestra la agenda de turnos filtrada por la veterinaria activa y fecha/estado seleccionados.

    Por defecto (sin filtro de fecha ni "ver todos") solo se muestra la agenda del día de hoy,
    para no traer el historial completo de turnos de la clínica en una sola consulta/página."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        turnos = Turno.objects.all()
    else:
        turnos = Turno.objects.filter(veterinaria=vet) if vet else Turno.objects.none()

    # 1. Filtro por Estado (Opcional)
    estado_filter = request.GET.get('estado')
    if estado_filter:
        turnos = turnos.filter(estado=estado_filter)

    # 2. Filtro por Fecha / "Ver todos"
    fecha_filter = request.GET.get('fecha')
    ver_todos = request.GET.get('todos') == '1'
    hoy = timezone.localdate()

    if fecha_filter:
        turnos = turnos.filter(fecha_hora__date=fecha_filter)
    elif not ver_todos:
        turnos = turnos.filter(fecha_hora__date=hoy)

    turnos = turnos.select_related('mascota', 'mascota__cliente', 'veterinario').order_by('fecha_hora')

    paginator = Paginator(turnos, 25)
    turnos_pagina = paginator.get_page(request.GET.get('page'))

    return render(request, 'turnos/agenda.html', {
        'turnos': turnos_pagina,
        'estado_filter': estado_filter,
        'fecha_filter': fecha_filter,  # Retorna el string enviado para mantener la fecha en el input
        'ver_todos': ver_todos,
        'hoy': hoy,
    })

@login_required
def crear_turno(request):
    """Formulario para agendar un nuevo turno aislando los datos por veterinaria."""
    vet = get_veterinaria_activa(request)

    if request.method == 'POST':
        form = TurnoForm(request.POST, user=request.user, veterinaria=vet)
        if form.is_valid():
            turno = form.save(commit=False)
            
            # Asignación del tenant
            if vet:
                turno.veterinaria = vet
            elif request.user.is_superuser:
                turno.veterinaria = Veterinaria.objects.first()
            else:
                messages.error(request, "No se encontró una veterinaria activa asociada a tu usuario.")
                return redirect('turnos:lista_turnos')

            turno.save()
            messages.success(request, f"¡Turno agendado con éxito para {turno.mascota.nombre}!")
            return redirect('turnos:lista_turnos')
        else:
            print("\n" + "="*50)
            print("❌ ERRORES DE VALIDACIÓN EN TURNOFORM:")
            print(form.errors)
            print("="*50 + "\n")
            messages.error(request, "Error al agendar el turno. Revisa los datos ingresados.")
    else:
        form = TurnoForm(user=request.user, veterinaria=vet)

    return render(request, 'turnos/nuevo_turno.html', {
        'form': form,
        'titulo': 'Agendar Nuevo Turno'
    })


@login_required
def editar_turno(request, pk):
    """Edita los datos de un turno con validación previa de tenant."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        turno = get_object_or_404(Turno, pk=pk)
    else:
        turno = get_object_or_404(Turno, pk=pk, veterinaria=vet)

    if request.method == 'POST':
        form = TurnoForm(request.POST, instance=turno, user=request.user, veterinaria=vet)
        if form.is_valid():
            form.save()
            messages.success(request, f"Turno de '{turno.mascota.nombre}' actualizado correctamente.")
            return redirect('turnos:lista_turnos')
        else:
            messages.error(request, "No se pudieron guardar los cambios. Revisa los campos.")
    else:
        form = TurnoForm(instance=turno, user=request.user, veterinaria=vet)

    return render(request, 'turnos/nuevo_turno.html', {
        'form': form,
        'turno': turno,
        'titulo': f'Editar Turno: {turno.mascota.nombre}'
    })


@login_required
def cambiar_estado_turno(request, pk, nuevo_estado):
    """Cambia el estado de un turno protegiendo el acceso multi-tenant."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        turno = get_object_or_404(Turno, pk=pk)
    else:
        turno = get_object_or_404(Turno, pk=pk, veterinaria=vet)

    if nuevo_estado in dict(Turno.ESTADOS):
        turno.estado = nuevo_estado
        turno.save()
        messages.info(request, f"Estado del turno actualizado a {turno.get_estado_display()}.")
    else:
        messages.error(request, "El estado especificado no es válido.")

    return redirect('turnos:lista_turnos')


@login_required
def atender_turno(request, pk):
    """
    Inicia la atención del paciente desde la agenda de turnos, pasa el estado a 'ATENDIENDO' 
    y redirige a la Historia Clínica con la referencia del turno activa.
    """
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        turno = get_object_or_404(Turno, pk=pk)
    else:
        turno = get_object_or_404(Turno, pk=pk, veterinaria=vet)

    # Actualizar estado a ATENDIENDO si estaba PENDIENTE o CONFIRMADO
    if turno.estado in ['PENDIENTE', 'CONFIRMADO', 'EN_ESPERA']:
        turno.estado = 'ATENDIENDO'
        turno.save(update_fields=['estado'])

    messages.success(request, f"Iniciando consulta para {turno.mascota.nombre}.")
    
    # Redirige a la historia clínica del paciente llevando la variable turno_id en la QueryString
    return redirect(f"/clientes/mascotas/{turno.mascota.id}/historia-clinica/?turno_id={turno.id}")


@login_required
def cancelar_turno(request, pk):
    """Marca un turno como cancelado previa confirmación."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        turno = get_object_or_404(Turno, pk=pk)
    else:
        turno = get_object_or_404(Turno, pk=pk, veterinaria=vet)

    if request.method == 'POST':
        turno.estado = 'CANCELADO'
        turno.save()
        messages.success(request, f"El turno de '{turno.mascota.nombre}' fue cancelado.")
        return redirect('turnos:lista_turnos')

    return render(request, 'turnos/confirmar_cancelar_turno.html', {'turno': turno})


# ==============================================================================
# RESERVA DE TURNOS ONLINE (SOLO CLIENTES CON CUENTA EN EL PORTAL)
# ==============================================================================

@login_required
def solicitar_turno_publico(request, veterinaria_id):
    """Formulario de reserva online, reservado a clientes que ya tienen cuenta en el
    Portal de ESTA veterinaria: se los reconoce automáticamente (nombre/teléfono
    autocompletados, mascota elegida de una lista) y no hace falta re-tipear nada.

    Quien no esté logueado, o esté logueado pero no sea cliente de esta veterinaria,
    no puede generar el pedido: tiene que pedirle a la clínica que lo cargue como
    cliente y le dé acceso al Portal primero. Genera una SolicitudTurnoWeb pendiente
    de revisión; el staff la convierte en Turno real."""
    veterinaria = get_object_or_404(Veterinaria, pk=veterinaria_id, activo=True)

    cliente_portal = getattr(request.user, 'cliente_portal', None)
    if not cliente_portal or cliente_portal.veterinaria_id != veterinaria.id:
        messages.error(
            request,
            f"Para solicitar un turno online necesitás una cuenta de cliente en {veterinaria.nombre}. "
            "Si ya sos paciente, pedile a la clínica que te dé acceso al Portal."
        )
        if cliente_portal:
            return redirect('portal:home')
        return redirect('landing')

    mascotas_cliente = cliente_portal.mascotas.all()

    if request.method == 'POST':
        motivo = request.POST.get('motivo')
        fecha_deseada = request.POST.get('fecha_deseada')
        franja_preferida = request.POST.get('franja_preferida') or 'CUALQUIERA'
        mascota = mascotas_cliente.filter(pk=request.POST.get('mascota_id')).first()

        if mascota and motivo and fecha_deseada:
            SolicitudTurnoWeb.objects.create(
                veterinaria=veterinaria,
                nombre_tutor=f"{cliente_portal.nombre} {cliente_portal.apellido}",
                telefono=cliente_portal.telefono,
                email=cliente_portal.email,
                nombre_mascota=mascota.nombre,
                especie=mascota.get_especie_display(),
                motivo=motivo,
                fecha_deseada=fecha_deseada,
                franja_preferida=franja_preferida,
            )
            messages.success(
                request,
                f"¡Gracias {cliente_portal.nombre}! Recibimos tu pedido de turno para {mascota.nombre}. "
                "El equipo de la clínica se va a comunicar para confirmarlo."
            )
            return redirect('portal:turnos')
        elif not mascota:
            messages.error(request, "Seleccioná para cuál de tus mascotas es el turno.")
        else:
            messages.error(request, "Por favor completá todos los campos obligatorios.")

    return render(request, 'turnos/solicitar_turno_publico.html', {
        'veterinaria': veterinaria,
        'cliente_portal': cliente_portal,
        'mascotas_cliente': mascotas_cliente,
    })


@login_required
def lista_solicitudes_turno(request):
    """Bandeja de pedidos de turno recibidos por el formulario público, para que el
    staff los revise y agende el turno real (o los descarte)."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        solicitudes = SolicitudTurnoWeb.objects.all()
    else:
        solicitudes = SolicitudTurnoWeb.objects.filter(veterinaria=vet) if vet else SolicitudTurnoWeb.objects.none()

    return render(request, 'turnos/lista_solicitudes.html', {
        'solicitudes': solicitudes.order_by('estado', '-creado_el'),
    })


@login_required
def actualizar_estado_solicitud(request, solicitud_id, nuevo_estado):
    """Marca una solicitud de turno web como Contactada o Descartada."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        solicitud = get_object_or_404(SolicitudTurnoWeb, pk=solicitud_id)
    else:
        solicitud = get_object_or_404(SolicitudTurnoWeb, pk=solicitud_id, veterinaria=vet)

    if nuevo_estado in dict(SolicitudTurnoWeb.ESTADOS):
        solicitud.estado = nuevo_estado
        solicitud.save(update_fields=['estado'])
        messages.success(request, "Solicitud actualizada correctamente.")

    return redirect('turnos:lista_solicitudes_turno')