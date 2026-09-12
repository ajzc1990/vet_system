import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Seguridad y Entorno
SECRET_KEY = os.getenv('SECRET_KEY', 'clave-secreta-desarrollo-local-12345')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

# Hosts permitidos y orígenes confiables para CSRF
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# En producción nginx sólo sirve HTTPS: el esquema tiene que matchear exacto con
# el que ve el navegador o Django rechaza el CSRF de cualquier POST (login, formularios).
_esquema_por_defecto = 'http://' if DEBUG else 'https://'
CSRF_TRUSTED_ORIGINS = [
    origin if origin.startswith(('http://', 'https://')) else f'{_esquema_por_defecto}{origin}'
    for origin in ALLOWED_HOSTS if origin and origin != '*'
]

# Apps instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework.authtoken',

    # Aplicaciones del proyecto VeterSystem
    'apps.clientes',
    'apps.turnos',
    'apps.historia_clinica',
    'apps.inventario',
    'apps.usuarios',
    'apps.ventas',
    'apps.dashboard',
    'apps.portal',
    'apps.api',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# Middlewares (Sin duplicados)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.usuarios.middleware.TenantMiddleware',  # TenantMiddleware unificado
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

# Configuración de Plantillas (Templates)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Carpeta global de plantillas
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.usuarios.context_processors.suscripcion_activa',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Configuración dinámica de Base de Datos (PostgreSQL vs SQLite)
USE_POSTGRES = os.getenv('USE_POSTGRES', 'False').lower() in ('true', '1', 't')

if USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'vetersystem_db'),
            'USER': os.getenv('DB_USER', 'vetersystem_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'vetersystem_pass_2026'),
            'HOST': os.getenv('DB_HOST', 'db'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Idioma y Zona Horaria
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Tucuman'
USE_I18N = True
USE_TZ = True

# Archivos Estáticos
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Obligatorio para produccion / collectstatic

# Configuración para archivos subidos por el usuario (Estudios, PDFs, Imágenes)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuración de Email (usado por el comando de recordatorios automáticos).
# En desarrollo se imprime por consola; en producción se activa SMTP configurando
# las variables de entorno EMAIL_HOST / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD.
if DEBUG or not os.getenv('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@vetersystem.local')

# Mercado Pago (cobro de suscripciones). Sin estas variables, el botón de pago
# muestra un aviso en vez de romper: se puede operar en modo de facturación manual.
MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')
MP_PUBLIC_KEY = os.getenv('MP_PUBLIC_KEY')

# Rutas de Autenticación
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/dashboard/'  # O la vista principal que prefieras
LOGOUT_REDIRECT_URL = 'landing'

# Seguridad para producción (detrás de Nginx con TLS terminado ahí, ver nginx/default.conf)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True