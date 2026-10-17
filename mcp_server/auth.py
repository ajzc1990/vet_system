"""Autenticación por token para el servidor MCP. Acepta dos tipos de token en el
header Authorization:

1. Un token de acceso OAuth (apps.usuarios.models.OAuthAccessToken), de corta
   duración, emitido por el flujo de /oauth/authorize + /oauth/token cuando
   alguien conecta Claude como "custom connector" desde la web.
2. El token fijo de siempre (rest_framework.authtoken.models.Token, el de "Mi
   Token de API"), para uso manual: MCP Inspector, Claude Desktop/Code con un
   header puesto a mano, etc.

En ambos casos se aplican las mismas reglas de habilitación que ya usa la API
REST (ver apps.usuarios.utils.usuario_habilitado_para_api), y corre en CADA
request (no solo al conectar), así que una cuenta a la que le revocaron el
acceso lo pierde al toque, sin esperar a que expire nada."""
from asgiref.sync import sync_to_async
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .context import usuario_actual, veterinaria_actual


@sync_to_async
def _resolver_token(token_key):
    from django.utils import timezone
    from rest_framework.authtoken.models import Token
    from apps.usuarios.models import OAuthAccessToken
    from apps.usuarios.utils import usuario_habilitado_para_api, veterinaria_del_usuario

    oauth_token = (
        OAuthAccessToken.objects.select_related('usuario__perfil__veterinaria')
        .filter(token=token_key).first()
    )
    if oauth_token:
        if oauth_token.esta_vencido:
            return None, None, "El token de acceso venció. Volvé a conectar el servidor en Claude."
        user = oauth_token.usuario
    else:
        try:
            user = Token.objects.select_related('user__perfil__veterinaria').get(key=token_key).user
        except Token.DoesNotExist:
            return None, None, "Token inválido."

    if not usuario_habilitado_para_api(user):
        return None, None, "Tu cuenta no está habilitada (sin aprobar, o te revocaron el acceso)."

    vet = veterinaria_del_usuario(user)
    if vet is None and not user.is_superuser:
        return None, None, "Tu usuario no tiene una veterinaria asignada."

    return user, vet, None


def _respuesta_401(request, mensaje):
    host = request.headers.get('host', 'vetersystem.com')
    resource_metadata = f"https://{host}/.well-known/oauth-protected-resource"
    return JSONResponse(
        {"error": mensaje},
        status_code=401,
        headers={"WWW-Authenticate": f'Bearer resource_metadata="{resource_metadata}"'},
    )


class AutenticacionPorTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        encabezado = request.headers.get('authorization', '')
        if not encabezado.lower().startswith('bearer '):
            return _respuesta_401(request, "Falta el token. Mandá el encabezado 'Authorization: Bearer <tu-token>'.")

        token_key = encabezado[7:].strip()
        if not token_key:
            return _respuesta_401(request, "El token está vacío.")

        user, vet, error = await _resolver_token(token_key)
        if error:
            return _respuesta_401(request, error)

        token_usuario = usuario_actual.set(user)
        token_vet = veterinaria_actual.set(vet)
        try:
            return await call_next(request)
        finally:
            usuario_actual.reset(token_usuario)
            veterinaria_actual.reset(token_vet)
