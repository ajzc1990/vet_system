from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .auth import obtener_token
from .views import ClienteViewSet, MascotaViewSet, ProductoViewSet, TurnoViewSet, VentaViewSet

router = DefaultRouter()
router.register('clientes', ClienteViewSet, basename='cliente')
router.register('mascotas', MascotaViewSet, basename='mascota')
router.register('productos', ProductoViewSet, basename='producto')
router.register('turnos', TurnoViewSet, basename='turno')
router.register('ventas', VentaViewSet, basename='venta')

urlpatterns = [
    path('token/', obtener_token, name='obtener_token'),
    path('', include(router.urls)),
]
