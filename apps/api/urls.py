from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .auth import obtener_token
from .views import (
    cerrar_sesion, registrar_dispositivo, yo,
    ClienteViewSet, InternacionViewSet, MascotaViewSet, ProductoViewSet, RecetaViewSet,
    SolicitudTurnoWebViewSet, TurnoViewSet, VentaViewSet, VeterinarioViewSet,
)

router = DefaultRouter()
router.register('clientes', ClienteViewSet, basename='cliente')
router.register('mascotas', MascotaViewSet, basename='mascota')
router.register('productos', ProductoViewSet, basename='producto')
router.register('turnos', TurnoViewSet, basename='turno')
router.register('ventas', VentaViewSet, basename='venta')
router.register('veterinarios', VeterinarioViewSet, basename='veterinario')
router.register('internaciones', InternacionViewSet, basename='internacion')
router.register('recetas', RecetaViewSet, basename='receta')
router.register('solicitudes', SolicitudTurnoWebViewSet, basename='solicitud')

urlpatterns = [
    path('token/', obtener_token, name='obtener_token'),
    path('yo/', yo, name='yo'),
    path('logout/', cerrar_sesion, name='cerrar_sesion'),
    path('dispositivos/', registrar_dispositivo, name='registrar_dispositivo'),
    path('', include(router.urls)),
]
