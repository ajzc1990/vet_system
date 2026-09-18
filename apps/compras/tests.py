from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilUsuario, Veterinaria
from apps.inventario.models import Producto, MovimientoStock
from .models import Proveedor, Compra, DetalleCompra


class ProveedoresTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.prov_a = Proveedor.objects.create(veterinaria=self.vet_a, nombre="Distribuidora A")
        self.prov_b = Proveedor.objects.create(veterinaria=self.vet_b, nombre="Distribuidora B")

        self.client.force_login(self.user_a)

    def test_lista_proveedores_solo_incluye_los_de_su_veterinaria(self):
        response = self.client.get(reverse('compras:lista_proveedores'))

        proveedores_listados = list(response.context['proveedores'])
        self.assertIn(self.prov_a, proveedores_listados)
        self.assertNotIn(self.prov_b, proveedores_listados)

    def test_no_puede_editar_un_proveedor_de_otra_veterinaria(self):
        response = self.client.get(reverse('compras:editar_proveedor', args=[self.prov_b.id]))
        self.assertEqual(response.status_code, 404)


class ComprasTenantIsolationTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        prov_a = Proveedor.objects.create(veterinaria=self.vet_a, nombre="Distribuidora A")
        prov_b = Proveedor.objects.create(veterinaria=self.vet_b, nombre="Distribuidora B")

        self.compra_a = Compra.objects.create(veterinaria=self.vet_a, proveedor=prov_a, total=100)
        self.compra_b = Compra.objects.create(veterinaria=self.vet_b, proveedor=prov_b, total=200)

        self.client.force_login(self.user_a)

    def test_lista_compras_solo_incluye_las_de_su_veterinaria(self):
        response = self.client.get(reverse('compras:lista_compras'))

        compras_listadas = list(response.context['compras'])
        self.assertIn(self.compra_a, compras_listadas)
        self.assertNotIn(self.compra_b, compras_listadas)

    def test_no_puede_ver_el_detalle_de_una_compra_de_otra_veterinaria(self):
        response = self.client.get(reverse('compras:detalle_compra', args=[self.compra_b.id]))
        self.assertEqual(response.status_code, 404)


class DetalleCompraStockTests(TestCase):
    def test_una_compra_suma_el_stock_una_sola_vez(self):
        vet = Veterinaria.objects.create(nombre="Clinica Stock")
        proveedor = Proveedor.objects.create(veterinaria=vet, nombre="Distribuidora")
        producto = Producto.objects.create(veterinaria=vet, nombre="Amoxicilina", stock_actual=10, precio_costo=50)
        compra = Compra.objects.create(veterinaria=vet, proveedor=proveedor, total=0)

        DetalleCompra.objects.create(compra=compra, producto=producto, cantidad=5, precio_unitario=80)

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 15)

    def test_registra_un_unico_movimiento_de_entrada_por_linea(self):
        vet = Veterinaria.objects.create(nombre="Clinica Stock 2")
        proveedor = Proveedor.objects.create(veterinaria=vet, nombre="Distribuidora")
        producto = Producto.objects.create(veterinaria=vet, nombre="Vacuna Quintuple", stock_actual=5)
        compra = Compra.objects.create(veterinaria=vet, proveedor=proveedor, total=0)

        DetalleCompra.objects.create(compra=compra, producto=producto, cantidad=2, precio_unitario=100)

        self.assertEqual(MovimientoStock.objects.filter(producto=producto, tipo='ENTRADA').count(), 1)

    def test_actualiza_el_costo_de_referencia_del_producto(self):
        vet = Veterinaria.objects.create(nombre="Clinica Stock 3")
        proveedor = Proveedor.objects.create(veterinaria=vet, nombre="Distribuidora")
        producto = Producto.objects.create(veterinaria=vet, nombre="Alimento", stock_actual=0, precio_costo=100)
        compra = Compra.objects.create(veterinaria=vet, proveedor=proveedor, total=0)

        DetalleCompra.objects.create(compra=compra, producto=producto, cantidad=1, precio_unitario=150)

        producto.refresh_from_db()
        self.assertEqual(producto.precio_costo, 150)


class RegistrarCompraViewTests(TestCase):
    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clinica Compras")
        self.user = User.objects.create_user(username="admin_compras", password="testpass123")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)

        self.proveedor = Proveedor.objects.create(veterinaria=self.vet, nombre="Distribuidora", activo=True)
        self.producto_a = Producto.objects.create(veterinaria=self.vet, nombre="Amoxicilina", stock_actual=0)
        self.producto_b = Producto.objects.create(veterinaria=self.vet, nombre="Vacuna Quintuple", stock_actual=0)

        self.client.force_login(self.user)

    def _formset_data(self, filas):
        data = {
            'form-TOTAL_FORMS': '6',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        }
        for i in range(6):
            if i < len(filas):
                producto, cantidad, precio = filas[i]
                data[f'form-{i}-producto'] = producto.id
                data[f'form-{i}-cantidad'] = cantidad
                data[f'form-{i}-precio_unitario'] = precio
            else:
                data[f'form-{i}-producto'] = ''
                data[f'form-{i}-cantidad'] = ''
                data[f'form-{i}-precio_unitario'] = ''
        return data

    def test_registra_compra_con_varias_lineas_y_suma_stock(self):
        data = {
            'proveedor': self.proveedor.id,
            'numero_factura': 'A-0001',
            'observaciones': '',
            **self._formset_data([
                (self.producto_a, 10, '50.00'),
                (self.producto_b, 4, '200.00'),
            ]),
        }
        response = self.client.post(reverse('compras:registrar_compra'), data)

        self.assertEqual(response.status_code, 302)
        compra = Compra.objects.get(proveedor=self.proveedor)
        self.assertEqual(compra.detalles.count(), 2)
        self.assertEqual(compra.total, 10 * 50 + 4 * 200)

        self.producto_a.refresh_from_db()
        self.producto_b.refresh_from_db()
        self.assertEqual(self.producto_a.stock_actual, 10)
        self.assertEqual(self.producto_b.stock_actual, 4)

    def test_rechaza_compra_sin_ninguna_linea_completa(self):
        data = {
            'proveedor': self.proveedor.id,
            'numero_factura': '',
            'observaciones': '',
            **self._formset_data([]),
        }
        response = self.client.post(reverse('compras:registrar_compra'), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Compra.objects.count(), 0)

    def test_precarga_proveedor_y_producto_desde_query_params(self):
        url = (
            reverse('compras:registrar_compra')
            + f'?proveedor={self.proveedor.id}&producto={self.producto_a.id}&cantidad=15&precio=80.00'
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('proveedor'), str(self.proveedor.id))
        primera_fila = response.context['formset'][0]
        self.assertEqual(primera_fila.initial.get('producto'), str(self.producto_a.id))
        self.assertEqual(primera_fila.initial.get('cantidad'), '15')


class SugerenciasCompraTests(TestCase):
    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clinica A")
        self.vet_b = Veterinaria.objects.create(nombre="Clinica B")

        self.user_a = User.objects.create_user(username="user_a_sug", password="testpass123")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)

        self.proveedor = Proveedor.objects.create(veterinaria=self.vet_a, nombre="Distribuidora")

        self.bajo_stock = Producto.objects.create(
            veterinaria=self.vet_a, nombre="Amoxicilina", stock_actual=1, stock_minimo=5, precio_costo=100
        )
        Producto.objects.create(veterinaria=self.vet_a, nombre="Vacuna Quintuple", stock_actual=20, stock_minimo=5)
        Producto.objects.create(veterinaria=self.vet_b, nombre="Alimento", stock_actual=0, stock_minimo=10)

        self.client.force_login(self.user_a)

    def test_solo_lista_productos_con_stock_bajo_de_su_veterinaria(self):
        response = self.client.get(reverse('compras:sugerencias'))

        productos_sugeridos = [s['producto'] for s in response.context['sugerencias']]
        self.assertIn(self.bajo_stock, productos_sugeridos)
        self.assertEqual(len(productos_sugeridos), 1)

    def test_sugiere_el_ultimo_proveedor_usado_para_ese_producto(self):
        # Cantidad chica para que, aun después de sumar stock, el producto siga
        # por debajo de su mínimo y no desaparezca de las sugerencias.
        compra = Compra.objects.create(veterinaria=self.vet_a, proveedor=self.proveedor, total=0)
        DetalleCompra.objects.create(compra=compra, producto=self.bajo_stock, cantidad=1, precio_unitario=100)

        response = self.client.get(reverse('compras:sugerencias'))

        sugerencia = response.context['sugerencias'][0]
        self.assertEqual(sugerencia['proveedor'], self.proveedor)

    def test_sin_historial_de_compra_no_sugiere_proveedor(self):
        response = self.client.get(reverse('compras:sugerencias'))

        sugerencia = response.context['sugerencias'][0]
        self.assertIsNone(sugerencia['proveedor'])
