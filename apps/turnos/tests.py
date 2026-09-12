from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import PerfilUsuario, Veterinaria
from .models import Turno, SolicitudTurnoWeb


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


class AgendaFiltroPorDefectoTests(TestCase):
    """Regresión: sin ningún filtro, la agenda traía TODOS los turnos históricos de la
    clínica. Por defecto ahora solo muestra los del día de hoy, salvo que se pida
    explícitamente ?todos=1 o se filtre por otra fecha."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Agenda")
        user = User.objects.create_user(username="admin_agenda", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet, rol="ADMIN", is_approved=True)

        cliente = Cliente.objects.create(veterinaria=self.vet, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        mascota = Mascota.objects.create(cliente=cliente, nombre="Firulais", especie="CANINO")

        hoy = timezone.now()
        self.turno_hoy = Turno.objects.create(veterinaria=self.vet, mascota=mascota, fecha_hora=hoy)
        self.turno_pasado = Turno.objects.create(veterinaria=self.vet, mascota=mascota, fecha_hora=hoy - timedelta(days=30))

        self.client.force_login(user)

    def test_sin_filtro_solo_muestra_los_turnos_de_hoy(self):
        response = self.client.get(reverse('turnos:lista_turnos'))
        turnos_listados = list(response.context['turnos'])
        self.assertIn(self.turno_hoy, turnos_listados)
        self.assertNotIn(self.turno_pasado, turnos_listados)

    def test_ver_todos_incluye_el_historial_completo(self):
        response = self.client.get(reverse('turnos:lista_turnos'), {'todos': '1'})
        turnos_listados = list(response.context['turnos'])
        self.assertIn(self.turno_hoy, turnos_listados)
        self.assertIn(self.turno_pasado, turnos_listados)

    def test_filtrar_por_una_fecha_especifica_funciona(self):
        fecha = self.turno_pasado.fecha_hora.date().isoformat()
        response = self.client.get(reverse('turnos:lista_turnos'), {'fecha': fecha})
        turnos_listados = list(response.context['turnos'])
        self.assertIn(self.turno_pasado, turnos_listados)
        self.assertNotIn(self.turno_hoy, turnos_listados)

    def test_la_agenda_pagina_de_a_25_turnos(self):
        mascota = self.turno_hoy.mascota
        hoy = timezone.now()
        for _ in range(30):
            Turno.objects.create(veterinaria=self.vet, mascota=mascota, fecha_hora=hoy)

        response = self.client.get(reverse('turnos:lista_turnos'), {'todos': '1'})
        self.assertEqual(len(response.context['turnos']), 25)
        self.assertEqual(response.context['turnos'].paginator.count, 32)


class SolicitudTurnoWebTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.solicitud_a = SolicitudTurnoWeb.objects.create(
            veterinaria=self.vet_a, nombre_tutor="Juan Perez", telefono="123", nombre_mascota="Firulais",
            motivo="Vacunación", fecha_deseada=timezone.now().date() + timedelta(days=2),
        )
        self.solicitud_b = SolicitudTurnoWeb.objects.create(
            veterinaria=self.vet_b, nombre_tutor="Ana Gomez", telefono="456", nombre_mascota="Michi",
            motivo="Control", fecha_deseada=timezone.now().date() + timedelta(days=2),
        )

    def test_formulario_publico_no_requiere_login_y_crea_la_solicitud(self):
        response = self.client.post(reverse('turnos:solicitar_turno_publico', args=[self.vet_a.id]), {
            'nombre_tutor': 'Maria Lopez',
            'telefono': '3811234567',
            'nombre_mascota': 'Rocky',
            'motivo': 'Chequeo general',
            'fecha_deseada': (timezone.now().date() + timedelta(days=3)).isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SolicitudTurnoWeb.objects.filter(nombre_mascota='Rocky', veterinaria=self.vet_a).exists())

    def test_bandeja_de_solicitudes_solo_muestra_las_del_tenant_activo(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('turnos:lista_solicitudes_turno'))

        solicitudes = list(response.context['solicitudes'])
        self.assertIn(self.solicitud_a, solicitudes)
        self.assertNotIn(self.solicitud_b, solicitudes)

    def test_no_puede_actualizar_una_solicitud_de_otra_veterinaria(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('turnos:actualizar_estado_solicitud', args=[self.solicitud_b.id, 'DESCARTADO']))

        self.assertEqual(response.status_code, 404)
        self.solicitud_b.refresh_from_db()
        self.assertEqual(self.solicitud_b.estado, 'PENDIENTE')
