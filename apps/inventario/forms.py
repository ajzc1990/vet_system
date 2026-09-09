# apps/inventario/forms.py
from django import forms
from django.db.models import Q
from .models import Producto, Categoria, MovimientoStock


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre', 'categoria', 'tipo', 'codigo_barras', 
            'stock_actual', 'stock_minimo', 'precio_costo', 
            'precio_venta', 'fecha_vencimiento'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto o insumo'}),
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 7791234567890'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'stock_actual': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'precio_costo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'precio_venta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'fecha_vencimiento': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        # Formatear fecha para el widget date en edición
        if self.instance and self.instance.pk and self.instance.fecha_vencimiento:
            self.initial['fecha_vencimiento'] = self.instance.fecha_vencimiento.strftime('%Y-%m-%d')

        # Filtrar categorías del tenant (propias + globales)
        if self.veterinaria:
            self.fields['categoria'].queryset = Categoria.objects.filter(
                Q(veterinaria=self.veterinaria) | Q(veterinaria__isnull=True)
            )

        # Labels amigables
        self.fields['nombre'].label = "Nombre del Producto *"
        self.fields['tipo'].label = "Tipo de Insumo *"
        self.fields['stock_actual'].label = "Stock Inicial *"
        self.fields['stock_minimo'].label = "Stock Mínimo (Alerta) *"
        self.fields['precio_costo'].label = "Precio de Costo ($)"
        self.fields['precio_venta'].label = "Precio de Venta ($)"

    def clean_codigo_barras(self):
        codigo = self.cleaned_data.get('codigo_barras')
        if not codigo:
            return codigo

        # Validar que no se repita el código de barras dentro de la misma veterinaria
        qs = Producto.objects.filter(codigo_barras=codigo)
        if self.veterinaria:
            qs = qs.filter(veterinaria=self.veterinaria)

        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Ya existe otro producto registrado con este código de barras en tu veterinaria.")

        return codigo


class MovimientoStockForm(forms.ModelForm):
    class Meta:
        model = MovimientoStock
        fields = ['tipo', 'cantidad', 'motivo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Cantidad'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Compra a proveedor, uso en consulta #12, descarte'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].label = "Tipo de Movimiento *"
        self.fields['cantidad'].label = "Cantidad *"
        self.fields['motivo'].label = "Motivo / Detalle"