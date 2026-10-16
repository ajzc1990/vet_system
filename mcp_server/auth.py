"""Autenticación por token para el servidor MCP: reusa el mismo modelo de Token
(rest_framework.authtoken) y las mismas reglas de habilitación que ya usa la API
REST y la app móvil (ver apps.usuarios.utils.usuario_habilitado_para_api). No es
OAuth ni nada nuevo: un token por usuario, igual que siempre.

Corre en CADA request al endpoint MCP (no solo al conectar), así que una cuenta a
la que le revocaron el acceso pierde el acceso al toque, sin esperar a que expire
una sesión."""
from asgiref.sync import sync_to_async
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .context import usuario_actual, veterinaria_actual


@sync_to_async
def _resolver_token(token_key):
    from rest_framework.authtoken.models import Token
    from apps.usuarios.utils import usuario_habilitado_para_api, veterinaria_del_usuario

    try:
        token = Token.objects.select_related('user__perfil__veterinaria').get(key=token_key)
    except Token.DoesNotExist:
        return None, None, "Token inválido."

    user = token.user
    if not usuario_habilitado_para_api(user):
        return None, None, "Tu cuenta no está habilitada (sin aprobar, o te revocaron el acceso)."

    vet = veterinaria_del_usuario(user)
    if vet is None and not user.is_superuser:
        return None, None, "Tu usuario no tiene una veterinaria asignada."

    return user, vet, None


class AutenticacionPorTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        encabezado = request.headers.get('authorization', '')
        if not encabezado.lower().startswith('bearer '):
            return JSONResponse(
                {"error": "Falta el token. Mandá el encabezado 'Authorization: Bearer <tu-token>'."},
                status_code=401,
            )

        token_key = encabezado[7:].strip()
        if not token_key:
            return JSONResponse({"error": "El token está vacío."}, status_code=401)

        user, vet, error = await _resolver_token(token_key)
        if error:
            return JSONResponse({"error": error}, status_code=401)

        token_usuario = usuario_actual.set(user)
        token_vet = veterinaria_actual.set(vet)
        try:
            return await call_next(request)
        finally:
            usuario_actual.reset(token_usuario)
            veterinaria_actual.reset(token_vet)
