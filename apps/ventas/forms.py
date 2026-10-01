from django import forms
from .models import Venta
from apps.clientes.models import Cliente

class VentaForm(forms.ModelForm):
    class Meta:
        model = Venta
        fields = ['cliente', 'medio_pago', 'descuento_porcentaje', 'observaciones']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'medio_pago': forms.Select(attrs={'class': 'form-select', 'id': 'id_medio_pago'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100', 'id': 'id_descuento_porcentaje'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notas opcionales de la venta'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        if veterinaria:
            self.fields['cliente'].queryset = Cliente.objects.filter(veterinaria=veterinaria)
        else:
            self.fields['cliente'].queryset = Cliente.objects.all()

        self.fields['cliente'].required = False
        self.fields['cliente'].empty_label = "Consumidor Final / Cliente Ocasional"
        self.fields['descuento_porcentaje'].required = False
        self.fields['descuento_porcentaje'].label = "Descuento (%)"

        # 'MERCADO_PAGO' queda solo para mostrar ventas históricas (antes de separar
        # QR_MP y TRANSFERENCIA): no se ofrece como opción para ventas nuevas.
        self.fields['medio_pago'].choices = [
            c for c in Venta.MEDIOS_PAGO if c[0] != 'MERCADO_PAGO'
        ]
