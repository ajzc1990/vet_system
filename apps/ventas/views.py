# apps/ventas/views.py
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse

# ReportLab para Ticket en PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from .models import Venta, DetalleVenta, CajaDiaria
from .forms import VentaForm
from apps.inventario.models import MovimientoStock
from apps.usuarios.utils import get_veterinaria_activa
from apps.usuarios.audit import registrar_auditoria


@login_required
def lista_ventas(request):
    """Listado general de ventas registradas en la veterinaria."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        ventas = Venta.objects.all().select_related('cliente', 'vendedor').order_by('-fecha_hora')
        caja_activa = CajaDiaria.objects.filter(estado='ABIERTA').first()
    else:
        ventas = Venta.objects.filter(veterinaria=vet).select_related('cliente', 'vendedor').order_by('-fecha_hora') if vet else Venta.objects.none()
        caja_activa = CajaDiaria.objects.filter(veterinaria=vet, estado='ABIERTA').first() if vet else None

    return render(request, 'ventas/lista_ventas.html', {
        'ventas': ventas,
        'caja_activa': caja_activa
    })


@login_required
@transaction.atomic
def registrar_venta(request):
    """Punto de Venta (POS) con validación de caja abierta y descuento de stock."""
    vet = get_veterinaria_activa(request)

    # Verificar que exista una caja abierta
    caja_activa = CajaDiaria.objects.filter(veterinaria=vet, estado='ABIERTA').first() if vet else CajaDiaria.objects.filter(estado='ABIERTA').first()
    
    if not caja_activa:
        messages.warning(request, "Debes abrir la Caja Diaria antes de registrar ventas.")
        return redirect('ventas:abrir_caja')

    if request.method == 'POST':
        form = VentaForm(request.POST, veterinaria=vet)
        if form.is_valid():
            producto = form.cleaned_data['producto']
            cantidad = form.cleaned_data['cantidad']

            # Validar stock disponible
            if producto.stock_actual < cantidad:
                messages.error(
                    request, 
                    f"Stock insuficiente de '{producto.nombre}'. Disponible: {producto.stock_actual} unidades."
                )
                return render(request, 'ventas/form_venta.html', {'form': form, 'vet': vet, 'caja_activa': caja_activa})

            # Crear Venta
            venta = form.save(commit=False)
            if vet:
                venta.veterinaria = vet
            venta.caja = caja_activa
            venta.vendedor = request.user
            precio_unitario = producto.precio_venta or 0
            venta.total = precio_unitario * cantidad
            venta.save()

            # Crear Detalle (DetalleVenta.save() ya descuenta stock y crea MovimientoStock)
            DetalleVenta.objects.create(
                venta=venta,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                subtotal=venta.total
            )

            registrar_auditoria(
                request, 'CREAR', modelo='Venta', objeto_id=venta.id,
                descripcion=f"Venta #{venta.id} registrada por ${venta.total} ({producto.nombre} x{cantidad})"
            )

            messages.success(request, f"¡Venta #{venta.id} registrada con éxito! Total: ${venta.total}")
            return redirect('ventas:lista_ventas')
        else:
            messages.error(request, "Por favor revisa los datos ingresados en el formulario de venta.")
    else:
        form = VentaForm(veterinaria=vet)

    return render(request, 'ventas/form_venta.html', {
        'form': form, 
        'vet': vet, 
        'caja_activa': caja_activa
    })


@login_required
def abrir_caja(request):
    """Abre la caja diaria para el turno de atención actual."""
    vet = get_veterinaria_activa(request)
    
    caja_abierta = CajaDiaria.objects.filter(veterinaria=vet, estado='ABIERTA').first() if vet else CajaDiaria.objects.filter(estado='ABIERTA').first()
    if caja_abierta:
        messages.info(request, f"La caja ya se encuentra abierta desde las {caja_abierta.fecha_apertura.strftime('%H:%M hs')}.")
        return redirect('ventas:lista_ventas')

    if request.method == 'POST':
        monto_inicial = request.POST.get('monto_inicial') or 0.00
        observaciones = request.POST.get('observaciones', '')

        caja = CajaDiaria.objects.create(
            veterinaria=vet,
            usuario_apertura=request.user,
            monto_inicial=monto_inicial,
            observaciones=observaciones,
            estado='ABIERTA'
        )
        registrar_auditoria(
            request, 'CREAR', modelo='CajaDiaria', objeto_id=caja.id,
            descripcion=f"Apertura de caja #{caja.id} con monto inicial ${caja.monto_inicial}"
        )

        messages.success(request, f"¡Caja #{caja.id} abierta con éxito! Monto inicial: ${caja.monto_inicial}")
        return redirect('ventas:lista_ventas')

    return render(request, 'ventas/abrir_caja.html', {'vet': vet})


@login_required
def cerrar_caja(request, caja_id):
    """Realiza el arqueo y cierre de la caja diaria."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        caja = get_object_or_404(CajaDiaria, pk=caja_id)
    else:
        caja = get_object_or_404(CajaDiaria, pk=caja_id, veterinaria=vet)

    if caja.estado == 'CERRADA':
        messages.warning(request, "Esta caja ya fue cerrada anteriormente.")
        return redirect('ventas:lista_ventas')

    if request.method == 'POST':
        monto_final_real = request.POST.get('monto_final_real') or 0.00
        caja.monto_final_real = monto_final_real
        caja.usuario_cierre = request.user
        caja.fecha_cierre = timezone.now()
        caja.estado = 'CERRADA'
        caja.save()

        diferencia = (caja.monto_final_real or 0) - caja.total_efectivo
        registrar_auditoria(
            request, 'EDITAR', modelo='CajaDiaria', objeto_id=caja.id,
            descripcion=f"Cierre de caja #{caja.id}. Diferencia de arqueo: ${diferencia:.2f}"
        )

        messages.success(request, f"Caja #{caja.id} cerrada correctamente.")
        return redirect('ventas:lista_ventas')

    return render(request, 'ventas/cerrar_caja.html', {
        'caja': caja,
        'total_efectivo': caja.total_efectivo,
        'total_digital': caja.total_digital_tarjetas,
        'total_general': caja.total_general_ventas,
    })


@login_required
def descargar_ticket_pdf(request, venta_id):
    """Genera un comprobante / ticket de venta en PDF."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        venta = get_object_or_404(Venta, pk=venta_id)
    else:
        venta = get_object_or_404(Venta, pk=venta_id, veterinaria=vet)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Comprobante_Venta_{venta.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    vet_obj = venta.veterinaria or vet
    nombre_vet = vet_obj.nombre if vet_obj else "Clínica Veterinaria VeterSystem"
    
    # Encabezado
    story.append(Paragraph(f"<b>{nombre_vet}</b>", ParagraphStyle('H1', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0d6efd'))))
    story.append(Paragraph(f"Comprobante de Venta #{venta.id} | Fecha: {venta.fecha_hora.strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0d6efd'), spaceBefore=8, spaceAfter=15))

    # Cliente y Vendedor
    cliente_str = f"{venta.cliente.nombre} {venta.cliente.apellido}" if venta.cliente else "Consumidor Final"
    vendedor_str = venta.vendedor.get_full_name() or venta.vendedor.username if venta.vendedor else "Caja"

    story.append(Paragraph(f"<b>Cliente:</b> {cliente_str}", styles['Normal']))
    story.append(Paragraph(f"<b>Atendido por:</b> {vendedor_str}", styles['Normal']))
    story.append(Paragraph(f"<b>Medio de Pago:</b> {venta.get_medio_pago_display()}", styles['Normal']))
    story.append(Spacer(1, 15))

    # Tabla de Detalle
    tabla_data = [["Producto", "Cant.", "Precio Unit.", "Subtotal"]]
    for d in venta.detalles.all():
        tabla_data.append([
            d.producto.nombre,
            str(d.cantidad),
            f"${d.precio_unitario:.2f}",
            f"${d.subtotal:.2f}"
        ])
    
    tabla_data.append(["TOTAL", "", "", f"${venta.total:.2f}"])

    t = Table(tabla_data, colWidths=[240, 60, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e9ecef')),
    ]))
    story.append(t)

    doc.build(story)
    return response

@login_required
def reporte_cajas(request):
    """
    Vista de auditoría y reportes para analizar los cierres de caja,
    diferencias de dinero (faltantes/sobrantes) y ventas por medio de pago.
    """
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        cajas = CajaDiaria.objects.all().prefetch_related('ventas').order_by('-fecha_apertura')
    else:
        cajas = CajaDiaria.objects.filter(veterinaria=vet).prefetch_related('ventas').order_by('-fecha_apertura') if vet else CajaDiaria.objects.none()

    # Procesar métricas por cada caja cerrada
    cajas_reporte = []
    total_efectivo_acumulado = 0
    total_digital_acumulado = 0
    total_diferencia_acumulada = 0

    for c in cajas:
        esperado = c.total_efectivo  # Fondo inicial + ventas efectivo
        real = c.monto_final_real or 0.00
        diferencia = real - esperado if c.estado == 'CERRADA' and c.monto_final_real is not None else 0.00
        
        cajas_reporte.append({
            'caja': c,
            'esperado': esperado,
            'real': real,
            'diferencia': diferencia,
            'digital': c.total_digital_tarjetas,
            'total_general': c.total_general_ventas,
        })

        if c.estado == 'CERRADA':
            total_efectivo_acumulado += (real - c.monto_inicial)  # Ganancia real neta en efectivo
            total_digital_acumulado += c.total_digital_tarjetas
            total_diferencia_acumulada += diferencia

    return render(request, 'ventas/reporte_cajas.html', {
        'cajas_reporte': cajas_reporte,
        'total_efectivo_acumulado': total_efectivo_acumulado,
        'total_digital_acumulado': total_digital_acumulado,
        'total_diferencia_acumulada': total_diferencia_acumulada,
        'cant_cajas': cajas.count(),
    })