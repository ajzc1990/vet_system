from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import Veterinaria


class PortalClienteIsolationTests(TestCase):
    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Portal")

        self.cliente_a = Cliente.objects.create(
            veterinaria=self.vet, nombre="Juan", apellido="Perez", dni="111", telefono="1",
        )
        self.mascota_a = Mascota.objects.create(cliente=self.cliente_a, nombre="Firulais", especie="CANINO")
        self.user_a = User.objects.create_user(username="portal_a", password="testpass123")
        self.cliente_a.usuario = self.user_a
        self.cliente_a.save()

        cliente_b = Cliente.objects.create(
            veterinaria=self.vet, nombre="Ana", apellido="Gomez", dni="222", telefono="2",
        )
        self.mascota_b = Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")

    def test_usuario_sin_cliente_vinculado_no_accede_al_portal(self):
        otro_user = User.objects.create_user(username="sin_portal", password="testpass123")
        self.client.force_login(otro_user)

        response = self.client.get(reverse('portal:home'))
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_cliente_del_portal_solo_ve_sus_propias_mascotas(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('portal:home'))

        self.assertEqual(response.status_code, 200)
        mascotas = list(response.context['mascotas'])
        self.assertIn(self.mascota_a, mascotas)
        self.assertNotIn(self.mascota_b, mascotas)

    def test_cliente_no_puede_ver_el_expediente_de_la_mascota_de_otro_cliente(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('portal:mascota_detalle', args=[self.mascota_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_cliente_puede_ver_el_expediente_de_su_propia_mascota(self):
        self.client.force_login(self.user_a)

        response = self.client.get(reverse('portal:mascota_detalle', args=[self.mascota_a.id]))
        self.assertEqual(response.status_code, 200)

    def test_login_redirige_al_portal_para_usuarios_con_cliente_vinculado(self):
        response = self.client.post(reverse('login'), {'username': 'portal_a', 'password': 'testpass123'})
        self.assertRedirects(response, reverse('portal:home'))

    def test_home_y_turnos_muestran_el_boton_de_solicitar_turno(self):
        """Regresión: portal_turnos no pasaba 'cliente' al contexto, así que el botón
        de Solicitar Turno (que depende de cliente.veterinaria_id) nunca se mostraba."""
        self.client.force_login(self.user_a)

        url_reserva = reverse('turnos:solicitar_turno_publico', args=[self.vet.id])

        response_home = self.client.get(reverse('portal:home'))
        self.assertContains(response_home, url_reserva)

        response_turnos = self.client.get(reverse('portal:turnos'))
        self.assertContains(response_turnos, url_reserva)


class OtorgarAccesoPortalTests(TestCase):
    def setUp(self):
        from apps.usuarios.models import PerfilUsuario

        self.vet = Veterinaria.objects.create(nombre="Clinica Portal")
        self.cliente = Cliente.objects.create(
            veterinaria=self.vet, nombre="Carlos", apellido="Diaz", dni="333444", telefono="3",
        )
        self.staff = User.objects.create_user(username="staff_admin", password="testpass123")
        PerfilUsuario.objects.create(user=self.staff, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        self.client.force_login(self.staff)

    def test_genera_usuario_y_vincula_el_cliente(self):
        response = self.client.post(reverse('clientes:otorgar_acceso_portal', args=[self.cliente.id]))
        self.cliente.refresh_from_db()

        self.assertRedirects(response, reverse('clientes:detalle_cliente', args=[self.cliente.id]))
        self.assertIsNotNone(self.cliente.usuario)
        self.assertEqual(self.cliente.usuario.username, "333444")

    def test_no_duplica_acceso_si_ya_tiene_usuario(self):
        user = User.objects.create_user(username="ya_existe", password="x")
        self.cliente.usuario = user
        self.cliente.save()

        response = self.client.post(reverse('clientes:otorgar_acceso_portal', args=[self.cliente.id]))
        self.assertRedirects(response, reverse('clientes:detalle_cliente', args=[self.cliente.id]))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.usuario, user)
