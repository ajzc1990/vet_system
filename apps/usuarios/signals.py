from datetime import timedelta

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from .audit import registrar_auditoria, _get_client_ip
from .models import PerfilUsuario, RegistroAuditoria, Veterinaria, Plan, Suscripcion


@receiver(user_logged_in)
def log_login_exitoso(sender, request, user, **kwargs):
    perfil = getattr(user, 'perfil', None)
    registrar_auditoria(
        request, 'LOGIN', modelo='User', objeto_id=user.pk,
        descripcion=f"Inicio de sesión: {user.username}",
        veterinaria=perfil.veterinaria if perfil else None,
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if not user:
        return
    perfil = getattr(user, 'perfil', None)
    registrar_auditoria(
        request, 'LOGOUT', modelo='User', objeto_id=user.pk,
        descripcion=f"Cierre de sesión: {user.username}",
        veterinaria=perfil.veterinaria if perfil else None,
    )


@receiver(user_login_failed)
def log_login_fallido(sender, credentials, request=None, **kwargs):
    username = credentials.get('username', 'desconocido')
    try:
        RegistroAuditoria.objects.create(
            usuario=None,
            accion='LOGIN_FALLIDO',
            modelo='User',
            objeto_id=username,
            descripcion=f"Intento de login fallido para el usuario '{username}'",
            ip_address=_get_client_ip(request),
        )
    except Exception:
        pass


@receiver(pre_save, sender=PerfilUsuario)
def log_aprobacion_usuario(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        anterior = PerfilUsuario.objects.get(pk=instance.pk)
    except PerfilUsuario.DoesNotExist:
        return

    if not anterior.is_approved and instance.is_approved:
        try:
            RegistroAuditoria.objects.create(
                veterinaria=instance.veterinaria,
                usuario=None,
                accion='APROBACION',
                modelo='PerfilUsuario',
                objeto_id=instance.pk,
                descripcion=f"Acceso aprobado para '{instance.user.username}' ({instance.get_rol_display()})",
            )
        except Exception:
            pass


@receiver(post_save, sender=Veterinaria)
def crear_suscripcion_de_prueba(sender, instance, created, **kwargs):
    """Al dar de alta una nueva veterinaria (nuevo tenant), se le asigna automáticamente
    un período de prueba sobre el plan de entrada más económico, si existe alguno cargado."""
    if not created:
        return
    if hasattr(instance, 'suscripcion'):
        return

    plan_entrada = Plan.objects.filter(activo=True).order_by('orden', 'precio_mensual').first()
    if not plan_entrada:
        return

    hoy = timezone.localdate()
    Suscripcion.objects.create(
        veterinaria=instance,
        plan=plan_entrada,
        estado='PRUEBA',
        fecha_inicio=hoy,
        fecha_vencimiento=hoy + timedelta(days=14),
    )
