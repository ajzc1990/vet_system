"""Tests del servidor MCP. La prueba más importante de todas es
test_una_clinica_jamas_ve_datos_de_otra: crea dos clínicas con productos,
pacientes y turnos de nombres parecidos a propósito, y confirma que cada
token SOLO ve los datos de su propia clínica en las 7 herramientas.

Usa TransactionTestCase (no TestCase) porque las tools corren en un hilo
aparte vía sync_to_async: con TestCase (que envuelve todo en una transacción)
ese hilo puede no ver los datos creados en setUp. TransactionTestCase hace
commits de verdad, así que no tiene ese problema -a costa de ser más lento."""
import contextlib
import json

from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from starlette.testclient import TestClient

from apps.clientes.models import Cliente, Mascota
from apps.historia_clinica.models import ConsultaMedica, RegistroVacuna
from apps.inventario.models import Categoria, Producto
from apps.turnos.models import Turno
from apps.usuarios.models import PerfilUsuario, Veterinaria

from .server import build_app


@contextlib.contextmanager
def _sesion_mcp(token):
    """TestClient con la sesión MCP ya inicializada (handshake initialize +
    notifications/initialized) para un token dado. Tiene que entrar como
    context manager: así es como Starlette dispara el lifespan de la app
    (mcp.session_manager.run()) -sin eso, toda llamada a una tool revienta
    con "Task group is not initialized"."""
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(build_app(), headers=headers, base_url="http://localhost") as client:
        r = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tests", "version": "1.0"}},
        })
        client.headers["mcp-session-id"] = r.headers.get("mcp-session-id")
        client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        yield client


def _llamar_tool(client, nombre, argumentos):
    r = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": nombre, "arguments": argumentos},
    })
    # La respuesta viaja como Server-Sent Events: una línea "data: {...}".
    linea_data = next(l for l in r.text.splitlines() if l.startswith("data: "))
    sobre = json.loads(linea_data[len("data: "):])
    contenido = sobre["result"]["content"][0]["text"]
    return json.loads(contenido) if contenido.strip().startswith(("{", "[")) else contenido


class AislamientoMultiTenantTests(TransactionTestCase):
    """Dos clínicas con datos de nombres parecidos a propósito, para que una
    búsqueda amplia detecte de inmediato si se filtra algo de la otra."""

    def setUp(self):
        self.vet_a = Veterinaria.objects.create(nombre="Clínica A (MCP test)")
        self.vet_b = Veterinaria.objects.create(nombre="Clínica B (MCP test)")

        self.user_a = User.objects.create_user(username="mcp_user_a", password="x")
        PerfilUsuario.objects.create(user=self.user_a, veterinaria=self.vet_a, rol="ADMIN", is_approved=True)
        self.token_a = Token.objects.create(user=self.user_a).key

        self.user_b = User.objects.create_user(username="mcp_user_b", password="x")
        PerfilUsuario.objects.create(user=self.user_b, veterinaria=self.vet_b, rol="ADMIN", is_approved=True)
        self.token_b = Token.objects.create(user=self.user_b).key

        cat_a = Categoria.objects.create(veterinaria=self.vet_a, nombre="General")
        cat_b = Categoria.objects.create(veterinaria=self.vet_b, nombre="General")
        self.producto_a = Producto.objects.create(
            veterinaria=self.vet_a, nombre="Pipeta Antipulgas Compartida", categoria=cat_a,
            tipo="OTRO", stock_actual=3, stock_minimo=10, precio_venta=1000,
            fecha_vencimiento=timezone.localdate() + timezone.timedelta(days=5),
        )
        self.producto_b = Producto.objects.create(
            veterinaria=self.vet_b, nombre="Pipeta Antipulgas Compartida", categoria=cat_b,
            tipo="OTRO", stock_actual=99, stock_minimo=5, precio_venta=500,
        )

        self.cliente_a = Cliente.objects.create(veterinaria=self.vet_a, nombre="Juan", apellido="Pérez", dni="111", telefono="381111")
        self.cliente_b = Cliente.objects.create(veterinaria=self.vet_b, nombre="Juan", apellido="Pérez", dni="222", telefono="381222")
        self.mascota_a = Mascota.objects.create(cliente=self.cliente_a, nombre="Toby", especie="CANINO")
        self.mascota_b = Mascota.objects.create(cliente=self.cliente_b, nombre="Toby", especie="CANINO")

        ConsultaMedica.objects.create(veterinaria=self.vet_a, mascota=self.mascota_a, fecha_hora=timezone.now(), motivo_consulta="Consulta secreta A", diagnostico="Dx A", tratamiento="Tto A")
        ConsultaMedica.objects.create(veterinaria=self.vet_b, mascota=self.mascota_b, fecha_hora=timezone.now(), motivo_consulta="Consulta secreta B", diagnostico="Dx B", tratamiento="Tto B")
        RegistroVacuna.objects.create(veterinaria=self.vet_a, mascota=self.mascota_a, nombre_vacuna="Antirrábica", fecha_aplicacion=timezone.localdate())
        RegistroVacuna.objects.create(veterinaria=self.vet_b, mascota=self.mascota_b, nombre_vacuna="Antirrábica", fecha_aplicacion=timezone.localdate())

        self.turno_a = Turno.objects.create(veterinaria=self.vet_a, mascota=self.mascota_a, fecha_hora=timezone.now(), motivo="Turno A")
        self.turno_b = Turno.objects.create(veterinaria=self.vet_b, mascota=self.mascota_b, fecha_hora=timezone.now(), motivo="Turno B")

    def tearDown(self):
        User.objects.filter(username__in=["mcp_user_a", "mcp_user_b"]).delete()
        Veterinaria.objects.filter(nombre__in=["Clínica A (MCP test)", "Clínica B (MCP test)"]).delete()

    def test_buscar_productos_no_mezcla_clinicas(self):
        with _sesion_mcp(self.token_a) as cliente:
            resultado = _llamar_tool(cliente, "buscar_productos", {"query": "Pipeta"})

        ids = [p["id"] for p in resultado["productos"]]
        self.assertIn(self.producto_a.id, ids)
        self.assertNotIn(self.producto_b.id, ids)

    def test_consultar_stock_no_mezcla_clinicas(self):
        with _sesion_mcp(self.token_b) as cliente_b:
            resultado = _llamar_tool(cliente_b, "consultar_stock", {"nombre_producto": "Pipeta"})

        self.assertEqual(len(resultado["productos"]), 1)
        self.assertEqual(resultado["productos"][0]["id"], self.producto_b.id)
        self.assertEqual(resultado["productos"][0]["stock_actual"], 99)

    def test_productos_por_vencer_no_mezcla_clinicas(self):
        with _sesion_mcp(self.token_a) as cliente_a:
            resultado = _llamar_tool(cliente_a, "productos_por_vencer", {"dias": 30})

        ids = [p["id"] for p in resultado["productos"]]
        self.assertIn(self.producto_a.id, ids)
        self.assertNotIn(self.producto_b.id, ids)

    def test_buscar_paciente_no_mezcla_clinicas_aunque_se_llamen_igual(self):
        with _sesion_mcp(self.token_a) as cliente_a:
            resultado = _llamar_tool(cliente_a, "buscar_paciente", {"query": "Toby"})

        self.assertEqual(len(resultado["pacientes"]), 1)
        self.assertEqual(resultado["pacientes"][0]["id"], self.mascota_a.id)

    def test_historial_paciente_rechaza_mascota_de_otra_clinica(self):
        """El caso más peligroso: pedir el historial de un paciente de la OTRA
        clínica por ID. Tiene que decir 'no encontrado', nunca devolver los datos."""
        with _sesion_mcp(self.token_a) as cliente_a:
            resultado = _llamar_tool(cliente_a, "historial_paciente", {"mascota_id": self.mascota_b.id})

        self.assertFalse(resultado["encontrado"])

    def test_historial_paciente_propio_si_funciona(self):
        with _sesion_mcp(self.token_a) as cliente_a:
            resultado = _llamar_tool(cliente_a, "historial_paciente", {"mascota_id": self.mascota_a.id})

        self.assertTrue(resultado["encontrado"])
        self.assertEqual(len(resultado["consultas"]), 1)
        self.assertEqual(resultado["consultas"][0]["motivo"], "Consulta secreta A")

    def test_buscar_cliente_no_mezcla_clinicas_aunque_se_llamen_igual(self):
        with _sesion_mcp(self.token_b) as cliente_b:
            resultado = _llamar_tool(cliente_b, "buscar_cliente", {"query": "Pérez"})

        ids = [c["id"] for c in resultado["clientes"]]
        self.assertIn(self.cliente_b.id, ids)
        self.assertNotIn(self.cliente_a.id, ids)

    def test_turnos_no_mezcla_clinicas(self):
        hoy = timezone.localdate().isoformat()
        with _sesion_mcp(self.token_a) as cliente_a:
            resultado = _llamar_tool(cliente_a, "turnos", {"fecha_desde": hoy, "fecha_hasta": hoy})

        ids = [t["id"] for t in resultado["turnos"]]
        self.assertIn(self.turno_a.id, ids)
        self.assertNotIn(self.turno_b.id, ids)


class AutenticacionTests(TransactionTestCase):
    def setUp(self):
        self.vet = Veterinaria.objects.create(nombre="Clínica Auth (MCP test)")
        self.user = User.objects.create_user(username="mcp_auth_user", password="x")
        PerfilUsuario.objects.create(user=self.user, veterinaria=self.vet, rol="ADMIN", is_approved=True)
        self.token = Token.objects.create(user=self.user).key

    def tearDown(self):
        User.objects.filter(username="mcp_auth_user").delete()
        Veterinaria.objects.filter(nombre="Clínica Auth (MCP test)").delete()

    def test_sin_token_rechaza(self):
        client = TestClient(build_app(), base_url="http://localhost")
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r.status_code, 401)

    def test_token_invalido_rechaza(self):
        client = TestClient(build_app(), headers={"Authorization": "Bearer esto-no-existe"}, base_url="http://localhost")
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r.status_code, 401)

    def test_cuenta_no_aprobada_rechaza(self):
        PerfilUsuario.objects.filter(user=self.user).update(is_approved=False)
        client = TestClient(build_app(), headers={"Authorization": f"Bearer {self.token}"}, base_url="http://localhost")
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r.status_code, 401)

    def test_token_valido_pasa(self):
        with TestClient(build_app(), headers={"Authorization": f"Bearer {self.token}"}, base_url="http://localhost") as client:
            r = client.post("/mcp", json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tests", "version": "1.0"}},
            })
        self.assertEqual(r.status_code, 200)
