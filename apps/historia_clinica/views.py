import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, Http404
from django.utils import timezone

# ReportLab Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from .forms import (
    ConsultaMedicaForm, RegistroVacunaForm, RegistroDesparasitacionForm, EstudioMedicoForm,
    InternacionForm, EvolucionInternacionForm, AltaInternacionForm,
    RecetaForm, ItemRecetaFormSet,
)
from .models import (
    Mascota, ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico,
    Internacion, EvolucionInternacion, Receta, ItemReceta,
)
from .ia import generar_resumen_clinico, ResumenIADeshabilitado, ResumenIAError
from apps.inventario.models import MovimientoStock, Producto
from apps.usuarios.decorators import requerir_rol_veterinario
from apps.usuarios.utils import get_veterinaria_activa
from apps.usuarios.audit import registrar_auditoria


@login_required
def expediente_mascota(request, mascota_id):
    """Alias histórico de la ficha del paciente. La vista canónica es clientes:detalle_historia_clinica;
    esta se conserva solo para no romper enlaces/URLs antiguos, pero delega el renderizado a esa vista
    (evita mantener dos plantillas duplicadas del mismo expediente clínico)."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        get_object_or_404(Mascota, pk=mascota_id)
    else:
        get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)


@login_required
@requerir_rol_veterinario
@transaction.atomic
def nueva_consulta(request, mascota_id):
    """Registra una consulta médica vinculada al paciente, descuenta insumos y adjunta un estudio si fue seleccionado."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    if request.method == 'POST':
        form = ConsultaMedicaForm(request.POST, request.FILES, veterinaria=vet)
        if form.is_valid():
            consulta = form.save(commit=False)
            consulta.mascota = mascota
            if vet:
                consulta.veterinaria = vet
            consulta.save()

            # Descuento de inventario opcional
            producto = form.cleaned_data.get('producto_inventario')
            cantidad = form.cleaned_data.get('cantidad_insumo') or 1

            if producto:
                if producto.stock_actual >= cantidad:
                    # MovimientoStock.save() ya descuenta el stock del producto: no repetir el descuento acá.
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo='SALIDA',
                        cantidad=cantidad,
                        motivo=f"Consulta Médica - Paciente: {mascota.nombre}"
                    )
                else:
                    messages.warning(
                        request,
                        f"Consulta registrada, pero '{producto.nombre}' no tenía suficiente stock ({producto.stock_actual} disp.)."
                    )

            # Procesar archivo/estudio adjunto opcional
            archivo = form.cleaned_data.get('estudio_archivo')
            if archivo:
                titulo_estudio = form.cleaned_data.get('estudio_titulo') or f"Estudio Consulta - {consulta.fecha_hora.strftime('%d/%m/%Y')}"
                tipo_estudio = form.cleaned_data.get('estudio_tipo') or 'OTRO'
                
                EstudioMedico.objects.create(
                    veterinaria=vet,
                    mascota=mascota,
                    veterinario=consulta.veterinario,
                    consulta=consulta,
                    titulo=titulo_estudio,
                    tipo_estudio=tipo_estudio,
                    archivo=archivo,
                    fecha_estudio=consulta.fecha_hora.date(),
                    observaciones=f"Adjuntado en consulta del {consulta.fecha_hora.strftime('%d/%m/%Y %H:%M')} hs."
                )

            messages.success(request, f"Consulta médica de {mascota.nombre} registrada correctamente.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)

        # Fallback: Procesamiento del formulario inline enviando inputs HTML directos
        motivo = request.POST.get('motivo_consulta')
        diagnostico = request.POST.get('diagnostico')
        tratamiento = request.POST.get('tratamiento')

        if motivo and diagnostico and tratamiento:
            vet_atendiente = None
            if hasattr(request.user, 'veterinario'):
                vet_atendiente = request.user.veterinario

            consulta = ConsultaMedica.objects.create(
                veterinaria=vet,
                mascota=mascota,
                veterinario=vet_atendiente,
                motivo_consulta=motivo,
                diagnostico=diagnostico,
                tratamiento=tratamiento,
                anamnesis=request.POST.get('anamnesis', ''),
                examen_clinico=request.POST.get('examen_clinico', ''),
                peso_actual_kg=request.POST.get('peso_actual_kg') or None,
                temperatura_c=request.POST.get('temperatura_c') or None,
                frecuencia_cardiaca=request.POST.get('frecuencia_cardiaca') or None,
            )

            # Procesar subida de archivo desde el formulario inline
            if 'estudio_archivo' in request.FILES and request.FILES['estudio_archivo']:
                archivo_subido = request.FILES['estudio_archivo']
                titulo_estudio = request.POST.get('estudio_titulo') or f"Estudio Adjunto - {consulta.fecha_hora.strftime('%d/%m/%Y')}"
                tipo_estudio = request.POST.get('estudio_tipo') or 'ECOGRAFIA'

                EstudioMedico.objects.create(
                    veterinaria=vet,
                    mascota=mascota,
                    veterinario=vet_atendiente,
                    consulta=consulta,
                    titulo=titulo_estudio,
                    tipo_estudio=tipo_estudio,
                    archivo=archivo_subido,
                    fecha_estudio=consulta.fecha_hora.date(),
                    observaciones=f"Adjuntado en consulta del {consulta.fecha_hora.strftime('%d/%m/%Y %H:%M')} hs."
                )

            messages.success(request, f"Consulta médica de {mascota.nombre} registrada correctamente.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
        else:
            messages.error(request, "Por favor completa los campos obligatorios (Motivo, Diagnóstico y Tratamiento).")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)

    else:
        form = ConsultaMedicaForm(veterinaria=vet)

    return render(request, 'historia_clinica/form_consulta.html', {
        'form': form,
        'mascota': mascota,
        'titulo': f'Nueva Consulta: {mascota.nombre}'
    })


@login_required
@requerir_rol_veterinario
@transaction.atomic
def registrar_vacuna(request, mascota_id):
    """Registra la aplicación de una vacuna y aplica el descuento en inventario."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    if request.method == 'POST':
        form = RegistroVacunaForm(request.POST, veterinaria=vet)
        if form.is_valid():
            vacuna = form.save(commit=False)
            vacuna.mascota = mascota
            if vet:
                vacuna.veterinaria = vet
            vacuna.save()

            producto = form.cleaned_data.get('producto_inventario')
            if producto:
                if producto.stock_actual >= 1:
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo='SALIDA',
                        cantidad=1,
                        motivo=f"Aplicación de Vacuna ({vacuna.nombre_vacuna}) - Paciente: {mascota.nombre}"
                    )
                else:
                    messages.warning(
                        request,
                        f"Vacuna registrada, pero '{producto.nombre}' no tenía stock disponible."
                    )

            messages.success(request, f"Vacuna registrada con éxito para {mascota.nombre}.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
        else:
            messages.error(request, "Error al registrar la vacuna. Revisa los datos ingresados.")
    else:
        form = RegistroVacunaForm(veterinaria=vet)

    return render(request, 'historia_clinica/form_vacuna.html', {
        'form': form,
        'mascota': mascota,
        'titulo': f'Aplicación de Vacuna: {mascota.nombre}'
    })


@login_required
@requerir_rol_veterinario
@transaction.atomic
def registrar_desparasitacion(request, mascota_id):
    """Registra la aplicación de desparasitantes internos/externos."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    if request.method == 'POST':
        form = RegistroDesparasitacionForm(request.POST, veterinaria=vet)
        if form.is_valid():
            desparasitacion = form.save(commit=False)
            desparasitacion.mascota = mascota
            if vet:
                desparasitacion.veterinaria = vet
            desparasitacion.save()

            producto = form.cleaned_data.get('producto_inventario')
            if producto:
                if producto.stock_actual >= 1:
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo='SALIDA',
                        cantidad=1,
                        motivo=f"Desparasitación ({desparasitacion.producto}) - Paciente: {mascota.nombre}"
                    )
                else:
                    messages.warning(
                        request,
                        f"Desparasitación registrada, pero '{producto.nombre}' no tenía stock disponible."
                    )

            messages.success(request, f"Desparasitación registrada para {mascota.nombre}.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
        else:
            messages.error(request, "Error al registrar la desparasitación. Revisa los datos.")
    else:
        form = RegistroDesparasitacionForm(veterinaria=vet)

    return render(request, 'historia_clinica/form_desparasitacion.html', {
        'form': form,
        'mascota': mascota,
        'titulo': f'Desparasitación: {mascota.nombre}'
    })


@login_required
@requerir_rol_veterinario
def subir_estudio(request, mascota_id):
    """Permite adjuntar un archivo/estudio médico de forma independiente."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    if request.method == 'POST':
        form = EstudioMedicoForm(request.POST, request.FILES, veterinaria=vet, mascota=mascota)
        if form.is_valid():
            estudio = form.save(commit=False)
            estudio.mascota = mascota
            if vet:
                estudio.veterinaria = vet
            elif hasattr(mascota.cliente, 'veterinaria'):
                estudio.veterinaria = mascota.cliente.veterinaria
            estudio.save()

            messages.success(request, f"Estudio '{estudio.titulo}' adjuntado correctamente a {mascota.nombre}.")
            return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
        else:
            messages.error(request, "Error al subir el estudio médico. Revisa los archivos o datos.")
    else:
        form = EstudioMedicoForm(veterinaria=vet, mascota=mascota)

    return render(request, 'historia_clinica/form_estudio.html', {
        'form': form,
        'mascota': mascota,
        'titulo': f'Adjuntar Estudio: {mascota.nombre}'
    })


@login_required
@requerir_rol_veterinario
def eliminar_estudio(request, estudio_id):
    """Elimina un estudio adjunto del expediente y borra el archivo físico del servidor."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        estudio = get_object_or_404(EstudioMedico, pk=estudio_id)
    else:
        estudio = get_object_or_404(EstudioMedico, pk=estudio_id, veterinaria=vet)

    mascota_id = estudio.mascota.id

    if request.method == 'POST':
        titulo_estudio = estudio.titulo
        if estudio.archivo and os.path.exists(estudio.archivo.path):
            try:
                os.remove(estudio.archivo.path)
            except Exception:
                pass

        estudio.delete()
        registrar_auditoria(
            request, 'ELIMINAR', modelo='EstudioMedico', objeto_id=estudio_id,
            descripcion=f"Eliminación del estudio '{titulo_estudio}' de {estudio.mascota.nombre}"
        )
        messages.success(request, "Estudio médico eliminado correctamente.")
        return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)

    return render(request, 'historia_clinica/confirmar_eliminar_estudio.html', {
        'estudio': estudio
    })


@login_required
def descargar_receta_pdf(request, consulta_id):
    """Genera un PDF con el resumen de la consulta, datos del tenant y logo institucional."""
    vet = get_veterinaria_activa(request)
    consulta = get_object_or_404(ConsultaMedica, pk=consulta_id)

    if not request.user.is_superuser:
        if vet and hasattr(consulta, 'veterinaria') and consulta.veterinaria and consulta.veterinaria != vet:
            raise Http404("No tienes permisos para acceder a esta receta.")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Receta_{consulta.mascota.nombre}_{consulta.fecha_hora.strftime("%Y%m%d")}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0d6efd'),
        spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6c757d'),
        spaceAfter=3
    )

    vet_obj = consulta.veterinaria or vet
    nombre_vet = vet_obj.nombre if vet_obj else "Clínica Veterinaria VeterSystem"
    cuit_vet = f"CUIT/RIF: {vet_obj.cuit_rif}" if vet_obj and vet_obj.cuit_rif else ""
    tel_vet = f"Tel: {vet_obj.telefono}" if vet_obj and vet_obj.telefono else ""
    dir_vet = vet_obj.direccion if vet_obj and vet_obj.direccion else ""

    header_text = [
        Paragraph(f"<b>{nombre_vet}</b>", title_style),
        Paragraph(f"{cuit_vet} {('| ' + tel_vet) if tel_vet else ''}".strip(), subtitle_style),
        Paragraph(f"{dir_vet}", subtitle_style),
        Paragraph(f"<b>Comprobante de Consulta Médica</b> | Fecha: {consulta.fecha_hora.strftime('%d/%m/%Y %H:%M')}", subtitle_style),
    ]

    logo_img = None
    if vet_obj and vet_obj.logo and os.path.exists(vet_obj.logo.path):
        try:
            logo_img = Image(vet_obj.logo.path, width=75, height=75)
            logo_img.hAlign = 'RIGHT'
        except Exception:
            logo_img = None

    if logo_img:
        header_table = Table([[header_text, logo_img]], colWidths=[430, 90])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        story.append(header_table)
    else:
        for p in header_text:
            story.append(p)

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0d6efd'), spaceBefore=8, spaceAfter=15))

    datos_paciente = [
        [
            Paragraph(f"<b>Paciente:</b> {consulta.mascota.nombre}", styles['Normal']),
            Paragraph(f"<b>Especie/Raza:</b> {consulta.mascota.get_especie_display()} / {consulta.mascota.raza or 'Mestizo'}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Tutor/a:</b> {consulta.mascota.cliente.nombre} {consulta.mascota.cliente.apellido}", styles['Normal']),
            Paragraph(f"<b>Peso:</b> {consulta.peso_actual_kg or '-'} kg | <b>Temp:</b> {consulta.temperatura_c or '-'} °C", styles['Normal'])
        ]
    ]
    t_paciente = Table(datos_paciente, colWidths=[260, 260])
    t_paciente.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(t_paciente)
    story.append(Spacer(1, 15))

    story.append(Paragraph(f"<b>Motivo de Consulta:</b> {consulta.motivo_consulta}", styles['Normal']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Diagnóstico:</b> {consulta.diagnostico or 'Sin registro'}", styles['Normal']))
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>RP / Indicaciones y Tratamiento:</b>", ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#198754'))))
    story.append(Spacer(1, 6))
    
    tratamiento_texto = consulta.tratamiento or "Sin indicaciones registradas."
    tratamiento_p = Paragraph(tratamiento_texto.replace('\n', '<br/>'), styles['Normal'])
    t_tratamiento = Table([[tratamiento_p]], colWidths=[520])
    t_tratamiento.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffffff')),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#198754')),
    ]))
    story.append(t_tratamiento)
    story.append(Spacer(1, 40))

    vet_nombre = "Médico Veterinario"
    if consulta.veterinario:
        vet_nombre = f"Dr(a). {consulta.veterinario.nombre} {consulta.veterinario.apellido}"

    datos_firma = [
        ["_______________________________________"],
        [f"<b>{vet_nombre}</b>"],
        ["Firma y Sello Profesional"]
    ]
    t_firma = Table(datos_firma, colWidths=[250], hAlign='RIGHT')
    t_firma.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_firma)

    doc.build(story)
    return response


@login_required
@requerir_rol_veterinario
@transaction.atomic
def nueva_receta(request, mascota_id):
    """Emite una receta digital estructurada (medicamento, dosis, duración, indicaciones) para el paciente."""
    vet = get_veterinaria_activa(request)
    mascota = _get_mascota_tenant(request, mascota_id, vet)

    if request.method == 'POST':
        form = RecetaForm(request.POST, veterinaria=vet, mascota=mascota)
        formset = ItemRecetaFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            filas_completas = [f for f in formset if f.cleaned_data and f.esta_completo()]

            if not filas_completas:
                messages.error(request, "Agregá al menos un medicamento antes de guardar la receta.")
            else:
                receta = form.save(commit=False)
                receta.mascota = mascota
                if vet:
                    receta.veterinaria = vet
                if not receta.veterinario_id and hasattr(request.user, 'veterinario'):
                    receta.veterinario = request.user.veterinario
                receta.save()

                for f in filas_completas:
                    ItemReceta.objects.create(
                        receta=receta,
                        medicamento=f.cleaned_data['medicamento'],
                        dosis=f.cleaned_data.get('dosis', ''),
                        duracion=f.cleaned_data.get('duracion', ''),
                        indicaciones=f.cleaned_data.get('indicaciones', ''),
                    )

                registrar_auditoria(
                    request, 'CREAR', modelo='Receta', objeto_id=receta.id,
                    descripcion=f"Emisión de receta digital para {mascota.nombre}"
                )

                messages.success(request, f"Receta emitida correctamente para {mascota.nombre}.")
                return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)
        else:
            messages.error(request, "No se pudo emitir la receta. Revisa los datos ingresados.")
    else:
        form = RecetaForm(veterinaria=vet, mascota=mascota)
        formset = ItemRecetaFormSet()

    return render(request, 'historia_clinica/form_receta.html', {
        'form': form,
        'formset': formset,
        'mascota': mascota,
        'titulo': f'Nueva Receta: {mascota.nombre}'
    })


@login_required
@requerir_rol_veterinario
def eliminar_receta(request, receta_id):
    """Elimina una receta digital emitida (uso administrativo, ej. carga erronea)."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        receta = get_object_or_404(Receta, pk=receta_id)
    else:
        receta = get_object_or_404(Receta, pk=receta_id, veterinaria=vet)

    mascota_id = receta.mascota.id

    if request.method == 'POST':
        mascota_nombre = receta.mascota.nombre
        receta.delete()
        registrar_auditoria(
            request, 'ELIMINAR', modelo='Receta', objeto_id=receta_id,
            descripcion=f"Eliminación de receta digital de {mascota_nombre}"
        )
        messages.success(request, "La receta fue eliminada correctamente.")
        return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)

    return render(request, 'historia_clinica/confirmar_eliminar_receta.html', {
        'receta': receta
    })


@login_required
def descargar_receta_digital_pdf(request, receta_id):
    """Genera el PDF de una receta digital estructurada (medicamentos, dosis, duración e indicaciones)."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        receta = get_object_or_404(Receta, pk=receta_id)
    else:
        receta = get_object_or_404(Receta, pk=receta_id, veterinaria=vet)

    mascota = receta.mascota

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Receta_{mascota.nombre}_{receta.fecha_emision.strftime("%Y%m%d")}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#0d6efd'), spaceAfter=2)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6c757d'), spaceAfter=3)

    vet_obj = receta.veterinaria or vet
    nombre_vet = vet_obj.nombre if vet_obj else "Clínica Veterinaria VeterSystem"
    cuit_vet = f"CUIT/RIF: {vet_obj.cuit_rif}" if vet_obj and vet_obj.cuit_rif else ""
    tel_vet = f"Tel: {vet_obj.telefono}" if vet_obj and vet_obj.telefono else ""
    dir_vet = vet_obj.direccion if vet_obj and vet_obj.direccion else ""

    header_text = [
        Paragraph(f"<b>{nombre_vet}</b>", title_style),
        Paragraph(f"{cuit_vet} {('| ' + tel_vet) if tel_vet else ''}".strip(), subtitle_style),
        Paragraph(f"{dir_vet}", subtitle_style),
        Paragraph(f"<b>Receta Digital</b> | Fecha: {receta.fecha_emision.strftime('%d/%m/%Y %H:%M')}", subtitle_style),
    ]

    logo_img = None
    if vet_obj and vet_obj.logo and os.path.exists(vet_obj.logo.path):
        try:
            logo_img = Image(vet_obj.logo.path, width=75, height=75)
            logo_img.hAlign = 'RIGHT'
        except Exception:
            logo_img = None

    if logo_img:
        header_table = Table([[header_text, logo_img]], colWidths=[430, 90])
        header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(header_table)
    else:
        for p in header_text:
            story.append(p)

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0d6efd'), spaceBefore=8, spaceAfter=15))

    datos_paciente = [
        [
            Paragraph(f"<b>Paciente:</b> {mascota.nombre}", styles['Normal']),
            Paragraph(f"<b>Especie/Raza:</b> {mascota.get_especie_display()} / {mascota.raza or 'Mestizo'}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Tutor/a:</b> {mascota.cliente.nombre} {mascota.cliente.apellido}", styles['Normal']),
            Paragraph(f"<b>Peso:</b> {mascota.peso_kg or '-'} kg", styles['Normal'])
        ]
    ]
    t_paciente = Table(datos_paciente, colWidths=[260, 260])
    t_paciente.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(t_paciente)
    story.append(Spacer(1, 15))

    if receta.diagnostico:
        story.append(Paragraph(f"<b>Diagnóstico:</b> {receta.diagnostico}", styles['Normal']))
        story.append(Spacer(1, 10))

    story.append(Paragraph("<b>RP / Medicamentos:</b>", ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#198754'))))
    story.append(Spacer(1, 6))

    tabla_data = [["Medicamento", "Dosis", "Duración", "Indicaciones"]]
    for item in receta.items.all():
        tabla_data.append([item.medicamento, item.dosis or '-', item.duracion or '-', item.indicaciones or '-'])

    t_items = Table(tabla_data, colWidths=[140, 110, 110, 160])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#198754')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 15))

    if receta.observaciones:
        story.append(Paragraph(f"<b>Observaciones:</b> {receta.observaciones}", styles['Normal']))
        story.append(Spacer(1, 30))
    else:
        story.append(Spacer(1, 30))

    vet_nombre = "Médico Veterinario"
    if receta.veterinario:
        vet_nombre = f"Dr(a). {receta.veterinario.nombre} {receta.veterinario.apellido}"

    datos_firma = [
        ["_______________________________________"],
        [f"<b>{vet_nombre}</b>"],
        ["Firma y Sello Profesional"]
    ]
    t_firma = Table(datos_firma, colWidths=[250], hAlign='RIGHT')
    t_firma.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_firma)

    doc.build(story)
    return response


@login_required
@requerir_rol_veterinario
def generar_resumen_ia(request, mascota_id):
    """Genera (o regenera) el resumen clínico de la mascota con IA."""
    vet = get_veterinaria_activa(request)
    mascota = _get_mascota_tenant(request, mascota_id, vet)

    if request.method == 'POST':
        try:
            generar_resumen_clinico(mascota, usuario=request.user)
            messages.success(request, "Resumen clínico generado con IA.")
        except ResumenIADeshabilitado:
            messages.error(request, "La función de resúmenes con IA no está habilitada.")
        except ResumenIAError:
            messages.error(request, "No se pudo generar el resumen en este momento. Probá de nuevo en unos minutos.")

    return redirect('clientes:detalle_historia_clinica', mascota_id=mascota.id)


@login_required
def descargar_carnet_vacunas_pdf(request, mascota_id):
    """Genera el Carnet de Vacunación oficial del paciente en PDF con el logo institucional."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        mascota = get_object_or_404(Mascota, pk=mascota_id)
    else:
        mascota = get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)

    vacunas = RegistroVacuna.objects.filter(mascota=mascota).order_by('-fecha_aplicacion')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Carnet_Vacunas_{mascota.nombre}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    vet_obj = mascota.cliente.veterinaria if hasattr(mascota, 'cliente') and mascota.cliente else vet
    logo_img = None
    if vet_obj and vet_obj.logo and os.path.exists(vet_obj.logo.path):
        try:
            logo_img = Image(vet_obj.logo.path, width=65, height=65)
            logo_img.hAlign = 'RIGHT'
        except Exception:
            logo_img = None

    title_text = [
        Paragraph("<b>CARNET SANITARIO Y DE VACUNACIÓN</b>", ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0d6efd'))),
        Paragraph(f"<b>{vet_obj.nombre if vet_obj else 'Clínica Veterinaria'}</b>", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#6c757d'))),
    ]

    if logo_img:
        t_header = Table([[title_text, logo_img]], colWidths=[430, 90])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        story.append(t_header)
    else:
        for p in title_text:
            story.append(p)

    story.append(Spacer(1, 10))

    info = [
        [Paragraph(f"<b>Mascota:</b> {mascota.nombre}", styles['Normal']), Paragraph(f"<b>Especie:</b> {mascota.get_especie_display()}", styles['Normal'])],
        [Paragraph(f"<b>Raza:</b> {mascota.raza or 'Mestizo'}", styles['Normal']), Paragraph(f"<b>Sexo:</b> {mascota.get_sexo_display()}", styles['Normal'])],
        [Paragraph(f"<b>Tutor/a:</b> {mascota.cliente.nombre} {mascota.cliente.apellido}", styles['Normal']), Paragraph(f"<b>Teléfono:</b> {mascota.cliente.telefono or '-'}", styles['Normal'])]
    ]
    t_info = Table(info, colWidths=[260, 260])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e9ecef')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#ced4da')),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 15))

    tabla_data = [["Vacuna / Dosis", "Lote", "Fecha Aplicación", "Próx. Revacunación", "Veterinario"]]
    for v in vacunas:
        v_vet_nombre = "-"
        if v.veterinario:
            v_vet_nombre = f"{v.veterinario.nombre} {v.veterinario.apellido}"

        prox_dosis = "-"
        if v.fecha_proxima_dosis:
            prox_dosis = v.fecha_proxima_dosis.strftime('%d/%m/%Y')

        tabla_data.append([
            v.nombre_vacuna,
            getattr(v, 'lote', '-') or '-',
            v.fecha_aplicacion.strftime('%d/%m/%Y'),
            prox_dosis,
            v_vet_nombre
        ])

    if len(tabla_data) == 1:
        tabla_data.append(["Sin vacunas registradas", "-", "-", "-", "-"])

    t_vacunas = Table(tabla_data, colWidths=[130, 80, 100, 100, 110])
    t_vacunas.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(t_vacunas)

    doc.build(story)
    return response


# ==============================================================================
# INTERNACIÓN / HOSPITALIZACIÓN
# ==============================================================================

def _get_mascota_tenant(request, mascota_id, vet):
    if request.user.is_superuser and not vet:
        return get_object_or_404(Mascota, pk=mascota_id)
    return get_object_or_404(Mascota, pk=mascota_id, cliente__veterinaria=vet)


def _get_internacion_tenant(request, internacion_id, vet):
    if request.user.is_superuser and not vet:
        return get_object_or_404(Internacion, pk=internacion_id)
    return get_object_or_404(Internacion, pk=internacion_id, veterinaria=vet)


@login_required
def lista_internaciones(request):
    """Sala de Internación: tablero con los pacientes actualmente internados y su historial reciente."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        qs = Internacion.objects.all()
    else:
        qs = Internacion.objects.filter(veterinaria=vet) if vet else Internacion.objects.none()

    qs = qs.select_related('mascota', 'mascota__cliente', 'veterinario_responsable')

    internaciones_activas = qs.filter(estado='INTERNADO').order_by('fecha_ingreso')
    internaciones_historial = qs.exclude(estado='INTERNADO')[:20]

    return render(request, 'historia_clinica/lista_internaciones.html', {
        'internaciones_activas': internaciones_activas,
        'internaciones_historial': internaciones_historial,
    })


@login_required
@requerir_rol_veterinario
@transaction.atomic
def internar_mascota(request, mascota_id):
    """Registra el ingreso de una mascota a internación."""
    vet = get_veterinaria_activa(request)
    mascota = _get_mascota_tenant(request, mascota_id, vet)

    if request.method == 'POST':
        form = InternacionForm(request.POST, veterinaria=vet)
        if form.is_valid():
            internacion = form.save(commit=False)
            internacion.mascota = mascota
            if vet:
                internacion.veterinaria = vet
            internacion.save()

            registrar_auditoria(
                request, 'CREAR', modelo='Internacion', objeto_id=internacion.id,
                descripcion=f"Ingreso a internación de {mascota.nombre} (Box: {internacion.box or '-'})"
            )

            messages.success(request, f"{mascota.nombre} fue ingresado/a a internación correctamente.")
            return redirect('historia_clinica:detalle_internacion', internacion_id=internacion.id)
    else:
        form = InternacionForm(veterinaria=vet)

    return render(request, 'historia_clinica/form_internacion.html', {
        'form': form,
        'mascota': mascota,
        'titulo': f'Ingreso a Internación: {mascota.nombre}'
    })


@login_required
def detalle_internacion(request, internacion_id):
    """Ficha de seguimiento de una internación: evoluciones, signos vitales y acciones de alta."""
    vet = get_veterinaria_activa(request)
    internacion = _get_internacion_tenant(request, internacion_id, vet)

    evoluciones = internacion.evoluciones.select_related('veterinario')
    evolucion_form = EvolucionInternacionForm(veterinaria=vet)
    alta_form = AltaInternacionForm()

    return render(request, 'historia_clinica/detalle_internacion.html', {
        'internacion': internacion,
        'mascota': internacion.mascota,
        'evoluciones': evoluciones,
        'evolucion_form': evolucion_form,
        'alta_form': alta_form,
    })


@login_required
@requerir_rol_veterinario
@transaction.atomic
def nueva_evolucion_internacion(request, internacion_id):
    """Registra un nuevo control/evolución dentro de una internación en curso, con descuento opcional de inventario."""
    vet = get_veterinaria_activa(request)
    internacion = _get_internacion_tenant(request, internacion_id, vet)

    if request.method == 'POST':
        form = EvolucionInternacionForm(request.POST, veterinaria=vet)
        if form.is_valid():
            evolucion = form.save(commit=False)
            evolucion.internacion = internacion
            evolucion.save()

            if evolucion.peso_kg:
                internacion.mascota.peso_kg = evolucion.peso_kg
                internacion.mascota.save(update_fields=['peso_kg'])

            producto = form.cleaned_data.get('producto_inventario')
            cantidad = form.cleaned_data.get('cantidad_insumo') or 1

            if producto:
                if producto.stock_actual >= cantidad:
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo='SALIDA',
                        cantidad=cantidad,
                        motivo=f"Internación #{internacion.id} - Paciente: {internacion.mascota.nombre}"
                    )
                else:
                    messages.warning(
                        request,
                        f"Evolución registrada, pero '{producto.nombre}' no tenía suficiente stock ({producto.stock_actual} disp.)."
                    )

            messages.success(request, "Evolución registrada correctamente.")
        else:
            messages.error(request, "No se pudo registrar la evolución. Revisa los campos obligatorios.")

    return redirect('historia_clinica:detalle_internacion', internacion_id=internacion.id)


@login_required
@requerir_rol_veterinario
@transaction.atomic
def dar_alta_internacion(request, internacion_id):
    """Cierra una internación activa (alta médica, fallecimiento o derivación)."""
    vet = get_veterinaria_activa(request)
    internacion = _get_internacion_tenant(request, internacion_id, vet)

    if not internacion.esta_activa:
        messages.warning(request, "Esta internación ya fue cerrada previamente.")
        return redirect('historia_clinica:detalle_internacion', internacion_id=internacion.id)

    if request.method == 'POST':
        form = AltaInternacionForm(request.POST, instance=internacion)
        if form.is_valid():
            internacion = form.save(commit=False)
            internacion.fecha_alta_real = timezone.now()
            internacion.save()

            registrar_auditoria(
                request, 'EDITAR', modelo='Internacion', objeto_id=internacion.id,
                descripcion=f"Cierre de internación de {internacion.mascota.nombre} ({internacion.get_estado_display()})"
            )

            messages.success(request, f"{internacion.mascota.nombre} fue dado/a de alta correctamente.")
        else:
            messages.error(request, "No se pudo procesar el alta. Revisa los campos obligatorios.")

    return redirect('historia_clinica:detalle_internacion', internacion_id=internacion.id)


@login_required
@requerir_rol_veterinario
def eliminar_internacion(request, internacion_id):
    """Elimina un registro de internación (uso administrativo, ej. carga erronea)."""
    vet = get_veterinaria_activa(request)
    internacion = _get_internacion_tenant(request, internacion_id, vet)
    mascota_id = internacion.mascota.id
    mascota_nombre = internacion.mascota.nombre

    if request.method == 'POST':
        internacion.delete()
        registrar_auditoria(
            request, 'ELIMINAR', modelo='Internacion', objeto_id=internacion_id,
            descripcion=f"Eliminación del registro de internación de {mascota_nombre}"
        )
        messages.success(request, "El registro de internación fue eliminado.")
        return redirect('clientes:detalle_historia_clinica', mascota_id=mascota_id)

    return render(request, 'historia_clinica/confirmar_eliminar_internacion.html', {
        'internacion': internacion
    })


@login_required
def descargar_informe_internacion_pdf(request, internacion_id):
    """Genera el informe/epicrisis de internación en PDF con el detalle de evoluciones."""
    vet = get_veterinaria_activa(request)
    internacion = _get_internacion_tenant(request, internacion_id, vet)
    mascota = internacion.mascota

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Informe_Internacion_{mascota.nombre}_{internacion.fecha_ingreso.strftime("%Y%m%d")}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#0d6efd'), spaceAfter=2)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6c757d'), spaceAfter=3)

    vet_obj = internacion.veterinaria or vet
    nombre_vet = vet_obj.nombre if vet_obj else "Clínica Veterinaria VeterSystem"

    logo_img = None
    if vet_obj and vet_obj.logo and os.path.exists(vet_obj.logo.path):
        try:
            logo_img = Image(vet_obj.logo.path, width=75, height=75)
            logo_img.hAlign = 'RIGHT'
        except Exception:
            logo_img = None

    header_text = [
        Paragraph(f"<b>{nombre_vet}</b>", title_style),
        Paragraph("<b>Informe de Internación / Epicrisis</b>", subtitle_style),
        Paragraph(f"Fecha de Emisión: {timezone.now().strftime('%d/%m/%Y %H:%M')} hs", subtitle_style),
    ]

    if logo_img:
        header_table = Table([[header_text, logo_img]], colWidths=[430, 90])
        header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(header_table)
    else:
        for p in header_text:
            story.append(p)

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0d6efd'), spaceBefore=8, spaceAfter=15))

    datos_paciente = [
        [
            Paragraph(f"<b>Paciente:</b> {mascota.nombre}", styles['Normal']),
            Paragraph(f"<b>Especie/Raza:</b> {mascota.get_especie_display()} / {mascota.raza or 'Mestizo'}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Tutor/a:</b> {mascota.cliente.nombre} {mascota.cliente.apellido}", styles['Normal']),
            Paragraph(f"<b>Box/Jaula:</b> {internacion.box or '-'}", styles['Normal'])
        ],
        [
            Paragraph(f"<b>Ingreso:</b> {internacion.fecha_ingreso.strftime('%d/%m/%Y %H:%M')} hs", styles['Normal']),
            Paragraph(f"<b>Alta:</b> {internacion.fecha_alta_real.strftime('%d/%m/%Y %H:%M') + ' hs' if internacion.fecha_alta_real else 'En curso'}", styles['Normal'])
        ],
    ]
    t_paciente = Table(datos_paciente, colWidths=[260, 260])
    t_paciente.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(t_paciente)
    story.append(Spacer(1, 15))

    story.append(Paragraph(f"<b>Motivo de Internación:</b> {internacion.motivo_ingreso}", styles['Normal']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Diagnóstico al Ingreso:</b> {internacion.diagnostico_ingreso or 'Sin registro'}", styles['Normal']))
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>Evolución Diaria:</b>", ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#198754'))))
    story.append(Spacer(1, 6))

    evoluciones_data = [["Fecha/Hora", "Estado", "Signos Vitales", "Notas / Medicación"]]
    for ev in internacion.evoluciones.select_related('veterinario').order_by('fecha_hora'):
        signos = f"P:{ev.peso_kg or '-'}kg T:{ev.temperatura_c or '-'}°C FC:{ev.frecuencia_cardiaca or '-'} FR:{ev.frecuencia_respiratoria or '-'}"
        notas = ev.notas + (f" | Medicación: {ev.medicacion_administrada}" if ev.medicacion_administrada else "")
        evoluciones_data.append([
            ev.fecha_hora.strftime('%d/%m %H:%M'),
            ev.get_estado_general_display(),
            signos,
            Paragraph(notas, styles['Normal']),
        ])

    if len(evoluciones_data) == 1:
        evoluciones_data.append(["-", "-", "-", "Sin evoluciones registradas."])

    t_evoluciones = Table(evoluciones_data, colWidths=[70, 70, 140, 240])
    t_evoluciones.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(t_evoluciones)
    story.append(Spacer(1, 20))

    if internacion.resumen_alta:
        story.append(Paragraph(f"<b>Resumen de Alta ({internacion.get_estado_display()}):</b>", ParagraphStyle('H3', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#0d6efd'))))
        story.append(Spacer(1, 6))
        story.append(Paragraph(internacion.resumen_alta.replace('\n', '<br/>'), styles['Normal']))

    doc.build(story)
    return response