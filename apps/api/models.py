from django.conf import settings
from django.db import models


class DispositivoPush(models.Model):
    """Celular donde un usuario del staff tiene la app instalada y aceptó notificaciones.
    El token lo da Expo (ExponentPushToken[...]); un mismo usuario puede tener varios
    dispositivos, y si el celular cambia de manos el token se reasigna al nuevo usuario."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dispositivos_push',
        verbose_name="Usuario",
    )
    token = models.CharField(max_length=255, unique=True, verbose_name="Token de Expo")
    plataforma = models.CharField(max_length=10, blank=True, verbose_name="Plataforma")
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Se desactiva al cerrar sesión o cuando Expo informa que la app se desinstaló.",
    )
    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dispositivo (notificaciones push)"
        verbose_name_plural = "Dispositivos (notificaciones push)"

    def __str__(self):
        return f"{self.usuario} · {self.plataforma or 'móvil'} ({'activo' if self.activo else 'inactivo'})"
