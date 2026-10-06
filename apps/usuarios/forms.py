from django import forms
from django.contrib.auth.models import User
from .models import Veterinaria, PerfilUsuario


class ConfigVeterinariaForm(forms.ModelForm):
    """Formulario para la configuración del perfil institucional de la clínica."""
    class Meta:
        model = Veterinaria
        fields = ['nombre', 'cuit_rif', 'telefono', 'direccion', 'email_contacto', 'logo', 'mp_access_token']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Clínica Veterinaria Central'}),
            'cuit_rif': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 20-30123456-7'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: +54 381 1234567'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ej: Av. Marcos Paz 450'}),
            'email_contacto': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contacto@veterinaria.com'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'mp_access_token': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'APP_USR-...', 'autocomplete': 'off'}, render_value=True),
        }
        labels = {
            'nombre': 'Nombre de la Clínica *',
            'cuit_rif': 'CUIT / ID Fiscal',
            'telefono': 'Teléfono de Contacto',
            'direccion': 'Dirección Física',
            'email_contacto': 'Correo Electrónico de Contacto',
            'logo': 'Logo Institucional (para PDFs y Membretes)',
            'mp_access_token': 'Access Token de Mercado Pago (cobro por QR)',
        }


class RegistroForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
        label="Contraseña *"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
        label="Confirmar Contraseña *"
    )
    veterinaria = forms.ModelChoiceField(
        queryset=Veterinaria.objects.filter(activo=True),
        empty_label="-- Selecciona tu Veterinaria --",
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="Veterinaria / Clínica *"
    )
    rol = forms.ChoiceField(
        choices=PerfilUsuario.ROLES,
        initial='VET',
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="Rol en la Veterinaria *"
    )
    telefono = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: +54 381 1234567'}),
        label="Teléfono de Contacto"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
        }
        labels = {
            'username': 'Usuario *',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico *',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError("El correo electrónico es obligatorio.")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo electrónico ya se encuentra registrado.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')

        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Las contraseñas ingresadas no coinciden.")
        return cleaned_data


class CrearUsuarioEquipoForm(forms.ModelForm):
    """Para que el ADMIN de una veterinaria sume directamente a un miembro de su propio
    equipo (veterinario, recepción), sin pasar por el registro público ni depender de
    que el superusuario lo apruebe a mano."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
        label="Contraseña Inicial *",
        min_length=8,
        help_text="La persona puede cambiarla después desde su perfil.",
    )
    rol = forms.ChoiceField(
        choices=PerfilUsuario.ROLES,
        initial='VET',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Rol en la Veterinaria *",
    )
    telefono = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: +54 381 1234567'}),
        label="Teléfono de Contacto",
    )
    matricula = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: MP-12345'}),
        label="Matrícula (si es Veterinario)",
        help_text="Para que aparezca en el desplegable al asignar turnos. Si no la tenés a mano, se puede cargar después.",
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
        }
        labels = {
            'username': 'Usuario *',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico *',
        }

    def __init__(self, *args, **kwargs):
        self.veterinaria = kwargs.pop('veterinaria', None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise forms.ValidationError("El correo electrónico es obligatorio.")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este correo electrónico ya se encuentra registrado.")
        return email

    def clean_matricula(self):
        matricula = self.cleaned_data.get('matricula')
        if matricula and self.veterinaria:
            from apps.turnos.models import Veterinario
            if Veterinario.objects.filter(veterinaria=self.veterinaria, matricula=matricula).exists():
                raise forms.ValidationError("Ya hay un veterinario con esa matrícula en tu clínica.")
        return matricula