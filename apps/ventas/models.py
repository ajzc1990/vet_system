# apps/ventas/models.py
from django.db import models
from django.conf import settings
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
    def total_efectivo(self):
        ventas_efectivo = self.ventas.filter(medio_pago='EFECTIVO').aggregate(total=models.Sum('total'))['total'] or 0
        return self.monto_inicial + ventas_efectivo

    @property
    def total_digital_tarjetas(self):
        return self.ventas.exclude(medio_pago='EFECTIVO').aggregate(total=models.Sum('total'))['total'] or 0

    @property
    def total_general_ventas(self):
        return self.ventas.aggregate(total=models.Sum('total'))['total'] or 0


class Venta(models.Model):
    MEDIOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('MERCADO_PAGO', 'Mercado Pago / Transferencia'),
        ('DEBITO', 'Tarjeta de Débito'),
        ('CREDITO', 'Tarjeta de Crédito'),
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
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_hora']

    def __str__(self):
        cliente_str = f"{self.cliente.nombre} {self.cliente.apellido}" if self.cliente else "Consumidor Final"
        return f"Venta #{self.id} - {cliente_str} (${self.total})"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)

        # Si es una venta nueva, descontamos del inventario y registramos el movimiento
        if es_nuevo and self.producto:
            # Descuento directo en stock
            self.producto.stock_actual = max(0, self.producto.stock_actual - self.cantidad)
            self.producto.save(update_fields=['stock_actual'])

            # Movimiento de auditoría
            cliente_str = f"{self.venta.cliente.nombre} {self.venta.cliente.apellido}" if self.venta.cliente else "Consumidor Final"
            MovimientoStock.objects.create(
                producto=self.producto,
                tipo='SALIDA',
                cantidad=self.cantidad,
                motivo=f"Venta #{self.venta.id} - Cliente: {cliente_str}"
            )

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} (${self.subtotal})"