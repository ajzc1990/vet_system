from django.db import models
from django.contrib.auth.models import User

class Veterinaria(models.Model):
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Veterinaria / Clínica")
    cuit_rif = models.CharField(max_length=20, blank=True, null=True, verbose_name="CUIT / ID Fiscal")
    telefono = models.CharField(max_length=30, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    email_contacto = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to='logos_veterinarias/', blank=True, null=True, verbose_name="Logo Institucional")
    creado = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Veterinaria"
        verbose_name_plural = "Veterinarias"

    def __str__(self):
        return self.nombre


class PerfilUsuario(models.Model):
    ROLES = (
        ('ADMIN', 'Administrador de Veterinaria'),
        ('VET', 'Veterinario / Profesional'),
        ('RECEPCION', 'Recepcionista / Auxiliar'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    veterinaria = models.ForeignKey(Veterinaria, on_delete=models.CASCADE, related_name='usuarios')
    rol = models.CharField(max_length=15, choices=ROLES, default='VET')
    telefono = models.CharField(max_length=20, blank=True, null=True)
    is_approved = models.BooleanField(
        default=False, 
        verbose_name="Aprobado por Admin",
        help_text="Requiere aprobación de un superusuario antes de poder iniciar sesión."
    )

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

    def __str__(self):
        estado = "Aprobado" if self.is_approved else "Pendiente"
        return f"{self.user.get_full_name() or self.user.username} - {self.get_rol_display()} ({self.veterinaria.nombre}) [{estado}]"


# apps/usuarios/models.py
from django.db import models

class MensajeContacto(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre Completo")
    email = models.EmailField(verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=30, blank=True, null=True, verbose_name="Teléfono / WhatsApp")
    asunto = models.CharField(max_length=150, blank=True, null=True, verbose_name="Asunto")
    mensaje = models.TextField(verbose_name="Mensaje o Consulta")
    fecha_envio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Envío")
    leido = models.BooleanField(default=False, verbose_name="¿Leído / Atendido?")

    class Meta:
        verbose_name = "Mensaje de Contacto"
        verbose_name_plural = "Mensajes de Contacto"
        ordering = ['-fecha_envio']

    def __str__(self):
        estado = "Leído" if self.leido else "NUEVO"
        return f"[{estado}] {self.nombre} ({self.email}) - {self.fecha_envio.strftime('%d/%m/%Y %H:%M')}"