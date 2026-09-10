from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.portal_home, name='home'),
    path('mascota/<int:mascota_id>/', views.portal_mascota_detalle, name='mascota_detalle'),
    path('turnos/', views.portal_turnos, name='turnos'),
]
