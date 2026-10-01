from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario, Veterinaria
from apps.inventario.models import Producto
from .models import Venta, DetalleVenta, CajaDiaria, GastoCaja, CobroQR


class VentasTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.venta_a = Venta.objects.create(veterinaria=self.vet_a, total="100.00")
        self.venta_b = Venta.objects.create(veterinaria=self.vet_b, total="200.00")

        self.client.force_login(self.user_a)

    def test_lista_ventas_solo_incluye_las_de_su_veterinaria(self):
        response = self.client.get(reverse('ventas:lista_ventas'))

        ventas_listadas = list(response.context['ventas'])
        self.assertIn(self.venta_a, ventas_listadas)
        self.assertNotIn(self.venta_b, ventas_listadas)


class DetalleVentaStockTests(TestCase):
    """Regresión: DetalleVenta.save() descontaba el stock a mano y ADEMÁS creaba un
    MovimientoStock('SALIDA'), cuyo propio save() vuelve a descontar el mismo producto.
    Una venta de 3 unidades terminaba restando 6 del stock."""

    def test_una_venta_descuenta_el_stock_una_sola_vez(self):
        vet = Veterinaria.objects.create(nombre="Clinica Stock")
        producto = Producto.objects.create(veterinaria=vet, nombre="Amoxicilina", stock_actual=10)
        venta = Venta.objects.create(veterinaria=vet, total=0)

        DetalleVenta.objects.create(venta=venta, producto=producto, cantidad=3, precio_unitario=100, subtotal=300)

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 7)

    def test_registra_un_unico_movimiento_de_stock_por_venta(self):
        from apps.inventario.models import MovimientoStock

        vet = Veterinaria.objects.create(nombre="Clinica Stock 2")
        producto = Producto.objects.create(veterinaria=vet, nombre="Vacuna Quintuple", stock_actual=5)
        venta = Venta.objects.create(veterinaria=vet, total=0)

        DetalleVenta.objects.create(venta=venta, producto=producto, cantidad=2, precio_unitario=100, subtotal=200)

        self.assertEqual(MovimientoStock.objects.filter(producto=producto, tipo='SALIDA').count(), 1)


class RegistrarVentaCarritoTests(TestCase):
    """El Punto de Venta ahora admite varios ítems por venta (antes solo permitía
    un producto a la vez), Servicios sin stock (consulta, baño, cirugía) y un
    descuento porcentual aplicado sobre el total."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica POS")
        self.user = User.objects.create_user(username="admin_pos", password="testpass123")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        self.caja = CajaDiaria.objects.create(veterinaria=self.vet, estado='ABIERTA', monto_inicial=0)

        self.amoxicilina = Producto.objects.create(veterinaria=self.vet, nombre="Amoxicilina", stock_actual=10, precio_venta=500)
        self.vacuna = Producto.objects.create(veterinaria=self.vet, nombre="Vacuna Quintuple", stock_actual=5, precio_venta=1000)
        self.consulta = Producto.objects.create(veterinaria=self.vet, nombre="Consulta General", tipo='SERVICIO', precio_venta=3000)

        self.client.force_login(self.user)

    def test_vende_varios_items_en_una_sola_venta(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [self.amoxicilina.id, self.vacuna.id],
            'cantidad': [2, 1],
            'medio_pago': 'EFECTIVO',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        venta = Venta.objects.get()
        self.assertEqual(venta.detalles.count(), 2)
        self.assertEqual(venta.total, 2000)  # 2*500 + 1*1000

    def test_aplica_descuento_porcentual_al_total(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [self.amoxicilina.id],
            'cantidad': [2],
            'medio_pago': 'EFECTIVO',
            'descuento_porcentaje': '10',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        venta = Venta.objects.get()
        self.assertEqual(venta.descuento_porcentaje, 10)
        self.assertEqual(venta.subtotal_sin_descuento, 1000)
        self.assertEqual(venta.total, 900)  # 1000 - 10%

    def test_vende_un_servicio_sin_descontar_stock_ni_exigirlo(self):
        from apps.inventario.models import MovimientoStock

        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [self.consulta.id],
            'cantidad': [1],
            'medio_pago': 'EFECTIVO',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        venta = Venta.objects.get()
        self.assertEqual(venta.total, 3000)
        self.consulta.refresh_from_db()
        self.assertEqual(self.consulta.stock_actual, 0)  # nunca se tocó
        self.assertFalse(MovimientoStock.objects.filter(producto=self.consulta).exists())

    def test_stock_insuficiente_en_un_item_no_registra_ninguna_venta(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [self.amoxicilina.id, self.vacuna.id],
            'cantidad': [2, 999],
            'medio_pago': 'EFECTIVO',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Venta.objects.exists())
        self.amoxicilina.refresh_from_db()
        self.assertEqual(self.amoxicilina.stock_actual, 10)  # nada se descontó

    def test_qr_mp_rechaza_carrito_con_mas_de_un_item(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [self.amoxicilina.id, self.vacuna.id],
            'cantidad': [1, 1],
            'medio_pago': 'QR_MP',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CobroQR.objects.exists())
        self.assertFalse(Venta.objects.exists())

    def test_carrito_vacio_no_registra_venta(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [''], 'cantidad': [''], 'medio_pago': 'EFECTIVO',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Venta.objects.exists())

    def test_no_se_puede_vender_un_producto_de_otra_veterinaria(self):
        otra_vet = Veterinaria.objects.create(nombre="Otra Clinica")
        producto_ajeno = Producto.objects.create(veterinaria=otra_vet, nombre="Producto Ajeno", stock_actual=10, precio_venta=100)

        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [producto_ajeno.id], 'cantidad': [1], 'medio_pago': 'EFECTIVO',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Venta.objects.exists())

    def test_cobra_un_cargo_personalizado_sin_producto_de_catalogo(self):
        """Para cobrar algo puntual (ej. el costo variable de una Internación) sin
        tener que crear un Producto/Servicio en el catálogo para esa cifra única."""
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [''], 'cantidad': [''], 'medio_pago': 'EFECTIVO',
            'cargo_descripcion': 'Internación Firulais (5 días)', 'cargo_monto': '270000',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        venta = Venta.objects.get()
        self.assertEqual(venta.total, 270000)
        detalle = venta.detalles.get()
        self.assertIsNone(detalle.producto)
        self.assertEqual(detalle.descripcion_personalizada, 'Internación Firulais (5 días)')
        self.assertEqual(detalle.nombre_item, 'Internación Firulais (5 días)')

    def test_combina_items_de_catalogo_con_un_cargo_personalizado(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [self.amoxicilina.id], 'cantidad': [1], 'medio_pago': 'EFECTIVO',
            'cargo_descripcion': 'Consulta', 'cargo_monto': '3000',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        venta = Venta.objects.get()
        self.assertEqual(venta.detalles.count(), 2)
        self.assertEqual(venta.total, 3500)  # 500 (amoxicilina) + 3000 (cargo)

    def test_cargo_personalizado_sin_monto_no_registra_venta(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [''], 'cantidad': [''], 'medio_pago': 'EFECTIVO',
            'cargo_descripcion': 'Internación', 'cargo_monto': '0',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Venta.objects.exists())

    def test_qr_mp_no_admite_cargo_personalizado(self):
        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [''], 'cantidad': [''], 'medio_pago': 'QR_MP',
            'cargo_descripcion': 'Internación', 'cargo_monto': '270000',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CobroQR.objects.exists())
        self.assertFalse(Venta.objects.exists())


class ExportarVentasCsvTests(TestCase):
    def test_exporta_csv_solo_con_las_ventas_del_tenant_activo(self):
        vet_a = Veterinaria.objects.create(nombre="Clinica A")
        vet_b = Veterinaria.objects.create(nombre="Clinica B")

        user = User.objects.create_user(username="admin_export", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=vet_a, rol="ADMIN", is_approved=True)

        Venta.objects.create(veterinaria=vet_a, total=1500)
        Venta.objects.create(veterinaria=vet_b, total=9999)

        self.client.force_login(user)
        response = self.client.get(reverse('ventas:exportar_ventas_csv'))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode('utf-8-sig')
        self.assertIn('1500.00', contenido)
        self.assertNotIn('9999.00', contenido)


class GastoCajaTests(TestCase):
    """Un gasto/salida de efectivo (pago a un service, flete, etc.) debe descontarse
    del efectivo esperado de la caja, y respetar el aislamiento multi-tenant."""

    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.caja_a = CajaDiaria.objects.create(veterinaria=self.vet_a, monto_inicial=1000, estado='ABIERTA')
        self.caja_b = CajaDiaria.objects.create(veterinaria=self.vet_b, monto_inicial=500, estado='ABIERTA')

        self.client.force_login(self.user_a)

    def test_el_gasto_se_descuenta_del_efectivo_esperado(self):
        Venta.objects.create(veterinaria=self.vet_a, caja=self.caja_a, medio_pago='EFECTIVO', total=300)
        GastoCaja.objects.create(caja=self.caja_a, concepto="Pago al delivery", monto=200, usuario=self.user_a)

        self.caja_a.refresh_from_db()
        # 1000 inicial + 300 venta - 200 gasto = 1100
        self.assertEqual(self.caja_a.total_efectivo, 1100)
        self.assertEqual(self.caja_a.total_gastos, 200)

    def test_registrar_gasto_vista_crea_el_registro_en_la_caja_activa(self):
        response = self.client.post(reverse('ventas:registrar_gasto'), {
            'concepto': 'Compra de insumos de limpieza',
            'monto': '450.50',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        gasto = GastoCaja.objects.get(caja=self.caja_a)
        self.assertEqual(gasto.concepto, 'Compra de insumos de limpieza')
        self.assertEqual(str(gasto.monto), '450.50')
        self.assertEqual(gasto.usuario, self.user_a)

    def test_no_registra_gasto_sin_concepto_ni_monto_valido(self):
        self.client.post(reverse('ventas:registrar_gasto'), {'concepto': '', 'monto': '100'})
        self.client.post(reverse('ventas:registrar_gasto'), {'concepto': 'Algo', 'monto': '0'})

        self.assertEqual(GastoCaja.objects.filter(caja=self.caja_a).count(), 0)

    def test_sin_caja_abierta_no_se_puede_registrar_gasto(self):
        self.caja_a.estado = 'CERRADA'
        self.caja_a.save()

        response = self.client.post(reverse('ventas:registrar_gasto'), {'concepto': 'Algo', 'monto': '100'})

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        self.assertEqual(GastoCaja.objects.count(), 0)

    def test_lista_ventas_solo_muestra_los_gastos_de_la_caja_del_tenant_activo(self):
        GastoCaja.objects.create(caja=self.caja_a, concepto="Gasto A", monto=100)
        GastoCaja.objects.create(caja=self.caja_b, concepto="Gasto B", monto=999)

        response = self.client.get(reverse('ventas:lista_ventas'))

        gastos = list(response.context['gastos_caja_activa'])
        self.assertEqual(len(gastos), 1)
        self.assertEqual(gastos[0].concepto, "Gasto A")


class CerrarCajaArqueoTests(TestCase):
    """Regresión: el cierre de caja aceptaba cualquier diferencia de arqueo sin ningún
    aviso (una caja que esperaba $94.000 se cerró con $1.000.000 sin que nada lo marcara).
    Ahora una diferencia grande exige una justificación escrita antes de poder cerrar."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Arqueo")
        self.user = User.objects.create_user(username="admin_arqueo", password="testpass123")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        # monto_inicial=1000, sin ventas: total_efectivo esperado = 1000, tolerancia = max(2000, 1000*0.03) = 2000
        self.caja = CajaDiaria.objects.create(veterinaria=self.vet, monto_inicial=1000, estado='ABIERTA')
        self.client.force_login(self.user)

    def test_diferencia_dentro_de_tolerancia_cierra_sin_justificacion(self):
        response = self.client.post(reverse('ventas:cerrar_caja', args=[self.caja.id]), {
            'monto_final_real': '1500',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        self.caja.refresh_from_db()
        self.assertEqual(self.caja.estado, 'CERRADA')

    def test_diferencia_grande_sin_justificacion_no_cierra_la_caja(self):
        response = self.client.post(reverse('ventas:cerrar_caja', args=[self.caja.id]), {
            'monto_final_real': '1000000',
        })

        self.assertEqual(response.status_code, 200)  # re-renderiza el formulario, no redirige
        self.caja.refresh_from_db()
        self.assertEqual(self.caja.estado, 'ABIERTA')
        self.assertIsNone(self.caja.monto_final_real)

    def test_diferencia_grande_con_justificacion_si_cierra_y_la_guarda(self):
        response = self.client.post(reverse('ventas:cerrar_caja', args=[self.caja.id]), {
            'monto_final_real': '1000000',
            'observaciones': 'Error de tipeo al contar, se recontó y se confirmó el sobrante real.',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        self.caja.refresh_from_db()
        self.assertEqual(self.caja.estado, 'CERRADA')
        self.assertEqual(str(self.caja.monto_final_real), '1000000.00')
        self.assertIn('Error de tipeo', self.caja.observaciones)

    def test_diferencia_exacta_cierra_sin_problema(self):
        response = self.client.post(reverse('ventas:cerrar_caja', args=[self.caja.id]), {
            'monto_final_real': '1000',
        })

        self.assertRedirects(response, reverse('ventas:lista_ventas'))
        self.caja.refresh_from_db()
        self.assertEqual(self.caja.estado, 'CERRADA')


class CobroQRTests(TestCase):
    """Cobro por QR/Mercado Pago: la Venta real (y el descuento de stock) solo se
    crea cuando el pago queda aprobado, nunca antes, y usando la cuenta de MP propia
    de cada clínica."""

    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A", mp_access_token="TOKEN-CLINICA-A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")  # sin MP configurado

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.producto = Producto.objects.create(veterinaria=self.vet_a, nombre="Amoxicilina", stock_actual=10, precio_venta=500)
        self.caja = CajaDiaria.objects.create(veterinaria=self.vet_a, estado='ABIERTA', monto_inicial=0)

        self.client.force_login(self.user_a)

    @patch('apps.ventas.views.crear_preferencia_cobro')
    def test_elegir_qr_crea_un_cobro_pendiente_y_redirige_sin_tocar_stock(self, mock_crear_pref):
        mock_crear_pref.return_value = {'id': 'pref-123', 'init_point': 'https://mp.example.com/checkout/pref-123'}

        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [self.producto.id], 'cantidad': [2], 'medio_pago': 'QR_MP',
        })

        self.assertRedirects(response, 'https://mp.example.com/checkout/pref-123', fetch_redirect_response=False)
        cobro = CobroQR.objects.get(veterinaria=self.vet_a)
        self.assertEqual(cobro.estado, 'PENDIENTE')
        self.assertEqual(cobro.total, 1000)
        self.assertEqual(cobro.mp_preference_id, 'pref-123')

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 10)  # sin descontar todavía
        self.assertFalse(Venta.objects.exists())

    def test_qr_no_disponible_si_la_clinica_no_configuro_mercado_pago(self):
        producto_b = Producto.objects.create(veterinaria=self.vet_b, nombre="Meloxicam", stock_actual=5, precio_venta=300)
        caja_b = CajaDiaria.objects.create(veterinaria=self.vet_b, estado='ABIERTA', monto_inicial=0)
        user_b = User.objects.create_user(username="user_b", password="testpass123")
        PerfilUsuario.objects.create(user=user_b, veterinaria=self.vet_b, rol="ADMIN", is_approved=True)
        self.client.force_login(user_b)

        response = self.client.post(reverse('ventas:registrar_venta'), {
            'producto_id': [producto_b.id], 'cantidad': [1], 'medio_pago': 'QR_MP',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CobroQR.objects.exists())

    @patch('apps.ventas.views.obtener_pago_para')
    def test_pago_aprobado_crea_la_venta_y_descuenta_stock(self, mock_obtener_pago):
        cobro = CobroQR.objects.create(
            veterinaria=self.vet_a, caja=self.caja, producto=self.producto,
            cantidad=3, precio_unitario=500, total=1500,
        )
        mock_obtener_pago.return_value = {'status': 'approved', 'external_reference': str(cobro.id)}

        response = self.client.get(reverse('ventas:ver_cobro_qr', args=[cobro.id]) + '?payment_id=mp-999')

        self.assertEqual(response.status_code, 200)
        cobro.refresh_from_db()
        self.assertEqual(cobro.estado, 'APROBADO')
        self.assertIsNotNone(cobro.venta)
        self.assertEqual(cobro.venta.medio_pago, 'QR_MP')
        self.assertEqual(cobro.venta.total, 1500)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, 7)

    @patch('apps.ventas.views.obtener_pago_para')
    def test_pago_rechazado_no_crea_venta(self, mock_obtener_pago):
        cobro = CobroQR.objects.create(
            veterinaria=self.vet_a, caja=self.caja, producto=self.producto,
            cantidad=1, precio_unitario=500, total=500,
        )
        mock_obtener_pago.return_value = {'status': 'rejected', 'external_reference': str(cobro.id)}

        self.client.get(reverse('ventas:ver_cobro_qr', args=[cobro.id]) + '?payment_id=mp-888')

        cobro.refresh_from_db()
        self.assertEqual(cobro.estado, 'RECHAZADO')
        self.assertFalse(Venta.objects.exists())

    @patch('apps.ventas.views.obtener_pago_para')
    def test_confirmar_dos_veces_no_duplica_la_venta(self, mock_obtener_pago):
        cobro = CobroQR.objects.create(
            veterinaria=self.vet_a, caja=self.caja, producto=self.producto,
            cantidad=1, precio_unitario=500, total=500,
        )
        mock_obtener_pago.return_value = {'status': 'approved', 'external_reference': str(cobro.id)}

        self.client.get(reverse('ventas:ver_cobro_qr', args=[cobro.id]) + '?payment_id=mp-777')
        self.client.get(reverse('ventas:ver_cobro_qr', args=[cobro.id]) + '?payment_id=mp-777')

        self.assertEqual(Venta.objects.filter(cobro_qr=cobro).count(), 1)

    @patch('apps.ventas.views.obtener_pago_para')
    def test_external_reference_que_no_coincide_no_confirma_el_cobro(self, mock_obtener_pago):
        cobro = CobroQR.objects.create(
            veterinaria=self.vet_a, caja=self.caja, producto=self.producto,
            cantidad=1, precio_unitario=500, total=500,
        )
        mock_obtener_pago.return_value = {'status': 'approved', 'external_reference': '999999'}

        self.client.get(reverse('ventas:ver_cobro_qr', args=[cobro.id]) + '?payment_id=mp-666')

        cobro.refresh_from_db()
        self.assertEqual(cobro.estado, 'PENDIENTE')
        self.assertFalse(Venta.objects.exists())

    def test_no_puede_ver_el_cobro_qr_de_otra_veterinaria(self):
        cobro_b = CobroQR.objects.create(
            veterinaria=self.vet_b,
            caja=CajaDiaria.objects.create(veterinaria=self.vet_b, estado='ABIERTA'),
            producto=Producto.objects.create(veterinaria=self.vet_b, nombre="Otro", stock_actual=1),
            cantidad=1, precio_unitario=100, total=100,
        )

        response = self.client.get(reverse('ventas:ver_cobro_qr', args=[cobro_b.id]))

        self.assertEqual(response.status_code, 404)
