from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.usuarios.models import Veterinaria
from apps.turnos.models import Turno
from apps.historia_clinica.models import RegistroVacuna, RegistroDesparasitacion


class Command(BaseCommand):
    help = (
        "Envia un resumen diario por email a cada veterinaria con los turnos de mañana y los "
        "refuerzos de vacunas/desparasitaciones vencidos o próximos a vencer. "
        "Pensado para programarse una vez al día via cron / Programador de Tareas de Windows, ej.: "
        "0 8 * * * cd /ruta/al/proyecto && python manage.py enviar_recordatorios"
    )

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        manana = hoy + timedelta(days=1)
        limite_proximos = hoy + timedelta(days=7)

        veterinarias = Veterinaria.objects.filter(activo=True, email_contacto__isnull=False).exclude(email_contacto='')
        enviados = 0

        for vet in veterinarias:
            turnos_manana = Turno.objects.filter(
                veterinaria=vet, fecha_hora__date=manana, estado__in=['PENDIENTE', 'CONFIRMADO']
            ).select_related('mascota', 'mascota__cliente').order_by('fecha_hora')

            vacunas_vencidas = RegistroVacuna.objects.filter(
                veterinaria=vet, fecha_proxima_dosis__lt=hoy
            ).select_related('mascota', 'mascota__cliente')

            vacunas_proximas = RegistroVacuna.objects.filter(
                veterinaria=vet, fecha_proxima_dosis__gte=hoy, fecha_proxima_dosis__lte=limite_proximos
            ).select_related('mascota', 'mascota__cliente')

            despara_vencidas = RegistroDesparasitacion.objects.filter(
                veterinaria=vet, fecha_proxima_dosis__lt=hoy
            ).select_related('mascota', 'mascota__cliente')

            despara_proximas = RegistroDesparasitacion.objects.filter(
                veterinaria=vet, fecha_proxima_dosis__gte=hoy, fecha_proxima_dosis__lte=limite_proximos
            ).select_related('mascota', 'mascota__cliente')

            total = (
                turnos_manana.count() + vacunas_vencidas.count() + vacunas_proximas.count()
                + despara_vencidas.count() + despara_proximas.count()
            )
            if total == 0:
                continue

            lineas = [f"Resumen de recordatorios de {vet.nombre} - {hoy.strftime('%d/%m/%Y')}", ""]

            if turnos_manana:
                lineas.append(f"TURNOS DE MAÑANA ({manana.strftime('%d/%m/%Y')}):")
                for t in turnos_manana:
                    lineas.append(f"  - {t.fecha_hora.strftime('%H:%M')} hs: {t.mascota.nombre} ({t.mascota.cliente.nombre} {t.mascota.cliente.apellido})")
                lineas.append("")

            if vacunas_vencidas:
                lineas.append("VACUNAS VENCIDAS:")
                for v in vacunas_vencidas:
                    lineas.append(f"  - {v.mascota.nombre}: {v.nombre_vacuna} (venció {v.fecha_proxima_dosis.strftime('%d/%m/%Y')})")
                lineas.append("")

            if vacunas_proximas:
                lineas.append("VACUNAS POR VENCER (7 días):")
                for v in vacunas_proximas:
                    lineas.append(f"  - {v.mascota.nombre}: {v.nombre_vacuna} (vence {v.fecha_proxima_dosis.strftime('%d/%m/%Y')})")
                lineas.append("")

            if despara_vencidas:
                lineas.append("DESPARASITACIONES VENCIDAS:")
                for d in despara_vencidas:
                    lineas.append(f"  - {d.mascota.nombre}: {d.producto} (venció {d.fecha_proxima_dosis.strftime('%d/%m/%Y')})")
                lineas.append("")

            if despara_proximas:
                lineas.append("DESPARASITACIONES POR VENCER (7 días):")
                for d in despara_proximas:
                    lineas.append(f"  - {d.mascota.nombre}: {d.producto} (vence {d.fecha_proxima_dosis.strftime('%d/%m/%Y')})")

            send_mail(
                subject=f"[VeterSystem] Recordatorios de hoy - {vet.nombre}",
                message="\n".join(lineas),
                from_email=None,
                recipient_list=[vet.email_contacto],
                fail_silently=True,
            )
            enviados += 1

        self.stdout.write(self.style.SUCCESS(f"Recordatorios enviados a {enviados} veterinaria(s)."))
