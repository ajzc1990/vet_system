# apps/ventas/urls.py
from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    # Listado y Punto de Venta
    path('', views.lista_ventas, name='lista_ventas'),
    path('exportar-csv/', views.exportar_ventas_csv, name='exportar_ventas_csv'),
    path('nueva/', views.registrar_venta, name='registrar_venta'),
    
    # Gestión de Caja Diaria
    path('caja/abrir/', views.abrir_caja, name='abrir_caja'),
    path('caja/<int:caja_id>/cerrar/', views.cerrar_caja, name='cerrar_caja'),

    # NUEVO: Reporte de Control de Cajas y Arqueos
    path('cajas/reporte/', views.reporte_cajas, name='reporte_cajas'),
    
    # Comprobante / Ticket PDF
    path('<int:venta_id>/ticket/', views.descargar_ticket_pdf, name='descargar_ticket_pdf'),
]