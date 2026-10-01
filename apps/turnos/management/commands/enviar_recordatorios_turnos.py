from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.turnos.models import Turno
from apps.turnos.whatsapp import (
    RecordatorioWhatsAppError,
    enviar_recordatorio_turno,
    whatsapp_configurado,
)


class Command(BaseCommand):
    help = (
        "Manda por WhatsApp (Twilio) un recordatorio a los clientes con turno para mañana, "
        "uno por cliente, evitando reenvíos con el flag recordatorio_whatsapp_enviado. "
        "Pensado para cron la tarde/noche anterior, ej. en el VPS: "
        "0 18 * * * cd /var/www/vet_system_new && docker compose exec -T web python manage.py enviar_recordatorios_turnos"
    )

    def handle(self, *args, **options):
        if not whatsapp_configurado():
            self.stdout.write("Los recordatorios de WhatsApp no están habilitados (WHATSAPP_RECORDATORIOS_ENABLED o credenciales de Twilio faltantes).")
            return

        mañana = timezone.localdate() + timedelta(days=1)
        turnos = Turno.objects.filter(
            fecha_hora__date=mañana,
            estado__in=['PENDIENTE', 'CONFIRMADO'],
            recordatorio_whatsapp_enviado=False,
        )

        enviados = 0
        fallidos = 0
        for turno in turnos:
            try:
                enviar_recordatorio_turno(turno)
            except RecordatorioWhatsAppError as e:
                fallidos += 1
                self.stdout.write(f"No se pudo avisar del turno #{turno.id}: {e}")
                continue
            turno.recordatorio_whatsapp_enviado = True
            turno.save(update_fields=['recordatorio_whatsapp_enviado'])
            enviados += 1

        self.stdout.write(f"Recordatorios enviados: {enviados}. Fallidos: {fallidos}.")
