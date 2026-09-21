import csv
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from apps.usuarios.decorators import requerir_rol_veterinario, es_veterinario_o_admin
from django.utils.crypto import get_random_string

# Importaciones locales de Clientes
from .models import Cliente, Mascota
from .forms import ClienteForm, MascotaForm
from apps.usuarios.utils import get_veterinaria_activa
from apps.usuarios.audit import registrar_auditoria


def get_historia_components():
    """
    Importa de forma lazy los modelos reales de la app historia_clinica y su formulario
    para evitar importaciones circulares en el arranque del servidor.
    """
    from apps.historia_clinica.models import ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico, Receta
    try:
        from apps.historia_clinica.forms import ConsultaMedicaForm, EstudioMedicoForm
    except ImportError:
        from .forms import ConsultaMedicaForm
        EstudioMedicoForm = None

    return ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico, ConsultaMedicaForm, EstudioMedicoForm, Receta


# ==============================================================================
# GESTIÓN DE CLIENTES
# ==============================================================================

@login_required
def lista_clientes(request):
    query = request.GET.get('q', '')
    user_vet = get_veterinaria_activa(request)

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
def exportar_clientes_csv(request):
    """Exporta a CSV el listado de clientes (respeta el mismo filtro de búsqueda de la lista)."""
    query = request.GET.get('q', '')
    user_vet = get_veterinaria_activa(request)

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

    clientes = clientes.prefetch_related('mascotas').order_by('apellido', 'nombre')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="clientes.csv"'
    response.write('﻿')  # BOM para que Excel detecte UTF-8 correctamente

    writer = csv.writer(response)
    writer.writerow(['Apellido', 'Nombre', 'DNI', 'Teléfono', 'Email', 'Dirección', 'Activo', 'Mascotas', 'Fecha de Alta'])
    for c in clientes:
        mascotas_str = ', '.join(m.nombre for m in c.mascotas.all())
        writer.writerow([
            c.apellido, c.nombre, c.dni, c.telefono, c.email or '', c.direccion or '',
            'Sí' if c.activo else 'No', mascotas_str, c.creado_en.strftime('%d/%m/%Y'),
        ])

    return response


@login_required
def detalle_cliente(request, cliente_id):
    vet = get_veterinaria_activa(request)
    
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
            user_vet = get_veterinaria_activa(request)
            if user_vet:
                cliente.veterinaria = user_vet
            cliente.save()
            registrar_auditoria(
                request, 'CREAR', modelo='Cliente', objeto_id=cliente.id,
                descripcion=f"Alta de cliente: {cliente.nombre} {cliente.apellido} (DNI: {cliente.dni})"
            )
            messages.success(request, f"Cliente {cliente.nombre} {cliente.apellido} registrado con éxito.")
            return redirect('clientes:detalle_cliente', cliente_id=cliente.id)
    else:
        form = ClienteForm()
    return render(request, 'clientes/form_cliente.html', {'form': form, 'titulo': 'Registrar Nuevo Cliente'})


@login_required
def editar_cliente(request, cliente_id):
    vet = get_veterinaria_activa(request)
    
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
    vet = get_veterinaria_activa(request)
    
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
    vet = get_veterinaria_activa(request)
    
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
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico, ConsultaMedicaForm, _, Receta = get_historia_components()
    
    consultas = getattr(mascota, 'consultas', ConsultaMedica.objects.filter(mascota=mascota)).all().order_by('-fecha_hora').prefetch_related('estudios')
    vacunas = getattr(mascota, 'vacunas', RegistroVacuna.objects.filter(mascota=mascota)).all().order_by('-fecha_aplicacion')
    desparasitaciones = getattr(mascota, 'desparasitaciones', RegistroDesparasitacion.objects.filter(mascota=mascota)).all().order_by('-fecha_aplicacion')
    
    # IMPORTANTE: Se recuperan los estudios asociados a la mascota
    estudios = EstudioMedico.objects.filter(mascota=mascota).order_by('-fecha_estudio')

    # Internaciones (hospitalizaciones) del paciente
    from apps.historia_clinica.models import Internacion
    internaciones = Internacion.objects.filter(mascota=mascota).select_related('veterinario_responsable')
    internacion_activa = internaciones.filter(estado='INTERNADO').first()

    # Recetas digitales emitidas al paciente
    recetas = Receta.objects.filter(mascota=mascota).select_related('veterinario').prefetch_related('items')

    if request.method == 'POST' and not es_veterinario_o_admin(request.user):
        messages.error(request, "Acceso denegado: Esta función requiere permisos de Médico Veterinario.")
        return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)

    if request.method == 'POST':
        form = ConsultaMedicaForm(request.POST, request.FILES, veterinaria=vet)

        if 'veterinario' in form.fields:
            form.fields['veterinario'].required = False
        if 'mascota' in form.fields:
            form.fields['mascota'].required = False

        if form.is_valid():
            consulta = form.save(commit=False)
            consulta.mascota = mascota
            
            from apps.turnos.models import Veterinario
            vet_instance = Veterinario.objects.filter(usuario=request.user).first()

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
        form = ConsultaMedicaForm(veterinaria=vet)

    context = {
        'mascota': mascota,
        'consultas': consultas,
        'vacunas': vacunas,
        'desparasitaciones': desparasitaciones,
        'estudios': estudios,  # <--- VARIABLE CLAVE ENVIADA A LA PLANTILLA
        'internaciones': internaciones,
        'internacion_activa': internacion_activa,
        'recetas': recetas,
        'form': form,
    }
    return render(request, 'clientes/historia_clinica.html', context)


@login_required
@requerir_rol_veterinario
def editar_consulta(request, consulta_id):
    vet = get_veterinaria_activa(request)
    ConsultaMedica, _, _, _, ConsultaMedicaForm, _, _ = get_historia_components()
    
    if request.user.is_superuser:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id)
    else:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id, mascota__cliente__veterinaria=vet)
        
    mascota = consulta.mascota

    if request.method == 'POST':
        form = ConsultaMedicaForm(request.POST, instance=consulta, veterinaria=vet)

        if 'veterinario' in form.fields:
            form.fields['veterinario'].required = False
        if 'mascota' in form.fields:
            form.fields['mascota'].required = False

        if form.is_valid():
            form.save()
            messages.success(request, "Consulta médica actualizada correctamente.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
    else:
        form = ConsultaMedicaForm(instance=consulta, veterinaria=vet)

    context = {
        'form': form,
        'consulta': consulta,
        'mascota': mascota,
        'titulo': f'Editar Consulta'
    }
    return render(request, 'clientes/form_consulta.html', context)


@login_required
@requerir_rol_veterinario
def eliminar_consulta(request, consulta_id):
    vet = get_veterinaria_activa(request)
    ConsultaMedica, _, _, _, _, _, _ = get_historia_components()
    
    if request.user.is_superuser:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id)
    else:
        consulta = get_object_or_404(ConsultaMedica, pk=consulta_id, mascota__cliente__veterinaria=vet)
        
    mascota_id = consulta.mascota.id

    if request.method == 'POST':
        mascota_nombre = consulta.mascota.nombre
        consulta.delete()
        registrar_auditoria(
            request, 'ELIMINAR', modelo='ConsultaMedica', objeto_id=consulta_id,
            descripcion=f"Eliminación de consulta médica de {mascota_nombre}"
        )
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
@requerir_rol_veterinario
def agregar_vacuna(request, mascota_id):
    if request.method == 'POST':
        vet = get_veterinaria_activa(request)
        
        if request.user.is_superuser:
            mascota = get_object_or_404(Mascota, pk=mascota_id)
        else:
            mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

        _, RegistroVacuna, _, _, _, _, _ = get_historia_components()

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
            
            if lote:
                datos['lote'] = lote

            if proxima_dosis:
                datos['fecha_proxima_dosis'] = proxima_dosis

            RegistroVacuna.objects.create(**datos)
            messages.success(request, f"Vacuna '{nombre_vacuna}' registrada con éxito.")
        else:
            messages.error(request, "Por favor completa los campos obligatorios para la vacuna.")

    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)


@login_required
@requerir_rol_veterinario
def eliminar_vacuna(request, vacuna_id):
    vet = get_veterinaria_activa(request)
    _, RegistroVacuna, _, _, _, _, _ = get_historia_components()
    
    if request.user.is_superuser:
        vacuna = get_object_or_404(RegistroVacuna, pk=vacuna_id)
    else:
        vacuna = get_object_or_404(RegistroVacuna, pk=vacuna_id, mascota__cliente__veterinaria=vet)
        
    mascota_id = vacuna.mascota.id
    mascota_nombre = vacuna.mascota.nombre
    nombre_vacuna = vacuna.nombre_vacuna
    vacuna.delete()
    registrar_auditoria(
        request, 'ELIMINAR', modelo='RegistroVacuna', objeto_id=vacuna_id,
        descripcion=f"Eliminación de vacuna '{nombre_vacuna}' de {mascota_nombre}"
    )
    messages.success(request, "Registro de vacuna eliminado correctamente.")
    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)


@login_required
@requerir_rol_veterinario
def agregar_desparasitacion(request, mascota_id):
    if request.method == 'POST':
        vet = get_veterinaria_activa(request)
        
        if request.user.is_superuser:
            mascota = get_object_or_404(Mascota, pk=mascota_id)
        else:
            mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

        _, _, RegistroDesparasitacion, _, _, _, _ = get_historia_components()

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

            if dosis:
                datos['dosis'] = dosis

            if proxima_dosis:
                datos['fecha_proxima_dosis'] = proxima_dosis

            RegistroDesparasitacion.objects.create(**datos)
            messages.success(request, f"Desparasitante '{producto}' registrado con éxito.")
        else:
            messages.error(request, "Por favor completa los campos obligatorios para el desparasitante.")

    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)


# ==============================================================================
# PORTAL DEL CLIENTE (ACCESO PARA TUTORES)
# ==============================================================================

@login_required
def otorgar_acceso_portal(request, cliente_id):
    """Genera credenciales de acceso al Portal del Cliente para que el tutor pueda
    consultar la historia clínica y turnos de sus mascotas desde su propia cuenta."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
    else:
        cliente = get_object_or_404(Cliente, pk=cliente_id, veterinaria=vet)

    if cliente.usuario:
        messages.info(request, f"{cliente.nombre} ya tiene acceso al portal (usuario: {cliente.usuario.username}).")
        return redirect('clientes:detalle_cliente', cliente_id=cliente.id)

    if request.method == 'POST':
        base_username = re.sub(r'[^a-zA-Z0-9]', '', cliente.dni) or f"cliente{cliente.id}"
        username = base_username
        contador = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{contador}"
            contador += 1

        password_generada = get_random_string(10)
        user = User.objects.create_user(
            username=username,
            password=password_generada,
            first_name=cliente.nombre,
            last_name=cliente.apellido,
            email=cliente.email or '',
        )
        cliente.usuario = user
        cliente.save(update_fields=['usuario'])

        registrar_auditoria(
            request, 'CREAR', modelo='PortalCliente', objeto_id=cliente.id,
            descripcion=f"Acceso al portal creado para {cliente.nombre} {cliente.apellido} (usuario: {username})"
        )

        if cliente.email:
            send_mail(
                subject="Acceso a tu Portal de Cliente - VeterSystem",
                message=(
                    f"Hola {cliente.nombre}!\n\n"
                    "Ya podés acceder al portal para consultar la historia clínica y los turnos de tus mascotas.\n\n"
                    f"Usuario: {username}\nContraseña: {password_generada}\n\n"
                    f"Ingresá en: {request.build_absolute_uri('/login/')}"
                ),
                from_email=None,
                recipient_list=[cliente.email],
                fail_silently=True,
            )

        messages.success(
            request,
            f"Acceso al portal creado. Usuario: '{username}' — Contraseña: '{password_generada}'. "
            "Compartísela al tutor/a: no se volverá a mostrar por seguridad."
        )
        return redirect('clientes:detalle_cliente', cliente_id=cliente.id)

    return render(request, 'clientes/confirmar_acceso_portal.html', {'cliente': cliente})


@login_required
@requerir_rol_veterinario
def eliminar_desparasitacion(request, desparasitacion_id):
    vet = get_veterinaria_activa(request)
    _, _, RegistroDesparasitacion, _, _, _, _ = get_historia_components()
    
    if request.user.is_superuser:
        registro = get_object_or_404(RegistroDesparasitacion, pk=desparasitacion_id)
    else:
        registro = get_object_or_404(RegistroDesparasitacion, pk=desparasitacion_id, mascota__cliente__veterinaria=vet)
        
    mascota_id = registro.mascota.id
    mascota_nombre = registro.mascota.nombre
    producto_registro = registro.producto
    registro.delete()
    registrar_auditoria(
        request, 'ELIMINAR', modelo='RegistroDesparasitacion', objeto_id=desparasitacion_id,
        descripcion=f"Eliminación de desparasitación '{producto_registro}' de {mascota_nombre}"
    )
    messages.success(request, "Registro antiparasitario eliminado correctamente.")
    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)