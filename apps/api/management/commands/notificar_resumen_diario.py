from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.api.models import DispositivoPush
from apps.api.push import enviar_push, usuarios_de_la_veterinaria
from apps.historia_clinica.models import Internacion, RegistroVacuna
from apps.turnos.models import SolicitudTurnoWeb, Turno
from apps.usuarios.models import Veterinaria


def _plural(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


class Command(BaseCommand):
    help = (
        "Manda a la app móvil del staff un push con el resumen del día: turnos de hoy, "
        "internados, solicitudes web pendientes y vacunas que vencen esta semana. "
        "Pensado para cron a primera hora, ej. en el VPS: "
        "0 8 * * * cd /var/www/vet_system_new && docker compose exec -T web python manage.py notificar_resumen_diario"
    )

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        en_una_semana = hoy + timedelta(days=7)

        # Sólo las clínicas con al menos un celular registrado: el resto no tiene a quién avisar.
        veterinarias = Veterinaria.objects.filter(
            activo=True,
            pk__in=DispositivoPush.objects.filter(activo=True).values('usuario__perfil__veterinaria'),
        )

        enviadas = 0
        for vet in veterinarias:
            turnos = Turno.objects.filter(
                veterinaria=vet, fecha_hora__date=hoy, estado__in=['PENDIENTE', 'CONFIRMADO'],
            ).count()
            internados = Internacion.objects.filter(veterinaria=vet, estado='INTERNADO').count()
            solicitudes = SolicitudTurnoWeb.objects.filter(veterinaria=vet, estado='PENDIENTE').count()
            vacunas = RegistroVacuna.objects.filter(
                veterinaria=vet, fecha_proxima_dosis__gte=hoy, fecha_proxima_dosis__lte=en_una_semana,
            ).count()

            partes = [_plural(turnos, 'turno', 'turnos') + ' hoy']
            if internados:
                partes.append(_plural(internados, 'internado', 'internados'))
            if solicitudes:
                partes.append(_plural(solicitudes, 'solicitud web pendiente', 'solicitudes web pendientes'))
            if vacunas:
                partes.append(_plural(vacunas, 'vacuna vence', 'vacunas vencen') + ' esta semana')

            if not (turnos or internados or solicitudes or vacunas):
                continue

            enviadas += enviar_push(
                usuarios_de_la_veterinaria(vet),
                titulo=f"Buen día · {vet.nombre}",
                cuerpo=" · ".join(partes) + ".",
                data={'url': '/'},
            )

        self.stdout.write(f"Resumen diario enviado a {enviadas} dispositivo(s).")
