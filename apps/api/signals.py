from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_date

from apps.turnos.models import SolicitudTurnoWeb

from .push import enviar_push_en_segundo_plano, usuarios_de_la_veterinaria


@receiver(post_save, sender=SolicitudTurnoWeb)
def avisar_nueva_solicitud_de_turno(sender, instance, created, **kwargs):
    """Push al staff de la clínica cuando un cliente pide un turno desde el Portal."""
    if not created:
        return
    # La vista pública guarda la fecha tal como llega del formulario (texto AAAA-MM-DD).
    fecha = instance.fecha_deseada
    if isinstance(fecha, str):
        fecha = parse_date(fecha)
    cuando = f" para el {fecha.strftime('%d/%m')}" if fecha else ""

    enviar_push_en_segundo_plano(
        usuarios_de_la_veterinaria(instance.veterinaria),
        titulo="Nueva solicitud de turno",
        cuerpo=f"{instance.nombre_tutor} pidió turno para {instance.nombre_mascota}{cuando}.",
        data={'url': '/solicitudes'},
    )
