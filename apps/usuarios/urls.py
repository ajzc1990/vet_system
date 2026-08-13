from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'usuarios'

urlpatterns = [
    # Dashboard Principal
    path('', views.dashboard, name='dashboard'),
    
    # Registro de Usuarios
    path('registro/', views.registro, name='registro'),
    
    # Autenticación Personalizada
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # Perfil / Configuración de la Veterinaria
    path('mi-veterinaria/', views.configurar_veterinaria, name='configurar_veterinaria'),
]