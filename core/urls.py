from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

# Importamos las vistas necesarias
from apps.usuarios.views import CustomLoginView
from apps.usuarios import views as usuario_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Vista Principal / Landing Page
    path('', usuario_views.landing_page, name='landing'),
    
    # Dashboard Operativo Centralizado
    path('dashboard/', include(('apps.dashboard.urls', 'dashboard'), namespace='dashboard')),
    
    # Autenticación (CustomLoginView incluye verificación de is_approved)
    path('login/', CustomLoginView.as_view(template_name='usuarios/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Recuperación de contraseña (staff y clientes del Portal por igual)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='usuarios/password_reset_form.html',
        email_template_name='usuarios/password_reset_email.html',
        subject_template_name='usuarios/password_reset_subject.txt',
        success_url='/password-reset/enviado/',
    ), name='password_reset'),
    path('password-reset/enviado/', auth_views.PasswordResetDoneView.as_view(
        template_name='usuarios/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/confirmar/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='usuarios/password_reset_confirm.html',
        success_url='/password-reset/completo/',
    ), name='password_reset_confirm'),
    path('password-reset/completo/', auth_views.PasswordResetCompleteView.as_view(
        template_name='usuarios/password_reset_complete.html',
    ), name='password_reset_complete'),

    # Apps del sistema con sus namespaces explícitos
    path('usuarios/', include(('apps.usuarios.urls', 'usuarios'), namespace='usuarios')),
    path('turnos/', include(('apps.turnos.urls', 'turnos'), namespace='turnos')),
    path('clientes/', include(('apps.clientes.urls', 'clientes'), namespace='clientes')),
    path('historia-clinica/', include(('apps.historia_clinica.urls', 'historia_clinica'), namespace='historia_clinica')),
    path('inventario/', include(('apps.inventario.urls', 'inventario'), namespace='inventario')),
    path('ventas/', include(('apps.ventas.urls', 'ventas'), namespace='ventas')),
    path('portal/', include(('apps.portal.urls', 'portal'), namespace='portal')),
]

# Servidor de archivos media en desarrollo (PDFs, ecografías, imágenes)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)