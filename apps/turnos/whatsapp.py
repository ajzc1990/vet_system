import json

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
        and settings.TWILIO_CONTENT_SID_RECORDATORIO
    )


def enviar_recordatorio_turno(turno):
    """Manda por WhatsApp (vía Twilio) el recordatorio de un turno al tutor de la mascota.

    Usa una Content Template (Twilio ya no acepta texto libre por WhatsApp) con 5
    variables: {{1}} nombre del tutor, {{2}} clínica, {{3}} mascota, {{4}} fecha,
    {{5}} hora. El número va con el formato completo de wa.me (54 + 9 + área + número):
    es el que efectivamente reconoce la API, confirmado a mano contra el sandbox real."""
    if not whatsapp_configurado():
        raise RecordatoriosDeshabilitados("Los recordatorios de WhatsApp no están habilitados.")

    if not turno.mascota_id or not turno.mascota.cliente or not turno.mascota.cliente.telefono:
        raise RecordatorioWhatsAppError("El cliente no tiene teléfono cargado.")

    cliente = turno.mascota.cliente
    telefono = formatear_telefono_whatsapp(cliente.telefono)
    if not telefono:
        raise RecordatorioWhatsAppError("El cliente no tiene teléfono cargado.")

    clinica = turno.veterinaria.nombre if turno.veterinaria else "la clínica"

    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    try:
        client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:+{telefono}",
            content_sid=settings.TWILIO_CONTENT_SID_RECORDATORIO,
            content_variables=json.dumps({
                '1': cliente.nombre,
                '2': clinica,
                '3': turno.mascota.nombre,
                '4': turno.fecha_hora.strftime('%d/%m/%Y'),
                '5': turno.fecha_hora.strftime('%H:%M'),
            }),
        )
    except TwilioRestException as e:
        raise RecordatorioWhatsAppError(str(e)) from e
