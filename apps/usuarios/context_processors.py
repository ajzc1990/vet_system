def suscripcion_activa(request):
    """Expone la suscripción de la veterinaria activa (si existe) a todos los templates,
    para poder mostrar el banner de vencimiento sin repetir la consulta en cada vista.
    Los tenants sin una Suscripcion asociada (ej. datos históricos/demo) simplemente no
    muestran el banner: la falta de registro de facturación nunca bloquea el acceso."""
    veterinaria = getattr(request, 'veterinaria', None)
    if not veterinaria:
        return {'suscripcion': None}

    suscripcion = getattr(veterinaria, 'suscripcion', None)
    return {'suscripcion': suscripcion}
