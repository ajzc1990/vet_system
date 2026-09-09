import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Turno, Veterinario
from .forms import TurnoForm, VeterinarioForm
from apps.usuarios.models import Veterinaria
from apps.usuarios.utils import get_veterinaria_activa


@login_required
def lista_turnos(request):
    """Muestra la agenda de turnos filtrada por la veterinaria activa y fecha/estado seleccionados."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        turnos = Turno.objects.all()
    else:
        turnos = Turno.objects.filter(veterinaria=vet) if vet else Turno.objects.none()

    # 1. Filtro por Estado (Opcional)
    estado_filter = request.GET.get('estado')
    if estado_filter:
        turnos = turnos.filter(estado=estado_filter)

    # 2. Filtro por Fecha (Captura el input de la agenda)
    fecha_filter = request.GET.get('fecha')
    if fecha_filter:
        # Filtra exactamente los turnos del día seleccionado
        turnos = turnos.filter(fecha_hora__date=fecha_filter)

    turnos = turnos.select_related('mascota', 'mascota__cliente', 'veterinario').order_by('fecha_hora')

    return render(request, 'turnos/agenda.html', {
        'turnos': turnos,
        'estado_filter': estado_filter,
        'fecha_filter': fecha_filter,  # Retorna el string enviado para mantener la fecha en el input
        'hoy': timezone.now().date()
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