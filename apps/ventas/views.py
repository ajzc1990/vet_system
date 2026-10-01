# apps/ventas/views.py
import csv
import json
import os
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.http import HttpResponse

# ReportLab para Ticket en PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from .models import Venta, DetalleVenta, CajaDiaria, GastoCaja, CobroQR
from .forms import VentaForm
from .pagos import mp_configurado_para, crear_preferencia_cobro, obtener_pago_para
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

    gastos_caja_activa = caja_activa.gastos.select_related('usuario').all() if caja_activa else None

    return render(request, 'ventas/lista_ventas.html', {
        'ventas': ventas,
        'caja_activa': caja_activa,
        'gastos_caja_activa': gastos_caja_activa,
    })


@login_required
def exportar_ventas_csv(request):
    """Exporta a CSV el historial de ventas de la veterinaria activa."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        ventas = Venta.objects.all()
    else:
        ventas = Venta.objects.filter(veterinaria=vet) if vet else Venta.objects.none()

    ventas = ventas.select_related('cliente', 'vendedor').prefetch_related('detalles__producto').order_by('-fecha_hora')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ventas.csv"'
    response.write('﻿')

    writer = csv.writer(response)
    writer.writerow(['Nº Venta', 'Fecha', 'Cliente', 'Vendedor', 'Medio de Pago', 'Productos', 'Total'])
    for v in ventas:
        cliente_str = f"{v.cliente.nombre} {v.cliente.apellido}" if v.cliente else "Consumidor Final"
        vendedor_str = (v.vendedor.get_full_name() or v.vendedor.username) if v.vendedor else '-'
        productos_str = '; '.join(f"{d.cantidad}x {d.producto.nombre}" for d in v.detalles.all())
        writer.writerow([
            v.id, v.fecha_hora.strftime('%d/%m/%Y %H:%M'), cliente_str, vendedor_str,
            v.get_medio_pago_display(), productos_str, f"{v.total:.2f}",
        ])

    return response


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

    vet_venta = vet or (caja_activa.veterinaria if caja_activa else None)

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

            # Cobro por QR/Mercado Pago: no se crea la Venta todavía. Se crea un
            # CobroQR pendiente y se redirige al Checkout de MP; la Venta real (con
            # su descuento de stock) recién se crea cuando el webhook confirma el pago.
            if form.cleaned_data['medio_pago'] == 'QR_MP':
                if not mp_configurado_para(vet_venta):
                    messages.warning(
                        request,
                        "Esta clínica todavía no configuró su cuenta de Mercado Pago. "
                        "Configurala en \"Configurar Clínica\" o elegí otro medio de pago."
                    )
                    return render(request, 'ventas/form_venta.html', {'form': form, 'vet': vet, 'caja_activa': caja_activa})

                precio_unitario = producto.precio_venta or 0
                cobro = CobroQR.objects.create(
                    veterinaria=vet_venta,
                    caja=caja_activa,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    total=precio_unitario * cantidad,
                    cliente=form.cleaned_data.get('cliente'),
                    vendedor=request.user,
                    observaciones=form.cleaned_data.get('observaciones'),
                )

                try:
                    preferencia = crear_preferencia_cobro(cobro, request)
                    init_point = preferencia.get('init_point') or preferencia.get('sandbox_init_point')
                except Exception:
                    init_point = None

                if not init_point:
                    cobro.delete()
                    messages.error(request, "No se pudo iniciar el cobro por Mercado Pago. Intentá nuevamente.")
                    return render(request, 'ventas/form_venta.html', {'form': form, 'vet': vet, 'caja_activa': caja_activa})

                cobro.mp_preference_id = preferencia.get('id')
                cobro.save(update_fields=['mp_preference_id'])
                return redirect(init_point)

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


def _confirmar_cobro_qr(cobro, payment_id=None):
    """Si el pago de un CobroQR está aprobado en Mercado Pago, crea recién ahí la
    Venta real (con su descuento de stock) y marca el cobro como aprobado. Es
    idempotente: si ya estaba aprobado o la Venta ya existe, no hace nada de nuevo."""
    if cobro.estado != 'PENDIENTE':
        return cobro

    payment_id = payment_id or cobro.mp_payment_id
    if not payment_id:
        return cobro

    try:
        pago = obtener_pago_para(cobro.veterinaria, payment_id)
    except Exception:
        return cobro

    if str(pago.get('external_reference')) != str(cobro.id):
        return cobro

    cobro.mp_payment_id = str(payment_id)

    if pago.get('status') == 'approved':
        with transaction.atomic():
            venta = Venta.objects.create(
                veterinaria=cobro.veterinaria,
                caja=cobro.caja,
                cliente=cobro.cliente,
                vendedor=cobro.vendedor,
                medio_pago='QR_MP',
                total=cobro.total,
                observaciones=cobro.observaciones,
            )
            DetalleVenta.objects.create(
                venta=venta,
                producto=cobro.producto,
                cantidad=cobro.cantidad,
                precio_unitario=cobro.precio_unitario,
                subtotal=cobro.total,
            )
            cobro.venta = venta
            cobro.estado = 'APROBADO'
            cobro.save()
    elif pago.get('status') in ('rejected', 'cancelled'):
        cobro.estado = 'RECHAZADO'
        cobro.save()
    else:
        cobro.save(update_fields=['mp_payment_id'])

    return cobro


@login_required
def ver_cobro_qr(request, cobro_id):
    """Pantalla de espera/resultado de un cobro por QR. Re-consulta el pago contra
    Mercado Pago por si el webhook todavía no llegó (hay latencia entre el back_url
    de MP y la notificación)."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        cobro = get_object_or_404(CobroQR, pk=cobro_id)
    else:
        cobro = get_object_or_404(CobroQR, pk=cobro_id, veterinaria=vet)

    if cobro.estado == 'PENDIENTE':
        payment_id = request.GET.get('payment_id') or request.GET.get('collection_id')
        cobro = _confirmar_cobro_qr(cobro, payment_id=payment_id)

    return render(request, 'ventas/cobro_qr.html', {'cobro': cobro})


@csrf_exempt
def webhook_cobro_qr(request, cobro_id):
    """Notificación de pago de Mercado Pago para un CobroQR puntual. El id del cobro
    viaja en la propia URL (no en el body) para saber de entrada con qué cuenta/token
    de qué clínica hay que consultar el pago, antes incluso de leer la notificación."""
    cobro = CobroQR.objects.filter(pk=cobro_id).first()
    if not cobro:
        return HttpResponse(status=200)

    topic = request.GET.get('type') or request.GET.get('topic')
    payment_id = request.GET.get('data.id') or request.GET.get('id')

    if not payment_id and request.method == 'POST' and request.body:
        try:
            body = json.loads(request.body)
            topic = topic or body.get('type') or body.get('action', '').split('.')[0]
            payment_id = payment_id or (body.get('data') or {}).get('id')
        except (ValueError, TypeError):
            pass

    if not payment_id or (topic and topic != 'payment'):
        return HttpResponse(status=200)

    _confirmar_cobro_qr(cobro, payment_id=payment_id)
    return HttpResponse(status=200)


@login_required
def registrar_gasto(request):
    """Registra una salida de efectivo de la caja activa (pago a un service, flete,
    insumos de urgencia, etc.), para que el arqueo final no dé un faltante irreal."""
    vet = get_veterinaria_activa(request)
    caja_activa = CajaDiaria.objects.filter(veterinaria=vet, estado='ABIERTA').first() if vet else CajaDiaria.objects.filter(estado='ABIERTA').first()

    if not caja_activa:
        messages.warning(request, "No hay una caja abierta para registrar el gasto.")
        return redirect('ventas:lista_ventas')

    if request.method == 'POST':
        concepto = request.POST.get('concepto', '').strip()
        monto = request.POST.get('monto') or 0

        if not concepto or not float(monto or 0) > 0:
            messages.error(request, "Completá el concepto y un monto mayor a cero.")
        else:
            gasto = GastoCaja.objects.create(
                caja=caja_activa,
                concepto=concepto,
                monto=monto,
                usuario=request.user,
            )
            registrar_auditoria(
                request, 'CREAR', modelo='GastoCaja', objeto_id=gasto.id,
                descripcion=f"Gasto de caja #{caja_activa.id}: {gasto.concepto} (-${gasto.monto})"
            )
            messages.success(request, f"Gasto '{gasto.concepto}' registrado por ${gasto.monto}.")

    return redirect('ventas:lista_ventas')


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

    ventas_efectivo = caja.ventas.filter(medio_pago='EFECTIVO').aggregate(total=Sum('total'))['total'] or 0
    total_efectivo = caja.total_efectivo
    # Tolerancia: 3% del efectivo esperado (así no queda desactualizada por inflación),
    # con un piso de $2000 para no exigir justificación por centavos de vuelto.
    tolerancia = max(Decimal('2000'), total_efectivo * Decimal('0.03'))

    if request.method == 'POST':
        try:
            monto_final_real = Decimal(request.POST.get('monto_final_real') or '0')
        except InvalidOperation:
            messages.error(request, "El monto ingresado no es un número válido.")
            return redirect('ventas:cerrar_caja', caja_id=caja.id)

        observaciones = (request.POST.get('observaciones') or '').strip()
        diferencia = monto_final_real - total_efectivo

        if abs(diferencia) > tolerancia and not observaciones:
            messages.error(
                request,
                f"La diferencia de arqueo es de ${diferencia:.2f}, mucho más de lo esperado. "
                "Volvé a contar el efectivo y, si se confirma, escribí abajo una justificación "
                "(qué pasó: vuelto mal dado, un cobro no registrado, etc.) para poder cerrar la caja."
            )
            return render(request, 'ventas/cerrar_caja.html', {
                'caja': caja,
                'total_efectivo': total_efectivo,
                'ventas_efectivo': ventas_efectivo,
                'total_digital': caja.total_digital_tarjetas,
                'total_general': caja.total_general_ventas,
                'total_gastos': caja.total_gastos,
                'gastos': caja.gastos.select_related('usuario').all(),
                'tolerancia': tolerancia,
                'monto_final_real_ingresado': monto_final_real,
                'observaciones_ingresadas': observaciones,
            })

        caja.monto_final_real = monto_final_real
        caja.observaciones = observaciones
        caja.usuario_cierre = request.user
        caja.fecha_cierre = timezone.now()
        caja.estado = 'CERRADA'
        caja.save()

        descripcion = f"Cierre de caja #{caja.id}. Diferencia de arqueo: ${diferencia:.2f}"
        if observaciones:
            descripcion += f". Justificación: {observaciones}"
        registrar_auditoria(request, 'EDITAR', modelo='CajaDiaria', objeto_id=caja.id, descripcion=descripcion)

        messages.success(request, f"Caja #{caja.id} cerrada correctamente.")
        return redirect('ventas:lista_ventas')

    return render(request, 'ventas/cerrar_caja.html', {
        'caja': caja,
        'total_efectivo': total_efectivo,
        'ventas_efectivo': ventas_efectivo,
        'total_digital': caja.total_digital_tarjetas,
        'total_general': caja.total_general_ventas,
        'total_gastos': caja.total_gastos,
        'gastos': caja.gastos.select_related('usuario').all(),
        'tolerancia': tolerancia,
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