from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

# Importamos las vistas necesarias
from apps.usuarios.views import CustomLoginView
from apps.usuarios import views as usuario_views
from apps.usuarios import oauth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Vista Principal / Landing Page
    path('', usuario_views.landing_page, name='landing'),

    # Demo pública de un clic (loguea directo como el admin de la veterinaria demo)
    path('demo/', usuario_views.entrar_a_demo, name='entrar_a_demo'),

    # Autoregistro público: crea Veterinaria + usuario ADMIN al instante, sin aprobación
    path('empezar/', usuario_views.registro_veterinaria_publico, name='registro_veterinaria_publico'),

    # Páginas legales
    path('terminos/', TemplateView.as_view(template_name='legal/terminos.html'), name='terminos'),
    path('privacidad/', TemplateView.as_view(template_name='legal/privacidad.html'), name='privacidad'),

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

    # Cambio de contraseña estando logueado (staff y clientes del Portal por igual)
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='usuarios/password_change_form.html',
    ), name='password_change'),
    path('password-change/hecho/', auth_views.PasswordChangeDoneView.as_view(
        template_name='usuarios/password_change_done.html',
    ), name='password_change_done'),

    # Apps del sistema con sus namespaces explícitos
    path('usuarios/', include(('apps.usuarios.urls', 'usuarios'), namespace='usuarios')),
    path('turnos/', include(('apps.turnos.urls', 'turnos'), namespace='turnos')),
    path('clientes/', include(('apps.clientes.urls', 'clientes'), namespace='clientes')),
    path('historia-clinica/', include(('apps.historia_clinica.urls', 'historia_clinica'), namespace='historia_clinica')),
    path('inventario/', include(('apps.inventario.urls', 'inventario'), namespace='inventario')),
    path('compras/', include(('apps.compras.urls', 'compras'), namespace='compras')),
    path('ventas/', include(('apps.ventas.urls', 'ventas'), namespace='ventas')),
    path('portal/', include(('apps.portal.urls', 'portal'), namespace='portal')),

    # API REST (lectura) para integraciones externas
    path('api/', include(('apps.api.urls', 'api'), namespace='api')),

    # OAuth para conectores MCP (ej. Claude.ai) — rutas fijas que exige la spec.
    path('.well-known/oauth-protected-resource', oauth_views.protected_resource_metadata, name='oauth_protected_resource'),
    path('.well-known/oauth-protected-resource/mcp', oauth_views.protected_resource_metadata, name='oauth_protected_resource_mcp'),
    path('.well-known/oauth-authorization-server', oauth_views.authorization_server_metadata, name='oauth_authorization_server'),
    path('oauth/register', oauth_views.oauth_register, name='oauth_register'),
    path('oauth/authorize', oauth_views.oauth_authorize, name='oauth_authorize'),
    path('oauth/token', oauth_views.oauth_token, name='oauth_token'),
]

# Servidor de archivos media en desarrollo (PDFs, ecografías, imágenes)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)