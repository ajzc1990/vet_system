from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api'
    label = 'api'

    def ready(self):
        from . import signals  # noqa: F401 - registra los avisos push
