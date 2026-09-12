from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.clientes.models import Cliente, Mascota
from apps.inventario.models import Producto
from apps.usuarios.models import PerfilUsuario, Veterinaria


class ObtenerTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vet = Veterinaria.objects.create(nombre="Clinica API")

    def test_usuario_aprobado_obtiene_token(self):
        user = User.objects.create_user(username="aprobado", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet, rol="ADMIN", is_approved=True)

        response = self.client.post(reverse('api:obtener_token'), {'username': 'aprobado', 'password': 'testpass123'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_usuario_no_aprobado_no_obtiene_token(self):
        user = User.objects.create_user(username="pendiente", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet, rol="ADMIN", is_approved=False)

        response = self.client.post(reverse('api:obtener_token'), {'username': 'pendiente', 'password': 'testpass123'})

        self.assertEqual(response.status_code, 403)

    def test_credenciales_invalidas_no_obtienen_token(self):
        response = self.client.post(reverse('api:obtener_token'), {'username': 'nadie', 'password': 'incorrecta'})
        self.assertEqual(response.status_code, 401)


class ApiTenantIsolationTests(TestCase):
    """Confirma que la API REST respeta el mismo aislamiento por tenant que el resto
    del sistema, tanto por sesión como por token."""

    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)
        self.token_a = Token.objects.create(user=self.user_a)

        self.cliente_a = Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        self.cliente_b = Cliente.objects.create(veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2")
        Mascota.objects.create(cliente=self.cliente_a, nombre="Firulais", especie="CANINO")
        Mascota.objects.create(cliente=self.cliente_b, nombre="Michi", especie="FELINO")

        Producto.objects.create(veterinaria=self.vet_a, nombre="Amoxicilina")
        Producto.objects.create(veterinaria=self.vet_b, nombre="Antiparasitario")

    def test_lista_clientes_por_token_solo_incluye_los_del_tenant_del_token(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:cliente-list'))

        nombres = [c['apellido'] for c in response.data['results']]
        self.assertIn('Perez', nombres)
        self.assertNotIn('Gomez', nombres)

    def test_lista_mascotas_solo_incluye_las_del_tenant(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:mascota-list'))

        nombres = [m['nombre'] for m in response.data['results']]
        self.assertIn('Firulais', nombres)
        self.assertNotIn('Michi', nombres)

    def test_lista_productos_solo_incluye_los_del_tenant(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:producto-list'))

        nombres = [p['nombre'] for p in response.data['results']]
        self.assertIn('Amoxicilina', nombres)
        self.assertNotIn('Antiparasitario', nombres)

    def test_sin_autenticacion_no_permite_listar(self):
        client = APIClient()
        response = client.get(reverse('api:cliente-list'))
        # DRF devuelve 403 (no 401) porque SessionAuthentication -el primer
        # authenticator configurado- no expone un WWW-Authenticate header.
        self.assertEqual(response.status_code, 403)

    def test_no_se_puede_acceder_al_detalle_de_un_cliente_de_otro_tenant(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:cliente-detail', args=[self.cliente_b.id]))

        self.assertEqual(response.status_code, 404)

    def test_usuario_no_aprobado_no_puede_usar_la_api_aunque_tenga_token(self):
        user_pendiente = User.objects.create_user(username="pendiente", password="testpass123")
        PerfilUsuario.objects.create(user=user_pendiente, veterinaria=self.vet_a, rol="ADMIN", is_approved=False)
        token_pendiente = Token.objects.create(user=user_pendiente)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token_pendiente.key}')
        response = client.get(reverse('api:cliente-list'))

        self.assertEqual(response.status_code, 403)
