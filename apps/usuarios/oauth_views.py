"""
Servidor OAuth mínimo para que Claude (u otro cliente MCP compatible) se pueda
conectar como "custom connector" sin que el usuario tenga que copiar un token a
mano. Implementa justo lo que Claude exige para un conector agregado por URL:

- Metadata de descubrimiento (RFC 9728 y RFC 8414)
- Registro dinámico de cliente (RFC 7591, DCR) — Claude se registra solo
- Authorization Code + PKCE S256 (RFC 7636)
- Refresh token con rotación (requerido para clientes "públicos" como Claude)

El login en sí reutiliza el login normal de VeterSystem (@login_required +
LOGIN_URL ya redirige con ?next=... a esta misma pantalla); acá solo se agrega
la pantalla de consentimiento ("¿autorizás a Claude...?").
"""
import base64
import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import OAuthClient, OAuthAuthorizationCode, OAuthAccessToken, OAuthRefreshToken
from .utils import usuario_habilitado_para_api, veterinaria_del_usuario

DURACION_CODIGO_MINUTOS = 10
DURACION_ACCESS_TOKEN_MINUTOS = 60
REDIRECT_URIS_PERMITIDAS_LOOPBACK = ('http://localhost', 'http://127.0.0.1')


def _base_url(request):
    return f"{request.scheme}://{request.get_host()}"


def _redirect_uri_valida(client, redirect_uri):
    if redirect_uri in client.redirect_uris:
        return True
    # Claude Code usa loopback en un puerto que cambia en cada sesión.
    return any(redirect_uri.startswith(prefijo) for prefijo in REDIRECT_URIS_PERMITIDAS_LOOPBACK)


# --------------------------------------------------------------------------
# Metadata de descubrimiento
# --------------------------------------------------------------------------

def protected_resource_metadata(request):
    base = _base_url(request)
    return JsonResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
    })


def authorization_server_metadata(request):
    base = _base_url(request)
    return JsonResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}{reverse('oauth_authorize')}",
        "token_endpoint": f"{base}{reverse('oauth_token')}",
        "registration_endpoint": f"{base}{reverse('oauth_register')}",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["mcp"],
    })


# --------------------------------------------------------------------------
# Registro dinámico de cliente (DCR)
# --------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def oauth_register(request):
    try:
        datos = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_client_metadata"}, status=400)

    redirect_uris = datos.get('redirect_uris') or []
    if not isinstance(redirect_uris, list) or not redirect_uris:
        return JsonResponse({"error": "invalid_redirect_uri", "error_description": "Falta redirect_uris."}, status=400)

    client = OAuthClient.objects.create(
        client_name=(datos.get('client_name') or '')[:150],
        redirect_uris=redirect_uris,
    )
    return JsonResponse({
        "client_id": client.client_id,
        "redirect_uris": client.redirect_uris,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }, status=201)


# --------------------------------------------------------------------------
# Autorización (login lo maneja @login_required; acá solo el consentimiento)
# --------------------------------------------------------------------------

@login_required
def oauth_authorize(request):
    client_id = request.GET.get('client_id') or request.POST.get('client_id')
    redirect_uri = request.GET.get('redirect_uri') or request.POST.get('redirect_uri')
    code_challenge = request.GET.get('code_challenge') or request.POST.get('code_challenge')
    code_challenge_method = request.GET.get('code_challenge_method') or request.POST.get('code_challenge_method')
    state = request.GET.get('state') or request.POST.get('state', '')
    resource = request.GET.get('resource') or request.POST.get('resource', '')
    response_type = request.GET.get('response_type') or request.POST.get('response_type')

    client = OAuthClient.objects.filter(client_id=client_id).first()
    if not client:
        return HttpResponseBadRequest("Cliente OAuth desconocido.")
    if response_type != 'code':
        return HttpResponseBadRequest("Solo se soporta response_type=code.")
    if code_challenge_method != 'S256':
        return HttpResponseBadRequest("Solo se soporta code_challenge_method=S256.")
    if not code_challenge:
        return HttpResponseBadRequest("Falta code_challenge (PKCE).")
    if not _redirect_uri_valida(client, redirect_uri or ''):
        return HttpResponseBadRequest("redirect_uri no registrada para este cliente.")

    if not usuario_habilitado_para_api(request.user):
        return render(request, 'usuarios/oauth_autorizar.html', {
            'bloqueado': True,
        })

    if request.method == 'POST' and request.POST.get('accion') == 'autorizar':
        codigo = OAuthAuthorizationCode.objects.create(
            client=client, usuario=request.user, redirect_uri=redirect_uri,
            code_challenge=code_challenge, resource=resource,
            expira_el=timezone.now() + timedelta(minutes=DURACION_CODIGO_MINUTOS),
        )
        separador = '&' if '?' in redirect_uri else '?'
        destino = f"{redirect_uri}{separador}code={codigo.code}"
        if state:
            destino += f"&state={state}"
        return HttpResponseRedirect(destino)

    if request.method == 'POST' and request.POST.get('accion') == 'rechazar':
        separador = '&' if '?' in redirect_uri else '?'
        destino = f"{redirect_uri}{separador}error=access_denied"
        if state:
            destino += f"&state={state}"
        return HttpResponseRedirect(destino)

    vet = veterinaria_del_usuario(request.user)
    return render(request, 'usuarios/oauth_autorizar.html', {
        'bloqueado': False,
        'client': client,
        'veterinaria': vet,
        'form_action_params': {
            'client_id': client_id, 'redirect_uri': redirect_uri,
            'code_challenge': code_challenge, 'code_challenge_method': code_challenge_method,
            'state': state, 'resource': resource, 'response_type': response_type,
        },
    })


# --------------------------------------------------------------------------
# Token endpoint: intercambio de código y refresco
# --------------------------------------------------------------------------

def _verificar_pkce(code_verifier, code_challenge):
    if not code_verifier:
        return False
    calculado = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).rstrip(b'=').decode('ascii')
    return calculado == code_challenge


def _emitir_tokens(client, usuario):
    OAuthAccessToken.objects.filter(client=client, usuario=usuario).delete()
    access = OAuthAccessToken.objects.create(
        client=client, usuario=usuario,
        expira_el=timezone.now() + timedelta(minutes=DURACION_ACCESS_TOKEN_MINUTOS),
    )
    refresh = OAuthRefreshToken.objects.create(client=client, usuario=usuario)
    return JsonResponse({
        "access_token": access.token,
        "token_type": "Bearer",
        "expires_in": DURACION_ACCESS_TOKEN_MINUTOS * 60,
        "refresh_token": refresh.token,
        "scope": "mcp",
    })


@csrf_exempt
@require_http_methods(["POST"])
def oauth_token(request):
    grant_type = request.POST.get('grant_type')
    client_id = request.POST.get('client_id')
    client = OAuthClient.objects.filter(client_id=client_id).first()
    if not client:
        return JsonResponse({"error": "invalid_client"}, status=401)

    if grant_type == 'authorization_code':
        code_valor = request.POST.get('code')
        redirect_uri = request.POST.get('redirect_uri')
        code_verifier = request.POST.get('code_verifier')

        codigo = OAuthAuthorizationCode.objects.filter(code=code_valor, client=client).first()
        if not codigo or codigo.usado or codigo.esta_vencido:
            return JsonResponse({"error": "invalid_grant"}, status=400)
        if codigo.redirect_uri != redirect_uri:
            return JsonResponse({"error": "invalid_grant", "error_description": "redirect_uri no coincide."}, status=400)
        if not _verificar_pkce(code_verifier, codigo.code_challenge):
            return JsonResponse({"error": "invalid_grant", "error_description": "code_verifier inválido."}, status=400)

        codigo.usado = True
        codigo.save(update_fields=['usado'])
        return _emitir_tokens(client, codigo.usuario)

    if grant_type == 'refresh_token':
        token_valor = request.POST.get('refresh_token')
        refresh = OAuthRefreshToken.objects.filter(token=token_valor, client=client).first()
        if not refresh or refresh.usado:
            return JsonResponse({"error": "invalid_grant"}, status=400)

        refresh.usado = True
        refresh.save(update_fields=['usado'])
        return _emitir_tokens(client, refresh.usuario)

    return JsonResponse({"error": "unsupported_grant_type"}, status=400)
