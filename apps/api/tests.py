from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.clientes.models import Cliente, Mascota
from apps.inventario.models import Producto
from apps.usuarios.models import PerfilUsuario, Veterinaria


class ObtenerTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vet = Veterinaria.objects.create(nombre="Clinica API")

    def test_usuario_aprobado_obtiene_token(self):
        user = User.objects.create_user(username="aprobado", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet, rol="ADMIN", is_approved=True)

        response = self.client.post(reverse('api:obtener_token'), {'username': 'aprobado', 'password': 'testpass123'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)

    def test_usuario_no_aprobado_no_obtiene_token(self):
        user = User.objects.create_user(username="pendiente", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet, rol="ADMIN", is_approved=False)

        response = self.client.post(reverse('api:obtener_token'), {'username': 'pendiente', 'password': 'testpass123'})

        self.assertEqual(response.status_code, 403)

    def test_credenciales_invalidas_no_obtienen_token(self):
        response = self.client.post(reverse('api:obtener_token'), {'username': 'nadie', 'password': 'incorrecta'})
        self.assertEqual(response.status_code, 401)


class ApiTenantIsolationTests(TestCase):
    """Confirma que la API REST respeta el mismo aislamiento por tenant que el resto
    del sistema, tanto por sesión como por token."""

    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)
        self.token_a = Token.objects.create(user=self.user_a)

        self.cliente_a = Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        self.cliente_b = Cliente.objects.create(veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2")
        Mascota.objects.create(cliente=self.cliente_a, nombre="Firulais", especie="CANINO")
        Mascota.objects.create(cliente=self.cliente_b, nombre="Michi", especie="FELINO")

        Producto.objects.create(veterinaria=self.vet_a, nombre="Amoxicilina")
        Producto.objects.create(veterinaria=self.vet_b, nombre="Antiparasitario")

    def test_lista_clientes_por_token_solo_incluye_los_del_tenant_del_token(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:cliente-list'))

        nombres = [c['apellido'] for c in response.data['results']]
        self.assertIn('Perez', nombres)
        self.assertNotIn('Gomez', nombres)

    def test_lista_mascotas_solo_incluye_las_del_tenant(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:mascota-list'))

        nombres = [m['nombre'] for m in response.data['results']]
        self.assertIn('Firulais', nombres)
        self.assertNotIn('Michi', nombres)

    def test_lista_productos_solo_incluye_los_del_tenant(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:producto-list'))

        nombres = [p['nombre'] for p in response.data['results']]
        self.assertIn('Amoxicilina', nombres)
        self.assertNotIn('Antiparasitario', nombres)

    def test_sin_autenticacion_no_permite_listar(self):
        client = APIClient()
        response = client.get(reverse('api:cliente-list'))
        # DRF devuelve 403 (no 401) porque SessionAuthentication -el primer
        # authenticator configurado- no expone un WWW-Authenticate header.
        self.assertEqual(response.status_code, 403)

    def test_no_se_puede_acceder_al_detalle_de_un_cliente_de_otro_tenant(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')

        response = client.get(reverse('api:cliente-detail', args=[self.cliente_b.id]))

        self.assertEqual(response.status_code, 404)

    def test_usuario_no_aprobado_no_puede_usar_la_api_aunque_tenga_token(self):
        user_pendiente = User.objects.create_user(username="pendiente", password="testpass123")
        PerfilUsuario.objects.create(user=user_pendiente, veterinaria=self.vet_a, rol="ADMIN", is_approved=False)
        token_pendiente = Token.objects.create(user=user_pendiente)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token_pendiente.key}')
        response = client.get(reverse('api:cliente-list'))

        self.assertEqual(response.status_code, 403)


class ApiAppMovilTests(TestCase):
    """Endpoints de escritura y de ficha que usa la app móvil del staff."""

    def setUp(self):
        from apps.turnos.models import Turno, Veterinario
        from django.utils import timezone

        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.medico = User.objects.create_user(username="medico", password="testpass123")
        PerfilUsuario.objects.create(user=self.medico, veterinaria=self.vet_a, rol="VET", is_approved=True)
        self.veterinario = Veterinario.objects.create(
            veterinaria=self.vet_a, usuario=self.medico, nombre="Laura", apellido="Diaz", matricula="M1")

        self.recepcion = User.objects.create_user(username="recepcion", password="testpass123")
        PerfilUsuario.objects.create(user=self.recepcion, veterinaria=self.vet_a, rol="RECEPCION", is_approved=True)

        cliente_a = Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        cliente_b = Cliente.objects.create(veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2")
        self.mascota_a = Mascota.objects.create(cliente=cliente_a, nombre="Firulais", especie="CANINO")
        self.mascota_b = Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")

        self.turno = Turno.objects.create(
            veterinaria=self.vet_a, mascota=self.mascota_a, fecha_hora=timezone.now(), estado='CONFIRMADO')

    def _cliente(self, user):
        client = APIClient()
        token = Token.objects.create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return client

    def _consulta(self, **extra):
        return {'motivo_consulta': 'Vómitos', 'diagnostico': 'Gastritis', 'tratamiento': 'Dieta blanda', **extra}

    def test_yo_devuelve_rol_y_si_puede_atender(self):
        response = self._cliente(self.recepcion).get(reverse('api:yo'))
        self.assertEqual(response.data['rol'], 'RECEPCION')
        self.assertFalse(response.data['puede_atender'])
        self.assertEqual(response.data['veterinaria'], 'Clinica A')

    def test_veterinario_registra_consulta_y_completa_el_turno(self):
        response = self._cliente(self.medico).post(
            reverse('api:mascota-consultas', args=[self.mascota_a.id]),
            self._consulta(turno=self.turno.id, peso_actual_kg='12.5'), format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['veterinario'], self.veterinario.id)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.estado, 'COMPLETADO')
        self.mascota_a.refresh_from_db()
        self.assertEqual(str(self.mascota_a.peso_kg), '12.50')

    def test_recepcion_no_puede_registrar_consultas(self):
        response = self._cliente(self.recepcion).post(
            reverse('api:mascota-consultas', args=[self.mascota_a.id]), self._consulta(), format='json')
        self.assertEqual(response.status_code, 403)

    def test_no_se_puede_registrar_consulta_en_mascota_de_otro_tenant(self):
        response = self._cliente(self.medico).post(
            reverse('api:mascota-consultas', args=[self.mascota_b.id]), self._consulta(), format='json')
        self.assertEqual(response.status_code, 404)

    def test_receta_sin_medicamentos_es_rechazada(self):
        response = self._cliente(self.medico).post(
            reverse('api:mascota-recetas', args=[self.mascota_a.id]),
            {'diagnostico': 'Otitis', 'items': [{'medicamento': '  '}]}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_receta_con_items_aparece_en_la_historia(self):
        client = self._cliente(self.medico)
        response = client.post(
            reverse('api:mascota-recetas', args=[self.mascota_a.id]),
            {'diagnostico': 'Otitis', 'items': [{'medicamento': 'Otomax', 'dosis': '3 gotas'}]}, format='json')
        self.assertEqual(response.status_code, 201)

        historia = client.get(reverse('api:mascota-historia', args=[self.mascota_a.id]))
        self.assertEqual(historia.data['recetas'][0]['items'][0]['medicamento'], 'Otomax')

    def test_agenda_filtrada_por_fecha_y_cambio_de_estado(self):
        client = self._cliente(self.recepcion)
        from django.utils import timezone
        hoy = timezone.localtime(self.turno.fecha_hora).date().isoformat()

        agenda = client.get(reverse('api:turno-list'), {'fecha': hoy})
        self.assertEqual([t['id'] for t in agenda.data['results']], [self.turno.id])

        response = client.post(reverse('api:turno-estado', args=[self.turno.id]), {'estado': 'CANCELADO'})
        self.assertEqual(response.data['estado'], 'CANCELADO')

        invalido = client.post(reverse('api:turno-estado', args=[self.turno.id]), {'estado': 'VOLANDO'})
        self.assertEqual(invalido.status_code, 400)

    def test_busqueda_de_mascotas_por_apellido_del_tutor(self):
        response = self._cliente(self.medico).get(reverse('api:mascota-list'), {'q': 'pere'})
        self.assertEqual([m['nombre'] for m in response.data['results']], ['Firulais'])

    def test_cerrar_sesion_revoca_el_token(self):
        client = self._cliente(self.medico)
        self.assertEqual(client.post(reverse('api:cerrar_sesion')).status_code, 204)
        self.assertFalse(Token.objects.filter(user=self.medico).exists())


class ApiAppMovilEtapaATests(TestCase):
    """Turnos, clientes/mascotas, estudios, internaciones, PDFs y desparasitaciones desde la app."""

    def setUp(self):
        from apps.turnos.models import Veterinario

        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.medico = User.objects.create_user(username="medico", password="testpass123")
        PerfilUsuario.objects.create(user=self.medico, veterinaria=self.vet_a, rol="VET", is_approved=True)
        self.veterinario = Veterinario.objects.create(
            veterinaria=self.vet_a, usuario=self.medico, nombre="Laura", apellido="Diaz", matricula="M1")
        self.veterinario_b = Veterinario.objects.create(
            veterinaria=self.vet_b, nombre="Otro", apellido="Medico", matricula="M2")

        self.recepcion = User.objects.create_user(username="recepcion", password="testpass123")
        PerfilUsuario.objects.create(user=self.recepcion, veterinaria=self.vet_a, rol="RECEPCION", is_approved=True)

        self.cliente_a = Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        self.cliente_b = Cliente.objects.create(veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2")
        self.mascota_a = Mascota.objects.create(cliente=self.cliente_a, nombre="Firulais", especie="CANINO")
        self.mascota_b = Mascota.objects.create(cliente=self.cliente_b, nombre="Michi", especie="FELINO")

    def _cliente(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.get_or_create(user=user)[0].key}')
        return client

    # --- Turnos ---------------------------------------------------------------

    def test_recepcion_agenda_un_turno_en_su_veterinaria(self):
        from apps.turnos.models import Turno
        response = self._cliente(self.recepcion).post(reverse('api:turno-list'), {
            'mascota': self.mascota_a.id, 'veterinario': self.veterinario.id,
            'fecha_hora': '2026-10-01T10:30:00-03:00', 'motivo': 'Control',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['estado'], 'PENDIENTE')
        self.assertEqual(Turno.objects.get(pk=response.data['id']).veterinaria, self.vet_a)

    def test_no_se_puede_agendar_turno_para_mascota_o_veterinario_de_otra_clinica(self):
        client = self._cliente(self.recepcion)
        otra_mascota = client.post(reverse('api:turno-list'), {
            'mascota': self.mascota_b.id, 'fecha_hora': '2026-10-01T10:30:00-03:00'}, format='json')
        self.assertEqual(otra_mascota.status_code, 400)
        self.assertIn('mascota', otra_mascota.data)

        otro_vet = client.post(reverse('api:turno-list'), {
            'mascota': self.mascota_a.id, 'veterinario': self.veterinario_b.id,
            'fecha_hora': '2026-10-01T10:30:00-03:00'}, format='json')
        self.assertEqual(otro_vet.status_code, 400)
        self.assertIn('veterinario', otro_vet.data)

    def test_reprogramar_turno_con_patch(self):
        from django.utils import timezone
        from apps.turnos.models import Turno
        turno = Turno.objects.create(veterinaria=self.vet_a, mascota=self.mascota_a, fecha_hora=timezone.now())
        response = self._cliente(self.recepcion).patch(
            reverse('api:turno-detail', args=[turno.id]), {'motivo': 'Vacunación'}, format='json')
        self.assertEqual(response.status_code, 200)
        turno.refresh_from_db()
        self.assertEqual(turno.motivo, 'Vacunación')

    def test_no_se_expone_borrado_por_api(self):
        response = self._cliente(self.medico).delete(reverse('api:cliente-detail', args=[self.cliente_a.id]))
        self.assertEqual(response.status_code, 405)

    def test_lista_de_veterinarios_solo_de_la_propia_clinica(self):
        response = self._cliente(self.recepcion).get(reverse('api:veterinario-list'))
        self.assertEqual([v['id'] for v in response.data['results']], [self.veterinario.id])

    # --- Clientes y mascotas --------------------------------------------------

    def test_alta_de_cliente_queda_en_la_veterinaria_del_usuario(self):
        response = self._cliente(self.recepcion).post(reverse('api:cliente-list'), {
            'nombre': 'Carla', 'apellido': 'Suarez', 'dni': '333', 'telefono': '381555'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Cliente.objects.get(dni='333').veterinaria, self.vet_a)

    def test_alta_de_mascota_valida_que_el_cliente_sea_de_la_clinica(self):
        client = self._cliente(self.recepcion)
        ok = client.post(reverse('api:mascota-list'), {
            'cliente': self.cliente_a.id, 'nombre': 'Luna', 'especie': 'FELINO', 'sexo': 'H'}, format='json')
        self.assertEqual(ok.status_code, 201, ok.data)

        ajeno = client.post(reverse('api:mascota-list'), {
            'cliente': self.cliente_b.id, 'nombre': 'Intrusa', 'especie': 'FELINO'}, format='json')
        self.assertEqual(ajeno.status_code, 400)
        self.assertFalse(Mascota.objects.filter(nombre='Intrusa').exists())

    # --- Estudios -------------------------------------------------------------

    def _imagen(self, nombre='foto.jpg'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(nombre, b'fake-jpeg-bytes', content_type='image/jpeg')

    def test_veterinario_sube_foto_de_estudio(self):
        import shutil
        import tempfile
        from django.test import override_settings
        media = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media):
                response = self._cliente(self.medico).post(
                    reverse('api:mascota-estudios', args=[self.mascota_a.id]),
                    {'titulo': 'Herida pata', 'tipo_estudio': 'OTRO', 'archivo': self._imagen()},
                    format='multipart')
                self.assertEqual(response.status_code, 201, response.data)
                self.assertTrue(response.data['es_imagen'])
                self.assertTrue(response.data['archivo'].startswith('http'))
        finally:
            shutil.rmtree(media, ignore_errors=True)

    def test_estudio_con_formato_no_permitido_es_rechazado(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self._cliente(self.medico).post(
            reverse('api:mascota-estudios', args=[self.mascota_a.id]),
            {'titulo': 'x', 'archivo': SimpleUploadedFile('virus.exe', b'MZ')}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_recepcion_no_puede_subir_estudios(self):
        response = self._cliente(self.recepcion).post(
            reverse('api:mascota-estudios', args=[self.mascota_a.id]),
            {'titulo': 'x', 'archivo': self._imagen()}, format='multipart')
        self.assertEqual(response.status_code, 403)

    # --- Internaciones --------------------------------------------------------

    def test_ciclo_completo_de_internacion(self):
        client = self._cliente(self.medico)
        ingreso = client.post(reverse('api:mascota-internar', args=[self.mascota_a.id]), {
            'motivo_ingreso': 'Gastroenteritis', 'box': '3', 'veterinario_responsable': self.veterinario.id,
        }, format='json')
        self.assertEqual(ingreso.status_code, 201, ingreso.data)
        internacion_id = ingreso.data['id']

        doble = client.post(reverse('api:mascota-internar', args=[self.mascota_a.id]),
                            {'motivo_ingreso': 'Otra'}, format='json')
        self.assertEqual(doble.status_code, 400)

        evolucion = client.post(reverse('api:internacion-evoluciones', args=[internacion_id]), {
            'estado_general': 'MEJORANDO', 'notas': 'Come bien', 'peso_kg': '8.40'}, format='json')
        self.assertEqual(evolucion.status_code, 201, evolucion.data)
        self.mascota_a.refresh_from_db()
        self.assertEqual(str(self.mascota_a.peso_kg), '8.40')

        activas = client.get(reverse('api:internacion-list'), {'activas': 1})
        self.assertEqual([i['id'] for i in activas.data['results']], [internacion_id])

        sin_resumen = client.post(reverse('api:internacion-alta', args=[internacion_id]),
                                  {'estado': 'ALTA'}, format='json')
        self.assertEqual(sin_resumen.status_code, 400)

        alta = client.post(reverse('api:internacion-alta', args=[internacion_id]),
                           {'estado': 'ALTA', 'resumen_alta': 'Alta con dieta'}, format='json')
        self.assertEqual(alta.status_code, 200, alta.data)
        self.assertEqual(alta.data['estado'], 'ALTA')
        self.assertIsNotNone(alta.data['fecha_alta_real'])

        cerrada = client.post(reverse('api:internacion-evoluciones', args=[internacion_id]),
                              {'notas': 'tarde'}, format='json')
        self.assertEqual(cerrada.status_code, 400)

    def test_no_se_ve_la_internacion_de_otra_clinica(self):
        from apps.historia_clinica.models import Internacion
        ajena = Internacion.objects.create(mascota=self.mascota_b, motivo_ingreso='x')
        response = self._cliente(self.medico).get(reverse('api:internacion-detail', args=[ajena.id]))
        self.assertEqual(response.status_code, 404)

    # --- PDFs, desparasitaciones, IA -----------------------------------------

    def test_pdf_de_receta_y_carnet_por_token(self):
        from apps.historia_clinica.models import ItemReceta, Receta
        receta = Receta.objects.create(mascota=self.mascota_a, diagnostico='Otitis')
        ItemReceta.objects.create(receta=receta, medicamento='Otomax')
        client = self._cliente(self.recepcion)

        pdf = client.get(reverse('api:receta-pdf', args=[receta.id]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

        carnet = client.get(reverse('api:mascota-carnet-pdf', args=[self.mascota_a.id]))
        self.assertEqual(carnet.status_code, 200)
        self.assertTrue(carnet.content.startswith(b'%PDF'))

    def test_pdf_de_receta_de_otra_clinica_da_404(self):
        from apps.historia_clinica.models import Receta
        ajena = Receta.objects.create(mascota=self.mascota_b)
        response = self._cliente(self.medico).get(reverse('api:receta-pdf', args=[ajena.id]))
        self.assertEqual(response.status_code, 404)

    def test_registrar_desparasitacion(self):
        response = self._cliente(self.medico).post(
            reverse('api:mascota-desparasitaciones', args=[self.mascota_a.id]),
            {'tipo': 'INTERNA', 'producto': 'Total Full', 'fecha_aplicacion': '2026-09-24'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.mascota_a.desparasitaciones.count(), 1)

    def test_resumen_ia_deshabilitado_responde_503(self):
        from django.test import override_settings
        with override_settings(IA_RESUMENES_ENABLED=False):
            response = self._cliente(self.medico).post(reverse('api:mascota-resumen-ia', args=[self.mascota_a.id]))
        self.assertEqual(response.status_code, 503)
