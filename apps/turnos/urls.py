# apps/turnos/urls.py
from django.urls import path
from . import views

app_name = 'turnos'

urlpatterns = [
    # Agenda / Listado de turnos
    path('', views.lista_turnos, name='lista_turnos'),
    path('agenda/', views.lista_turnos, name='agenda_diaria'),
    
    # Gestión de turnos
    path('nuevo/', views.crear_turno, name='nuevo_turno'),
    path('<int:pk>/editar/', views.editar_turno, name='editar_turno'),
    path('<int:pk>/cancelar/', views.cancelar_turno, name='cancelar_turno'),
    path('<int:pk>/atender/', views.atender_turno, name='atender_turno'),  # <--- RUTA NUEVA
    
    # Cambio rápido de estado desde la interfaz
    path('<int:pk>/estado/<str:nuevo_estado>/', views.cambiar_estado_turno, name='cambiar_estado'),

    # Reserva de Turnos Online (Público)
    path('reservar/<int:veterinaria_id>/', views.solicitar_turno_publico, name='solicitar_turno_publico'),
    path('solicitudes/', views.lista_solicitudes_turno, name='lista_solicitudes_turno'),
    path('solicitudes/<int:solicitud_id>/estado/<str:nuevo_estado>/', views.actualizar_estado_solicitud, name='actualizar_estado_solicitud'),
]