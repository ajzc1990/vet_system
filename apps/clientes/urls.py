from django.urls import path
from . import views
from apps.historia_clinica import views as historia_views

app_name = 'clientes'

urlpatterns = [
    # Clientes
    path('', views.lista_clientes, name='lista_clientes'),
    path('nuevo/', views.crear_cliente, name='crear_cliente'),
    path('<int:cliente_id>/', views.detalle_cliente, name='detalle_cliente'),
    path('<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),

    # Mascotas
    path('<int:cliente_id>/mascotas/nueva/', views.agregar_mascota, name='agregar_mascota'),
    path('mascotas/<int:mascota_id>/editar/', views.editar_mascota, name='editar_mascota'),

    # Historia Clínica
    path('mascotas/<int:mascota_id>/historia-clinica/', views.detalle_historia_clinica, name='detalle_historia_clinica'),

    # Consultas
    path('consultas/<int:consulta_id>/editar/', views.editar_consulta, name='editar_consulta'),
    path('consultas/<int:consulta_id>/eliminar/', views.eliminar_consulta, name='eliminar_consulta'),

    # Vacunas y Desparasitaciones (Modales)
    path('mascotas/<int:mascota_id>/vacunas/agregar/', views.agregar_vacuna, name='agregar_vacuna'),
    path('vacunas/<int:vacuna_id>/eliminar/', views.eliminar_vacuna, name='eliminar_vacuna'),

    path('mascotas/<int:mascota_id>/desparasitaciones/agregar/', views.agregar_desparasitacion, name='agregar_desparasitacion'),
    path('desparasitaciones/<int:desparasitacion_id>/eliminar/', views.eliminar_desparasitacion, name='eliminar_desparasitacion'),

    # Subida y Eliminación de Estudios (Reutilizando views de historia_clinica de forma directa)
    path('mascotas/<int:mascota_id>/subir-estudio/', historia_views.subir_estudio, name='subir_estudio'),
    path('estudio/<int:estudio_id>/eliminar/', historia_views.eliminar_estudio, name='eliminar_estudio'),
]