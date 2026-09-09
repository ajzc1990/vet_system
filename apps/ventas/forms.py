from django import forms
from .models import Venta
from apps.inventario.models import Producto
from apps.clientes.models import Cliente

class VentaForm(forms.ModelForm):
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_producto'}),
        label="Producto / Insumo *"
    )
    cantidad = forms.IntegerField(
        min_value=1, 
        initial=1, 
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_cantidad'}),
        label="Cantidad *"
    )

    class Meta:
        model = Venta
        fields = ['cliente', 'medio_pago', 'observaciones']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'medio_pago': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notas opcionales de la venta'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        if veterinaria:
            self.fields['cliente'].queryset = Cliente.objects.filter(veterinaria=veterinaria)
            self.fields['producto'].queryset = Producto.objects.filter(veterinaria=veterinaria, stock_actual__gt=0)
        else:
            self.fields['cliente'].queryset = Cliente.objects.all()
            self.fields['producto'].queryset = Producto.objects.filter(stock_actual__gt=0)

        self.fields['cliente'].required = False
        self.fields['cliente'].empty_label = "Consumidor Final / Cliente Ocasional"