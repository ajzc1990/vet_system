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


class SolicitarTurnoClientePortalTests(TestCase):
    """La reserva de turno online está reservada a clientes con cuenta en el Portal: no
    vuelven a tipear su nombre/teléfono ni el nombre de su mascota, se autocompletan
    desde su cuenta y elige la mascota de una lista. Quien no sea cliente de esa
    veterinaria (o no esté logueado) no puede generar el pedido."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Portal")
        self.otra_vet = Veterinaria.objects.create(nombre="Otra Clinica")

        self.user_portal = User.objects.create_user(username="tutor_portal", password="testpass123")
        self.cliente = Cliente.objects.create(
            veterinaria=self.vet, nombre="Laura", apellido="Diaz", dni="333", telefono="3811112222",
            usuario=self.user_portal,
        )
        self.mascota = Mascota.objects.create(cliente=self.cliente, nombre="Rocky", especie="CANINO")

    def test_cliente_logueado_no_necesita_re_tipear_sus_datos(self):
        self.client.force_login(self.user_portal)

        response = self.client.post(reverse('turnos:solicitar_turno_publico', args=[self.vet.id]), {
            'mascota_id': self.mascota.id,
            'motivo': 'Chequeo anual',
            'fecha_deseada': (timezone.now().date() + timedelta(days=3)).isoformat(),
        })

        self.assertRedirects(response, reverse('portal:turnos'))
        solicitud = SolicitudTurnoWeb.objects.get(nombre_mascota='Rocky', veterinaria=self.vet)
        self.assertEqual(solicitud.nombre_tutor, 'Laura Diaz')
        self.assertEqual(solicitud.telefono, '3811112222')

    def test_no_puede_pedir_turno_para_una_mascota_ajena(self):
        cliente_ajeno = Cliente.objects.create(
            veterinaria=self.vet, nombre="Pedro", apellido="Ruiz", dni="444", telefono="1",
        )
        mascota_ajena = Mascota.objects.create(cliente=cliente_ajeno, nombre="Toby", especie="CANINO")
        self.client.force_login(self.user_portal)

        self.client.post(reverse('turnos:solicitar_turno_publico', args=[self.vet.id]), {
            'mascota_id': mascota_ajena.id,
            'motivo': 'Chequeo anual',
            'fecha_deseada': (timezone.now().date() + timedelta(days=3)).isoformat(),
        })

        self.assertFalse(SolicitudTurnoWeb.objects.filter(nombre_mascota='Toby').exists())

    def test_cliente_de_otra_veterinaria_no_puede_reservar_ahi(self):
        """Si entra al link de reserva de una veterinaria que no es la suya, se lo
        rechaza en vez de mostrarle el formulario (no es cliente de esa clínica)."""
        self.client.force_login(self.user_portal)

        response = self.client.get(reverse('turnos:solicitar_turno_publico', args=[self.otra_vet.id]))

        self.assertRedirects(response, reverse('portal:home'))

    def test_usuario_anonimo_debe_loguearse_para_reservar(self):
        response = self.client.get(reverse('turnos:solicitar_turno_publico', args=[self.vet.id]))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('turnos:solicitar_turno_publico', args=[self.vet.id])}",
        )

    def test_usuario_logueado_sin_cuenta_de_cliente_no_puede_reservar(self):
        staff = User.objects.create_user(username="staff_sin_cliente", password="testpass123")
        PerfilUsuario.objects.create(user=staff, veterinaria=self.vet, rol="RECEPCION", is_approved=True)
        self.client.force_login(staff)

        response = self.client.get(reverse('turnos:solicitar_turno_publico', args=[self.vet.id]))

        # No se sigue el redirect: landing() a su vez redirige de nuevo (staff logueado -> dashboard).
        self.assertRedirects(response, reverse('landing'), fetch_redirect_response=False)
