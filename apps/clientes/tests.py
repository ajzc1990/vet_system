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

        self.user_a = User.objects.create_user(username="vet_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="VET", is_approved=True)

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


class ModalRapidoProximaDosisTests(TestCase):
    """Regresión: agregar_vacuna/agregar_desparasitacion (los modales de carga rápida)
    buscaban hasattr(RegistroVacuna, 'proxima_dosis') / 'fecha_proxima' / 'proximo_refuerzo',
    ninguno de los cuales existe (el campo real es fecha_proxima_dosis): la fecha de
    refuerzo cargada por el usuario nunca se guardaba."""

    def setUp(self):
        vet = Veterinaria.objects.create(nombre="Clinica Modal")
        user = User.objects.create_user(username="admin_modal", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=vet, rol="ADMIN", is_approved=True)
        cliente = Cliente.objects.create(veterinaria=vet, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        self.mascota = Mascota.objects.create(cliente=cliente, nombre="Firulais", especie="CANINO")
        self.client.force_login(user)

    def test_agregar_vacuna_guarda_la_proxima_dosis(self):
        self.client.post(reverse('clientes:agregar_vacuna', args=[self.mascota.id]), {
            'nombre_vacuna': 'Antirrábica', 'fecha_aplicacion': '2026-01-01', 'proxima_dosis': '2027-01-01',
        })
        vacuna = self.mascota.vacunas.get()
        self.assertEqual(str(vacuna.fecha_proxima_dosis), '2027-01-01')

    def test_agregar_desparasitacion_guarda_la_proxima_dosis(self):
        self.client.post(reverse('clientes:agregar_desparasitacion', args=[self.mascota.id]), {
            'producto': 'Simparica', 'fecha_aplicacion': '2026-01-01', 'proxima_dosis': '2026-04-01',
        })
        registro = self.mascota.desparasitaciones.get()
        self.assertEqual(str(registro.fecha_proxima_dosis), '2026-04-01')


class AsignacionVeterinarioDetalleHistoriaClinicaTests(TestCase):
    """La consulta creada desde clientes:detalle_historia_clinica debe asignar
    automáticamente el Veterinario vinculado al usuario logueado, si existe uno."""

    def test_asigna_el_veterinario_vinculado_al_usuario_logueado(self):
        from apps.turnos.models import Veterinario

        vet = Veterinaria.objects.create(nombre="Clinica Asignacion")
        user = User.objects.create_user(username="vet_logueado", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=vet, rol="VET", is_approved=True)
        veterinario = Veterinario.objects.create(veterinaria=vet, usuario=user, nombre="Sofía", apellido="Herrera", matricula="MP-1")

        cliente = Cliente.objects.create(veterinaria=vet, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        mascota = Mascota.objects.create(cliente=cliente, nombre="Firulais", especie="CANINO")

        self.client.force_login(user)
        self.client.post(reverse('clientes:detalle_historia_clinica', args=[mascota.id]), {
            'motivo_consulta': 'Control', 'diagnostico': 'Sano', 'tratamiento': 'Ninguno',
        })

        consulta = mascota.consultas.get()
        self.assertEqual(consulta.veterinario, veterinario)


class ExportarClientesCsvTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        vet_b = Veterinaria.objects.create(nombre="Clinica B")

        user = User.objects.create_user(username="admin_export", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        Cliente.objects.create(veterinaria=vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2")

        self.client.force_login(user)

    def test_exporta_csv_solo_con_los_clientes_del_tenant_activo(self):
        response = self.client.get(reverse('clientes:exportar_clientes_csv'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        contenido = response.content.decode('utf-8-sig')
        self.assertIn('Perez', contenido)
        self.assertNotIn('Gomez', contenido)


class RecepcionNoPuedeEscribirHistoriaClinicaTests(TestCase):
    """Antes, estas acciones solo estaban ocultas en la plantilla (el botón no se
    mostraba), pero un RECEPCION que entrara directo a la URL igual podía cargar/editar/
    borrar historia clínica. Ahora también están bloqueadas del lado del servidor."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Permisos")
        self.recepcion = User.objects.create_user(username="recepcion_permisos", password="testpass123")
        PerfilUsuario.objects.create(user=self.recepcion, veterinaria=self.vet, rol="RECEPCION", is_approved=True)

        cliente = Cliente.objects.create(veterinaria=self.vet, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        self.mascota = Mascota.objects.create(cliente=cliente, nombre="Firulais", especie="CANINO")
        self.consulta = ConsultaMedica.objects.create(
            mascota=self.mascota, motivo_consulta="Control", diagnostico="Sano", tratamiento="Ninguno",
        )
        self.vacuna = RegistroVacuna.objects.create(
            mascota=self.mascota, nombre_vacuna="Antirrábica", fecha_aplicacion=timezone.now().date(),
        )
        self.desparasitacion = RegistroDesparasitacion.objects.create(
            mascota=self.mascota, producto="Simparica", fecha_aplicacion=timezone.now().date(),
        )

        self.client.force_login(self.recepcion)

    def test_no_puede_registrar_una_consulta(self):
        response = self.client.post(reverse('clientes:detalle_historia_clinica', args=[self.mascota.id]), {
            'motivo_consulta': 'Chequeo', 'diagnostico': 'Sano', 'tratamiento': 'Ninguno',
        })

        self.assertRedirects(response, reverse('clientes:detalle_historia_clinica', args=[self.mascota.id]))
        self.assertEqual(self.mascota.consultas.count(), 1)  # solo la creada en setUp

    def test_no_puede_editar_ni_eliminar_una_consulta(self):
        response_editar = self.client.get(reverse('clientes:editar_consulta', args=[self.consulta.id]))
        response_eliminar = self.client.post(reverse('clientes:eliminar_consulta', args=[self.consulta.id]))

        self.assertRedirects(response_editar, reverse('dashboard:index'))
        self.assertRedirects(response_eliminar, reverse('dashboard:index'))
        self.assertTrue(ConsultaMedica.objects.filter(pk=self.consulta.id).exists())

    def test_no_puede_agregar_ni_eliminar_una_vacuna(self):
        self.client.post(reverse('clientes:agregar_vacuna', args=[self.mascota.id]), {
            'nombre_vacuna': 'Rabia', 'fecha_aplicacion': '2026-01-01',
        })
        self.assertEqual(self.mascota.vacunas.count(), 1)  # no se agregó la nueva

        response_eliminar = self.client.post(reverse('clientes:eliminar_vacuna', args=[self.vacuna.id]))
        self.assertRedirects(response_eliminar, reverse('dashboard:index'))
        self.assertTrue(RegistroVacuna.objects.filter(pk=self.vacuna.id).exists())

    def test_no_puede_agregar_ni_eliminar_una_desparasitacion(self):
        self.client.post(reverse('clientes:agregar_desparasitacion', args=[self.mascota.id]), {
            'producto': 'Bravecto', 'fecha_aplicacion': '2026-01-01',
        })
        self.assertEqual(self.mascota.desparasitaciones.count(), 1)  # no se agregó la nueva

        response_eliminar = self.client.post(reverse('clientes:eliminar_desparasitacion', args=[self.desparasitacion.id]))
        self.assertRedirects(response_eliminar, reverse('dashboard:index'))
        self.assertTrue(RegistroDesparasitacion.objects.filter(pk=self.desparasitacion.id).exists())

    def test_si_puede_ver_la_historia_clinica(self):
        """La restricción es solo de escritura: recepción sigue pudiendo consultar."""
        response = self.client.get(reverse('clientes:detalle_historia_clinica', args=[self.mascota.id]))
        self.assertEqual(response.status_code, 200)
