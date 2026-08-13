from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required

# Importaciones locales de Clientes
from .models import Cliente, Mascota
from .forms import ClienteForm, MascotaForm


def get_historia_components():
    """
    Importa de forma lazy los modelos reales de la app historia_clinica y su formulario
    para evitar importaciones circulares en el arranque del servidor.
    """
    from apps.historia_clinica.models import ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico
    try:
        from apps.historia_clinica.forms import ConsultaMedicaForm, EstudioMedicoForm
    except ImportError:
        from .forms import ConsultaMedicaForm
        EstudioMedicoForm = None

    return ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico, ConsultaMedicaForm, EstudioMedicoForm


def _get_user_veterinaria(user):
    """
    Helper para obtener la veterinaria asignada al usuario (soporta perfil o atributo directo).
    """
    if hasattr(user, 'perfil') and user.perfil and hasattr(user.perfil, 'veterinaria'):
        return user.perfil.veterinaria
    if hasattr(user, 'veterinaria'):
        return user.veterinaria
    return None


# ==============================================================================
# GESTIÓN DE CLIENTES
# ==============================================================================

@login_required
def lista_clientes(request):
    query = request.GET.get('q', '')
    user_vet = _get_user_veterinaria(request.user)

    if request.user.is_superuser:
        clientes = Cliente.objects.all()
    else:
        clientes = Cliente.objects.filter(veterinaria=user_vet) if user_vet else Cliente.objects.none()

    if query:
        clientes = clientes.filter(
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query) |
            Q(dni__icontains=query) |
            Q(telefono__icontains=query)
        )

    clientes = clientes.prefetch_related('mascotas')
    return render(request, 'clientes/lista_clientes.html', {'clientes': clientes, 'query': query})


@login_required
def detalle_cliente(request, cliente_id):
    vet = _get_user_veterinaria(request.user)
    
    if request.user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
    else:
        cliente = get_object_or_404(Cliente, pk=cliente_id, veterinaria=vet)

    mascotas = cliente.mascotas.all()
    return render(request, 'clientes/detalle_cliente.html', {
        'cliente': cliente, 
        'mascotas': mascotas
    })


@login_required
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            user_vet = _get_user_veterinaria(request.user)
            if user_vet:
                cliente.veterinaria = user_vet
            cliente.save()
            messages.success(request, f"Cliente {cliente.nombre} {cliente.apellido} registrado con éxito.")
            return redirect('clientes:detalle_cliente', cliente_id=cliente.id)
    else:
        form = ClienteForm()
    return render(request, 'clientes/form_cliente.html', {'form': form, 'titulo': 'Registrar Nuevo Cliente'})


@login_required
def editar_cliente(request, cliente_id):
    vet = _get_user_veterinaria(request.user)
    
    if request.user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
    else:
        cliente = get_object_or_404(Cliente, pk=cliente_id, veterinaria=vet)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos del cliente actualizados correctamente.")
            return redirect('clientes:detalle_cliente', cliente_id=cliente.id)
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'clientes/form_cliente.html', {'form': form, 'titulo': f'Editar Cliente: {cliente.nombre} {cliente.apellido}'})


# ==============================================================================
# GESTIÓN DE MASCOTAS
# ==============================================================================

@login_required
def agregar_mascota(request, cliente_id):
    vet = _get_user_veterinaria(request.user)
    
    if request.user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
    else:
        cliente = get_object_or_404(Cliente, pk=cliente_id, veterinaria=vet)

    if request.method == 'POST':
        form = MascotaForm(request.POST)
        if form.is_valid():
            mascota = form.save(commit=False)
            mascota.cliente = cliente
            mascota.save()
            messages.success(request, f"Mascota {mascota.nombre} agregada a {cliente.nombre}.")
            return redirect('clientes:detalle_cliente', cliente_id=cliente.id)
    else:
        form = MascotaForm()
    return render(request, 'clientes/form_mascota.html', {'form': form, 'cliente': cliente, 'titulo': f'Nueva Mascota para {cliente.nombre}'})


@login_required
def editar_mascota(request, mascota_id):
    vet = _get_user_veterinaria(request.user)
    
    if request.user.is_superuser:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    if request.method == 'POST':
        form = MascotaForm(request.POST, instance=mascota)
        if form.is_valid():
            form.save()
            messages.success(request, f"Datos de {mascota.nombre} actualizados.")
            return redirect('clientes:detalle_cliente', cliente_id=mascota.cliente.id)
    else:
        form = MascotaForm(instance=mascota)
    return render(request, 'clientes/form_mascota.html', {'form': form, 'cliente': mascota.cliente, 'titulo': f'Editar Mascota: {mascota.nombre}'})


# ==============================================================================
# HISTORIA CLÍNICA & CONSULTAS MÉDICAS
# ==============================================================================

@login_required
def detalle_historia_clinica(request, mascota_id):
    vet = _get_user_veterinaria(request.user)
    
    if request.user.is_superuser:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico, ConsultaMedicaForm, _ = get_historia_components()
    
    consultas = getattr(mascota, 'consultas', ConsultaMedica.objects.filter(mascota=mascota)).all().order_by('-fecha_hora').prefetch_related('estudios')
    vacunas = getattr(mascota, 'vacunas', RegistroVacuna.objects.filter(mascota=mascota)).all().order_by('-fecha_aplicacion')
    desparasitaciones = getattr(mascota, 'desparasitaciones', RegistroDesparasitacion.objects.filter(mascota=mascota)).all().order_by('-fecha_aplicacion')
    
    # IMPORTANTE: Se recuperan los estudios asociados a la mascota
    estudios = EstudioMedico.objects.filter(mascota=mascota).order_by('-fecha_estudio')

    if request.method == 'POST':
        form = ConsultaMedicaForm(request.POST, request.FILES)
        
        if 'veterinario' in form.fields:
            form.fields['veterinario'].required = False
        if 'mascota' in form.fields:
            form.fields['mascota'].required = False

        if form.is_valid():
            consulta = form.save(commit=False)
            consulta.mascota = mascota
            
            vet_instance = None
            if hasattr(request.user, 'veterinario'):
                vet_instance = request.user.veterinario
            elif hasattr(request.user, 'perfil') and hasattr(request.user.perfil, 'veterinario'):
                vet_instance = request.user.perfil.veterinario
            else:
                try:
                    from apps.historia_clinica.models import Veterinario
                    vet_instance = Veterinario.objects.filter(usuario=request.user).first() or Veterinario.objects.first()
                except Exception:
                    pass

            if vet_instance:
                consulta.veterinario = vet_instance

            consulta.save()

            # Procesar la subida del estudio desde la consulta inline
            if 'estudio_archivo' in request.FILES and request.FILES['estudio_archivo']:
                archivo_subido = request.FILES['estudio_archivo']
                titulo_estudio = request.POST.get('estudio_titulo') or f"Estudio Consulta - {consulta.fecha_hora.strftime('%d/%m/%Y')}"
                tipo_estudio = request.POST.get('estudio_tipo') or 'ECOGRAFIA'

                EstudioMedico.objects.create(
                    veterinaria=vet,
                    mascota=mascota,
                    veterinario=vet_instance,
                    consulta=consulta,
                    titulo=titulo_estudio,
                    tipo_estudio=tipo_estudio,
                    archivo=archivo_subido,
                    fecha_estudio=consulta.fecha_hora.date(),
                    observaciones=f"Adjuntado en consulta del {consulta.fecha_hora.strftime('%d/%m/%Y %H:%M')} hs."
                )

            messages.success(request, "Consulta médica registrada correctamente.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
        else:
            messages.error(request, "No se pudo guardar la consulta. Por favor, revisa los campos requeridos.")
    else:
        form = ConsultaMedicaForm()

    context = {
        'mascota': mascota,
        'consultas': consultas,
        'vacunas': vacunas,
        'desparasitaciones': desparasitaciones,
        'estudios': estudios,  # <--- VARIABLE CLAVE ENVIADA A LA PLANTILLA
        'form': form,
    }
    return render(request, 'clientes/historia_clinica.html', context)


@login_required
def editar_consulta(request, consulta_id):
    vet = _get_user_veterinaria(request.user)
    ConsultaMedica, _, _, _, ConsultaMedicaForm, _ = get_historia_components()
    
    if request.user.is_superuser:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id)
    else:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id, mascota__cliente__veterinaria=vet)
        
    mascota = consulta.mascota

    if request.method == 'POST':
        form = ConsultaMedicaForm(request.POST, instance=consulta)
        
        if 'veterinario' in form.fields:
            form.fields['veterinario'].required = False
        if 'mascota' in form.fields:
            form.fields['mascota'].required = False

        if form.is_valid():
            form.save()
            messages.success(request, "Consulta médica actualizada correctamente.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
    else:
        form = ConsultaMedicaForm(instance=consulta)

    context = {
        'form': form,
        'consulta': consulta,
        'mascota': mascota,
        'titulo': f'Editar Consulta'
    }
    return render(request, 'clientes/form_consulta.html', context)


@login_required
def eliminar_consulta(request, consulta_id):
    vet = _get_user_veterinaria(request.user)
    ConsultaMedica, _, _, _, _, _ = get_historia_components()
    
    if request.user.is_superuser:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id)
    else:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id, mascota__cliente__veterinaria=vet)
        
    mascota_id = consulta.mascota.id

    if request.method == 'POST':
        consulta.delete()
        messages.success(request, "La consulta médica ha sido eliminada.")
        return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)

    return render(request, 'clientes/confirmar_eliminar_consulta.html', {
        'consulta': consulta,
        'mascota': consulta.mascota
    })


# ==============================================================================
# VACUNAS Y DESPARASITACIONES (MODALES)
# ==============================================================================

@login_required
def agregar_vacuna(request, mascota_id):
    if request.method == 'POST':
        vet = _get_user_veterinaria(request.user)
        
        if request.user.is_superuser:
            mascota = get_object_or_404(Mascota, pk=mascota_id)
        else:
            mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

        _, RegistroVacuna, _, _, _, _ = get_historia_components()

        nombre_vacuna = request.POST.get('nombre_vacuna')
        fecha_aplicacion = request.POST.get('fecha_aplicacion')
        proxima_dosis = request.POST.get('proxima_dosis') or None
        lote = request.POST.get('lote') or None

        if nombre_vacuna and fecha_aplicacion:
            datos = {
                'mascota': mascota,
                'nombre_vacuna': nombre_vacuna,
                'fecha_aplicacion': fecha_aplicacion,
            }
            
            if hasattr(RegistroVacuna, 'lote') and lote:
                datos['lote'] = lote

            if proxima_dosis:
                if hasattr(RegistroVacuna, 'proxima_dosis'):
                    datos['proxima_dosis'] = proxima_dosis
                elif hasattr(RegistroVacuna, 'fecha_proxima'):
                    datos['fecha_proxima'] = proxima_dosis
                elif hasattr(RegistroVacuna, 'proximo_refuerzo'):
                    datos['proximo_refuerzo'] = proxima_dosis

            RegistroVacuna.objects.create(**datos)
            messages.success(request, f"Vacuna '{nombre_vacuna}' registrada con éxito.")
        else:
            messages.error(request, "Por favor completa los campos obligatorios para la vacuna.")

    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)


@login_required
def eliminar_vacuna(request, vacuna_id):
    vet = _get_user_veterinaria(request.user)
    _, RegistroVacuna, _, _, _, _ = get_historia_components()
    
    if request.user.is_superuser:
        vacuna = get_object_or_404(RegistroVacuna, pk=vacuna_id)
    else:
        vacuna = get_object_or_404(RegistroVacuna, pk=vacuna_id, mascota__cliente__veterinaria=vet)
        
    mascota_id = vacuna.mascota.id
    vacuna.delete()
    messages.success(request, "Registro de vacuna eliminado correctamente.")
    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)


@login_required
def agregar_desparasitacion(request, mascota_id):
    if request.method == 'POST':
        vet = _get_user_veterinaria(request.user)
        
        if request.user.is_superuser:
            mascota = get_object_or_404(Mascota, pk=mascota_id)
        else:
            mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

        _, _, RegistroDesparasitacion, _, _, _ = get_historia_components()

        producto = request.POST.get('producto')
        fecha_aplicacion = request.POST.get('fecha_aplicacion')
        proxima_dosis = request.POST.get('proxima_dosis') or None
        dosis = request.POST.get('dosis') or None

        if producto and fecha_aplicacion:
            datos = {
                'mascota': mascota,
                'producto': producto,
                'fecha_aplicacion': fecha_aplicacion,
            }

            if dosis and hasattr(RegistroDesparasitacion, 'dosis'):
                datos['dosis'] = dosis

            if proxima_dosis:
                if hasattr(RegistroDesparasitacion, 'proxima_dosis'):
                    datos['proxima_dosis'] = proxima_dosis
                elif hasattr(RegistroDesparasitacion, 'fecha_proxima'):
                    datos['fecha_proxima'] = proxima_dosis
                elif hasattr(RegistroDesparasitacion, 'proximo_refuerzo'):
                    datos['proximo_refuerzo'] = proxima_dosis

            RegistroDesparasitacion.objects.create(**datos)
            messages.success(request, f"Desparasitante '{producto}' registrado con éxito.")
        else:
            messages.error(request, "Por favor completa los campos obligatorios para el desparasitante.")

    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)


@login_required
def eliminar_desparasitacion(request, desparasitacion_id):
    vet = _get_user_veterinaria(request.user)
    _, _, RegistroDesparasitacion, _, _, _ = get_historia_components()
    
    if request.user.is_superuser:
        registro = get_object_or_404(RegistroDesparasitacion, pk=desparasitacion_id)
    else:
        registro = get_object_or_404(RegistroDesparasitacion, pk=desparasitacion_id, mascota__cliente__veterinaria=vet)
        
    mascota_id = registro.mascota.id
    registro.delete()
    messages.success(request, "Registro antiparasitario eliminado correctamente.")
    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)