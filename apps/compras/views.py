# apps/compras/views.py
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse

from .models import Proveedor, Compra, DetalleCompra
from .forms import ProveedorForm, CompraForm, DetalleCompraFormSet
from apps.usuarios.utils import get_veterinaria_activa
from apps.usuarios.audit import registrar_auditoria


@login_required
def lista_proveedores(request):
    """Listado de proveedores de la veterinaria activa."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        proveedores = Proveedor.objects.all()
    else:
        proveedores = Proveedor.objects.filter(veterinaria=vet) if vet else Proveedor.objects.none()

    return render(request, 'compras/lista_proveedores.html', {
        'proveedores': proveedores,
    })


@login_required
def nuevo_proveedor(request):
    """Alta de un nuevo proveedor asociado a la veterinaria activa."""
    vet = get_veterinaria_activa(request)
    if not vet:
        messages.error(request, "No se encontró una veterinaria activa asociada a la cuenta.")
        return redirect('compras:lista_proveedores')

    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save(commit=False)
            proveedor.veterinaria = vet
            proveedor.save()
            messages.success(request, f"Proveedor '{proveedor.nombre}' agregado correctamente.")
            return redirect('compras:lista_proveedores')
        messages.error(request, "Por favor revisa los datos ingresados en el formulario.")
    else:
        form = ProveedorForm(initial={'activo': True})

    return render(request, 'compras/form_proveedor.html', {'form': form, 'titulo': 'Nuevo Proveedor'})


@login_required
def editar_proveedor(request, proveedor_id):
    """Edita los datos de un proveedor existente, respetando el aislamiento multi-tenant."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        proveedor = get_object_or_404(Proveedor, pk=proveedor_id)
    else:
        proveedor = get_object_or_404(Proveedor, pk=proveedor_id, veterinaria=vet)

    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, f"Proveedor '{proveedor.nombre}' actualizado correctamente.")
            return redirect('compras:lista_proveedores')
        messages.error(request, "Error al actualizar el proveedor. Por favor revisa los datos.")
    else:
        form = ProveedorForm(instance=proveedor)

    return render(request, 'compras/form_proveedor.html', {
        'form': form, 'titulo': 'Editar Proveedor', 'proveedor': proveedor
    })


@login_required
def lista_compras(request):
    """Historial de compras registradas a proveedores."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        compras = Compra.objects.select_related('proveedor', 'usuario')
    else:
        compras = (
            Compra.objects.filter(veterinaria=vet).select_related('proveedor', 'usuario')
            if vet else Compra.objects.none()
        )

    return render(request, 'compras/lista_compras.html', {'compras': compras})


@login_required
def exportar_compras_csv(request):
    """Exporta a CSV el historial de compras de la veterinaria activa."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        compras = Compra.objects.all()
    else:
        compras = Compra.objects.filter(veterinaria=vet) if vet else Compra.objects.none()

    compras = compras.select_related('proveedor', 'usuario').prefetch_related('detalles__producto').order_by('-fecha_hora')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="compras.csv"'
    response.write('﻿')

    writer = csv.writer(response)
    writer.writerow(['Nº Compra', 'Fecha', 'Proveedor', 'Nº Factura', 'Registrada por', 'Productos', 'Total'])
    for c in compras:
        usuario_str = (c.usuario.get_full_name() or c.usuario.username) if c.usuario else '-'
        productos_str = '; '.join(f"{d.cantidad}x {d.producto.nombre}" for d in c.detalles.all())
        writer.writerow([
            c.id, c.fecha_hora.strftime('%d/%m/%Y %H:%M'), c.proveedor.nombre,
            c.numero_factura or '-', usuario_str, productos_str, f"{c.total:.2f}",
        ])

    return response


@login_required
@transaction.atomic
def registrar_compra(request):
    """Registra una compra a proveedor con varias líneas de productos, sumando stock."""
    vet = get_veterinaria_activa(request)

    if not vet and not request.user.is_superuser:
        messages.error(request, "No se encontró una veterinaria activa asociada a la cuenta.")
        return redirect('compras:lista_compras')

    if not Proveedor.objects.filter(veterinaria=vet, activo=True).exists():
        messages.warning(request, "Primero tenés que cargar al menos un proveedor activo.")
        return redirect('compras:nuevo_proveedor')

    if request.method == 'POST':
        form = CompraForm(request.POST, veterinaria=vet)
        formset = DetalleCompraFormSet(request.POST, form_kwargs={'veterinaria': vet})

        if form.is_valid() and formset.is_valid():
            filas_completas = [f for f in formset if f.cleaned_data and f.esta_completo()]

            if not filas_completas:
                messages.error(request, "Agregá al menos un producto con cantidad y costo antes de guardar.")
            else:
                compra = form.save(commit=False)
                if vet:
                    compra.veterinaria = vet
                compra.usuario = request.user
                compra.total = sum(
                    f.cleaned_data['cantidad'] * f.cleaned_data['precio_unitario'] for f in filas_completas
                )
                compra.save()

                for f in filas_completas:
                    DetalleCompra.objects.create(
                        compra=compra,
                        producto=f.cleaned_data['producto'],
                        cantidad=f.cleaned_data['cantidad'],
                        precio_unitario=f.cleaned_data['precio_unitario'],
                    )

                registrar_auditoria(
                    request, 'CREAR', modelo='Compra', objeto_id=compra.id,
                    descripcion=f"Compra #{compra.id} registrada a {compra.proveedor.nombre} por ${compra.total}"
                )

                messages.success(request, f"¡Compra #{compra.id} registrada con éxito! Total: ${compra.total}")
                return redirect('compras:lista_compras')
        else:
            messages.error(request, "Por favor revisa los datos ingresados en el formulario.")
    else:
        form = CompraForm(veterinaria=vet)
        formset = DetalleCompraFormSet(form_kwargs={'veterinaria': vet})

    return render(request, 'compras/form_compra.html', {'form': form, 'formset': formset})


@login_required
def detalle_compra(request, compra_id):
    """Muestra el detalle completo de una compra ya registrada."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        compra = get_object_or_404(Compra.objects.select_related('proveedor', 'usuario'), pk=compra_id)
    else:
        compra = get_object_or_404(
            Compra.objects.select_related('proveedor', 'usuario'), pk=compra_id, veterinaria=vet
        )

    return render(request, 'compras/detalle_compra.html', {
        'compra': compra,
        'detalles': compra.detalles.select_related('producto'),
    })
