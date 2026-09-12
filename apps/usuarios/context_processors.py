def suscripcion_activa(request):
    """Expone la suscripción de la veterinaria activa (si existe) a todos los templates,
    para poder mostrar el banner de vencimiento sin repetir la consulta en cada vista.
    Los tenants sin una Suscripcion asociada (ej. datos históricos/demo) simplemente no
    muestran el banner: la falta de registro de facturación nunca bloquea el acceso.

    También expone es_demo_publica, para avisar en cualquier pantalla que el usuario está
    en el entorno de demo compartido (ver usuarios.views.entrar_a_demo)."""
    veterinaria = getattr(request, 'veterinaria', None)
    if not veterinaria:
        return {'suscripcion': None, 'es_demo_publica': False}

    from .management.commands.seed_demo import DEMO_VET_NOMBRE

    suscripcion = getattr(veterinaria, 'suscripcion', None)
    return {'suscripcion': suscripcion, 'es_demo_publica': veterinaria.nombre == DEMO_VET_NOMBRE}
