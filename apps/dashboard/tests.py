from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import PerfilUsuario, Veterinaria


class DashboardPrincipalTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        cliente_a = Cliente.objects.create(
            veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1",
        )
        Mascota.objects.create(cliente=cliente_a, nombre="Firulais", especie="CANINO")

        cliente_b = Cliente.objects.create(
            veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2",
        )
        Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")

    def test_usuario_sin_perfil_no_ve_pacientes_de_ninguna_veterinaria(self):
        user = User.objects.create_user(username="sin_perfil", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cant_pacientes'], 0)

    def test_usuario_con_perfil_solo_ve_pacientes_de_su_veterinaria(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cant_pacientes'], 1)
