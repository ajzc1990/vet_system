from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

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


class DashboardAliasRedirectTests(TestCase):
    """usuarios:dashboard era una segunda implementación del panel operativo, duplicada
    de dashboard:index (apps.dashboard), con su propio template y sus propias consultas.
    Ahora es solo un alias que redirige a la vista canónica, que ya tiene su propia
    cobertura de aislamiento multi-tenant en apps.dashboard.tests."""

    def test_redirige_a_la_vista_canonica_del_dashboard(self):
        user = User.objects.create_user(username="user_a", password="testpass123")
        vet = Veterinaria.objects.create(nombre="Clinica A")
        PerfilUsuario.objects.create(user=user, veterinaria=vet, rol="ADMIN", is_approved=True)
        self.client.force_login(user)

        response = self.client.get(reverse('usuarios:dashboard'))

        self.assertRedirects(response, reverse('dashboard:index'))


class LoginThrottleTests(TestCase):
    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Throttle")
        self.user = User.objects.create_user(username="user_throttle", password="testpass123")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)

    def test_bloquea_tras_varios_intentos_fallidos_aunque_la_password_sea_correcta(self):
        for _ in range(5):
            self.client.post(reverse('login'), {'username': 'user_throttle', 'password': 'incorrecta'})

        response = self.client.post(reverse('login'), {'username': 'user_throttle', 'password': 'testpass123'})

        self.assertRedirects(response, reverse('login'))
        self.assertFalse(response.wsgi_request.user.is_authenticated if hasattr(response, 'wsgi_request') else True)
        # El usuario sigue sin poder loguearse aunque la contraseña sea correcta
        self.assertFalse(self.client.session.get('_auth_user_id'))

    def test_no_bloquea_con_pocos_intentos_fallidos(self):
        for _ in range(3):
            self.client.post(reverse('login'), {'username': 'user_throttle', 'password': 'incorrecta'})

        response = self.client.post(reverse('login'), {'username': 'user_throttle', 'password': 'testpass123'})
        self.assertTrue(self.client.session.get('_auth_user_id'))
        self.assertRedirects(response, '/dashboard/')

    def test_el_bloqueo_es_especifico_por_usuario(self):
        otro = User.objects.create_user(username="otro_usuario", password="testpass123")
        PerfilUsuario.objects.create(user=otro, veterinaria=self.vet, rol="ADMIN", is_approved=True)

        for _ in range(5):
            self.client.post(reverse('login'), {'username': 'user_throttle', 'password': 'incorrecta'})

        response = self.client.post(reverse('login'), {'username': 'otro_usuario', 'password': 'testpass123'})
        self.assertTrue(self.client.session.get('_auth_user_id'))


class PasswordResetTests(TestCase):
    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Reset")
        self.user = User.objects.create_user(username="user_reset", password="oldpass123", email="reset@example.com")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)

    def test_solicitar_reset_envia_email_con_enlace_valido(self):
        response = self.client.post(reverse('password_reset'), {'email': 'reset@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('password-reset/confirmar/', mail.outbox[0].body)

    def test_email_inexistente_no_revela_si_la_cuenta_existe(self):
        response = self.client.post(reverse('password_reset'), {'email': 'no-existe@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_flujo_completo_permite_loguearse_con_la_nueva_contrasena(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # Django redirige el primer GET a una URL "set-password" guardada en sesión
        self.client.get(reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token}))
        response = self.client.post(
            reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': 'set-password'}),
            {'new_password1': 'NuevaPass456!', 'new_password2': 'NuevaPass456!'},
        )
        self.assertRedirects(response, reverse('password_reset_complete'))

        login_ok = self.client.login(username='user_reset', password='NuevaPass456!')
        self.assertTrue(login_ok)


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

    def test_extender_suscripcion_con_ciclo_anual_extiende_365_dias(self):
        Plan.objects.create(nombre="Básico", precio_mensual=5000, precio_anual=50000, orden=0)
        vet = Veterinaria.objects.create(nombre="Clinica Anual")
        vencimiento_original = vet.suscripcion.fecha_vencimiento

        super_user = User.objects.create_superuser(username="super_x", password="testpass123", email="s@s.com")
        self.client.force_login(super_user)

        response = self.client.post(reverse('usuarios:extender_suscripcion', args=[vet.suscripcion.id]), {'ciclo': 'ANUAL'})

        self.assertRedirects(response, reverse('usuarios:panel_suscripciones'))
        vet.suscripcion.refresh_from_db()
        self.assertEqual(vet.suscripcion.ciclo_facturacion, 'ANUAL')
        self.assertEqual(vet.suscripcion.estado, 'ACTIVA')
        self.assertEqual((vet.suscripcion.fecha_vencimiento - vencimiento_original).days, 365)

    def test_precio_ciclo_actual_refleja_el_ciclo_contratado(self):
        plan = Plan.objects.create(nombre="Básico", precio_mensual=5000, precio_anual=50000, orden=0)
        vet = Veterinaria.objects.create(nombre="Clinica Precio")
        suscripcion = vet.suscripcion

        self.assertEqual(suscripcion.precio_ciclo_actual, plan.precio_mensual)

        suscripcion.ciclo_facturacion = 'ANUAL'
        suscripcion.save()
        self.assertEqual(suscripcion.precio_ciclo_actual, plan.precio_anual)


class PagoSuscripcionTests(TestCase):
    """Los tests mockean el SDK de Mercado Pago: no hay credenciales reales disponibles
    en este entorno, pero se verifica que la vista arme la preferencia correctamente,
    redirija al checkout y que el webhook actualice la Suscripcion al recibir un pago
    aprobado, sin depender de la red."""

    def setUp(self):
        self.plan = Plan.objects.create(nombre="Básico", precio_mensual=5000, precio_anual=50000, orden=0)
        self.vet = Veterinaria.objects.create(nombre="Clinica Pagos")
        self.admin = User.objects.create_user(username="admin_pagos", password="testpass123")
        PerfilUsuario.objects.create(user=self.admin, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        self.client.force_login(self.admin)

    def test_sin_mp_configurado_muestra_aviso_en_vez_de_romper(self):
        with patch('apps.usuarios.views.mp_configurado', return_value=False):
            response = self.client.get(reverse('usuarios:iniciar_pago_suscripcion'))
        self.assertRedirects(response, reverse('usuarios:mi_suscripcion'))

    def test_con_mp_configurado_redirige_al_checkout(self):
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.crear_preferencia_pago', return_value={'init_point': 'https://mp.example/checkout/abc'}):
            response = self.client.get(reverse('usuarios:iniciar_pago_suscripcion'))
        self.assertRedirects(response, 'https://mp.example/checkout/abc', fetch_redirect_response=False)

    def test_ciclo_elegido_en_la_url_se_pasa_a_la_preferencia(self):
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.crear_preferencia_pago', return_value={'init_point': 'https://mp.example/checkout/abc'}) as mock_crear:
            self.client.get(reverse('usuarios:iniciar_pago_suscripcion'), {'ciclo': 'ANUAL'})

        self.assertEqual(mock_crear.call_args.kwargs.get('ciclo'), 'ANUAL')

    def test_un_ciclo_invalido_en_la_url_se_ignora(self):
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.crear_preferencia_pago', return_value={'init_point': 'https://mp.example/checkout/abc'}) as mock_crear:
            self.client.get(reverse('usuarios:iniciar_pago_suscripcion'), {'ciclo': 'QUINCENAL'})

        self.assertIsNone(mock_crear.call_args.kwargs.get('ciclo'))

    def test_error_al_crear_preferencia_no_rompe_la_vista(self):
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.crear_preferencia_pago', side_effect=Exception("timeout")):
            response = self.client.get(reverse('usuarios:iniciar_pago_suscripcion'))
        self.assertRedirects(response, reverse('usuarios:mi_suscripcion'))

    def test_webhook_de_pago_aprobado_extiende_la_suscripcion(self):
        suscripcion = self.vet.suscripcion
        vencimiento_original = suscripcion.fecha_vencimiento

        pago_mock = {'status': 'approved', 'external_reference': str(suscripcion.id)}
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.obtener_pago', return_value=pago_mock):
            response = self.client.get(reverse('usuarios:webhook_mercadopago'), {'type': 'payment', 'id': '123456'})

        self.assertEqual(response.status_code, 200)
        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, 'ACTIVA')
        self.assertEqual(suscripcion.ultimo_pago_registrado, timezone.now().date())
        self.assertGreater(suscripcion.fecha_vencimiento, vencimiento_original)

    def test_webhook_de_pago_anual_extiende_365_dias_y_guarda_el_ciclo(self):
        suscripcion = self.vet.suscripcion
        self.assertEqual(suscripcion.ciclo_facturacion, 'MENSUAL')
        vencimiento_original = suscripcion.fecha_vencimiento

        pago_mock = {
            'status': 'approved', 'external_reference': str(suscripcion.id),
            'metadata': {'ciclo': 'ANUAL'},
        }
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.obtener_pago', return_value=pago_mock):
            self.client.get(reverse('usuarios:webhook_mercadopago'), {'type': 'payment', 'id': '123457'})

        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.ciclo_facturacion, 'ANUAL')
        self.assertEqual((suscripcion.fecha_vencimiento - vencimiento_original).days, 365)

    def test_webhook_sin_metadata_de_ciclo_extiende_30_dias_por_compatibilidad(self):
        """Preferencias creadas antes de que existiera el campo metadata.ciclo no lo
        traen: debe seguir tratándose como mensual (30 días), no romper."""
        suscripcion = self.vet.suscripcion
        vencimiento_original = suscripcion.fecha_vencimiento

        pago_mock = {'status': 'approved', 'external_reference': str(suscripcion.id)}
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.obtener_pago', return_value=pago_mock):
            self.client.get(reverse('usuarios:webhook_mercadopago'), {'type': 'payment', 'id': '123458'})

        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.ciclo_facturacion, 'MENSUAL')
        self.assertEqual((suscripcion.fecha_vencimiento - vencimiento_original).days, 30)

    def test_webhook_de_pago_pendiente_no_modifica_la_suscripcion(self):
        suscripcion = self.vet.suscripcion
        estado_original = suscripcion.estado

        pago_mock = {'status': 'pending', 'external_reference': str(suscripcion.id)}
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.obtener_pago', return_value=pago_mock):
            self.client.get(reverse('usuarios:webhook_mercadopago'), {'type': 'payment', 'id': '999'})

        suscripcion.refresh_from_db()
        self.assertEqual(suscripcion.estado, estado_original)

    def test_webhook_ignora_notificaciones_que_no_son_de_pago(self):
        with patch('apps.usuarios.views.mp_configurado', return_value=True), \
             patch('apps.usuarios.views.obtener_pago') as mock_obtener:
            response = self.client.get(reverse('usuarios:webhook_mercadopago'), {'type': 'merchant_order', 'id': '1'})

        self.assertEqual(response.status_code, 200)
        mock_obtener.assert_not_called()


class EntrarADemoTests(TestCase):
    """El botón público 'Ver Demo en Vivo' debe loguear directo al admin de la
    veterinaria demo (creada por seed_demo) sin pedir usuario/clave."""

    def test_loguea_directamente_como_el_admin_de_la_veterinaria_demo(self):
        from apps.usuarios.management.commands.seed_demo import DEMO_VET_NOMBRE, DEMO_ADMIN_USERNAME

        vet_demo = Veterinaria.objects.create(nombre=DEMO_VET_NOMBRE)
        admin_demo = User.objects.create_user(username=DEMO_ADMIN_USERNAME, password="lo-que-sea")
        PerfilUsuario.objects.create(user=admin_demo, veterinaria=vet_demo, rol="ADMIN", is_approved=True)

        response = self.client.get(reverse('entrar_a_demo'), follow=True)

        self.assertEqual(response.wsgi_request.user, admin_demo)
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_sin_tenant_demo_creado_redirige_a_landing_con_error(self):
        response = self.client.get(reverse('entrar_a_demo'), follow=True)

        self.assertRedirects(response, reverse('landing'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_banner_de_demo_publica_aparece_dentro_del_dashboard(self):
        from apps.usuarios.management.commands.seed_demo import DEMO_VET_NOMBRE, DEMO_ADMIN_USERNAME

        vet_demo = Veterinaria.objects.create(nombre=DEMO_VET_NOMBRE)
        admin_demo = User.objects.create_user(username=DEMO_ADMIN_USERNAME, password="lo-que-sea")
        PerfilUsuario.objects.create(user=admin_demo, veterinaria=vet_demo, rol="ADMIN", is_approved=True)
        self.client.force_login(admin_demo)

        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, "demo pública")


class CrearPreferenciaPagoTests(TestCase):
    """Confirma que el precio enviado a Mercado Pago corresponde al ciclo elegido,
    mockeando el SDK (no hay credenciales reales en este entorno)."""

    def setUp(self):
        self.plan = Plan.objects.create(nombre="Básico", precio_mensual=5000, precio_anual=50000, orden=0)
        self.vet = Veterinaria.objects.create(nombre="Clinica Preferencia")
        self.suscripcion = self.vet.suscripcion

    def _mock_sdk(self):
        sdk = type('FakeSDK', (), {})()
        preferencias_creadas = []

        class FakePreferenceClient:
            def create(self, data):
                preferencias_creadas.append(data)
                return {'response': {'init_point': 'https://mp.example/checkout/abc'}}

        sdk.preference = lambda: FakePreferenceClient()
        return sdk, preferencias_creadas

    def test_ciclo_mensual_cobra_el_precio_mensual(self):
        from apps.usuarios.pagos import crear_preferencia_pago
        sdk, creadas = self._mock_sdk()

        with patch('apps.usuarios.pagos.get_sdk', return_value=sdk):
            crear_preferencia_pago(self.suscripcion, RequestFactory().get('/'), ciclo='MENSUAL')

        self.assertEqual(creadas[0]['items'][0]['unit_price'], 5000.0)
        self.assertEqual(creadas[0]['metadata']['ciclo'], 'MENSUAL')

    def test_ciclo_anual_cobra_el_precio_anual(self):
        from apps.usuarios.pagos import crear_preferencia_pago
        sdk, creadas = self._mock_sdk()

        with patch('apps.usuarios.pagos.get_sdk', return_value=sdk):
            crear_preferencia_pago(self.suscripcion, RequestFactory().get('/'), ciclo='ANUAL')

        self.assertEqual(creadas[0]['items'][0]['unit_price'], 50000.0)
        self.assertEqual(creadas[0]['metadata']['ciclo'], 'ANUAL')

    def test_sin_ciclo_explicito_usa_el_de_la_suscripcion(self):
        from apps.usuarios.pagos import crear_preferencia_pago
        sdk, creadas = self._mock_sdk()
        self.suscripcion.ciclo_facturacion = 'ANUAL'
        self.suscripcion.save()

        with patch('apps.usuarios.pagos.get_sdk', return_value=sdk):
            crear_preferencia_pago(self.suscripcion, RequestFactory().get('/'))

        self.assertEqual(creadas[0]['items'][0]['unit_price'], 50000.0)


class LandingPricingTests(TestCase):
    def test_muestra_el_precio_mensual_y_anual_del_plan_activo(self):
        Plan.objects.create(nombre="Profesional", precio_mensual=20000, precio_anual=200000, activo=True, orden=0)

        response = self.client.get(reverse('landing'))

        self.assertContains(response, '20000')
        self.assertContains(response, '200000')

    def test_sin_plan_activo_no_rompe_ni_muestra_la_seccion(self):
        response = self.client.get(reverse('landing'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="precios"')


class LandingLlamadoAContactoTests(TestCase):
    """El formulario de 'usuarios:registro' es para que el STAFF de una veterinaria YA
    dada de alta en el sistema se sume a su propia cuenta (el form obliga a elegir una
    veterinaria existente de un desplegable). No sirve como alta de un prospecto nuevo:
    lo expondría a la lista de clínicas ya registradas y no crea una Veterinaria nueva.
    Por eso los llamados a la acción públicos de la landing tienen que apuntar al
    formulario de contacto, no al de registro."""

    def test_ningun_cta_publico_de_la_landing_apunta_al_formulario_de_registro(self):
        response = self.client.get(reverse('landing'))

        self.assertNotContains(response, reverse('usuarios:registro'))

    def test_los_cta_principales_apuntan_al_formulario_de_contacto(self):
        Plan.objects.create(nombre="Profesional", precio_mensual=20000, precio_anual=200000, activo=True, orden=0)

        response = self.client.get(reverse('landing'))

        # 5 = el link "Contacto" del nav + los 4 botones de llamado a la acción
        # (Quiero Sumarme, Probar Gratis, y los dos "Empezar Ahora" de precios).
        self.assertContains(response, 'href="#contacto"', count=5)


class CambiarContrasenaTests(TestCase):
    """Cualquier usuario logueado (staff o cliente del Portal) puede cambiar su propia
    contraseña sin depender de un superusuario ni del flujo de 'olvidé mi contraseña'."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Password")
        self.staff = User.objects.create_user(username="staff_pw", password="ViejaClave123")
        PerfilUsuario.objects.create(user=self.staff, veterinaria=self.vet, rol="ADMIN", is_approved=True)

    def test_usuario_logueado_puede_cambiar_su_contrasena(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse('password_change'), {
            'old_password': 'ViejaClave123',
            'new_password1': 'NuevaClaveSegura456',
            'new_password2': 'NuevaClaveSegura456',
        })

        self.assertRedirects(response, reverse('password_change_done'))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password('NuevaClaveSegura456'))

    def test_no_cambia_si_la_contrasena_actual_es_incorrecta(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse('password_change'), {
            'old_password': 'ClaveIncorrecta',
            'new_password1': 'NuevaClaveSegura456',
            'new_password2': 'NuevaClaveSegura456',
        })

        self.assertEqual(response.status_code, 200)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password('ViejaClave123'))

    def test_sigue_logueado_despues_de_cambiar_la_contrasena(self):
        """Regresión típica de Django: si no se actualiza el session auth hash, cambiar
        la contraseña invalida la sesión actual y el usuario queda deslogueado."""
        self.client.force_login(self.staff)
        self.client.post(reverse('password_change'), {
            'old_password': 'ViejaClave123',
            'new_password1': 'NuevaClaveSegura456',
            'new_password2': 'NuevaClaveSegura456',
        })

        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)

    def test_usuario_anonimo_es_redirigido_a_login(self):
        response = self.client.get(reverse('password_change'))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('password_change')}")

    def test_link_para_cambiar_contrasena_aparece_en_el_menu(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, reverse('password_change'))
