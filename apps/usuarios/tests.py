from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.urls import reverse

from apps.clientes.models import Cliente
from .models import PerfilUsuario, Veterinaria, RegistroAuditoria, Plan, Suscripcion
from .utils import get_veterinaria_activa


class GetVeterinariaActivaTests(TestCase):
    """get_veterinaria_activa es el único punto que decide el tenant de cada request.

    No debe existir ningun fallback a "la primera veterinaria de la base": eso filtraria
    datos de otro tenant a un usuario sin perfil asignado.
    """

    def test_sin_atributo_veterinaria_devuelve_none(self):
        request = RequestFactory().get('/')
        self.assertIsNone(get_veterinaria_activa(request))

    def test_devuelve_la_veterinaria_inyectada_por_el_middleware(self):
        vet = Veterinaria.objects.create(nombre="Clinica Sur")
        request = RequestFactory().get('/')
        request.veterinaria = vet
        self.assertEqual(get_veterinaria_activa(request), vet)


class DashboardTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")
        Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        Cliente.objects.create(veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2")

    def test_usuario_sin_perfil_no_ve_datos_de_ninguna_veterinaria(self):
        """Antes de la corrección, un usuario sin perfil caía en Veterinaria.objects.first()
        y veia los datos completos de esa veterinaria ajena."""
        user = User.objects.create_user(username="sin_perfil", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse('usuarios:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clientes'], 0)

    def test_usuario_con_perfil_solo_ve_su_propia_veterinaria(self):
        user = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)
        self.client.force_login(user)

        response = self.client.get(reverse('usuarios:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clientes'], 1)

    def test_superuser_sin_perfil_ve_todas_las_veterinarias(self):
        user = User.objects.create_superuser(username="root", password="testpass123", email="root@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse('usuarios:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clientes'], 2)


class AuditoriaTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.admin_a = User.objects.create_user(username="admin_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.admin_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        admin_b = User.objects.create_user(username="admin_b", password="testpass123")
        PerfilUsuario.objects.create(user=admin_b, veterinaria=self.vet_b, rol="ADMIN", is_approved=True)

        RegistroAuditoria.objects.create(veterinaria=self.vet_a, usuario=self.admin_a, accion='CREAR', descripcion="Evento de Clinica A")
        RegistroAuditoria.objects.create(veterinaria=self.vet_b, usuario=admin_b, accion='CREAR', descripcion="Evento de Clinica B")

    def test_login_exitoso_queda_registrado_en_la_auditoria(self):
        # Se hace un POST real al endpoint de login (en vez de client.login()) porque
        # client.login() arma un HttpRequest "pelado" que nunca pasa por el
        # AuthenticationMiddleware: request.user jamás queda seteado y por lo tanto
        # tampoco se podría probar que el registro de auditoría lo capture bien.
        self.client.post(reverse('login'), {'username': 'admin_a', 'password': 'testpass123'})
        registro = RegistroAuditoria.objects.filter(accion='LOGIN', usuario=self.admin_a).first()
        self.assertIsNotNone(registro)

    def test_login_fallido_queda_registrado_en_la_auditoria(self):
        self.client.post(reverse('login'), {'username': 'admin_a', 'password': 'password-incorrecta'})
        registro = RegistroAuditoria.objects.filter(accion='LOGIN_FALLIDO').first()
        self.assertIsNotNone(registro)

    def test_admin_de_veterinaria_solo_ve_la_auditoria_de_su_propio_tenant(self):
        self.client.force_login(self.admin_a)
        response = self.client.get(reverse('usuarios:auditoria'))

        self.assertEqual(response.status_code, 200)
        descripciones = [r.descripcion for r in response.context['registros']]
        self.assertIn("Evento de Clinica A", descripciones)
        self.assertNotIn("Evento de Clinica B", descripciones)

    def test_usuario_sin_rol_admin_no_puede_ver_la_auditoria(self):
        vet_user = User.objects.create_user(username="vet_a", password="testpass123")
        PerfilUsuario.objects.create(user=vet_user, veterinaria=self.vet_a, rol="VET", is_approved=True)
        self.client.force_login(vet_user)

        response = self.client.get(reverse('usuarios:auditoria'))
        self.assertRedirects(response, reverse('dashboard:index'))


class SuscripcionTests(TestCase):
    def test_nueva_veterinaria_recibe_periodo_de_prueba_si_hay_un_plan_activo(self):
        Plan.objects.create(nombre="Básico", precio_mensual=5000, orden=0)
        vet = Veterinaria.objects.create(nombre="Clinica Nueva")

        self.assertTrue(hasattr(vet, 'suscripcion'))
        self.assertEqual(vet.suscripcion.estado, 'PRUEBA')

    def test_nueva_veterinaria_sin_planes_cargados_no_falla(self):
        vet = Veterinaria.objects.create(nombre="Clinica Sin Plan")
        self.assertFalse(hasattr(vet, 'suscripcion'))

    def test_extender_suscripcion_requiere_superusuario(self):
        Plan.objects.create(nombre="Básico", precio_mensual=5000, orden=0)
        vet = Veterinaria.objects.create(nombre="Clinica X")
        admin = User.objects.create_user(username="admin_x", password="testpass123")
        PerfilUsuario.objects.create(user=admin, veterinaria=vet, rol="ADMIN", is_approved=True)
        self.client.force_login(admin)

        response = self.client.post(reverse('usuarios:extender_suscripcion', args=[vet.suscripcion.id]))
        self.assertRedirects(response, reverse('dashboard:index'))
        vet.suscripcion.refresh_from_db()
        self.assertEqual(vet.suscripcion.estado, 'PRUEBA')
