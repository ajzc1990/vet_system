# apps/compras/models.py
from django.conf import settings
from django.db import models
from apps.inventario.models import MovimientoStock


class Proveedor(models.Model):
    veterinaria = models.ForeignKey(
        'usuarios.Veterinaria',
        on_delete=models.CASCADE,
        related_name='proveedores',
        null=True, blank=True,
        verbose_name="Veterinaria"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre / Razón Social")
    contacto = models.CharField(max_length=150, blank=True, verbose_name="Persona de Contacto")
    telefono = models.CharField(max_length=30, blank=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, verbose_name="Email")
    direccion = models.CharField(max_length=255, blank=True, verbose_name="Dirección")
    cuit = models.CharField(max_length=20, blank=True, verbose_name="CUIT")
    notas = models.TextField(blank=True, verbose_name="Notas")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_el = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Compra(models.Model):
    veterinaria = models.ForeignKey(
        'usuarios.Veterinaria',
        on_delete=models.CASCADE,
        related_name='compras',
        null=True, blank=True,
        verbose_name="Veterinaria"
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name='compras',
        verbose_name="Proveedor"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Registrada por"
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)
    numero_factura = models.CharField(max_length=50, blank=True, verbose_name="Nº de Factura / Remito")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Compra #{self.id} - {self.proveedor.nombre} (${self.total})"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Unitario")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        es_nuevo = self.pk is None
        super().save(*args, **kwargs)

        # Si es un renglón nuevo, registramos la entrada de stock y actualizamos el
        # costo de referencia del producto. MovimientoStock.save() ya suma
        # self.producto.stock_actual: no hay que repetir el incremento acá.
        if es_nuevo and self.producto:
            MovimientoStock.objects.create(
                producto=self.producto,
                tipo='ENTRADA',
                cantidad=self.cantidad,
                motivo=f"Compra #{self.compra.id} a {self.compra.proveedor.nombre}"
            )
            self.producto.precio_costo = self.precio_unitario
            self.producto.save(update_fields=['precio_costo'])

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} (${self.subtotal})"
