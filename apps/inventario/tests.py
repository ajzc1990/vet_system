from django.contrib.auth.models import User
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario, Veterinaria
from .models import Producto


class InventarioTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.producto_a = Producto.objects.create(veterinaria=self.vet_a, nombre="Amoxicilina")
        self.producto_b = Producto.objects.create(veterinaria=self.vet_b, nombre="Antiparasitario")

        self.client.force_login(self.user_a)

    def test_lista_productos_solo_incluye_los_de_su_veterinaria(self):
        response = self.client.get(reverse('inventario:lista_productos'))

        productos_listados = list(response.context['productos'])
        self.assertIn(self.producto_a, productos_listados)
        self.assertNotIn(self.producto_b, productos_listados)


class MovimientoStockTests(TestCase):
    def test_un_movimiento_de_entrada_suma_exactamente_la_cantidad_cargada(self):
        from .models import MovimientoStock

        vet = Veterinaria.objects.create(nombre="Clinica Movimientos")
        producto = Producto.objects.create(veterinaria=vet, nombre="Alimento", stock_actual=0)

        MovimientoStock.objects.create(producto=producto, tipo='ENTRADA', cantidad=15, motivo="Carga inicial")

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 15)


class CargarInventarioCommandTests(TestCase):
    """Regresión: el comando fijaba stock_actual=stock_inicial al crear el Producto y
    ADEMÁS registraba un MovimientoStock('ENTRADA') por esa misma cantidad, que vuelve a
    sumarla — el stock cargado terminaba siendo el doble del que se pensaba cargar."""

    def test_el_stock_final_coincide_con_el_movimiento_de_entrada_registrado(self):
        from django.core.management import call_command
        from .models import MovimientoStock

        Veterinaria.objects.create(nombre="Clinica Demo", activo=True)

        call_command('cargar_inventario')

        producto = Producto.objects.first()
        self.assertIsNotNone(producto)
        total_entradas = MovimientoStock.objects.filter(producto=producto, tipo='ENTRADA').aggregate(
            total=Sum('cantidad')
        )['total']
        self.assertEqual(producto.stock_actual, total_entradas)
