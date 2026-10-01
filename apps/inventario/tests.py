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


class ExportarProductosCsvTests(TestCase):
    def test_exporta_csv_solo_con_los_productos_del_tenant_activo(self):
        vet_a = Veterinaria.objects.create(nombre="Clinica A")
        vet_b = Veterinaria.objects.create(nombre="Clinica B")

        user = User.objects.create_user(username="admin_export", password="testpass123")
        PerfilUsuario.objects.create(user=user, veterinaria=vet_a, rol="ADMIN", is_approved=True)

        Producto.objects.create(veterinaria=vet_a, nombre="Amoxicilina")
        Producto.objects.create(veterinaria=vet_b, nombre="Antiparasitario")

        self.client.force_login(user)
        response = self.client.get(reverse('inventario:exportar_productos_csv'))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode('utf-8-sig')
        self.assertIn('Amoxicilina', contenido)
        self.assertNotIn('Antiparasitario', contenido)


class PrecioVentaObligatorioTests(TestCase):
    """Regresión: se podían cargar productos con precio de venta $0 (ej. por dejar el
    campo en blanco o no completarlo), lo que rompe la venta real de ese producto."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Precios")
        self.user = User.objects.create_user(username="admin_precios", password="testpass123")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        self.client.force_login(self.user)

    def test_no_se_puede_crear_un_producto_con_precio_de_venta_cero(self):
        response = self.client.post(reverse('inventario:nuevo_producto'), {
            'nombre': 'Bastón suspensión', 'tipo': 'MEDICAMENTO',
            'stock_actual': '10', 'stock_minimo': '2',
            'precio_costo': '100', 'precio_venta': '0',
        })

        self.assertEqual(response.status_code, 200)  # re-renderiza el form con el error
        self.assertFalse(Producto.objects.filter(nombre='Bastón suspensión').exists())

    def test_se_puede_crear_un_producto_con_precio_de_venta_positivo(self):
        response = self.client.post(reverse('inventario:nuevo_producto'), {
            'nombre': 'Amoxicilina 500mg', 'tipo': 'MEDICAMENTO',
            'stock_actual': '10', 'stock_minimo': '2',
            'precio_costo': '100', 'precio_venta': '250',
        })

        self.assertRedirects(response, reverse('inventario:lista_productos'))
        self.assertTrue(Producto.objects.filter(nombre='Amoxicilina 500mg').exists())


class ProductoServicioTests(TestCase):
    """Un Servicio (consulta, cirugía, baño) no lleva control de stock: se puede
    cargar sin completar stock_actual/stock_minimo y nunca entra en las alertas
    de bajo stock ni en las sugerencias de compra."""

    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Servicios")
        self.user = User.objects.create_user(username="admin_servicios", password="testpass123")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        self.client.force_login(self.user)

    def test_se_puede_crear_un_servicio_sin_cargar_stock(self):
        response = self.client.post(reverse('inventario:nuevo_producto'), {
            'nombre': 'Consulta General', 'tipo': 'SERVICIO', 'precio_costo': '0', 'precio_venta': '3000',
        })

        self.assertRedirects(response, reverse('inventario:lista_productos'))
        servicio = Producto.objects.get(nombre='Consulta General')
        self.assertEqual(servicio.stock_actual, 0)
        self.assertEqual(servicio.stock_minimo, 0)
        self.assertFalse(servicio.bajo_stock)

    def test_un_servicio_nunca_cuenta_como_bajo_stock(self):
        servicio = Producto.objects.create(veterinaria=self.vet, nombre="Baño y Peluquería", tipo='SERVICIO', precio_venta=5000)

        response = self.client.get(reverse('inventario:lista_productos') + '?filtro=bajo_stock')

        self.assertEqual(response.context['cant_bajo_stock'], 0)
        self.assertNotIn(servicio, list(response.context['productos']))
