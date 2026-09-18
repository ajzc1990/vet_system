# apps/inventario/views.py
import csv
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone

from .models import Producto, Categoria, MovimientoStock
from .forms import ProductoForm, MovimientoStockForm
from apps.usuarios.utils import get_veterinaria_activa


@login_required
def lista_productos(request):
    """
    Muestra la lista de productos e insumos de la veterinaria activa,
    con soporte de filtros de alertas de stock mínimo y vencimientos.
    """
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        qs_base = Producto.objects.select_related('categoria', 'veterinaria')
    else:
        qs_base = Producto.objects.filter(veterinaria=vet).select_related('categoria') if vet else Producto.objects.none()

    hoy = timezone.localdate()
    limite_vencimiento = hoy + timedelta(days=30)

    # Contadores para las tarjetas/KPIs de la cabecera
    total_productos = qs_base.count()
    cant_bajo_stock = qs_base.filter(stock_actual__lte=F('stock_minimo')).count()
    cant_vencidos = qs_base.filter(fecha_vencimiento__lt=hoy).count()
    cant_proximo_vencer = qs_base.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=limite_vencimiento
    ).count()

    # Aplicación del filtro seleccionado desde la URL (?filtro=...)
    filtro = request.GET.get('filtro')
    productos = qs_base

    if filtro == 'bajo_stock':
        productos = productos.filter(stock_actual__lte=F('stock_minimo'))
    elif filtro == 'vencidos':
        productos = productos.filter(fecha_vencimiento__lt=hoy)
    elif filtro == 'proximo_vencer':
        productos = productos.filter(
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=limite_vencimiento
        )

    return render(request, 'inventario/lista_productos.html', {
        'productos': productos,
        'filtro_activo': filtro,
        'total_productos': total_productos,
        'cant_bajo_stock': cant_bajo_stock,
        'cant_vencidos': cant_vencidos,
        'cant_proximo_vencer': cant_proximo_vencer,
    })


@login_required
def exportar_productos_csv(request):
    """Exporta a CSV el inventario de la veterinaria activa (respeta el filtro de alertas aplicado)."""
    vet = get_veterinaria_activa(request)

    if request.user.is_superuser and not vet:
        productos = Producto.objects.select_related('categoria')
    else:
        productos = Producto.objects.filter(veterinaria=vet).select_related('categoria') if vet else Producto.objects.none()

    hoy = timezone.localdate()
    limite_vencimiento = hoy + timedelta(days=30)
    filtro = request.GET.get('filtro')
    if filtro == 'bajo_stock':
        productos = productos.filter(stock_actual__lte=F('stock_minimo'))
    elif filtro == 'vencidos':
        productos = productos.filter(fecha_vencimiento__lt=hoy)
    elif filtro == 'proximo_vencer':
        productos = productos.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=limite_vencimiento)

    productos = productos.order_by('nombre')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="inventario.csv"'
    response.write('﻿')

    writer = csv.writer(response)
    writer.writerow(['Producto', 'Categoría', 'Tipo', 'Código de Barras', 'Stock Actual', 'Stock Mínimo', 'Precio Costo', 'Precio Venta', 'Vencimiento'])
    for p in productos:
        writer.writerow([
            p.nombre, p.categoria.nombre if p.categoria else '', p.get_tipo_display(),
            p.codigo_barras or '', p.stock_actual, p.stock_minimo,
            f"{p.precio_costo:.2f}", f"{p.precio_venta:.2f}",
            p.fecha_vencimiento.strftime('%d/%m/%Y') if p.fecha_vencimiento else '',
        ])

    return response


@login_required
def nuevo_producto(request):
    """Crea un nuevo producto en el inventario asociándolo a la veterinaria."""
    vet = get_veterinaria_activa(request)
    if not vet:
        messages.error(request, "No se encontró una veterinaria activa asociada a la cuenta.")
        return redirect('inventario:lista_productos')

    if request.method == 'POST':
        form = ProductoForm(request.POST, veterinaria=vet)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.veterinaria = vet
            producto.save()
            
            messages.success(request, f"Producto '{producto.nombre}' agregado correctamente al inventario.")
            return redirect('inventario:lista_productos')
        else:
            print("\n" + "="*50)
            print("❌ ERRORES DE VALIDACIÓN EN PRODUCTOFORM:")
            print(form.errors)
            print("="*50 + "\n")
            messages.error(request, "Por favor revisa los datos ingresados en el formulario.")
    else:
        form = ProductoForm(veterinaria=vet)
        
    return render(request, 'inventario/form_producto.html', {
        'form': form, 
        'titulo': 'Nuevo Producto'
    })


@login_required
def registrar_movimiento(request, producto_id):
    """Registra una entrada, salida o ajuste de stock delegando el cálculo al modelo MovimientoStock."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        producto = get_object_or_404(Producto, pk=producto_id)
    else:
        producto = get_object_or_404(Producto, pk=producto_id, veterinaria=vet)
    
    if request.method == 'POST':
        form = MovimientoStockForm(request.POST)
        if form.is_valid():
            movimiento = form.save(commit=False)
            movimiento.producto = producto
            # El save() de MovimientoStock actualiza automáticamente producto.stock_actual
            movimiento.save()
            
            messages.success(request, f"Movimiento de stock registrado para '{producto.nombre}'. Nuevo stock: {producto.stock_actual}.")
            return redirect('inventario:lista_productos')
        else:
            print("\n" + "="*50)
            print("❌ ERRORES DE VALIDACIÓN EN MOVIMIENTOFORM:")
            print(form.errors)
            print("="*50 + "\n")
            messages.error(request, "No se pudo registrar el movimiento. Revisa los campos.")
    else:
        form = MovimientoStockForm()
        
    return render(request, 'inventario/form_movimiento.html', {
        'form': form, 
        'producto': producto
    })


@login_required
def editar_producto(request, producto_id):
    """Edita los datos de un producto existente asegurando el aislamiento multi-tenant."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        producto = get_object_or_404(Producto, pk=producto_id)
    else:
        producto = get_object_or_404(Producto, pk=producto_id, veterinaria=vet)
    
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto, veterinaria=vet)
        if form.is_valid():
            producto_editado = form.save(commit=False)
            if not producto_editado.veterinaria and vet:
                producto_editado.veterinaria = vet
            producto_editado.save()
            
            messages.success(request, f"Producto '{producto.nombre}' actualizado correctamente.")
            return redirect('inventario:lista_productos')
        else:
            print("\n" + "="*50)
            print("❌ ERRORES DE VALIDACIÓN EN PRODUCTOFORM (EDICIÓN):")
            print(form.errors)
            print("="*50 + "\n")
            messages.error(request, "Error al actualizar el producto. Por favor revisa los datos.")
    else:
        form = ProductoForm(instance=producto, veterinaria=vet)
    
    return render(request, 'inventario/form_producto.html', {
        'form': form,
        'titulo': 'Editar Producto',
        'producto': producto
    })


@login_required
def eliminar_producto(request, producto_id):
    """Elimina un producto del inventario."""
    vet = get_veterinaria_activa(request)
    
    if request.user.is_superuser and not vet:
        producto = get_object_or_404(Producto, pk=producto_id)
    else:
        producto = get_object_or_404(Producto, pk=producto_id, veterinaria=vet)
    
    if request.method == 'POST':
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f"Producto '{nombre}' eliminado del inventario.")
        return redirect('inventario:lista_productos')
    
    return render(request, 'inventario/confirmar_eliminar.html', {'producto': producto})