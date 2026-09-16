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

    @property
    def link_recordatorio_whatsapp(self):
        """Link de WhatsApp (wa.me) con un mensaje de recordatorio del turno ya redactado
        -incluye mascota, fecha y hora-, listo para que el staff se lo mande al tutor con
        un clic. None si no hay mascota/cliente o el cliente no tiene teléfono cargado."""
        if not self.mascota_id or not self.mascota.cliente or not self.mascota.cliente.telefono:
            return None

        from urllib.parse import quote

        cliente = self.mascota.cliente
        clinica = self.veterinaria.nombre if self.veterinaria else "la clínica"
        telefono = "".join(ch for ch in cliente.telefono if ch.isdigit())
        if not telefono:
            return None

        mensaje = (
            f"Hola {cliente.nombre}! Te escribimos de {clinica} para recordarte el turno de "
            f"{self.mascota.nombre} el {self.fecha_hora.strftime('%d/%m/%Y')} a las "
            f"{self.fecha_hora.strftime('%H:%M')} hs. ¡Te esperamos!"
        )
        return f"https://wa.me/{telefono}?text={quote(mensaje)}"


class SolicitudTurnoWeb(models.Model):
    """Pedido de turno enviado desde el formulario público de reserva online (sin necesidad
    de que el tutor tenga cuenta). El staff lo revisa y agenda el Turno real manualmente,
    evitando escribir datos de clientes/mascotas no validados directamente en el sistema."""

    FRANJAS = [
        ('MANANA', 'Mañana'),
        ('TARDE', 'Tarde'),
        ('CUALQUIERA', 'Cualquier horario'),
    ]
    ESTADOS = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('CONTACTADO', 'Contactado / En Gestión'),
        ('DESCARTADO', 'Descartado'),
    ]

    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='solicitudes_turno_web',
        verbose_name="Veterinaria"
    )
    nombre_tutor = models.CharField(max_length=150, verbose_name="Nombre y Apellido")
    telefono = models.CharField(max_length=30, verbose_name="Teléfono / WhatsApp")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    nombre_mascota = models.CharField(max_length=100, verbose_name="Nombre de la Mascota")
    especie = models.CharField(max_length=50, blank=True, null=True, verbose_name="Especie")
    motivo = models.TextField(verbose_name="Motivo de la Consulta")
    fecha_deseada = models.DateField(verbose_name="Fecha Deseada")
    franja_preferida = models.CharField(max_length=15, choices=FRANJAS, default='CUALQUIERA', verbose_name="Horario Preferido")
    estado = models.CharField(max_length=15, choices=ESTADOS, default='PENDIENTE', verbose_name="Estado")
    turno_creado = models.ForeignKey(
        Turno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitud_origen',
        verbose_name="Turno Agendado"
    )
    creado_el = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Solicitud de Turno Web"
        verbose_name_plural = "Solicitudes de Turno Web"
        ordering = ['-creado_el']

    def __str__(self):
        return f"{self.nombre_tutor} - {self.nombre_mascota} ({self.fecha_deseada.strftime('%d/%m/%Y')}) [{self.get_estado_display()}]"