from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.turnos.models import Veterinario
from apps.usuarios.models import PerfilUsuario, Veterinaria
from .models import Cliente, Mascota


class ClientesTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.cliente_a = Cliente.objects.create(
            veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1",
        )
        self.cliente_b = Cliente.objects.create(
            veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2",
        )

        self.client.force_login(self.user_a)

    def test_lista_clientes_solo_incluye_los_de_su_veterinaria(self):
        response = self.client.get(reverse('clientes:lista_clientes'))

        clientes_listados = list(response.context['clientes'])
        self.assertIn(self.cliente_a, clientes_listados)
        self.assertNotIn(self.cliente_b, clientes_listados)

    def test_no_puede_ver_el_detalle_de_un_cliente_de_otra_veterinaria(self):
        response = self.client.get(reverse('clientes:detalle_cliente', args=[self.cliente_b.id]))

        self.assertEqual(response.status_code, 404)


class NuevaConsultaAsignacionVeterinarioTests(TestCase):
    """Regresion del bug donde, si el usuario no tenia un Veterinario asociado, el sistema
    asignaba la consulta al primer Veterinario de TODA la base de datos (de cualquier tenant)
    en lugar de dejarla sin veterinario asignado."""

    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        # Se crea antes que cualquier veterinario de la clinica A, para que sea
        # ".first()" en toda la tabla si el fallback buggy siguiera presente.
        self.veterinario_de_otra_clinica = Veterinario.objects.create(
            veterinaria=self.vet_b, nombre="Ajena", apellido="Otra", matricula="B-1",
        )

        self.user_a = User.objects.create_user(username="recepcion_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="RECEPCION", is_approved=True)

        cliente_a = Cliente.objects.create(
            veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1",
        )
        self.mascota_a = Mascota.objects.create(cliente=cliente_a, nombre="Firulais", especie="CANINO")

        self.client.force_login(self.user_a)

    def test_no_asigna_un_veterinario_de_otra_veterinaria(self):
        url = reverse('clientes:detalle_historia_clinica', args=[self.mascota_a.id])
        data = {
            'motivo_consulta': 'Chequeo de rutina',
            'diagnostico': 'Sano',
            'tratamiento': 'Ninguno',
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        consulta = self.mascota_a.consultas.get()
        self.assertNotEqual(consulta.veterinario_id, self.veterinario_de_otra_clinica.id)
        self.assertIsNone(consulta.veterinario)
