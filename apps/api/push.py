"""Envío de notificaciones push a la app móvil a través del servicio de Expo.

Nunca levanta excepciones hacia quien lo llama: una notificación que no sale no puede
romper el guardado de un turno ni el formulario público de reservas.
"""
import logging
import threading

import requests
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import DispositivoPush

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
LOTE_MAXIMO = 100  # límite de mensajes por request del servicio de Expo


def usuarios_de_la_veterinaria(veterinaria):
    """Staff aprobado de una clínica (todos los roles)."""
    return get_user_model().objects.filter(
        perfil__veterinaria=veterinaria, perfil__is_approved=True, is_active=True,
    )


def enviar_push(usuarios, titulo, cuerpo, data=None):
    """Envía la notificación a todos los dispositivos activos de `usuarios`.
    Devuelve cuántos mensajes aceptó Expo."""
    dispositivos = list(DispositivoPush.objects.filter(usuario__in=usuarios, activo=True))
    if not dispositivos:
        return 0

    aceptados = 0
    for i in range(0, len(dispositivos), LOTE_MAXIMO):
        lote = dispositivos[i:i + LOTE_MAXIMO]
        mensajes = [
            {
                'to': d.token,
                'title': titulo,
                'body': cuerpo,
                'data': data or {},
                'sound': 'default',
                'channelId': 'default',
                'priority': 'high',
            }
            for d in lote
        ]
        try:
            respuesta = requests.post(
                EXPO_PUSH_URL,
                json=mensajes,
                headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
                timeout=10,
            )
            respuesta.raise_for_status()
            tickets = respuesta.json().get('data', [])
        except (requests.RequestException, ValueError) as e:
            logger.warning("No se pudieron enviar notificaciones push: %s", e)
            continue

        for dispositivo, ticket in zip(lote, tickets):
            if ticket.get('status') == 'ok':
                aceptados += 1
                continue
            error = (ticket.get('details') or {}).get('error')
            if error == 'DeviceNotRegistered':
                # La app se desinstaló o el token venció: dejar de mandarle.
                DispositivoPush.objects.filter(pk=dispositivo.pk).update(activo=False)
            else:
                # Ej. InvalidCredentials si falta o venció la clave de Firebase en EAS.
                logger.warning(
                    "Expo rechazó un push para %s: %s (%s)",
                    dispositivo.usuario, ticket.get('message'), error,
                )
    return aceptados


def enviar_push_en_segundo_plano(usuarios, titulo, cuerpo, data=None):
    """Para disparar desde una vista o señal sin demorar la respuesta: espera a que la
    transacción confirme (así no se avisa de algo que después se revierte) y manda en un
    hilo aparte."""
    ids = list(usuarios.values_list('pk', flat=True))

    def _enviar():
        try:
            enviar_push(get_user_model().objects.filter(pk__in=ids), titulo, cuerpo, data)
        except Exception:  # noqa: BLE001 - nunca romper el flujo principal
            logger.exception("Error inesperado enviando notificaciones push")

    transaction.on_commit(lambda: threading.Thread(target=_enviar, daemon=True).start())
