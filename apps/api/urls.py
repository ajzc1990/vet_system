from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .auth import obtener_token
from .views import (
    cerrar_sesion, yo, ClienteViewSet, MascotaViewSet, ProductoViewSet, TurnoViewSet, VentaViewSet,
)

router = DefaultRouter()
router.register('clientes', ClienteViewSet, basename='cliente')
router.register('mascotas', MascotaViewSet, basename='mascota')
router.register('productos', ProductoViewSet, basename='producto')
router.register('turnos', TurnoViewSet, basename='turno')
router.register('ventas', VentaViewSet, basename='venta')

urlpatterns = [
    path('token/', obtener_token, name='obtener_token'),
    path('yo/', yo, name='yo'),
    path('logout/', cerrar_sesion, name='cerrar_sesion'),
    path('', include(router.urls)),
]
