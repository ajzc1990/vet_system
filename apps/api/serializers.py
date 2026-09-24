from django.utils import timezone
from rest_framework import serializers

from apps.clientes.models import Cliente, Mascota
from apps.inventario.models import Producto
from apps.turnos.models import Turno, Veterinario
from apps.ventas.models import Venta, DetalleVenta


class TenantSerializerMixin:
    """Valida que las FKs que manda la app (mascota, cliente, veterinario...) sean de la
    veterinaria del usuario. La vista pasa la veterinaria en el context; para el superusuario
    viene None y no se restringe, igual que en el resto del sistema."""

    def _del_tenant(self, obj, veterinaria_de_obj, mensaje):
        vet = self.context.get('veterinaria')
        if obj is not None and vet is not None and veterinaria_de_obj != vet.id:
            raise serializers.ValidationError(mensaje)
        return obj


class MascotaSerializer(TenantSerializerMixin, serializers.ModelSerializer):
    especie_display = serializers.CharField(source='get_especie_display', read_only=True)
    sexo_display = serializers.CharField(source='get_sexo_display', read_only=True)

    class Meta:
        model = Mascota
        fields = [
            'id', 'cliente', 'nombre', 'especie', 'especie_display', 'raza',
            'fecha_nacimiento', 'sexo', 'sexo_display', 'peso_kg', 'castrado',
            'observaciones', 'creado_en',
        ]

    def validate_cliente(self, cliente):
        return self._del_tenant(cliente, cliente.veterinaria_id, "El cliente no pertenece a tu veterinaria.")


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


class VeterinarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Veterinario
        fields = ['id', 'nombre', 'apellido', 'matricula']


class TurnoSerializer(TenantSerializerMixin, serializers.ModelSerializer):
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

    def validate_mascota(self, mascota):
        return self._del_tenant(mascota, mascota.cliente.veterinaria_id, "La mascota no pertenece a tu veterinaria.")

    def validate_veterinario(self, veterinario):
        if veterinario is not None and not veterinario.activo:
            raise serializers.ValidationError("El veterinario no está activo.")
        return self._del_tenant(
            veterinario, getattr(veterinario, 'veterinaria_id', None), "El veterinario no pertenece a tu veterinaria.")


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


# Los modelos usan default=timezone.now en DateFields: si la app omite la fecha, el objeto
# queda con un datetime y DRF no lo puede serializar como fecha. Se usa la fecha local.
FECHA_DE_HOY = {'default': timezone.localdate}


class RegistroVacunaSerializer(serializers.ModelSerializer):
    veterinario_nombre = serializers.SerializerMethodField()
    fecha_aplicacion = serializers.DateField(**FECHA_DE_HOY)
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
    fecha_aplicacion = serializers.DateField(**FECHA_DE_HOY)
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


# ==============================================================================
# APP MÓVIL: estudios (foto/archivo) e internaciones
# ==============================================================================

from apps.historia_clinica.forms import validar_archivo_medico
from apps.historia_clinica.models import EstudioMedico, EvolucionInternacion


class EstudioMedicoSerializer(serializers.ModelSerializer):
    tipo_estudio_display = serializers.CharField(source='get_tipo_estudio_display', read_only=True)
    es_imagen = serializers.BooleanField(read_only=True)
    fecha_estudio = serializers.DateField(**FECHA_DE_HOY)

    class Meta:
        model = EstudioMedico
        fields = [
            'id', 'titulo', 'tipo_estudio', 'tipo_estudio_display', 'archivo', 'es_imagen',
            'fecha_estudio', 'observaciones',
        ]

    def validate_archivo(self, archivo):
        # Mismas reglas que el formulario web: 10 MB, PDF/JPG/PNG.
        return validar_archivo_medico(archivo)


class EvolucionInternacionSerializer(serializers.ModelSerializer):
    estado_general_display = serializers.CharField(source='get_estado_general_display', read_only=True)
    veterinario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = EvolucionInternacion
        fields = [
            'id', 'fecha_hora', 'estado_general', 'estado_general_display', 'peso_kg', 'temperatura_c',
            'frecuencia_cardiaca', 'frecuencia_respiratoria', 'notas', 'medicacion_administrada',
            'veterinario_nombre',
        ]
        read_only_fields = ['fecha_hora']

    def get_veterinario_nombre(self, obj):
        return _nombre_veterinario(obj.veterinario)


class InternacionSerializer(TenantSerializerMixin, serializers.ModelSerializer):
    """Ingreso a internación (POST /mascotas/{id}/internar/) y ficha de seguimiento."""
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    mascota_nombre = serializers.CharField(source='mascota.nombre', read_only=True)
    especie_display = serializers.CharField(source='mascota.get_especie_display', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    cliente_telefono = serializers.CharField(source='mascota.cliente.telefono', read_only=True)
    veterinario_responsable_nombre = serializers.SerializerMethodField()
    evoluciones = EvolucionInternacionSerializer(many=True, read_only=True)

    class Meta:
        model = Internacion
        fields = [
            'id', 'mascota', 'mascota_nombre', 'especie_display', 'cliente_nombre', 'cliente_telefono',
            'veterinario_responsable', 'veterinario_responsable_nombre', 'box', 'motivo_ingreso',
            'diagnostico_ingreso', 'dieta_indicaciones', 'fecha_ingreso', 'fecha_alta_estimada',
            'fecha_alta_real', 'estado', 'estado_display', 'resumen_alta', 'dias_internado',
            'costo_dia_estadia', 'evoluciones',
        ]
        read_only_fields = ['mascota', 'fecha_ingreso', 'fecha_alta_real', 'estado', 'resumen_alta']

    def get_cliente_nombre(self, obj):
        return f"{obj.mascota.cliente.nombre} {obj.mascota.cliente.apellido}"

    def get_veterinario_responsable_nombre(self, obj):
        return _nombre_veterinario(obj.veterinario_responsable)

    def validate_veterinario_responsable(self, veterinario):
        return self._del_tenant(
            veterinario, getattr(veterinario, 'veterinaria_id', None), "El veterinario no pertenece a tu veterinaria.")


class AltaInternacionSerializer(serializers.Serializer):
    """Mismas reglas que AltaInternacionForm: estado de cierre y epicrisis obligatoria."""
    estado = serializers.ChoiceField(choices=[c for c in Internacion.ESTADOS if c[0] != 'INTERNADO'])
    resumen_alta = serializers.CharField()


# ==============================================================================
# APP MÓVIL, FASE 2: notificaciones push y solicitudes de turno web
# ==============================================================================

from apps.turnos.models import SolicitudTurnoWeb

from .models import DispositivoPush


class DispositivoPushSerializer(serializers.Serializer):
    token = serializers.RegexField(r'^(ExponentPushToken|ExpoPushToken)\[.+\]$', max_length=255)
    plataforma = serializers.ChoiceField(choices=['android', 'ios'], required=False, default='')


class SolicitudTurnoWebSerializer(serializers.ModelSerializer):
    franja_preferida_display = serializers.CharField(source='get_franja_preferida_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = SolicitudTurnoWeb
        fields = [
            'id', 'nombre_tutor', 'telefono', 'email', 'nombre_mascota', 'especie', 'motivo',
            'fecha_deseada', 'franja_preferida', 'franja_preferida_display', 'estado', 'estado_display',
            'creado_el',
        ]
        read_only_fields = fields
