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


# ==============================================================================
# APP MÓVIL (staff): historia clínica y altas desde el celular
# ==============================================================================

from apps.historia_clinica.models import (
    ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, Receta, ItemReceta,
    Internacion,
)


def _nombre_veterinario(veterinario):
    if not veterinario:
        return None
    return f"{veterinario.nombre} {veterinario.apellido}"


class MascotaDetalleSerializer(MascotaSerializer):
    """Mascota con los datos de contacto del tutor, para la ficha del paciente en la app."""
    cliente_nombre = serializers.SerializerMethodField()
    cliente_telefono = serializers.CharField(source='cliente.telefono', read_only=True)

    class Meta(MascotaSerializer.Meta):
        fields = MascotaSerializer.Meta.fields + ['cliente_nombre', 'cliente_telefono']

    def get_cliente_nombre(self, obj):
        return f"{obj.cliente.nombre} {obj.cliente.apellido}"


class ConsultaMedicaSerializer(serializers.ModelSerializer):
    veterinario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ConsultaMedica
        fields = [
            'id', 'mascota', 'turno', 'veterinario', 'veterinario_nombre', 'fecha_hora',
            'peso_actual_kg', 'temperatura_c', 'frecuencia_cardiaca', 'frecuencia_respiratoria',
            'motivo_consulta', 'anamnesis', 'examen_clinico', 'diagnostico', 'tratamiento',
            'observaciones_privadas',
        ]
        read_only_fields = ['mascota', 'veterinario', 'fecha_hora']

    def get_veterinario_nombre(self, obj):
        return _nombre_veterinario(obj.veterinario)


class RegistroVacunaSerializer(serializers.ModelSerializer):
    veterinario_nombre = serializers.SerializerMethodField()
    proxima_dosis_vencida = serializers.BooleanField(read_only=True)

    class Meta:
        model = RegistroVacuna
        fields = [
            'id', 'mascota', 'veterinario', 'veterinario_nombre', 'nombre_vacuna', 'lote',
            'fecha_aplicacion', 'fecha_proxima_dosis', 'proxima_dosis_vencida', 'observaciones',
        ]
        read_only_fields = ['mascota', 'veterinario']

    def get_veterinario_nombre(self, obj):
        return _nombre_veterinario(obj.veterinario)


class RegistroDesparasitacionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    proxima_dosis_vencida = serializers.BooleanField(read_only=True)

    class Meta:
        model = RegistroDesparasitacion
        fields = [
            'id', 'tipo', 'tipo_display', 'producto', 'dosis', 'fecha_aplicacion',
            'fecha_proxima_dosis', 'proxima_dosis_vencida',
        ]


class ItemRecetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemReceta
        fields = ['id', 'medicamento', 'dosis', 'duracion', 'indicaciones']


class RecetaSerializer(serializers.ModelSerializer):
    items = ItemRecetaSerializer(many=True)
    veterinario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Receta
        fields = [
            'id', 'mascota', 'consulta', 'veterinario', 'veterinario_nombre',
            'fecha_emision', 'diagnostico', 'observaciones', 'items',
        ]
        read_only_fields = ['mascota', 'veterinario', 'fecha_emision']

    def get_veterinario_nombre(self, obj):
        return _nombre_veterinario(obj.veterinario)

    def validate_items(self, items):
        # Igual que la vista web (nueva_receta): una receta sin medicamentos no se emite.
        items = [i for i in items if i.get('medicamento', '').strip()]
        if not items:
            raise serializers.ValidationError("Agregá al menos un medicamento.")
        return items

    def create(self, validated_data):
        items = validated_data.pop('items')
        receta = Receta.objects.create(**validated_data)
        for item in items:
            ItemReceta.objects.create(receta=receta, **item)
        return receta


class InternacionResumenSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Internacion
        fields = ['id', 'box', 'motivo_ingreso', 'fecha_ingreso', 'estado', 'estado_display', 'dias_internado']
