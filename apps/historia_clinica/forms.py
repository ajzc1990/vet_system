from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico,
    Internacion, EvolucionInternacion,
)
from apps.inventario.models import Producto
from apps.turnos.models import Veterinario, Turno


def validar_archivo_medico(archivo):
    """Auxiliar para validar tamaño máximo (10 MB) y formatos soportados."""
    if archivo:
        # Límite de 10 MB
        max_bytes = 10 * 1024 * 1024
        if archivo.size > max_bytes:
            raise ValidationError("El archivo supera el tamaño máximo permitido de 10 MB.")
        
        # Extensiones permitidas
        ext = archivo.name.split('.')[-1].lower()
        if ext not in ['pdf', 'png', 'jpg', 'jpeg']:
            raise ValidationError("Formato no soportado. Solo se permiten archivos PDF, JPG y PNG.")
    return archivo


class ConsultaMedicaForm(forms.ModelForm):
    # Descuento opcional de inventario
    producto_inventario = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        required=False,
        label="Insumo / Medicamento utilizado",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Seleccionar insumo del inventario (opcional) --"
    )
    cantidad_insumo = forms.IntegerField(
        required=False,
        initial=1,
        min_value=1,
        label="Cantidad utilizada",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )

    # Campos adicionales para adjuntar un estudio/análisis en la misma consulta
    estudio_titulo = forms.CharField(
        required=False,
        label="Título del Estudio / Adjunto",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ecografía abdominal, Hemograma completo'})
    )
    estudio_tipo = forms.ChoiceField(
        choices=EstudioMedico.TIPO_ESTUDIO,
        required=False,
        initial='OTRO',
        label="Tipo de Estudio",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    estudio_archivo = forms.FileField(
        required=False,
        label="Adjuntar Archivo (PDF, JPG, PNG)",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = ConsultaMedica
        fields = [
            'veterinario', 'turno', 'peso_actual_kg', 'temperatura_c',
            'frecuencia_cardiaca', 'frecuencia_respiratoria', 'motivo_consulta',
            'anamnesis', 'examen_clinico', 'diagnostico', 'tratamiento', 'observaciones_privadas'
        ]
        widgets = {
            'veterinario': forms.Select(attrs={'class': 'form-select'}),
            'turno': forms.Select(attrs={'class': 'form-select'}),
            'peso_actual_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ej: 14.5'}),
            'temperatura_c': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ej: 38.5'}),
            'frecuencia_cardiaca': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'LPM (Ej: 110)'}),
            'frecuencia_respiratoria': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'RPM (Ej: 24)'}),
            'motivo_consulta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Decaimiento y vómitos desde hace 24hs'}),
            'anamnesis': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Síntomas referidos por el tutor...'}),
            'examen_clinico': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Hallazgos a la palpación, auscultación, mucosas...'}),
            'diagnostico': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Gastroenteritis aguda / Otitis externa'}),
            'tratamiento': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Medicamentos recetados, dosis y plan de acción...'}),
            'observaciones_privadas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notas internas solo visibles para el equipo...'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        # Filtrar datos pertenecientes al tenant activo
        if veterinaria:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(
                veterinaria=veterinaria, 
                stock_actual__gt=0
            )
            self.fields['veterinario'].queryset = Veterinario.objects.filter(
                veterinaria=veterinaria, 
                activo=True
            )
            self.fields['turno'].queryset = Turno.objects.filter(
                veterinaria=veterinaria, 
                estado__in=['PENDIENTE', 'CONFIRMADO', 'EN_ESPERA', 'ATENDIENDO']
            )
        else:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(stock_actual__gt=0)

        # Configurar etiquetas
        self.fields['motivo_consulta'].label = "Motivo de Consulta *"
        self.fields['diagnostico'].label = "Diagnóstico *"
        self.fields['tratamiento'].label = "Tratamiento e Indicaciones *"

    def clean_estudio_archivo(self):
        archivo = self.cleaned_data.get('estudio_archivo')
        return validar_archivo_medico(archivo)


class RegistroVacunaForm(forms.ModelForm):
    producto_inventario = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        required=False,
        label="Descontar vacuna del inventario",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Seleccionar lote/vacuna del inventario (opcional) --"
    )

    class Meta:
        model = RegistroVacuna
        fields = ['veterinario', 'nombre_vacuna', 'lote', 'fecha_aplicacion', 'fecha_proxima_dosis', 'observaciones']
        widgets = {
            'veterinario': forms.Select(attrs={'class': 'form-select'}),
            'nombre_vacuna': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Quíntuple / Antirrábica'}),
            'lote': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: L-48291'}),
            'fecha_aplicacion': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_proxima_dosis': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Anotaciones adicionales'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        if not self.initial.get('fecha_aplicacion'):
            self.initial['fecha_aplicacion'] = timezone.now().strftime('%Y-%m-%d')

        if veterinaria:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(
                veterinaria=veterinaria, 
                tipo='VACUNA', 
                stock_actual__gt=0
            )
            self.fields['veterinario'].queryset = Veterinario.objects.filter(
                veterinaria=veterinaria, 
                activo=True
            )
        else:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(stock_actual__gt=0)

        self.fields['nombre_vacuna'].label = "Nombre de la Vacuna *"
        self.fields['fecha_aplicacion'].label = "Fecha de Aplicación *"


class RegistroDesparasitacionForm(forms.ModelForm):
    producto_inventario = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        required=False,
        label="Descontar antiparasitario del inventario",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Seleccionar producto del inventario (opcional) --"
    )

    class Meta:
        model = RegistroDesparasitacion
        fields = ['veterinario', 'tipo', 'producto', 'dosis', 'fecha_aplicacion', 'fecha_proxima_dosis']
        widgets = {
            'veterinario': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Simparica / Total Full'}),
            'dosis': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1 comp. 10-20kg'}),
            'fecha_aplicacion': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_proxima_dosis': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        if not self.initial.get('fecha_aplicacion'):
            self.initial['fecha_aplicacion'] = timezone.now().strftime('%Y-%m-%d')

        if veterinaria:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(
                veterinaria=veterinaria, 
                stock_actual__gt=0
            )
            self.fields['veterinario'].queryset = Veterinario.objects.filter(
                veterinaria=veterinaria, 
                activo=True
            )
        else:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(stock_actual__gt=0)

        self.fields['producto'].label = "Producto Suministrado *"
        self.fields['fecha_aplicacion'].label = "Fecha de Aplicación *"


class EstudioMedicoForm(forms.ModelForm):
    class Meta:
        model = EstudioMedico
        fields = ['veterinario', 'consulta', 'tipo_estudio', 'titulo', 'archivo', 'fecha_estudio', 'observaciones']
        widgets = {
            'veterinario': forms.Select(attrs={'class': 'form-select'}),
            'consulta': forms.Select(attrs={'class': 'form-select'}),
            'tipo_estudio': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ecografía abdominal, RX Tórax'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            'fecha_estudio': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Informe médico o conclusiones del estudio...'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        mascota = kwargs.pop('mascota', None)
        super().__init__(*args, **kwargs)

        if not self.initial.get('fecha_estudio'):
            self.initial['fecha_estudio'] = timezone.now().strftime('%Y-%m-%d')

        if veterinaria:
            self.fields['veterinario'].queryset = Veterinario.objects.filter(
                veterinaria=veterinaria,
                activo=True
            )
        
        if mascota:
            self.fields['consulta'].queryset = ConsultaMedica.objects.filter(mascota=mascota)
            self.fields['consulta'].empty_label = "-- Vincula a consulta (opcional) --"

        self.fields['titulo'].label = "Título del Estudio *"
        self.fields['archivo'].label = "Archivo / Documento *"
        self.fields['fecha_estudio'].label = "Fecha de Realización *"

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        return validar_archivo_medico(archivo)


class InternacionForm(forms.ModelForm):
    class Meta:
        model = Internacion
        fields = [
            'veterinario_responsable', 'box', 'motivo_ingreso', 'diagnostico_ingreso',
            'dieta_indicaciones', 'fecha_alta_estimada', 'costo_dia_estadia',
        ]
        widgets = {
            'veterinario_responsable': forms.Select(attrs={'class': 'form-select'}),
            'box': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Box 3 / Jaula A'}),
            'motivo_ingreso': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ej: Politraumatismo por accidente automovilístico, requiere observación'}),
            'diagnostico_ingreso': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Diagnóstico presuntivo al momento del ingreso'}),
            'dieta_indicaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Dieta, reposo, indicaciones generales de enfermería'}),
            'fecha_alta_estimada': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'costo_dia_estadia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 15000.00'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        if veterinaria:
            self.fields['veterinario_responsable'].queryset = Veterinario.objects.filter(
                veterinaria=veterinaria,
                activo=True
            )

        self.fields['motivo_ingreso'].label = "Motivo de Internación *"
        self.fields['veterinario_responsable'].required = False


class EvolucionInternacionForm(forms.ModelForm):
    producto_inventario = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        required=False,
        label="Insumo / Medicamento administrado",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- Descontar insumo del inventario (opcional) --"
    )
    cantidad_insumo = forms.IntegerField(
        required=False,
        initial=1,
        min_value=1,
        label="Cantidad utilizada",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )

    class Meta:
        model = EvolucionInternacion
        fields = [
            'veterinario', 'estado_general', 'peso_kg', 'temperatura_c',
            'frecuencia_cardiaca', 'frecuencia_respiratoria', 'notas', 'medicacion_administrada',
        ]
        widgets = {
            'veterinario': forms.Select(attrs={'class': 'form-select'}),
            'estado_general': forms.Select(attrs={'class': 'form-select'}),
            'peso_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ej: 14.5'}),
            'temperatura_c': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ej: 38.5'}),
            'frecuencia_cardiaca': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'LPM'}),
            'frecuencia_respiratoria': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'RPM'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Evolución clínica, novedades, procedimientos realizados en este control...'}),
            'medicacion_administrada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Meloxicam 0.2mg/kg SC'}),
        }

    def __init__(self, *args, **kwargs):
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        if veterinaria:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(
                veterinaria=veterinaria,
                stock_actual__gt=0
            )
            self.fields['veterinario'].queryset = Veterinario.objects.filter(
                veterinaria=veterinaria,
                activo=True
            )
        else:
            self.fields['producto_inventario'].queryset = Producto.objects.filter(stock_actual__gt=0)

        self.fields['notas'].label = "Evolución Clínica / Novedades *"
        self.fields['veterinario'].required = False


class AltaInternacionForm(forms.ModelForm):
    class Meta:
        model = Internacion
        fields = ['estado', 'resumen_alta']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'resumen_alta': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Resumen de la evolución, indicaciones para el hogar y seguimiento post-alta...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].choices = [
            c for c in Internacion.ESTADOS if c[0] != 'INTERNADO'
        ]
        self.fields['resumen_alta'].label = "Resumen / Epicrisis de Alta *"
        self.fields['resumen_alta'].required = True