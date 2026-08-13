from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
from .models import Mascota

@receiver(post_save, sender=Mascota)
def crear_historia_clinica(sender, instance, created, **kwargs):
    if created:
        try:
            HistoriaClinica = apps.get_model('historia_clinica', 'HistoriaClinica')
            HistoriaClinica.objects.create(mascota=instance)
        except LookupError:
            pass