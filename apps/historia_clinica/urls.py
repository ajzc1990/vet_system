from django.urls import path
from . import views

app_name = 'historia_clinica'

urlpatterns = [
    # Vista principal del expediente
    path('mascota/<int:mascota_id>/', views.expediente_mascota, name='expediente_mascota'),
    
    # Consultas Médicas
    path('mascota/<int:mascota_id>/nueva-consulta/', views.nueva_consulta, name='nueva_consulta'),
    path('consulta/<int:consulta_id>/receta-pdf/', views.descargar_receta_pdf, name='descargar_receta_pdf'),
    
    # Vacunas y Desparasitaciones
    path('mascota/<int:mascota_id>/registrar-vacuna/', views.registrar_vacuna, name='registrar_vacuna'),
    path('mascota/<int:mascota_id>/registrar-desparasitacion/', views.registrar_desparasitacion, name='registrar_desparasitacion'),
    path('mascota/<int:mascota_id>/carnet-vacunas-pdf/', views.descargar_carnet_vacunas_pdf, name='descargar_carnet_vacunas_pdf'),
    
    # Estudios Médicos / Adjuntos
    path('mascota/<int:mascota_id>/subir-estudio/', views.subir_estudio, name='subir_estudio'),
    path('estudio/<int:estudio_id>/eliminar/', views.eliminar_estudio, name='eliminar_estudio'),
]