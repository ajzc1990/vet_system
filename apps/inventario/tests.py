from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario, Veterinaria
from .models import Producto


class InventarioTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.producto_a = Producto.objects.create(veterinaria=self.vet_a, nombre="Amoxicilina")
        self.producto_b = Producto.objects.create(veterinaria=self.vet_b, nombre="Antiparasitario")

        self.client.force_login(self.user_a)

    def test_lista_productos_solo_incluye_los_de_su_veterinaria(self):
        response = self.client.get(reverse('inventario:lista_productos'))

        productos_listados = list(response.context['productos'])
        self.assertIn(self.producto_a, productos_listados)
        self.assertNotIn(self.producto_b, productos_listados)
