from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario, Veterinaria
from apps.inventario.models import Producto
from .models import Venta, DetalleVenta


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
