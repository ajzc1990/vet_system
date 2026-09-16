from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import MensajeContacto, PerfilUsuario, Veterinaria
from apps.historia_clinica.models import RegistroVacuna


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


class MensajesDeContactoSoloSuperusuarioTests(TestCase):
    """Los mensajes del formulario de contacto de la landing son consultas de
    prospectos de todo el SaaS, no de una veterinaria en particular: ningún staff de
    ninguna clínica debería poder verlos, solo el superusuario."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica A")
        self.admin = User.objects.create_user(username="admin_clinica", password="testpass123")
        PerfilUsuario.objects.create(user=self.admin, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        self.superuser = User.objects.create_superuser(username="super", password="testpass123", email="s@s.com")

        MensajeContacto.objects.create(
            nombre="Prospecto", email="prospecto@example.com", mensaje="Quiero info", leido=False,
        )

    def test_staff_de_una_veterinaria_no_ve_los_mensajes_de_contacto(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['mensajes_contacto']), [])
        self.assertEqual(response.context['mensajes_no_leidos_count'], 0)
        self.assertNotContains(response, "prospecto@example.com")

    def test_superusuario_si_ve_los_mensajes_de_contacto(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['mensajes_no_leidos_count'], 1)
        self.assertContains(response, "prospecto@example.com")

    def test_staff_de_una_veterinaria_no_puede_entrar_al_admin_de_mensajes(self):
        self.client.force_login(self.admin)
        self.admin.is_staff = True
        self.admin.save()

        response = self.client.get('/admin/usuarios/mensajecontacto/')

        self.assertEqual(response.status_code, 403)

    def test_superusuario_puede_entrar_al_admin_de_mensajes(self):
        self.client.force_login(self.superuser)

        response = self.client.get('/admin/usuarios/mensajecontacto/')

        self.assertEqual(response.status_code, 200)


class CentroRecordatoriosTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A", email_contacto="clinica.a@example.com")
        vet_b = Veterinaria.objects.create(nombre="Clinica B", email_contacto="clinica.b@example.com")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        cliente_a = Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="3811111111")
        mascota_a = Mascota.objects.create(cliente=cliente_a, nombre="Firulais", especie="CANINO")
        self.vacuna_a = RegistroVacuna.objects.create(
            veterinaria=self.vet_a, mascota=mascota_a, nombre_vacuna="Antirrábica",
            fecha_proxima_dosis=timezone.now().date() - timedelta(days=2),
        )

        cliente_b = Cliente.objects.create(veterinaria=vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="3822222222")
        mascota_b = Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")
        RegistroVacuna.objects.create(
            veterinaria=vet_b, mascota=mascota_b, nombre_vacuna="Triple Felina",
            fecha_proxima_dosis=timezone.now().date() - timedelta(days=1),
        )

    def test_solo_muestra_vencimientos_del_tenant_activo(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('dashboard:centro_recordatorios'))

        self.assertEqual(response.status_code, 200)
        vacunas = [row['item'] for row in response.context['vacunas_vencidas_data']]
        self.assertIn(self.vacuna_a, vacunas)
        self.assertEqual(len(vacunas), 1)

    def test_comando_enviar_recordatorios_envia_un_email_por_veterinaria_con_pendientes(self):
        call_command('enviar_recordatorios')
        self.assertEqual(len(mail.outbox), 2)
        destinatarios = {m.to[0] for m in mail.outbox}
        self.assertEqual(destinatarios, {"clinica.a@example.com", "clinica.b@example.com"})
