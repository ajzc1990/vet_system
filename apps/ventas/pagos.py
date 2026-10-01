import mercadopago


def mp_configurado_para(veterinaria):
    return bool(veterinaria and veterinaria.mp_access_token)


def get_sdk_para(veterinaria):
    return mercadopago.SDK(veterinaria.mp_access_token)


def crear_preferencia_cobro(cobro, request):
    """Crea una preferencia de pago (Checkout Pro) por un CobroQR, usando la cuenta
    de Mercado Pago propia de la veterinaria (no la de VeterSystem). El dinero cobrado
    va directo a esa cuenta. El external_reference y la notification_url llevan el id
    del CobroQR, para poder identificarlo al recibir la notificación de pago sin
    ambigüedad entre clínicas."""
    sdk = get_sdk_para(cobro.veterinaria)
    base_url = request.build_absolute_uri('/').rstrip('/')

    preference_data = {
        "items": [{
            "title": f"{cobro.producto.nombre} x{cobro.cantidad} ({cobro.veterinaria.nombre})",
            "quantity": 1,
            "unit_price": float(cobro.total),
            "currency_id": "ARS",
        }],
        "external_reference": str(cobro.id),
        "back_urls": {
            "success": f"{base_url}/ventas/cobro-qr/{cobro.id}/",
            "failure": f"{base_url}/ventas/cobro-qr/{cobro.id}/",
            "pending": f"{base_url}/ventas/cobro-qr/{cobro.id}/",
        },
        "auto_return": "approved",
        "notification_url": f"{base_url}/ventas/cobro-qr/{cobro.id}/webhook/",
    }

    resultado = sdk.preference().create(preference_data)
    return resultado.get("response", {})


def obtener_pago_para(veterinaria, payment_id):
    sdk = get_sdk_para(veterinaria)
    resultado = sdk.payment().get(payment_id)
    return resultado.get("response", {})
