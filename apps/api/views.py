from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication

from apps.clientes.models import Cliente, Mascota
from apps.inventario.models import Producto
from apps.turnos.models import Turno
from apps.ventas.models import Venta

from .permissions import EsUsuarioAprobadoDeLaVeterinaria
from .serializers import (
    ClienteSerializer, MascotaSerializer, ProductoSerializer,
    TurnoSerializer, VentaSerializer,
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
    queryset = Mascota.objects.select_related('cliente').all().order_by('nombre')
    serializer_class = MascotaSerializer
    tenant_field = 'cliente__veterinaria'


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


class VentaViewSet(TenantReadOnlyViewSet):
    queryset = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').all().order_by('-fecha_hora')
    serializer_class = VentaSerializer
    tenant_field = 'veterinaria'
