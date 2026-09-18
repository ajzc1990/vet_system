# apps/compras/urls.py
from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    # Compras
    path('', views.lista_compras, name='lista_compras'),
    path('exportar-csv/', views.exportar_compras_csv, name='exportar_compras_csv'),
    path('sugerencias/', views.sugerencias_compra, name='sugerencias'),
    path('nueva/', views.registrar_compra, name='registrar_compra'),
    path('<int:compra_id>/', views.detalle_compra, name='detalle_compra'),

    # Proveedores
    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
    path('proveedores/nuevo/', views.nuevo_proveedor, name='nuevo_proveedor'),
    path('proveedores/<int:proveedor_id>/editar/', views.editar_proveedor, name='editar_proveedor'),
]
