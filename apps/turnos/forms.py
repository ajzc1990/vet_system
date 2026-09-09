# apps/turnos/forms.py
from django import forms
from .models import Turno, Veterinario
from apps.clientes.models import Mascota


class TurnoForm(forms.ModelForm):
    class Meta:
        model = Turno
        fields = ['mascota', 'veterinario', 'fecha_hora', 'motivo', 'estado', 'observaciones']
        widgets = {
            'mascota': forms.Select(attrs={'class': 'form-select'}),
            'veterinario': forms.Select(attrs={'class': 'form-select'}),
            'fecha_hora': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Vacunación, Consulta clínica, Control posoperatorio'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas adicionales sobre el turno...'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

        # 1. Marcar el campo 'estado' como opcional para que no rebote en el form.is_valid()
        self.fields['estado'].required = False
        self.fields['estado'].initial = 'PENDIENTE'

        # Formateador para renderizar correctamente el campo datetime-local en edición
        if self.instance and self.instance.pk and self.instance.fecha_hora:
            self.initial['fecha_hora'] = self.instance.fecha_hora.strftime('%Y-%m-%dT%H:%M')

        # Determinar la veterinaria activa
        vet_activa = veterinaria
        if not vet_activa and user and not user.is_superuser:
            if hasattr(user, 'perfil') and user.perfil and user.perfil.veterinaria:
                vet_activa = user.perfil.veterinaria
            elif hasattr(user, 'veterinaria'):
                vet_activa = user.veterinaria

        # Filtrar QuerySets según la veterinaria (Multi-Tenant)
        if vet_activa:
            self.fields['mascota'].queryset = Mascota.objects.filter(
                cliente__veterinaria=vet_activa, 
                cliente__activo=True
            ).select_related('cliente')
            
            self.fields['veterinario'].queryset = Veterinario.objects.filter(
                veterinaria=vet_activa, 
                activo=True
            )
        elif user and user.is_superuser:
            self.fields['mascota'].queryset = Mascota.objects.filter(cliente__activo=True).select_related('cliente')
            self.fields['veterinario'].queryset = Veterinario.objects.filter(activo=True)

        # Formato personalizado de etiqueta
        self.fields['mascota'].label_from_instance = lambda obj: (
            f"{obj.nombre} — (Dueño: {obj.cliente.apellido}, {obj.cliente.nombre})" 
            if hasattr(obj, 'cliente') and obj.cliente else obj.nombre
        )

        # Labels formateados
        self.fields['mascota'].label = "Mascota (Paciente) *"
        self.fields['fecha_hora'].label = "Fecha y Hora *"
        self.fields['veterinario'].label = "Veterinario Asignado"
        self.fields['motivo'].label = "Motivo del Turno"

    def clean_estado(self):
        """2. Si el cliente no mandó un 'estado' en el POST, asignamos 'PENDIENTE'."""
        estado = self.cleaned_data.get('estado')
        return estado if estado else 'PENDIENTE'


class VeterinarioForm(forms.ModelForm):
    class Meta:
        model = Veterinario
        fields = ['nombre', 'apellido', 'matricula', 'telefono', 'email', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'matricula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. MP-12345'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 381 1234567'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        self.veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

    def clean_matricula(self):
        matricula = self.cleaned_data.get('matricula')
        if not matricula:
            return matricula

        qs = Veterinario.objects.filter(matricula=matricula)
        if self.veterinaria:
            qs = qs.filter(veterinaria=self.veterinaria)

        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Ya existe un profesional registrado con esta matrícula en esta veterinaria.")

        return matricula