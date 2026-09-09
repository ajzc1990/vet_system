# apps/inventario/models.py
from datetime import timedelta
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from apps.usuarios.models import Veterinaria


class Categoria(models.Model):
    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='categorias_inventario',
        null=True,
        blank=True,
        verbose_name="Veterinaria",
        help_text="Si se deja en blanco, la categoría será global para todas las veterinarias."
    )
    nombre = models.CharField(max_length=100, verbose_name="Nombre de Categoría")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']
        unique_together = [['veterinaria', 'nombre']]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    TIPO_CHOICES = [
        ('MEDICAMENTO', 'Medicamento / Fármaco'),
        ('VACUNA', 'Vacuna'),
        ('ALIMENTO', 'Alimento / Nutrición'),
        ('DESCARTABLE', 'Material Descartable'),
        ('OTRO', 'Otro insumo'),
    ]

    veterinaria = models.ForeignKey(
        Veterinaria, 
        on_delete=models.CASCADE, 
        related_name='productos',
        verbose_name="Veterinaria"
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Producto")
    categoria = models.ForeignKey(
        Categoria, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='productos',
        verbose_name="Categoría"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='MEDICAMENTO', verbose_name="Tipo de Insumo")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código de Barras")
    
    stock_actual = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Stock Actual")
    stock_minimo = models.IntegerField(default=5, validators=[MinValueValidator(0)], verbose_name="Stock Mínimo Alerta")
    
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio de Costo")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio de Venta")
    
    fecha_vencimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Vencimiento")
    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto / Insumo"
        verbose_name_plural = "Productos e Insumos"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} (Stock: {self.stock_actual})"

    @property
    def bajo_stock(self):
        """Retorna True si el stock actual cayó por debajo o igual al mínimo."""
        return self.stock_actual <= self.stock_minimo

    @property
    def esta_vencido(self):
        """Retorna True si la fecha de vencimiento transcurrió."""
        if self.fecha_vencimiento:
            return self.fecha_vencimiento < timezone.now().date()
        return False

    @property
    def proximo_a_vencer(self):
        """Retorna True si el producto vence dentro de los próximos 30 días y aún no expiró."""
        if self.fecha_vencimiento:
            hoy = timezone.now().date()
            limite = hoy + timedelta(days=30)
            return hoy <= self.fecha_vencimiento <= limite
        return False

    @property
    def dias_para_vencer(self):
        """Devuelve el número de días restantes para vencer (negativo si ya venció)."""
        if self.fecha_vencimiento:
            return (self.fecha_vencimiento - timezone.now().date()).days
        return None


class MovimientoStock(models.Model):
    TIPO_MOVIMIENTO = [
        ('ENTRADA', 'Entrada (Compra / Reposición)'),
        ('SALIDA', 'Salida (Venta / Uso en Consulta)'),
        ('AJUSTE', 'Ajuste de Inventario / Pérdida'),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    cantidad = models.PositiveIntegerField()
    motivo = models.CharField(max_length=255, blank=True, null=True, help_text="Ej: Consulta #12, Compra a proveedor, etc.")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.tipo} - {self.producto.nombre} ({self.cantidad})"

    def save(self, *args, **kwargs):
        # Descuento o incremento automático en la tabla Producto al registrar el movimiento
        if not self.pk:  # Solo al crear el registro
            if self.tipo == 'ENTRADA':
                self.producto.stock_actual += self.cantidad
            elif self.tipo in ['SALIDA', 'AJUSTE']:
                self.producto.stock_actual = max(0, self.producto.stock_actual - self.cantidad)
            self.producto.save(update_fields=['stock_actual'])
        super().save(*args, **kwargs)