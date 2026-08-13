# apps/turnos/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.usuarios.models import Veterinaria
from apps.clientes.models import Mascota


class Veterinario(models.Model):
    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='veterinarios',
        verbose_name="Veterinaria",
        null=True,  # <--- Agrega null=True
        blank=True,
        
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='veterinario_perfil',
        verbose_name="Usuario de Sistema"
    )
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    matricula = models.CharField(max_length=50, verbose_name="Matrícula Profesional")
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Veterinario"
        verbose_name_plural = "Veterinarios"
        ordering = ['apellido', 'nombre']
        unique_together = ('veterinaria', 'matricula')

    def __str__(self):
        return f"Dr(a). {self.apellido}, {self.nombre} (Mat: {self.matricula})"


class Turno(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADO', 'Confirmado'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO', 'Cancelado'),
    ]

    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='turnos',
        verbose_name="Veterinaria"
    )
    mascota = models.ForeignKey(
        Mascota,
        on_delete=models.CASCADE,
        related_name='turnos',
        verbose_name="Mascota"
    )
    veterinario = models.ForeignKey(
        Veterinario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='turnos',
        verbose_name="Veterinario Asignado"
    )
    fecha_hora = models.DateTimeField(verbose_name="Fecha y Hora")
    motivo = models.TextField(blank=True, null=True, verbose_name="Motivo de Consulta")
    estado = models.CharField(
        max_length=15,
        choices=ESTADOS,
        default='PENDIENTE',
        verbose_name="Estado"
    )
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    creado = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    actualizado = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"
        ordering = ['fecha_hora']

    def __str__(self):
        return f"Turno: {self.mascota.nombre} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')} [{self.get_estado_display()}]"

    @property
    def es_pasado(self):
        """Devuelve True si la fecha/hora del turno ya transcurrió."""
        return self.fecha_hora < timezone.now()