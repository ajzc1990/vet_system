from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import PerfilUsuario, Veterinaria


class ExpedienteMascotaTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        cliente_b = Cliente.objects.create(
            veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2",
        )
        self.mascota_b = Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")

        self.client.force_login(self.user_a)

    def test_no_puede_ver_el_expediente_de_una_mascota_de_otra_veterinaria(self):
        response = self.client.get(reverse('historia_clinica:expediente_mascota', args=[self.mascota_b.id]))

        self.assertEqual(response.status_code, 404)
