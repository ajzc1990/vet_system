from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import PerfilUsuario, Veterinaria
from .models import Turno


class TurnosTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        cliente_a = Cliente.objects.create(
            veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1",
        )
        mascota_a = Mascota.objects.create(cliente=cliente_a, nombre="Firulais", especie="CANINO")
        cliente_b = Cliente.objects.create(
            veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2",
        )
        mascota_b = Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")

        ahora = timezone.now()
        self.turno_a = Turno.objects.create(veterinaria=self.vet_a, mascota=mascota_a, fecha_hora=ahora)
        self.turno_b = Turno.objects.create(veterinaria=self.vet_b, mascota=mascota_b, fecha_hora=ahora)

        self.client.force_login(self.user_a)

    def test_lista_turnos_solo_incluye_los_de_su_veterinaria(self):
        response = self.client.get(reverse('turnos:lista_turnos'))

        turnos_listados = list(response.context['turnos'])
        self.assertIn(self.turno_a, turnos_listados)
        self.assertNotIn(self.turno_b, turnos_listados)
