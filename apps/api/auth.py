from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['POST'])
@permission_classes([AllowAny])
def obtener_token(request):
    """Login por usuario/clave que devuelve un token de API, replicando la misma
    validación de is_approved que ya aplica CustomLoginView: sin esto, un usuario
    pendiente de aprobación (o al que se la revocaron) podría igual sacar un token
    válido usando el endpoint estándar de DRF."""
    username = request.data.get('username')
    password = request.data.get('password')
    if not username or not password:
        return Response(
            {'detail': 'Usuario y contraseña son requeridos.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'detail': 'Credenciales inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.is_superuser:
        perfil = getattr(user, 'perfil', None)
        if not perfil or not perfil.is_approved:
            return Response(
                {'detail': 'Tu cuenta todavía no fue aprobada por un administrador.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key})
