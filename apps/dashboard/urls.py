from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_principal, name='index'),
    path('recordatorios/', views.centro_recordatorios, name='centro_recordatorios'),
]