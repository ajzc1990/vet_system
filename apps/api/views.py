from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.clientes.models import Cliente, Mascota
from apps.inventario.models import Producto
from apps.turnos.models import Turno
from apps.usuarios.audit import registrar_auditoria
from apps.usuarios.decorators import es_veterinario_o_admin
from apps.ventas.models import Venta

from .permissions import EsUsuarioAprobadoDeLaVeterinaria, EsVeterinarioOAdmin
from .serializers import (
    ClienteSerializer, MascotaDetalleSerializer, ProductoSerializer,
    TurnoSerializer, VentaSerializer, ConsultaMedicaSerializer,
    RegistroVacunaSerializer, RegistroDesparasitacionSerializer, RecetaSerializer,
    InternacionResumenSerializer,
)


class TenantReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """Base de sólo-lectura que restringe el queryset a la veterinaria del usuario
    logueado. request.veterinaria (TenantMiddleware) no se puede usar acá porque ese
    middleware corre antes de que DRF resuelva la autenticación por token, así que
    se recalcula directo desde request.user.perfil."""

    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [EsUsuarioAprobadoDeLaVeterinaria]

    def get_veterinaria(self):
        perfil = getattr(self.request.user, 'perfil', None)
        return perfil.veterinaria if perfil else None

    def get_queryset(self):
        # Igual que el resto del sistema (ver turnos.views.lista_turnos): el superusuario
        # no tiene un tenant propio, así que ve todo en vez de quedar sin resultados.
        if self.request.user.is_superuser:
            return self.queryset
        vet = self.get_veterinaria()
        if vet is None:
            return self.queryset.model.objects.none()
        return self.queryset.filter(**{self.tenant_field: vet})


class ClienteViewSet(TenantReadOnlyViewSet):
    queryset = Cliente.objects.all().order_by('apellido', 'nombre')
    serializer_class = ClienteSerializer
    tenant_field = 'veterinaria'


class MascotaViewSet(TenantReadOnlyViewSet):
    """Lectura de pacientes más las altas médicas que la app móvil hace sobre una mascota
    (POST /mascotas/{id}/consultas/, /vacunas/, /recetas/). Las altas cuelgan de la mascota
    para que el aislamiento por tenant lo resuelva get_object() y no haya que revalidarlo."""

    queryset = Mascota.objects.select_related('cliente').all().order_by('nombre')
    serializer_class = MascotaDetalleSerializer
    tenant_field = 'cliente__veterinaria'

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) | Q(cliente__apellido__icontains=q)
                | Q(cliente__nombre__icontains=q) | Q(cliente__dni__icontains=q)
            )
        return qs

    def get_permissions(self):
        if self.action in ('consultas', 'vacunas', 'recetas'):
            return [EsUsuarioAprobadoDeLaVeterinaria(), EsVeterinarioOAdmin()]
        return super().get_permissions()

    def _veterinario_del_usuario(self):
        # La relación inversa de Veterinario.usuario se llama 'veterinario_perfil'.
        return getattr(self.request.user, 'veterinario_perfil', None)

    @action(detail=True, methods=['get'])
    def historia(self, request, pk=None):
        """Todo lo que la ficha del paciente de la app necesita, en un solo request."""
        mascota = self.get_object()
        resumen = getattr(mascota, 'resumen_ia', None)
        return Response({
            'mascota': MascotaDetalleSerializer(mascota).data,
            'consultas': ConsultaMedicaSerializer(
                mascota.consultas.select_related('veterinario')[:20], many=True).data,
            'vacunas': RegistroVacunaSerializer(
                mascota.vacunas.select_related('veterinario'), many=True).data,
            'desparasitaciones': RegistroDesparasitacionSerializer(
                mascota.desparasitaciones.all(), many=True).data,
            'recetas': RecetaSerializer(
                mascota.recetas.select_related('veterinario').prefetch_related('items')[:20],
                many=True).data,
            'internaciones_activas': InternacionResumenSerializer(
                mascota.internaciones.filter(estado='INTERNADO'), many=True).data,
            'resumen_ia': (
                {'texto': resumen.texto, 'generado_el': resumen.generado_el} if resumen else None
            ),
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def consultas(self, request, pk=None):
        mascota = self.get_object()
        serializer = ConsultaMedicaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        turno = serializer.validated_data.get('turno')
        if turno and turno.mascota_id != mascota.id:
            raise ValidationError({'turno': 'El turno no corresponde a esta mascota.'})

        # ConsultaMedica.save() ya actualiza el peso de la mascota y completa el turno.
        consulta = serializer.save(
            mascota=mascota,
            veterinaria=mascota.cliente.veterinaria,
            veterinario=self._veterinario_del_usuario(),
        )
        registrar_auditoria(
            request, 'CREAR', modelo='ConsultaMedica', objeto_id=consulta.id,
            descripcion=f"Consulta médica de {mascota.nombre} (app móvil)",
            veterinaria=mascota.cliente.veterinaria,
        )
        return Response(ConsultaMedicaSerializer(consulta).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def vacunas(self, request, pk=None):
        mascota = self.get_object()
        serializer = RegistroVacunaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vacuna = serializer.save(
            mascota=mascota,
            veterinaria=mascota.cliente.veterinaria,
            veterinario=self._veterinario_del_usuario(),
        )
        return Response(RegistroVacunaSerializer(vacuna).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def recetas(self, request, pk=None):
        mascota = self.get_object()
        serializer = RecetaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        consulta = serializer.validated_data.get('consulta')
        if consulta and consulta.mascota_id != mascota.id:
            raise ValidationError({'consulta': 'La consulta no corresponde a esta mascota.'})

        receta = serializer.save(
            mascota=mascota,
            veterinaria=mascota.cliente.veterinaria,
            veterinario=self._veterinario_del_usuario(),
        )
        registrar_auditoria(
            request, 'CREAR', modelo='Receta', objeto_id=receta.id,
            descripcion=f"Emisión de receta digital para {mascota.nombre} (app móvil)",
            veterinaria=mascota.cliente.veterinaria,
        )
        return Response(RecetaSerializer(receta).data, status=status.HTTP_201_CREATED)


class ProductoViewSet(TenantReadOnlyViewSet):
    queryset = Producto.objects.select_related('categoria').all().order_by('nombre')
    serializer_class = ProductoSerializer
    tenant_field = 'veterinaria'


class TurnoViewSet(TenantReadOnlyViewSet):
    queryset = Turno.objects.select_related(
        'mascota', 'mascota__cliente', 'veterinario',
    ).all().order_by('-fecha_hora')
    serializer_class = TurnoSerializer
    tenant_field = 'veterinaria'

    def get_queryset(self):
        qs = super().get_queryset()
        # ?fecha=YYYY-MM-DD: agenda de un día, en orden cronológico.
        fecha = self.request.query_params.get('fecha')
        if fecha:
            qs = qs.filter(fecha_hora__date=fecha).order_by('fecha_hora')
        return qs

    @action(detail=True, methods=['post'])
    def estado(self, request, pk=None):
        """Cambio de estado desde la agenda (confirmar, cancelar...), igual que
        turnos.views.cambiar_estado_turno: cualquier usuario aprobado de la clínica."""
        turno = self.get_object()
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in dict(Turno.ESTADOS):
            raise ValidationError({'estado': 'El estado especificado no es válido.'})
        turno.estado = nuevo_estado
        turno.save(update_fields=['estado', 'actualizado'])
        return Response(TurnoSerializer(turno).data)


class VentaViewSet(TenantReadOnlyViewSet):
    queryset = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').all().order_by('-fecha_hora')
    serializer_class = VentaSerializer
    tenant_field = 'veterinaria'


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([EsUsuarioAprobadoDeLaVeterinaria])
def yo(request):
    """Datos del usuario logueado para la app: nombre, rol, clínica y si puede cargar
    actos médicos (la app oculta esos botones a recepción)."""
    user = request.user
    perfil = getattr(user, 'perfil', None)
    veterinaria = perfil.veterinaria if perfil else None
    return Response({
        'username': user.username,
        'nombre': user.get_full_name() or user.username,
        'rol': perfil.rol if perfil else None,
        'rol_display': perfil.get_rol_display() if perfil else None,
        'veterinaria': veterinaria.nombre if veterinaria else None,
        'puede_atender': es_veterinario_o_admin(user),
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([EsUsuarioAprobadoDeLaVeterinaria])
def cerrar_sesion(request):
    """Revoca el token del dispositivo: al cerrar sesión, ese celular pierde el acceso."""
    request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
