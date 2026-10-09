# apps/ventas/urls.py
from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    # Listado y Punto de Venta
    path('', views.lista_ventas, name='lista_ventas'),
    path('exportar-csv/', views.exportar_ventas_csv, name='exportar_ventas_csv'),
    path('nueva/', views.registrar_venta, name='registrar_venta'),

    # Cobro por link de pago (Mercado Pago)
    path('cobro-qr/<int:cobro_id>/', views.ver_cobro_qr, name='ver_cobro_qr'),
    path('cobro-qr/<int:cobro_id>/webhook/', views.webhook_cobro_qr, name='webhook_cobro_qr'),

    # Cobro con QR real en el local (API de Orders de Mercado Pago)
    path('cobro-qr-local/<int:cobro_id>/', views.ver_cobro_qr_local, name='ver_cobro_qr_local'),
    path('cobro-qr-local/<int:cobro_id>/estado/', views.estado_cobro_qr_local, name='estado_cobro_qr_local'),

    # Gestión de Caja Diaria
    path('caja/abrir/', views.abrir_caja, name='abrir_caja'),
    path('caja/<int:caja_id>/cerrar/', views.cerrar_caja, name='cerrar_caja'),
    path('caja/gasto/', views.registrar_gasto, name='registrar_gasto'),

    # NUEVO: Reporte de Control de Cajas y Arqueos
    path('cajas/reporte/', views.reporte_cajas, name='reporte_cajas'),
    
    # Comprobante / Ticket PDF
    path('<int:venta_id>/ticket/', views.descargar_ticket_pdf, name='descargar_ticket_pdf'),
]