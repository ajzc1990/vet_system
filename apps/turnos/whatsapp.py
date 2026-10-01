from django.conf import settings

from apps.clientes.models import formatear_telefono_whatsapp


class RecordatoriosDeshabilitados(Exception):
    """Los recordatorios de turnos por WhatsApp no están habilitados en este entorno."""


class RecordatorioWhatsAppError(Exception):
    """Falló el envío del recordatorio (error de red, de la API, etc.)."""


def whatsapp_configurado():
    return bool(
        settings.WHATSAPP_RECORDATORIOS_ENABLED
        and settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_WHATSAPP_FROM
    )


def enviar_recordatorio_turno(turno):
    """Manda por WhatsApp (vía Twilio) el recordatorio de un turno al tutor de la mascota."""
    if not whatsapp_configurado():
        raise RecordatoriosDeshabilitados("Los recordatorios de WhatsApp no están habilitados.")

    if not turno.mascota_id or not turno.mascota.cliente or not turno.mascota.cliente.telefono:
        raise RecordatorioWhatsAppError("El cliente no tiene teléfono cargado.")

    cliente = turno.mascota.cliente
    telefono = formatear_telefono_whatsapp(cliente.telefono)
    if not telefono:
        raise RecordatorioWhatsAppError("El cliente no tiene teléfono cargado.")
    # La API de WhatsApp Business (a diferencia de los links wa.me) espera el número
    # argentino SIN el 9 de celular; si no se lo sacamos, Twilio no reconoce al destinatario.
    if telefono.startswith("549"):
        telefono = "54" + telefono[3:]

    clinica = turno.veterinaria.nombre if turno.veterinaria else "la clínica"
    mensaje = (
        f"Hola {cliente.nombre}! Te escribimos de {clinica} para recordarte el turno de "
        f"{turno.mascota.nombre} mañana {turno.fecha_hora.strftime('%d/%m/%Y')} a las "
        f"{turno.fecha_hora.strftime('%H:%M')} hs. ¡Te esperamos!"
    )

    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    try:
        client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:+{telefono}",
            body=mensaje,
        )
    except TwilioRestException as e:
        raise RecordatorioWhatsAppError(str(e)) from e
