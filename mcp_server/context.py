"""Identidad del usuario autenticado por token, disponible para las herramientas
MCP durante el procesamiento de UNA request HTTP (la auth corre en cada POST al
endpoint MCP, no solo al conectar: ver auth.py). Usamos contextvars en vez de
pasarlo como parámetro porque las tools las invoca el SDK de MCP, no nosotros."""
import contextvars

usuario_actual = contextvars.ContextVar('usuario_actual', default=None)
veterinaria_actual = contextvars.ContextVar('veterinaria_actual', default=None)


class NoAutenticado(Exception):
    """La herramienta se llamó sin pasar por el middleware de autenticación
    (no debería poder pasar nunca en producción; es un resguardo)."""


def veterinaria_o_error():
    vet = veterinaria_actual.get()
    user = usuario_actual.get()
    if user is None:
        raise NoAutenticado("No se encontró un usuario autenticado.")
    if vet is None and not user.is_superuser:
        raise NoAutenticado("Tu usuario no tiene una veterinaria asignada.")
    return vet
