from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import PerfilUsuario, Veterinaria
from .models import Turno, SolicitudTurnoWeb
from .whatsapp import (
    RecordatoriosDeshabilitados,
    RecordatorioWhatsAppError,
    enviar_recordatorio_turno,
)


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
        fecha = timezone.localtime(self.turno_pasado.fecha_hora).date().isoformat()
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

    def test_la_demo_no_muestra_el_link_de_whatsapp_de_las_solicitudes(self):
        """Regresión: la demo pública dejaba mandar un WhatsApp real a los teléfonos
        cargados en los datos de ejemplo."""
        from apps.usuarios.management.commands.seed_demo import DEMO_VET_NOMBRE

        vet_demo = Veterinaria.objects.create(nombre=DEMO_VET_NOMBRE)
        demo_admin = User.objects.create_user(username="demo_admin_sol", password="testpass123")
        PerfilUsuario.objects.create(user=demo_admin, veterinaria=vet_demo, rol="ADMIN", is_approved=True)
        SolicitudTurnoWeb.objects.create(
            veterinaria=vet_demo, nombre_tutor="Laura Diaz", telefono="3811112222", nombre_mascota="Rocky",
            motivo="Consulta", fecha_deseada=timezone.now().date() + timedelta(days=2),
        )

        self.client.force_login(demo_admin)
        response = self.client.get(reverse('turnos:lista_solicitudes_turno'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'wa.me')

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


class LinkRecordatorioWhatsappTests(TestCase):
    """El link de WhatsApp debe traer un mensaje pre-cargado con la mascota, fecha y hora
    del turno, listo para que el staff se lo mande al tutor con un clic."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Recordatorios")
        self.cliente = Cliente.objects.create(
            veterinaria=self.vet, nombre="Laura", apellido="Diaz", dni="333", telefono="381 111-2222",
        )
        self.mascota = Mascota.objects.create(cliente=self.cliente, nombre="Rocky", especie="CANINO")
        self.fecha_hora = timezone.now().replace(hour=15, minute=30, second=0, microsecond=0) + timedelta(days=2)

    def test_arma_el_link_con_telefono_limpio_y_mensaje_con_fecha_y_hora(self):
        from urllib.parse import unquote

        turno = Turno.objects.create(veterinaria=self.vet, mascota=self.mascota, fecha_hora=self.fecha_hora)

        link = turno.link_recordatorio_whatsapp
        mensaje = unquote(link.split("?text=")[1])

        self.assertTrue(link.startswith("https://wa.me/5493811112222?text="))
        self.assertIn("Rocky", mensaje)
        self.assertIn(self.fecha_hora.strftime("%d/%m/%Y"), mensaje)
        self.assertIn(self.fecha_hora.strftime("%H:%M"), mensaje)

    def test_sin_telefono_cargado_no_genera_link(self):
        self.cliente.telefono = ""
        self.cliente.save()
        turno = Turno.objects.create(veterinaria=self.vet, mascota=self.mascota, fecha_hora=self.fecha_hora)

        self.assertIsNone(turno.link_recordatorio_whatsapp)

    def test_en_la_veterinaria_demo_no_genera_link(self):
        """Regresión: la demo pública dejaba mandar un WhatsApp real a los teléfonos
        cargados en los datos de ejemplo."""
        from apps.usuarios.management.commands.seed_demo import DEMO_VET_NOMBRE

        vet_demo = Veterinaria.objects.create(nombre=DEMO_VET_NOMBRE)
        cliente_demo = Cliente.objects.create(
            veterinaria=vet_demo, nombre="Laura", apellido="Diaz", dni="334", telefono="381 111-2222",
        )
        mascota_demo = Mascota.objects.create(cliente=cliente_demo, nombre="Rocky", especie="CANINO")
        turno = Turno.objects.create(veterinaria=vet_demo, mascota=mascota_demo, fecha_hora=self.fecha_hora)

        self.assertIsNone(turno.link_recordatorio_whatsapp)


@override_settings(
    WHATSAPP_RECORDATORIOS_ENABLED=True,
    TWILIO_ACCOUNT_SID='ACxxxx',
    TWILIO_AUTH_TOKEN='token',
    TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
)
class EnviarRecordatorioWhatsappTests(TestCase):
    """Servicio apps/turnos/whatsapp.py: arma y manda el recordatorio vía Twilio,
    reusando el mismo mensaje y la misma normalización de teléfono que el link wa.me."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica WhatsApp")
        self.cliente = Cliente.objects.create(
            veterinaria=self.vet, nombre="Laura", apellido="Diaz", dni="444", telefono="381 111-2222",
        )
        self.mascota = Mascota.objects.create(cliente=self.cliente, nombre="Rocky", especie="CANINO")
        self.fecha_hora = timezone.now().replace(hour=15, minute=30, second=0, microsecond=0) + timedelta(days=1)
        self.turno = Turno.objects.create(veterinaria=self.vet, mascota=self.mascota, fecha_hora=self.fecha_hora)

    @override_settings(WHATSAPP_RECORDATORIOS_ENABLED=False)
    def test_deshabilitado_lanza_excepcion(self):
        with self.assertRaises(RecordatoriosDeshabilitados):
            enviar_recordatorio_turno(self.turno)

    def test_sin_telefono_lanza_error(self):
        self.cliente.telefono = ""
        self.cliente.save()
        with self.assertRaises(RecordatorioWhatsAppError):
            enviar_recordatorio_turno(self.turno)

    @patch('twilio.rest.Client')
    def test_envia_mensaje_con_twilio(self, mock_client_cls):
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        enviar_recordatorio_turno(self.turno)

        mock_client_cls.assert_called_once_with('ACxxxx', 'token')
        mock_instance.messages.create.assert_called_once()
        kwargs = mock_instance.messages.create.call_args.kwargs
        self.assertEqual(kwargs['from_'], 'whatsapp:+14155238886')
        self.assertEqual(kwargs['to'], 'whatsapp:+543811112222')
        self.assertIn('Rocky', kwargs['body'])

    @patch('twilio.rest.Client')
    def test_error_de_twilio_se_traduce_a_excepcion_propia(self, mock_client_cls):
        from twilio.base.exceptions import TwilioRestException

        mock_instance = MagicMock()
        mock_instance.messages.create.side_effect = TwilioRestException(500, 'uri', msg='fallo')
        mock_client_cls.return_value = mock_instance

        with self.assertRaises(RecordatorioWhatsAppError):
            enviar_recordatorio_turno(self.turno)


@override_settings(
    WHATSAPP_RECORDATORIOS_ENABLED=True,
    TWILIO_ACCOUNT_SID='ACxxxx',
    TWILIO_AUTH_TOKEN='token',
    TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
)
class EnviarRecordatoriosTurnosCommandTests(TestCase):
    """Management command enviar_recordatorios_turnos: el cron que corre la noche
    anterior y avisa sólo los turnos de mañana que todavía no fueron avisados."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Cron")
        self.cliente = Cliente.objects.create(
            veterinaria=self.vet, nombre="Pedro", apellido="Lopez", dni="555", telefono="381 222-3333",
        )
        self.mascota = Mascota.objects.create(cliente=self.cliente, nombre="Luna", especie="FELINO")
        self.turno_mañana = Turno.objects.create(
            veterinaria=self.vet, mascota=self.mascota,
            fecha_hora=timezone.now() + timedelta(days=1), estado='CONFIRMADO',
        )
        self.turno_pasado_mañana = Turno.objects.create(
            veterinaria=self.vet, mascota=self.mascota,
            fecha_hora=timezone.now() + timedelta(days=2), estado='CONFIRMADO',
        )

    @patch('apps.turnos.management.commands.enviar_recordatorios_turnos.enviar_recordatorio_turno')
    def test_solo_avisa_turnos_de_mañana_y_marca_el_flag(self, mock_enviar):
        out = StringIO()
        call_command('enviar_recordatorios_turnos', stdout=out)

        mock_enviar.assert_called_once_with(self.turno_mañana)
        self.turno_mañana.refresh_from_db()
        self.turno_pasado_mañana.refresh_from_db()
        self.assertTrue(self.turno_mañana.recordatorio_whatsapp_enviado)
        self.assertFalse(self.turno_pasado_mañana.recordatorio_whatsapp_enviado)
        self.assertIn('Recordatorios enviados: 1', out.getvalue())

    @patch('apps.turnos.management.commands.enviar_recordatorios_turnos.enviar_recordatorio_turno')
    def test_no_reenvia_si_ya_se_mando(self, mock_enviar):
        self.turno_mañana.recordatorio_whatsapp_enviado = True
        self.turno_mañana.save()

        call_command('enviar_recordatorios_turnos', stdout=StringIO())

        mock_enviar.assert_not_called()

    @override_settings(WHATSAPP_RECORDATORIOS_ENABLED=False)
    def test_no_hace_nada_si_esta_deshabilitado(self):
        out = StringIO()
        call_command('enviar_recordatorios_turnos', stdout=out)

        self.assertIn('no están habilitados', out.getvalue())
        self.turno_mañana.refresh_from_db()
        self.assertFalse(self.turno_mañana.recordatorio_whatsapp_enviado)

    @patch('apps.turnos.management.commands.enviar_recordatorios_turnos.enviar_recordatorio_turno')
    def test_turno_cancelado_no_recibe_recordatorio(self, mock_enviar):
        self.turno_mañana.estado = 'CANCELADO'
        self.turno_mañana.save()

        call_command('enviar_recordatorios_turnos', stdout=StringIO())

        mock_enviar.assert_not_called()

    @patch('apps.turnos.management.commands.enviar_recordatorios_turnos.enviar_recordatorio_turno')
    def test_la_veterinaria_demo_no_recibe_recordatorios(self, mock_enviar):
        from apps.usuarios.management.commands.seed_demo import DEMO_VET_NOMBRE

        vet_demo = Veterinaria.objects.create(nombre=DEMO_VET_NOMBRE)
        cliente_demo = Cliente.objects.create(
            veterinaria=vet_demo, nombre="Laura", apellido="Diaz", dni="556", telefono="381 111-2222",
        )
        mascota_demo = Mascota.objects.create(cliente=cliente_demo, nombre="Rocky", especie="CANINO")
        Turno.objects.create(
            veterinaria=vet_demo, mascota=mascota_demo,
            fecha_hora=timezone.now() + timedelta(days=1), estado='CONFIRMADO',
        )

        call_command('enviar_recordatorios_turnos', stdout=StringIO())

        mock_enviar.assert_called_once_with(self.turno_mañana)  # solo el de la clínica real
