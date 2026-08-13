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

CSRF_TRUSTED_ORIGINS = [
    origin if origin.startswith(('http://', 'https://')) else f'http://{origin}'
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

    # Aplicaciones del proyecto VetSoft
    'apps.clientes',
    'apps.turnos',
    'apps.historia_clinica',
    'apps.inventario',
    'apps.usuarios',
    'apps.ventas',
    'apps.dashboard',
]

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
            'NAME': os.getenv('DB_NAME', 'vetsoft_db'),
            'USER': os.getenv('DB_USER', 'vetsoft_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'vetsoft_pass_2026'),
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

# Rutas de Autenticación
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/dashboard/'  # O la vista principal que prefieras
LOGOUT_REDIRECT_URL = 'landing'