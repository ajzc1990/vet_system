"""Deja el ORM de Django listo para usarse desde un proceso que no es manage.py
(este servidor corre como su propio proceso async, separado de Gunicorn).
Se importa una sola vez, antes que cualquier modelo, desde server.py."""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
