"""Servidor MCP de VeterSystem. Corre como proceso propio (no dentro de Gunicorn:
el SDK de MCP necesita un servidor async, y Gunicorn hoy sirve la app principal en
modo síncrono) — ver docker-compose.yml, servicio 'mcp'. Se conecta a la misma base
de datos y reusa los mismos modelos/reglas de Django que el resto de VeterSystem.

Arrancar en local: uvicorn mcp_server.server:app --host 0.0.0.0 --port 8001
"""
from . import django_setup  # noqa: F401  (django.setup() antes de tocar cualquier modelo)

import os

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount
from contextlib import asynccontextmanager

from . import tools

from .auth import AutenticacionPorTokenMiddleware  # noqa: E402


def build_app():
    """Arma una instancia nueva de punta a punta (MCPServer + app Starlette).
    Es una función, en vez de construirlo una sola vez a nivel de módulo,
    porque StreamableHTTPSessionManager.run() -el lifespan- solo se puede
    llamar UNA vez por instancia: los tests (que levantan la app una vez por
    cada test method) necesitan poder pedir una instancia nueva por test."""
    mcp = MCPServer("VeterSystem")
    mcp.tool()(tools.buscar_productos)
    mcp.tool()(tools.consultar_stock)
    mcp.tool()(tools.productos_por_vencer)
    mcp.tool()(tools.buscar_paciente)
    mcp.tool()(tools.historial_paciente)
    mcp.tool()(tools.buscar_cliente)
    mcp.tool()(tools.turnos)
    mcp.tool()(tools.ventas)
    mcp.tool()(tools.estado_caja)
    mcp.tool()(tools.compras)
    mcp.tool()(tools.buscar_proveedores)
    mcp.tool()(tools.internaciones)
    mcp.tool()(tools.equipo_veterinarios)
    mcp.tool()(tools.datos_veterinaria)

    hosts_permitidos = [h.strip() for h in os.environ.get('MCP_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]
    seguridad = TransportSecuritySettings(
        allowed_hosts=hosts_permitidos,
        allowed_origins=[f"https://{h}" for h in hosts_permitidos if h not in ('localhost', '127.0.0.1')],
    )
    mcp_asgi_app = mcp.streamable_http_app(transport_security=seguridad)

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    app = Starlette(routes=[Mount('/', app=mcp_asgi_app)], lifespan=lifespan)
    app.add_middleware(AutenticacionPorTokenMiddleware)
    return app


# Instancia única para producción: uvicorn mcp_server.server:app la importa UNA
# sola vez y la deja correr todo el proceso, así que el límite de un solo run() no molesta acá.
app = build_app()
