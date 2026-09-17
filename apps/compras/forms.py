# apps/compras/forms.py
from django import forms
from django.forms import formset_factory
from .models import Proveedor, Compra
from apps.inventario.models import Producto


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'telefono', 'email', 'direccion', 'cuit', 'notas', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Distribuidora Vet Sur SRL'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de quien atiende los pedidos'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'cuit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '30-XXXXXXXX-X'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ['proveedor', 'numero_factura', 'observaciones']
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'numero_factura': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notas opcionales de la compra'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)
        if veterinaria:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(veterinaria=veterinaria, activo=True)
        else:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True)


class DetalleCompraForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Producto"
    )
    cantidad = forms.IntegerField(
        min_value=1, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Cantidad"
    )
    precio_unitario = forms.DecimalField(
        min_value=0, decimal_places=2, max_digits=10, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Costo Unitario"
    )

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = (
            Producto.objects.filter(veterinaria=veterinaria) if veterinaria else Producto.objects.all()
        )

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        cantidad = cleaned_data.get('cantidad')
        precio_unitario = cleaned_data.get('precio_unitario')

        # Una fila se considera "completa" si tiene producto y cantidad; si está
        # totalmente vacía (fila sobrante del formset), se ignora sin error.
        if not producto and not cantidad and precio_unitario is None:
            return cleaned_data

        if not producto:
            raise forms.ValidationError("Seleccioná un producto para esta línea.")
        if not cantidad:
            raise forms.ValidationError("Indicá la cantidad para esta línea.")
        if precio_unitario is None:
            raise forms.ValidationError("Indicá el costo unitario para esta línea.")

        return cleaned_data

    def esta_completo(self):
        return bool(self.cleaned_data.get('producto') and self.cleaned_data.get('cantidad'))


DetalleCompraFormSet = formset_factory(DetalleCompraForm, extra=6)
