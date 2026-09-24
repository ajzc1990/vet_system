from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.clientes.models import Cliente, Mascota
from apps.historia_clinica import views as vistas_web
from apps.historia_clinica.ia import ResumenIADeshabilitado, ResumenIAError, generar_resumen_clinico
from apps.historia_clinica.models import Internacion, Receta
from apps.inventario.models import Producto
from apps.turnos.models import SolicitudTurnoWeb, Turno, Veterinario
from apps.usuarios.audit import registrar_auditoria
from apps.usuarios.decorators import es_veterinario_o_admin
from apps.ventas.models import Venta

from .models import DispositivoPush
from .permissions import EsUsuarioAprobadoDeLaVeterinaria, EsVeterinarioOAdmin
from .serializers import (
    AltaInternacionSerializer, ClienteSerializer, DispositivoPushSerializer, SolicitudTurnoWebSerializer, ConsultaMedicaSerializer, EstudioMedicoSerializer,
    EvolucionInternacionSerializer, InternacionResumenSerializer, InternacionSerializer,
    MascotaDetalleSerializer, ProductoSerializer, RecetaSerializer, RegistroDesparasitacionSerializer,
    RegistroVacunaSerializer, TurnoSerializer, VentaSerializer, VeterinarioSerializer,
)


def _veterinaria_del_usuario(user):
    perfil = getattr(user, 'perfil', None)
    return perfil.veterinaria if perfil else None


def _pdf_de_la_web(request, vista, **kwargs):
    """Reutiliza las vistas PDF de la web (mismo diseño, mismo código de ReportLab) para la app.
    DRF ya dejó el usuario del token en request._request.user; falta la veterinaria, que en la
    web resuelve TenantMiddleware antes de conocer al usuario del token. La vista web vuelve a
    filtrar por esa veterinaria, así que el aislamiento por tenant se mantiene."""
    django_request = request._request
    django_request.veterinaria = _veterinaria_del_usuario(request.user)
    return vista(django_request, **kwargs)


class TenantReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """Base de sólo-lectura que restringe el queryset a la veterinaria del usuario
    logueado. request.veterinaria (TenantMiddleware) no se puede usar acá porque ese
    middleware corre antes de que DRF resuelva la autenticación por token, así que
    se recalcula directo desde request.user.perfil."""

    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [EsUsuarioAprobadoDeLaVeterinaria]

    def get_veterinaria(self):
        return _veterinaria_del_usuario(self.request.user)

    def get_serializer_context(self):
        # Los serializers validan contra esto que las FKs recibidas sean del mismo tenant.
        context = super().get_serializer_context()
        context['veterinaria'] = None if self.request.user.is_superuser else self.get_veterinaria()
        return context

    def get_queryset(self):
        # Igual que el resto del sistema (ver turnos.views.lista_turnos): el superusuario
        # no tiene un tenant propio, así que ve todo en vez de quedar sin resultados.
        if self.request.user.is_superuser:
            return self.queryset
        vet = self.get_veterinaria()
        if vet is None:
            return self.queryset.model.objects.none()
        return self.queryset.filter(**{self.tenant_field: vet})

    def veterinario_del_usuario(self):
        # La relación inversa de Veterinario.usuario se llama 'veterinario_perfil'.
        return getattr(self.request.user, 'veterinario_perfil', None)


class TenantEditableViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, TenantReadOnlyViewSet):
    """Alta y edición parcial (PATCH). No se expone borrado por la API: eso queda en la web."""

    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class ClienteViewSet(TenantEditableViewSet):
    queryset = Cliente.objects.prefetch_related('mascotas').all().order_by('apellido', 'nombre')
    serializer_class = ClienteSerializer
    tenant_field = 'veterinaria'

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(Q(apellido__icontains=q) | Q(nombre__icontains=q) | Q(dni__icontains=q))
        return qs

    def perform_create(self, serializer):
        vet = self.get_veterinaria()
        if vet is None:
            raise ValidationError({'detail': 'Tu usuario no tiene una veterinaria asignada.'})
        cliente = serializer.save(veterinaria=vet)
        registrar_auditoria(
            self.request, 'CREAR', modelo='Cliente', objeto_id=cliente.id, veterinaria=vet,
            descripcion=f"Alta de cliente: {cliente.nombre} {cliente.apellido} (DNI: {cliente.dni}) (app móvil)",
        )


class MascotaViewSet(TenantEditableViewSet):
    """Pacientes: alta/edición más las acciones clínicas que la app hace sobre una mascota.
    Las acciones cuelgan de la mascota para que el aislamiento por tenant lo resuelva
    get_object() y no haya que revalidarlo en cada una."""

    queryset = Mascota.objects.select_related('cliente').all().order_by('nombre')
    serializer_class = MascotaDetalleSerializer
    tenant_field = 'cliente__veterinaria'
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    ACCIONES_MEDICAS = (
        'consultas', 'vacunas', 'recetas', 'desparasitaciones', 'estudios', 'resumen_ia', 'internar',
    )

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
        # Mismo criterio que @requerir_rol_veterinario en la web.
        if self.action in self.ACCIONES_MEDICAS:
            return [EsUsuarioAprobadoDeLaVeterinaria(), EsVeterinarioOAdmin()]
        return super().get_permissions()

    def _alta_clinica(self, serializer_class, mascota, **extra):
        serializer = serializer_class(data=self.request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        return serializer, serializer.save(
            mascota=mascota,
            veterinaria=mascota.cliente.veterinaria,
            **extra,
        )

    @action(detail=True, methods=['get'])
    def historia(self, request, pk=None):
        """Todo lo que la ficha del paciente de la app necesita, en un solo request."""
        mascota = self.get_object()
        resumen = getattr(mascota, 'resumen_ia', None)
        contexto = self.get_serializer_context()
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
            'estudios': EstudioMedicoSerializer(mascota.estudios.all()[:30], many=True, context=contexto).data,
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
            veterinario=self.veterinario_del_usuario(),
        )
        registrar_auditoria(
            request, 'CREAR', modelo='ConsultaMedica', objeto_id=consulta.id,
            descripcion=f"Consulta médica de {mascota.nombre} (app móvil)",
            veterinaria=mascota.cliente.veterinaria,
        )
        return Response(ConsultaMedicaSerializer(consulta).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def vacunas(self, request, pk=None):
        serializer, _ = self._alta_clinica(
            RegistroVacunaSerializer, self.get_object(), veterinario=self.veterinario_del_usuario())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def desparasitaciones(self, request, pk=None):
        serializer, _ = self._alta_clinica(
            RegistroDesparasitacionSerializer, self.get_object(), veterinario=self.veterinario_del_usuario())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def estudios(self, request, pk=None):
        """Sube una foto o archivo (multipart, campo 'archivo') a la historia clínica."""
        serializer, _ = self._alta_clinica(
            EstudioMedicoSerializer, self.get_object(), veterinario=self.veterinario_del_usuario())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
            veterinario=self.veterinario_del_usuario(),
        )
        registrar_auditoria(
            request, 'CREAR', modelo='Receta', objeto_id=receta.id,
            descripcion=f"Emisión de receta digital para {mascota.nombre} (app móvil)",
            veterinaria=mascota.cliente.veterinaria,
        )
        return Response(RecetaSerializer(receta).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='resumen-ia')
    def resumen_ia(self, request, pk=None):
        mascota = self.get_object()
        try:
            resumen = generar_resumen_clinico(mascota, usuario=request.user)
        except ResumenIADeshabilitado:
            return Response({'detail': 'La función de resúmenes con IA no está habilitada.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ResumenIAError:
            return Response({'detail': 'No se pudo generar el resumen. Probá de nuevo en unos minutos.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response({'texto': resumen.texto, 'generado_el': resumen.generado_el})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def internar(self, request, pk=None):
        mascota = self.get_object()
        if mascota.internaciones.filter(estado='INTERNADO').exists():
            raise ValidationError({'detail': f'{mascota.nombre} ya tiene una internación en curso.'})
        _, internacion = self._alta_clinica(InternacionSerializer, mascota)
        registrar_auditoria(
            request, 'CREAR', modelo='Internacion', objeto_id=internacion.id,
            descripcion=f"Ingreso a internación de {mascota.nombre} (Box: {internacion.box or '-'}) (app móvil)",
            veterinaria=mascota.cliente.veterinaria,
        )
        return Response(InternacionSerializer(internacion).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='carnet-pdf')
    def carnet_pdf(self, request, pk=None):
        mascota = self.get_object()
        return _pdf_de_la_web(request, vistas_web.descargar_carnet_vacunas_pdf, mascota_id=mascota.id)


class InternacionViewSet(TenantReadOnlyViewSet):
    """Sala de internación: ?activas=1 para los pacientes internados ahora."""

    queryset = Internacion.objects.select_related(
        'mascota', 'mascota__cliente', 'veterinario_responsable',
    ).prefetch_related('evoluciones__veterinario').order_by('-fecha_ingreso')
    serializer_class = InternacionSerializer
    tenant_field = 'veterinaria'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('activas'):
            qs = qs.filter(estado='INTERNADO').order_by('fecha_ingreso')
        return qs

    def get_permissions(self):
        if self.action in ('evoluciones', 'alta'):
            return [EsUsuarioAprobadoDeLaVeterinaria(), EsVeterinarioOAdmin()]
        return super().get_permissions()

    def _activa(self):
        internacion = self.get_object()
        if not internacion.esta_activa:
            raise ValidationError({'detail': 'Esta internación ya fue cerrada.'})
        return internacion

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def evoluciones(self, request, pk=None):
        internacion = self._activa()
        serializer = EvolucionInternacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        evolucion = serializer.save(internacion=internacion, veterinario=self.veterinario_del_usuario())
        # Igual que la web: el peso del control pasa a ser el peso actual del paciente.
        if evolucion.peso_kg:
            internacion.mascota.peso_kg = evolucion.peso_kg
            internacion.mascota.save(update_fields=['peso_kg'])
        return Response(EvolucionInternacionSerializer(evolucion).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def alta(self, request, pk=None):
        internacion = self._activa()
        serializer = AltaInternacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        internacion.estado = serializer.validated_data['estado']
        internacion.resumen_alta = serializer.validated_data['resumen_alta']
        internacion.fecha_alta_real = timezone.now()
        internacion.save()
        registrar_auditoria(
            request, 'EDITAR', modelo='Internacion', objeto_id=internacion.id,
            descripcion=f"Cierre de internación de {internacion.mascota.nombre} "
                        f"({internacion.get_estado_display()}) (app móvil)",
            veterinaria=internacion.veterinaria,
        )
        return Response(InternacionSerializer(internacion).data)

    @action(detail=True, methods=['get'], url_path='informe-pdf')
    def informe_pdf(self, request, pk=None):
        internacion = self.get_object()
        return _pdf_de_la_web(request, vistas_web.descargar_informe_internacion_pdf, internacion_id=internacion.id)


class RecetaViewSet(TenantReadOnlyViewSet):
    queryset = Receta.objects.select_related('veterinario').prefetch_related('items').order_by('-fecha_emision')
    serializer_class = RecetaSerializer
    tenant_field = 'veterinaria'

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        receta = self.get_object()
        return _pdf_de_la_web(request, vistas_web.descargar_receta_digital_pdf, receta_id=receta.id)


class ProductoViewSet(TenantReadOnlyViewSet):
    queryset = Producto.objects.select_related('categoria').all().order_by('nombre')
    serializer_class = ProductoSerializer
    tenant_field = 'veterinaria'


class VeterinarioViewSet(TenantReadOnlyViewSet):
    queryset = Veterinario.objects.filter(activo=True).order_by('apellido', 'nombre')
    serializer_class = VeterinarioSerializer
    tenant_field = 'veterinaria'


class TurnoViewSet(TenantEditableViewSet):
    """Agenda: alta y edición de turnos desde la app, con las mismas reglas que TurnoForm
    (mascota y veterinario de la propia clínica). Cualquier usuario aprobado puede agendar,
    igual que en la web."""

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

    def perform_create(self, serializer):
        # El tenant del turno es el de la mascota (ya validada contra el del usuario).
        serializer.save(veterinaria=serializer.validated_data['mascota'].cliente.veterinaria)

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


class SolicitudTurnoWebViewSet(TenantReadOnlyViewSet):
    """Pedidos de turno hechos por clientes desde el Portal. ?pendientes=1 para los sin revisar."""

    queryset = SolicitudTurnoWeb.objects.all().order_by('-creado_el')
    serializer_class = SolicitudTurnoWebSerializer
    tenant_field = 'veterinaria'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('pendientes'):
            qs = qs.filter(estado='PENDIENTE')
        return qs

    @action(detail=True, methods=['post'])
    def estado(self, request, pk=None):
        """Igual que turnos.views.actualizar_estado_solicitud: contactado o descartado."""
        solicitud = self.get_object()
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in dict(SolicitudTurnoWeb.ESTADOS):
            raise ValidationError({'estado': 'El estado especificado no es válido.'})
        solicitud.estado = nuevo_estado
        solicitud.save(update_fields=['estado'])
        return Response(SolicitudTurnoWebSerializer(solicitud).data)


class VentaViewSet(TenantReadOnlyViewSet):
    queryset = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').all().order_by('-fecha_hora')
    serializer_class = VentaSerializer
    tenant_field = 'veterinaria'


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([EsUsuarioAprobadoDeLaVeterinaria])
def yo(request):
    """Datos del usuario logueado para la app: nombre, rol, clínica y qué puede hacer
    (la app oculta los botones que el rol o la configuración no permiten)."""
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
        'ia_habilitada': bool(settings.IA_RESUMENES_ENABLED and settings.ANTHROPIC_API_KEY),
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([EsUsuarioAprobadoDeLaVeterinaria])
def registrar_dispositivo(request):
    """La app avisa su token de Expo al iniciar sesión. Si el celular ya estaba registrado a
    nombre de otro usuario (equipo compartido), pasa a ser del que inició sesión ahora."""
    serializer = DispositivoPushSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    DispositivoPush.objects.update_or_create(
        token=serializer.validated_data['token'],
        defaults={
            'usuario': request.user,
            'plataforma': serializer.validated_data['plataforma'],
            'activo': True,
        },
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([EsUsuarioAprobadoDeLaVeterinaria])
def cerrar_sesion(request):
    """Revoca el token del dispositivo: al cerrar sesión, ese celular pierde el acceso y deja
    de recibir notificaciones (si la app manda su token de push)."""
    token_push = request.data.get('token_push')
    if token_push:
        DispositivoPush.objects.filter(token=token_push, usuario=request.user).update(activo=False)
    request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
