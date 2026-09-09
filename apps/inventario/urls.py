from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    path('', views.lista_productos, name='lista_productos'),
    path('nuevo/', views.nuevo_producto, name='nuevo_producto'),
    path('<int:producto_id>/editar/', views.editar_producto, name='editar_producto'),
    path('<int:producto_id>/eliminar/', views.eliminar_producto, name='eliminar_producto'),
    path('<int:producto_id>/movimiento/', views.registrar_movimiento, name='registrar_movimiento'),
]