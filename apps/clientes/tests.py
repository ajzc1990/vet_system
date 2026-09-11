from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.turnos.models import Veterinario
from apps.usuarios.models import PerfilUsuario, Veterinaria
from apps.historia_clinica.models import ConsultaMedica, RegistroVacuna, RegistroDesparasitacion
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


class HistoriaClinicaRenderTests(TestCase):
    """Regresión: la plantilla usaba consulta.veterinario.user (el campo real es
    'usuario') y encadenaba v.proxima_dosis (campo inexistente, es fecha_proxima_dosis)
    como argumento del filtro 'default'. Django resuelve los argumentos de filtro sin
    el manejo silencioso habitual, así que cualquier consulta con veterinario asignado,
    o cualquier vacuna/desparasitación con fecha_proxima_dosis cargada, tiraba un 500
    (VariableDoesNotExist) en vez de renderizar la página."""

    def setUp(self):
        vet = Veterinaria.objects.create(nombre="Clinica Render")
        user = User.objects.create_user(username="admin_render", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=vet, rol="ADMIN", is_approved=True)

        cliente = Cliente.objects.create(veterinaria=vet, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        self.mascota = Mascota.objects.create(cliente=cliente, nombre="Firulais", especie="CANINO")

        self.veterinario = Veterinario.objects.create(veterinaria=vet, nombre="Sofía", apellido="Herrera", matricula="MP-1")

        self.client.force_login(user)

    def test_no_rompe_con_una_consulta_que_tiene_veterinario_asignado(self):
        ConsultaMedica.objects.create(
            veterinaria=None, mascota=self.mascota, veterinario=self.veterinario,
            motivo_consulta="Control", diagnostico="Sano", tratamiento="Ninguno",
        )
        response = self.client.get(reverse('clientes:detalle_historia_clinica', args=[self.mascota.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Herrera")

    def test_no_rompe_con_una_vacuna_con_fecha_proxima_dosis_cargada(self):
        RegistroVacuna.objects.create(
            mascota=self.mascota, nombre_vacuna="Antirrábica",
            fecha_aplicacion=timezone.now().date(),
            fecha_proxima_dosis=timezone.now().date() + timedelta(days=365),
        )
        response = self.client.get(reverse('clientes:detalle_historia_clinica', args=[self.mascota.id]))
        self.assertEqual(response.status_code, 200)

    def test_no_rompe_con_una_desparasitacion_con_fecha_proxima_dosis_cargada(self):
        RegistroDesparasitacion.objects.create(
            mascota=self.mascota, producto="Simparica",
            fecha_aplicacion=timezone.now().date(),
            fecha_proxima_dosis=timezone.now().date() + timedelta(days=90),
        )
        response = self.client.get(reverse('clientes:detalle_historia_clinica', args=[self.mascota.id]))
        self.assertEqual(response.status_code, 200)

    def test_confirmar_eliminar_consulta_no_rompe(self):
        """Regresión: la plantilla usaba consulta.fecha y consulta.motivo, campos que no
        existen (son fecha_hora y motivo_consulta) — la página de confirmación de borrado
        tiraba 500 siempre, para cualquier consulta."""
        consulta = ConsultaMedica.objects.create(
            mascota=self.mascota, motivo_consulta="Control", diagnostico="Sano", tratamiento="Ninguno",
        )
        response = self.client.get(reverse('clientes:eliminar_consulta', args=[consulta.id]))
        self.assertEqual(response.status_code, 200)
