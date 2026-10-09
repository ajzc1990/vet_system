# apps/ventas/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.inventario.models import MovimientoStock


class CajaDiaria(models.Model):
    ESTADOS = [
        ('ABIERTA', 'Abierta'),
        ('CERRADA', 'Cerrada'),
    ]

    veterinaria = models.ForeignKey(
        'usuarios.Veterinaria',
        on_delete=models.CASCADE,
        related_name='cajas_diarias',
        null=True, blank=True
    )
    usuario_apertura = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cajas_abiertas'
    )
    usuario_cierre = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cajas_cerradas'
    )
    fecha_apertura = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    monto_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Monto Inicial (Mano de Caja)")
    monto_final_real = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Monto Final Real en Arqueo")
    estado = models.CharField(max_length=10, choices=ESTADOS, default='ABIERTA')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Caja Diaria"
        verbose_name_plural = "Cajas Diarias"
        ordering = ['-fecha_apertura']

    def __str__(self):
        return f"Caja #{self.id} - {self.fecha_apertura.strftime('%d/%m/%Y %H:%M')} ({self.get_estado_display()})"

    @property
    def total_gastos(self):
        return self.gastos.aggregate(total=models.Sum('monto'))['total'] or 0

    @property
    def total_efectivo(self):
        ventas_efectivo = self.ventas.filter(medio_pago='EFECTIVO').aggregate(total=models.Sum('total'))['total'] or 0
        return self.monto_inicial + ventas_efectivo - self.total_gastos

    @property
    def total_digital_tarjetas(self):
        return self.ventas.exclude(medio_pago='EFECTIVO').aggregate(total=models.Sum('total'))['total'] or 0

    @property
    def total_general_ventas(self):
        return self.ventas.aggregate(total=models.Sum('total'))['total'] or 0


class Venta(models.Model):
    MEDIOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('QR_MP', 'Link de pago (Mercado Pago)'),
        ('QR_LOCAL', 'QR en el local (Mercado Pago)'),
        ('DEBITO', 'Tarjeta de Débito'),
        ('CREDITO', 'Tarjeta de Crédito'),
        ('MERCADO_PAGO', 'Mercado Pago / Transferencia'),  # legado: ventas registradas antes de separar QR_MP y TRANSFERENCIA
    ]

    veterinaria = models.ForeignKey(
        'usuarios.Veterinaria', 
        on_delete=models.CASCADE, 
        related_name='ventas',
        null=True, blank=True
    )
    caja = models.ForeignKey(
        CajaDiaria,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ventas'
    )
    cliente = models.ForeignKey(
        'clientes.Cliente', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='compras'
    )
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)
    medio_pago = models.CharField(max_length=20, choices=MEDIOS_PAGO, default='EFECTIVO')
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Descuento (%)",
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_hora']

    def __str__(self):
        cliente_str = f"{self.cliente.nombre} {self.cliente.apellido}" if self.cliente else "Consumidor Final"
        return f"Venta #{self.id} - {cliente_str} (${self.total})"

    @property
    def subtotal_sin_descuento(self):
        return self.detalles.aggregate(total=models.Sum('subtotal'))['total'] or 0

    @property
    def monto_descuento(self):
        return self.subtotal_sin_descuento * self.descuento_porcentaje / 100


class CobroQR(models.Model):
    """Intento de cobro por QR/Mercado Pago, con la cuenta de MP propia de la
    veterinaria. La Venta real (y el descuento de stock) recién se crea cuando el
    webhook confirma el pago aprobado — así un cobro abandonado no deja ventas
    fantasma ni descuenta stock de algo que nunca se pagó."""
    ESTADOS = [
        ('PENDIENTE', 'Pendiente de Pago'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    veterinaria = models.ForeignKey(
        'usuarios.Veterinaria',
        on_delete=models.CASCADE,
        related_name='cobros_qr'
    )
    caja = models.ForeignKey(CajaDiaria, on_delete=models.CASCADE, related_name='cobros_qr')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Descuento (%)",
    )
    total = models.DecimalField(max_digits=12, decimal_places=2)
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.SET_NULL, null=True, blank=True)
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    mp_preference_id = models.CharField(max_length=100, blank=True, null=True)
    mp_payment_id = models.CharField(max_length=100, blank=True, null=True)
    mp_order_id = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="ID de orden de Mercado Pago",
        help_text="Solo para cobros con QR real en el local (API de Orders), distinto del link de pago.",
    )
    mp_qr_data = models.TextField(
        blank=True, null=True,
        verbose_name="Datos del QR",
        help_text="String que se convierte en imagen de QR para que el cliente escanee.",
    )
    estado = models.CharField(max_length=12, choices=ESTADOS, default='PENDIENTE')
    venta = models.OneToOneField(Venta, on_delete=models.SET_NULL, null=True, blank=True, related_name='cobro_qr')

    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cobro por QR"
        verbose_name_plural = "Cobros por QR"
        ordering = ['-creado_el']

    def __str__(self):
        return f"Cobro QR #{self.id} - {self.producto.nombre} (${self.total}) [{self.get_estado_display()}]"


class GastoCaja(models.Model):
    """Salida de efectivo de la caja en el momento: pago a un service, un flete,
    insumos de urgencia, etc. Se descuenta del efectivo esperado al arquear."""
    caja = models.ForeignKey(
        CajaDiaria,
        on_delete=models.CASCADE,
        related_name='gastos'
    )
    concepto = models.CharField(max_length=255, verbose_name="Concepto / Motivo")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto")
    fecha_hora = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        verbose_name = "Gasto de Caja"
        verbose_name_plural = "Gastos de Caja"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.concepto} (-${self.monto})"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT, null=True, blank=True)
    descripcion_personalizada = models.CharField(
        max_length=255, blank=True,
        verbose_name="Descripción (cargo sin producto de catálogo)",
        help_text="Para cobrar algo puntual (ej. una internación con costo variable) sin tener que crear un Producto/Servicio en el catálogo.",
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)

        # Si es una venta nueva, registramos el movimiento de stock. MovimientoStock.save()
        # ya descuenta self.producto.stock_actual: no hay que repetir el descuento acá.
        # Los Servicios no llevan stock, así que no generan movimiento.
        if es_nuevo and self.producto and not self.producto.es_servicio:
            cliente_str = f"{self.venta.cliente.nombre} {self.venta.cliente.apellido}" if self.venta.cliente else "Consumidor Final"
            MovimientoStock.objects.create(
                producto=self.producto,
                tipo='SALIDA',
                cantidad=self.cantidad,
                motivo=f"Venta #{self.venta.id} - Cliente: {cliente_str}"
            )

    @property
    def nombre_item(self):
        return self.producto.nombre if self.producto else self.descripcion_personalizada

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_item} (${self.subtotal})"