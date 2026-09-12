from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, Mascota
from apps.usuarios.models import PerfilUsuario, Veterinaria
from apps.historia_clinica.models import Internacion, ConsultaMedica
from apps.inventario.models import Producto


class ExpedienteMascotaTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        cliente_b = Cliente.objects.create(
            veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2",
        )
        self.mascota_b = Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")

        self.client.force_login(self.user_a)

    def test_no_puede_ver_el_expediente_de_una_mascota_de_otra_veterinaria(self):
        response = self.client.get(reverse('historia_clinica:expediente_mascota', args=[self.mascota_b.id]))

        self.assertEqual(response.status_code, 404)


class InternacionTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        cliente_a = Cliente.objects.create(
            veterinaria=self.vet_a, nombre="Carlos", apellido="Diaz", dni="111", telefono="1",
        )
        self.mascota_a = Mascota.objects.create(cliente=cliente_a, nombre="Rocky", especie="CANINO")

        cliente_b = Cliente.objects.create(
            veterinaria=self.vet_b, nombre="Ana", apellido="Gomez", dni="222", telefono="2",
        )
        mascota_b = Mascota.objects.create(cliente=cliente_b, nombre="Michi", especie="FELINO")
        self.internacion_b = Internacion.objects.create(
            veterinaria=self.vet_b,
            mascota=mascota_b,
            motivo_ingreso="Observación post-quirúrgica",
        )

        self.client.force_login(self.user_a)

    def test_no_puede_ver_la_internacion_de_una_mascota_de_otra_veterinaria(self):
        response = self.client.get(reverse('historia_clinica:detalle_internacion', args=[self.internacion_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_no_puede_registrar_evolucion_en_internacion_de_otra_veterinaria(self):
        response = self.client.post(
            reverse('historia_clinica:nueva_evolucion_internacion', args=[self.internacion_b.id]),
            {'estado_general': 'ESTABLE', 'notas': 'Intento de acceso indebido'},
        )
        self.assertEqual(response.status_code, 404)

    def test_no_puede_dar_de_alta_una_internacion_de_otra_veterinaria(self):
        response = self.client.post(
            reverse('historia_clinica:dar_alta_internacion', args=[self.internacion_b.id]),
            {'estado': 'ALTA', 'resumen_alta': 'Intento de acceso indebido'},
        )
        self.assertEqual(response.status_code, 404)
        self.internacion_b.refresh_from_db()
        self.assertEqual(self.internacion_b.estado, 'INTERNADO')

    def test_lista_internaciones_solo_muestra_pacientes_del_tenant_activo(self):
        internacion_a = Internacion.objects.create(
            veterinaria=self.vet_a,
            mascota=self.mascota_a,
            motivo_ingreso="Gastroenteritis severa",
        )
        response = self.client.get(reverse('historia_clinica:lista_internaciones'))

        self.assertEqual(response.status_code, 200)
        activas = list(response.context['internaciones_activas'])
        self.assertIn(internacion_a, activas)
        self.assertNotIn(self.internacion_b, activas)

    def test_puede_internar_y_ver_el_seguimiento_de_su_propia_mascota(self):
        response = self.client.post(
            reverse('historia_clinica:internar_mascota', args=[self.mascota_a.id]),
            {'motivo_ingreso': 'Requiere fluidoterapia y monitoreo', 'costo_dia_estadia': '10000.00'},
        )
        internacion = Internacion.objects.get(mascota=self.mascota_a)
        self.assertRedirects(response, reverse('historia_clinica:detalle_internacion', args=[internacion.id]))
        self.assertEqual(internacion.veterinaria, self.vet_a)


class DescuentoDeInventarioUnicaVezTests(TestCase):
    """Regresión: varias vistas creaban un MovimientoStock('SALIDA') y ADEMÁS restaban
    la cantidad a mano sobre el mismo objeto Producto en memoria; como MovimientoStock.save()
    ya hace ese descuento, el stock terminaba bajando el doble de lo vendido/usado."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Stock")
        self.user = User.objects.create_user(username="admin_stock", password="testpass123")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)

        cliente = Cliente.objects.create(veterinaria=self.vet, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        self.mascota = Mascota.objects.create(cliente=cliente, nombre="Firulais", especie="CANINO")

        self.client.force_login(self.user)

    def test_nueva_consulta_descuenta_el_insumo_una_sola_vez(self):
        producto = Producto.objects.create(veterinaria=self.vet, nombre="Meloxicam", stock_actual=10)

        self.client.post(reverse('historia_clinica:nueva_consulta', args=[self.mascota.id]), {
            'motivo_consulta': 'Control', 'diagnostico': 'Sano', 'tratamiento': 'Ninguno',
            'producto_inventario': producto.id, 'cantidad_insumo': 2,
        })

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 8)

    def test_registrar_vacuna_descuenta_el_insumo_una_sola_vez(self):
        producto = Producto.objects.create(veterinaria=self.vet, nombre="Vacuna Quintuple", tipo="VACUNA", stock_actual=10)

        self.client.post(reverse('historia_clinica:registrar_vacuna', args=[self.mascota.id]), {
            'nombre_vacuna': 'Quíntuple', 'fecha_aplicacion': '2026-01-01',
            'producto_inventario': producto.id,
        })

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 9)

    def test_registrar_desparasitacion_descuenta_el_insumo_una_sola_vez(self):
        producto = Producto.objects.create(veterinaria=self.vet, nombre="Simparica", stock_actual=10)

        self.client.post(reverse('historia_clinica:registrar_desparasitacion', args=[self.mascota.id]), {
            'tipo': 'INTERNA', 'producto': 'Simparica', 'fecha_aplicacion': '2026-01-01',
            'producto_inventario': producto.id,
        })

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 9)

    def test_nueva_evolucion_internacion_descuenta_el_insumo_una_sola_vez(self):
        from apps.historia_clinica.models import Internacion

        producto = Producto.objects.create(veterinaria=self.vet, nombre="Meloxicam", stock_actual=10)
        internacion = Internacion.objects.create(veterinaria=self.vet, mascota=self.mascota, motivo_ingreso="Observación")

        self.client.post(reverse('historia_clinica:nueva_evolucion_internacion', args=[internacion.id]), {
            'estado_general': 'ESTABLE', 'notas': 'Paciente estable',
            'producto_inventario': producto.id, 'cantidad_insumo': 3,
        })

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 7)


class ConsultaMedicaActualizaPesoTests(TestCase):
    """Regresión: el save() chequeaba hasattr(self.mascota, 'peso'), un campo que no
    existe (es peso_kg) — la sincronización de peso nunca se ejecutaba."""

    def test_guardar_una_consulta_con_peso_actualiza_el_peso_de_la_mascota(self):
        vet = Veterinaria.objects.create(nombre="Clinica Peso")
        cliente = Cliente.objects.create(veterinaria=vet, nombre="Juan", apellido="Perez", dni="111", telefono="1")
        mascota = Mascota.objects.create(cliente=cliente, nombre="Firulais", especie="CANINO", peso_kg=10)

        ConsultaMedica.objects.create(
            mascota=mascota, motivo_consulta="Control", diagnostico="Sano", tratamiento="Ninguno",
            peso_actual_kg=12.5,
        )

        mascota.refresh_from_db()
        self.assertEqual(mascota.peso_kg, 12.5)
