from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario, Veterinaria
from apps.inventario.models import Producto
from .models import Venta, DetalleVenta, CajaDiaria, GastoCaja


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
