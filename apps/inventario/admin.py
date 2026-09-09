# apps/inventario/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Producto, Categoria, MovimientoStock


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'veterinaria', 'descripcion')
    list_filter = ('veterinaria',)
    search_fields = ('nombre', 'descripcion')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 
        'veterinaria', 
        'categoria', 
        'precio_costo', 
        'precio_venta', 
        'stock_status', 
        'fecha_vencimiento'
    )
    list_filter = ('veterinaria', 'tipo', 'categoria')
    search_fields = ('nombre', 'codigo_barras')
    readonly_fields = ('creado_el', 'actualizado_el')

    @admin.display(description='Stock Actual')
    def stock_status(self, obj):
        if obj.bajo_stock:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠️ {} (Mín: {})</span>',
                obj.stock_actual,
                obj.stock_minimo
            )
        return format_html('<span style="color: green; font-weight: bold;">{}</span>', obj.stock_actual)


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tipo_badge', 'cantidad', 'motivo', 'fecha')
    list_filter = ('tipo', 'fecha')
    search_fields = ('producto__nombre', 'motivo')
    readonly_fields = ('fecha',)

    @admin.display(description='Tipo')
    def tipo_badge(self, obj):
        colors = {
            'ENTRADA': 'green',
            'SALIDA': 'blue',
            'AJUSTE': 'orange',
        }
        color = colors.get(obj.tipo, 'black')
        return format_html(
            '<strong style="color: {};">{}</strong>',
            color,
            obj.get_tipo_display()
        )