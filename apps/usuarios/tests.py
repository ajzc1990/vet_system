from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.urls import reverse

from apps.clientes.models import Cliente
from .models import PerfilUsuario, Veterinaria
from .utils import get_veterinaria_activa


class GetVeterinariaActivaTests(TestCase):
    """get_veterinaria_activa es el único punto que decide el tenant de cada request.

    No debe existir ningun fallback a "la primera veterinaria de la base": eso filtraria
    datos de otro tenant a un usuario sin perfil asignado.
    """

    def test_sin_atributo_veterinaria_devuelve_none(self):
        request = RequestFactory().get('/')
        self.assertIsNone(get_veterinaria_activa(request))

    def test_devuelve_la_veterinaria_inyectada_por_el_middleware(self):
        vet = Veterinaria.objects.create(nombre="Clinica Sur")
        request = RequestFactory().get('/')
        request.veterinaria = vet
        self.assertEqual(get_veterinaria_activa(request), vet)


class DashboardTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")
        Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        Cliente.objects.create(veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2")

    def test_usuario_sin_perfil_no_ve_datos_de_ninguna_veterinaria(self):
        """Antes de la corrección, un usuario sin perfil caía en Veterinaria.objects.first()
        y veia los datos completos de esa veterinaria ajena."""
        user = User.objects.create_user(username="sin_perfil", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse('usuarios:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clientes'], 0)

    def test_usuario_con_perfil_solo_ve_su_propia_veterinaria(self):
        user = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)
        self.client.force_login(user)

        response = self.client.get(reverse('usuarios:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clientes'], 1)

    def test_superuser_sin_perfil_ve_todas_las_veterinarias(self):
        user = User.objects.create_superuser(username="root", password="testpass123", email="root@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse('usuarios:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clientes'], 2)
