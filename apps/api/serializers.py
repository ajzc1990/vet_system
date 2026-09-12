from rest_framework import serializers

from apps.clientes.models import Cliente, Mascota
from apps.inventario.models import Producto
from apps.turnos.models import Turno
from apps.ventas.models import Venta, DetalleVenta


class MascotaSerializer(serializers.ModelSerializer):
    especie_display = serializers.CharField(source='get_especie_display', read_only=True)
    sexo_display = serializers.CharField(source='get_sexo_display', read_only=True)

    class Meta:
        model = Mascota
        fields = [
            'id', 'cliente', 'nombre', 'especie', 'especie_display', 'raza',
            'fecha_nacimiento', 'sexo', 'sexo_display', 'peso_kg', 'castrado',
            'observaciones', 'creado_en',
        ]


class ClienteSerializer(serializers.ModelSerializer):
    mascotas = MascotaSerializer(many=True, read_only=True)

    class Meta:
        model = Cliente
        fields = [
            'id', 'nombre', 'apellido', 'dni', 'telefono', 'email', 'direccion',
            'activo', 'creado_en', 'mascotas',
        ]


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True, default=None)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'categoria', 'categoria_nombre', 'tipo', 'tipo_display',
            'codigo_barras', 'stock_actual', 'stock_minimo', 'precio_costo',
            'precio_venta', 'fecha_vencimiento', 'actualizado_el',
        ]


class TurnoSerializer(serializers.ModelSerializer):
    mascota_nombre = serializers.CharField(source='mascota.nombre', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    veterinario_nombre = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Turno
        fields = [
            'id', 'mascota', 'mascota_nombre', 'cliente_nombre', 'veterinario',
            'veterinario_nombre', 'fecha_hora', 'motivo', 'estado', 'estado_display',
            'observaciones',
        ]

    def get_cliente_nombre(self, obj):
        cliente = obj.mascota.cliente
        return f"{cliente.nombre} {cliente.apellido}"

    def get_veterinario_nombre(self, obj):
        if not obj.veterinario:
            return None
        return f"{obj.veterinario.nombre} {obj.veterinario.apellido}"


class DetalleVentaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True, default=None)

    class Meta:
        model = DetalleVenta
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_unitario', 'subtotal']


class VentaSerializer(serializers.ModelSerializer):
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    medio_pago_display = serializers.CharField(source='get_medio_pago_display', read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id', 'fecha_hora', 'cliente', 'cliente_nombre', 'medio_pago',
            'medio_pago_display', 'total', 'observaciones', 'detalles',
        ]

    def get_cliente_nombre(self, obj):
        if not obj.cliente:
            return None
        return f"{obj.cliente.nombre} {obj.cliente.apellido}"
