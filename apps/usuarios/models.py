from django.db import models
from django.utils import timezone
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


# ==============================================================================
# AUDITORÍA (REGISTRO DE ACCIONES)
# ==============================================================================

class RegistroAuditoria(models.Model):
    ACCIONES = [
        ('CREAR', 'Creación'),
        ('EDITAR', 'Edición'),
        ('ELIMINAR', 'Eliminación'),
        ('LOGIN', 'Inicio de Sesión'),
        ('LOGIN_FALLIDO', 'Intento de Login Fallido'),
        ('LOGOUT', 'Cierre de Sesión'),
        ('APROBACION', 'Aprobación de Acceso'),
    ]

    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auditorias',
        verbose_name="Veterinaria"
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acciones_auditoria',
        verbose_name="Usuario"
    )
    accion = models.CharField(max_length=15, choices=ACCIONES, verbose_name="Acción")
    modelo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Entidad Afectada")
    objeto_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID del Registro")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="Dirección IP")
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora")

    class Meta:
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        ordering = ['-fecha']

    def __str__(self):
        quien = self.usuario.username if self.usuario else "Anónimo"
        return f"[{self.get_accion_display()}] {quien} - {self.descripcion} ({self.fecha.strftime('%d/%m/%Y %H:%M')})"


# ==============================================================================
# PLANES Y SUSCRIPCIONES (BILLING)
# ==============================================================================

class Plan(models.Model):
    nombre = models.CharField(max_length=50, verbose_name="Nombre del Plan")
    precio_mensual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio Mensual")
    precio_anual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio Anual")
    max_usuarios = models.PositiveIntegerField(default=3, verbose_name="Máximo de Usuarios")
    max_mascotas = models.PositiveIntegerField(default=100, verbose_name="Máximo de Pacientes Activos")
    permite_internacion = models.BooleanField(default=True, verbose_name="¿Incluye módulo de Internación?")
    permite_multiples_veterinarios = models.BooleanField(default=True, verbose_name="¿Permite múltiples veterinarios?")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción / Beneficios")
    activo = models.BooleanField(default=True, verbose_name="¿Plan disponible para contratar?")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden de Visualización")

    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ['orden', 'precio_mensual']

    def __str__(self):
        return f"{self.nombre} (${self.precio_mensual}/mes)"


class Suscripcion(models.Model):
    ESTADOS = [
        ('ACTIVA', 'Activa'),
        ('VENCIDA', 'Vencida'),
        ('CANCELADA', 'Cancelada'),
        ('PRUEBA', 'Período de Prueba'),
    ]
    CICLOS = [
        ('MENSUAL', 'Mensual'),
        ('ANUAL', 'Anual'),
    ]

    veterinaria = models.OneToOneField(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='suscripcion',
        verbose_name="Veterinaria"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='suscripciones',
        verbose_name="Plan Contratado"
    )
    ciclo_facturacion = models.CharField(
        max_length=10, choices=CICLOS, default='MENSUAL', verbose_name="Ciclo de Facturación"
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default='PRUEBA', verbose_name="Estado")
    fecha_inicio = models.DateField(default=timezone.now, verbose_name="Fecha de Inicio")
    fecha_vencimiento = models.DateField(verbose_name="Próximo Vencimiento / Renovación")
    ultimo_pago_registrado = models.DateField(blank=True, null=True, verbose_name="Fecha del Último Pago Registrado")
    notas = models.TextField(blank=True, null=True, verbose_name="Notas Internas de Facturación")

    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"
        ordering = ['fecha_vencimiento']

    def __str__(self):
        return f"Suscripción de {self.veterinaria.nombre} - {self.plan.nombre} [{self.get_estado_display()}]"

    @property
    def dias_para_vencer(self):
        return (self.fecha_vencimiento - timezone.localdate()).days

    @property
    def esta_vencida(self):
        return self.estado != 'CANCELADA' and self.fecha_vencimiento < timezone.localdate()

    @property
    def proxima_a_vencer(self):
        return not self.esta_vencida and 0 <= self.dias_para_vencer <= 7

    @property
    def precio_ciclo_actual(self):
        """Precio del plan correspondiente al ciclo de facturación contratado (mensual o anual)."""
        return self.plan.precio_anual if self.ciclo_facturacion == 'ANUAL' else self.plan.precio_mensual