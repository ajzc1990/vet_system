# core/managers.py
from django.db import models

class TenantManager(models.Manager):
    """Manager que restringe las búsquedas según la veterinaria especificada."""
    def for_tenant(self, veterinaria):
        if veterinaria is None: # Si es superusuario global
            return self.get_queryset()
        return self.get_queryset().filter(veterinaria=veterinaria)