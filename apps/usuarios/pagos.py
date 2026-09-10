import mercadopago
from django.conf import settings


def mp_configurado():
    return bool(settings.MP_ACCESS_TOKEN)


def get_sdk():
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def crear_preferencia_pago(suscripcion, request):
    """Crea una preferencia de pago (Checkout Pro) por el precio mensual del plan
    contratado. El external_reference lleva el id de la Suscripcion para poder
    identificarla al recibir la notificación de pago."""
    sdk = get_sdk()
    base_url = request.build_absolute_uri('/').rstrip('/')

    preference_data = {
        "items": [{
            "title": f"Suscripción VeterSystem - Plan {suscripcion.plan.nombre} ({suscripcion.veterinaria.nombre})",
            "quantity": 1,
            "unit_price": float(suscripcion.plan.precio_mensual),
            "currency_id": "ARS",
        }],
        "external_reference": str(suscripcion.id),
        "back_urls": {
            "success": f"{base_url}/usuarios/mi-suscripcion/?pago=exitoso",
            "failure": f"{base_url}/usuarios/mi-suscripcion/?pago=fallido",
            "pending": f"{base_url}/usuarios/mi-suscripcion/?pago=pendiente",
        },
        "auto_return": "approved",
        "notification_url": f"{base_url}/usuarios/pagos/webhook/",
    }

    resultado = sdk.preference().create(preference_data)
    return resultado.get("response", {})


def obtener_pago(payment_id):
    sdk = get_sdk()
    resultado = sdk.payment().get(payment_id)
    return resultado.get("response", {})
