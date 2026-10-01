from django import template

from apps.clientes.models import formatear_telefono_whatsapp

register = template.Library()


@register.filter(name='wa_numero')
def wa_numero(telefono):
    """Normaliza un teléfono al formato que espera wa.me (ver formatear_telefono_whatsapp)."""
    return formatear_telefono_whatsapp(telefono)
