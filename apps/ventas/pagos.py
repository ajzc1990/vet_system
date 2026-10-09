import mercadopago
import requests

MP_API_BASE = "https://api.mercadopago.com"


def mp_configurado_para(veterinaria):
    return bool(veterinaria and veterinaria.mp_access_token)


def get_sdk_para(veterinaria):
    return mercadopago.SDK(veterinaria.mp_access_token)


def _headers_para(veterinaria):
    return {
        "Authorization": f"Bearer {veterinaria.mp_access_token}",
        "Content-Type": "application/json",
    }


class MercadoPagoApiError(Exception):
    """La API de Mercado Pago devolvió un error al crear la tienda/punto de venta/orden."""


def _post(veterinaria, path, payload, idempotency_key=None):
    headers = _headers_para(veterinaria)
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    resp = requests.post(f"{MP_API_BASE}{path}", headers=headers, json=payload, timeout=15)
    if resp.status_code >= 400:
        raise MercadoPagoApiError(f"{resp.status_code} en {path}: {resp.text[:300]}")
    return resp.json()


def _get(veterinaria, path):
    resp = requests.get(f"{MP_API_BASE}{path}", headers=_headers_para(veterinaria), timeout=15)
    if resp.status_code >= 400:
        raise MercadoPagoApiError(f"{resp.status_code} en {path}: {resp.text[:300]}")
    return resp.json()


def asegurar_pos_para(veterinaria):
    """Da de alta (una sola vez) la Tienda y el Punto de Venta de esta clínica en su
    propia cuenta de Mercado Pago, necesarios para generar un QR real escaneable (API
    de Orders). Si ya están creados, no hace nada y devuelve el external_id del POS."""
    if veterinaria.mp_pos_external_id:
        return veterinaria.mp_pos_external_id

    me = _get(veterinaria, "/users/me")
    user_id = me["id"]

    external_store_id = f"VETSYS{veterinaria.id}"
    direccion = (veterinaria.direccion or veterinaria.nombre).strip().replace("\n", ", ")
    tienda = _post(
        veterinaria, f"/users/{user_id}/stores",
        {
            "name": veterinaria.nombre[:60],
            "external_id": external_store_id,
            # state_name tiene que ser una provincia argentina válida para la API (no
            # acepta "-" ni texto libre). Por ahora todas las clínicas son de Tucumán;
            # si en algún momento hay una clínica de otra provincia, esto necesita un
            # campo propio en Veterinaria en vez de este valor fijo.
            "location": {
                "street_name": direccion[:100] or "-",
                "street_number": "S/N",
                "city_name": "San Miguel de Tucumán",
                "state_name": "Tucumán",
                "latitude": -26.8083,
                "longitude": -65.2176,
            },
        },
    )
    store_id = tienda["id"]

    external_pos_id = f"VETSYSPOS{veterinaria.id}"
    _post(
        veterinaria, "/pos",
        {
            "name": f"Caja {veterinaria.nombre}"[:40],
            "fixed_amount": False,
            "store_id": store_id,
            "external_id": external_pos_id,
        },
    )

    veterinaria.mp_user_id = str(user_id)
    veterinaria.mp_store_id = str(store_id)
    veterinaria.mp_pos_external_id = external_pos_id
    veterinaria.save(update_fields=['mp_user_id', 'mp_store_id', 'mp_pos_external_id'])
    return external_pos_id


def crear_orden_qr(cobro):
    """Crea una Orden de tipo QR (API de Orders) para un CobroQR puntual y devuelve el
    string qr_data que hay que convertir en imagen de QR para que el cliente escanee."""
    import uuid
    external_pos_id = asegurar_pos_para(cobro.veterinaria)
    total = f"{cobro.total:.2f}"
    payload = {
        "type": "qr",
        "total_amount": total,
        "description": f"{cobro.producto.nombre} x{cobro.cantidad}"[:250],
        "external_reference": f"cobroqr-{cobro.id}",
        "config": {"qr": {"external_pos_id": external_pos_id, "mode": "dynamic"}},
        "transactions": {"payments": [{"amount": total}]},
        "items": [{
            "title": cobro.producto.nombre[:256],
            "unit_price": total,
            "quantity": 1,
            "unit_measure": "unit",
        }],
    }
    orden = _post(cobro.veterinaria, "/v1/orders", payload, idempotency_key=str(uuid.uuid4()))
    qr_data = (orden.get("type_response") or {}).get("qr_data")
    return orden.get("id"), qr_data


def obtener_orden(veterinaria, order_id):
    return _get(veterinaria, f"/v1/orders/{order_id}")


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
