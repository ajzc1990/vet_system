from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario, Veterinaria
from .models import Venta


class VentasTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.venta_a = Venta.objects.create(veterinaria=self.vet_a, total="100.00")
        self.venta_b = Venta.objects.create(veterinaria=self.vet_b, total="200.00")

        self.client.force_login(self.user_a)

    def test_lista_ventas_solo_incluye_las_de_su_veterinaria(self):
        response = self.client.get(reverse('ventas:lista_ventas'))

        ventas_listadas = list(response.context['ventas'])
        self.assertIn(self.venta_a, ventas_listadas)
        self.assertNotIn(self.venta_b, ventas_listadas)
