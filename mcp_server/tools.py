"""Las herramientas de sólo lectura del servidor MCP. Cada una reusa el mismo patrón de filtrado
por tenant que ya usan los ViewSets de apps.api (tenant_field), nunca una consulta
nueva "desde cero": así cualquier corrección futura al aislamiento multi-tenant
sigue aplicando acá también. Ver mcp_server/context.py para cómo se resuelve el
usuario/veterinaria autenticado."""
import functools
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.db.models import Q
from django.utils import timezone

from .context import veterinaria_o_error, usuario_actual, NoAutenticado

LIMITE_RESULTADOS = 20


def _es_superuser_global(vet):
    user = usuario_actual.get()
    return bool(user and user.is_superuser and vet is None)


def _manejar_errores(func):
    """Convierte NoAutenticado y cualquier excepción inesperada en un diccionario
    de error en español en vez de una traza cruda (nada de detalles internos).
    functools.wraps es clave acá: sin preservar la firma original, el SDK de MCP
    arma el esquema de la tool a partir de *args/**kwargs del wrapper en vez de
    los parámetros reales (query, dias, mascota_id, etc.)."""
    @functools.wraps(func)
    async def envoltura(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NoAutenticado as e:
            return {"error": str(e)}
        except Exception:
            return {"error": "Ocurrió un error inesperado procesando la consulta. Intentá de nuevo."}
    return envoltura


@sync_to_async
def _buscar_productos_sync(query):
    from apps.inventario.models import Producto
    vet = veterinaria_o_error()

    qs = Producto.objects.select_related('categoria').all()
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    if query:
        qs = qs.filter(Q(nombre__icontains=query) | Q(categoria__nombre__icontains=query))

    total = qs.count()
    productos = list(qs.order_by('nombre')[:LIMITE_RESULTADOS])
    return {
        "total_encontrado": total,
        "mostrando": len(productos),
        "productos": [
            {
                "id": p.id,
                "nombre": p.nombre,
                "categoria": p.categoria.nombre if p.categoria else None,
                "tipo": p.get_tipo_display(),
                "stock_actual": p.stock_actual,
                "stock_minimo": p.stock_minimo,
                "stock_bajo": (not p.es_servicio) and p.stock_actual <= p.stock_minimo,
                "precio_venta": str(p.precio_venta),
                "vencimiento": p.fecha_vencimiento.isoformat() if p.fecha_vencimiento else None,
            }
            for p in productos
        ],
    }


@_manejar_errores
async def buscar_productos(query: str = "") -> dict:
    """Busca productos/insumos del catálogo de tu clínica por nombre o categoría.
    Dejá 'query' vacío para listar los primeros productos sin filtrar."""
    return await _buscar_productos_sync(query)


@sync_to_async
def _consultar_stock_sync(nombre_producto):
    from apps.inventario.models import Producto
    vet = veterinaria_o_error()

    qs = Producto.objects.select_related('categoria').all()
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    qs = qs.filter(nombre__icontains=nombre_producto)

    productos = list(qs.order_by('nombre')[:LIMITE_RESULTADOS])
    if not productos:
        return {"encontrado": False, "mensaje": f"No encontré ningún producto que coincida con '{nombre_producto}'."}

    return {
        "encontrado": True,
        "productos": [
            {
                "id": p.id,
                "nombre": p.nombre,
                "stock_actual": p.stock_actual,
                "stock_minimo": p.stock_minimo,
                "stock_bajo": (not p.es_servicio) and p.stock_actual <= p.stock_minimo,
                "unidad": "no aplica (es un servicio)" if p.es_servicio else "unidades",
            }
            for p in productos
        ],
    }


@_manejar_errores
async def consultar_stock(nombre_producto: str) -> dict:
    """Consulta el stock actual de uno o más productos por nombre (ej: 'pipeta antipulgas'),
    y si está por debajo del stock mínimo configurado."""
    return await _consultar_stock_sync(nombre_producto)


@sync_to_async
def _productos_por_vencer_sync(dias):
    from apps.inventario.models import Producto
    vet = veterinaria_o_error()

    hoy = timezone.localdate()
    limite = hoy + timedelta(days=dias)
    qs = Producto.objects.select_related('categoria').exclude(tipo='SERVICIO').filter(
        fecha_vencimiento__isnull=False, fecha_vencimiento__lte=limite,
    )
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)

    total = qs.count()
    productos = list(qs.order_by('fecha_vencimiento')[:LIMITE_RESULTADOS])
    return {
        "dias_consultados": dias,
        "total_encontrado": total,
        "mostrando": len(productos),
        "productos": [
            {
                "id": p.id,
                "nombre": p.nombre,
                "stock_actual": p.stock_actual,
                "vencimiento": p.fecha_vencimiento.isoformat(),
                "ya_vencido": p.fecha_vencimiento < hoy,
                "dias_restantes": (p.fecha_vencimiento - hoy).days,
            }
            for p in productos
        ],
    }


@_manejar_errores
async def productos_por_vencer(dias: int = 30) -> dict:
    """Lista productos cuyo vencimiento cae dentro de los próximos N días (default 30),
    incluyendo los que ya vencieron. Útil para planificar reposición o retirar del catálogo."""
    return await _productos_por_vencer_sync(dias)


@sync_to_async
def _buscar_paciente_sync(query):
    from apps.clientes.models import Mascota
    vet = veterinaria_o_error()

    qs = Mascota.objects.select_related('cliente').filter(cliente__activo=True)
    if not _es_superuser_global(vet):
        qs = qs.filter(cliente__veterinaria=vet)
    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) | Q(especie__icontains=query) | Q(raza__icontains=query)
            | Q(cliente__nombre__icontains=query) | Q(cliente__apellido__icontains=query)
        )

    total = qs.count()
    mascotas = list(qs.order_by('nombre')[:LIMITE_RESULTADOS])
    return {
        "total_encontrado": total,
        "mostrando": len(mascotas),
        "pacientes": [
            {
                "id": m.id,
                "nombre": m.nombre,
                "especie": m.get_especie_display(),
                "raza": m.raza,
                "sexo": m.get_sexo_display() if m.sexo else None,
                "peso_kg": str(m.peso_kg) if m.peso_kg else None,
                "tutor": f"{m.cliente.nombre} {m.cliente.apellido}",
                "telefono_tutor": m.cliente.telefono,
            }
            for m in mascotas
        ],
    }


@_manejar_errores
async def buscar_paciente(query: str) -> dict:
    """Busca una mascota/paciente por su nombre, el nombre del tutor, especie o raza."""
    return await _buscar_paciente_sync(query)


@sync_to_async
def _historial_paciente_sync(mascota_id):
    from apps.clientes.models import Mascota
    from apps.historia_clinica.models import ConsultaMedica, RegistroVacuna, RegistroDesparasitacion
    vet = veterinaria_o_error()

    qs_mascota = Mascota.objects.select_related('cliente')
    if not _es_superuser_global(vet):
        qs_mascota = qs_mascota.filter(cliente__veterinaria=vet)
    mascota = qs_mascota.filter(id=mascota_id).first()
    if not mascota:
        return {"encontrado": False, "mensaje": "No encontré ningún paciente con ese ID en tu clínica."}

    from apps.historia_clinica.models import Receta

    consultas = ConsultaMedica.objects.filter(mascota=mascota).select_related('veterinario').order_by('-fecha_hora')[:LIMITE_RESULTADOS]
    vacunas = RegistroVacuna.objects.filter(mascota=mascota).order_by('-fecha_aplicacion')[:LIMITE_RESULTADOS]
    desparasitaciones = RegistroDesparasitacion.objects.filter(mascota=mascota).order_by('-fecha_aplicacion')[:LIMITE_RESULTADOS]
    recetas = Receta.objects.filter(mascota=mascota).prefetch_related('items').order_by('-fecha_emision')[:LIMITE_RESULTADOS]

    return {
        "encontrado": True,
        "paciente": {"id": mascota.id, "nombre": mascota.nombre, "tutor": f"{mascota.cliente.nombre} {mascota.cliente.apellido}"},
        "consultas": [
            {
                "fecha": c.fecha_hora.date().isoformat(),
                "veterinario": f"{c.veterinario.nombre} {c.veterinario.apellido}" if c.veterinario else None,
                "motivo": c.motivo_consulta,
                "diagnostico": c.diagnostico,
                "tratamiento": c.tratamiento,
            }
            for c in consultas
        ],
        "vacunas": [
            {
                "vacuna": v.nombre_vacuna,
                "fecha_aplicacion": v.fecha_aplicacion.isoformat(),
                "proxima_dosis": v.fecha_proxima_dosis.isoformat() if v.fecha_proxima_dosis else None,
            }
            for v in vacunas
        ],
        "desparasitaciones": [
            {
                "tipo": d.get_tipo_display(),
                "producto": d.producto,
                "fecha_aplicacion": d.fecha_aplicacion.isoformat(),
                "proxima_dosis": d.fecha_proxima_dosis.isoformat() if d.fecha_proxima_dosis else None,
            }
            for d in desparasitaciones
        ],
        "recetas": [
            {
                "fecha": r.fecha_emision.date().isoformat(),
                "diagnostico": r.diagnostico,
                "medicamentos": [
                    {"medicamento": i.medicamento, "dosis": i.dosis, "duracion": i.duracion, "indicaciones": i.indicaciones}
                    for i in r.items.all()
                ],
            }
            for r in recetas
        ],
    }


@_manejar_errores
async def historial_paciente(mascota_id: int) -> dict:
    """Historia clínica de una mascota: últimas consultas, vacunas, desparasitaciones
    y recetas con sus medicamentos. Necesitás el ID de la mascota (usá buscar_paciente
    primero si no lo tenés)."""
    return await _historial_paciente_sync(mascota_id)


@sync_to_async
def _buscar_cliente_sync(query):
    from apps.clientes.models import Cliente
    vet = veterinaria_o_error()

    qs = Cliente.objects.filter(activo=True)
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query)
            | Q(dni__icontains=query) | Q(telefono__icontains=query)
        )

    total = qs.count()
    clientes = list(qs.order_by('apellido', 'nombre')[:LIMITE_RESULTADOS])
    return {
        "total_encontrado": total,
        "mostrando": len(clientes),
        "clientes": [
            {
                "id": c.id,
                "nombre_completo": f"{c.nombre} {c.apellido}",
                "dni": c.dni,
                "telefono": c.telefono,
                "email": c.email,
                "cantidad_mascotas": c.mascotas.count(),
            }
            for c in clientes
        ],
    }


@_manejar_errores
async def buscar_cliente(query: str) -> dict:
    """Busca un cliente/tutor por nombre, apellido, DNI o teléfono."""
    return await _buscar_cliente_sync(query)


@sync_to_async
def _turnos_sync(fecha_desde, fecha_hasta):
    from apps.turnos.models import Turno
    vet = veterinaria_o_error()

    qs = Turno.objects.select_related('mascota', 'mascota__cliente', 'veterinario').all()
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    qs = qs.filter(fecha_hora__date__gte=fecha_desde, fecha_hora__date__lte=fecha_hasta)

    total = qs.count()
    turnos = list(qs.order_by('fecha_hora')[:LIMITE_RESULTADOS])
    return {
        "desde": fecha_desde.isoformat(),
        "hasta": fecha_hasta.isoformat(),
        "total_encontrado": total,
        "mostrando": len(turnos),
        "turnos": [
            {
                "id": t.id,
                "fecha_hora": t.fecha_hora.isoformat(),
                "paciente": t.mascota.nombre if t.mascota else None,
                "tutor": f"{t.mascota.cliente.nombre} {t.mascota.cliente.apellido}" if t.mascota and t.mascota.cliente else None,
                "veterinario": f"{t.veterinario.nombre} {t.veterinario.apellido}" if t.veterinario else None,
                "estado": t.get_estado_display(),
                "motivo": t.motivo,
            }
            for t in turnos
        ],
    }


@_manejar_errores
async def turnos(fecha_desde: str = "", fecha_hasta: str = "") -> dict:
    """Turnos agendados en un rango de fechas (formato AAAA-MM-DD). Si no se pasa
    ninguna fecha, muestra los turnos de hoy."""
    from datetime import date
    hoy = timezone.localdate()
    try:
        desde = date.fromisoformat(fecha_desde) if fecha_desde else hoy
        hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else desde
    except ValueError:
        return {"error": "Las fechas tienen que tener el formato AAAA-MM-DD, por ejemplo 2026-10-20."}
    return await _turnos_sync(desde, hasta)


def _parsear_rango_fechas(fecha_desde, fecha_hasta, default_dias=7):
    from datetime import date
    hoy = timezone.localdate()
    try:
        hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else hoy
        desde = date.fromisoformat(fecha_desde) if fecha_desde else (hasta - timedelta(days=default_dias))
    except ValueError:
        return None, None, {"error": "Las fechas tienen que tener el formato AAAA-MM-DD, por ejemplo 2026-10-20."}
    return desde, hasta, None


@sync_to_async
def _ventas_sync(fecha_desde, fecha_hasta):
    from apps.ventas.models import Venta
    vet = veterinaria_o_error()

    qs = Venta.objects.select_related('cliente', 'vendedor').prefetch_related('detalles').all()
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    qs = qs.filter(fecha_hora__date__gte=fecha_desde, fecha_hora__date__lte=fecha_hasta)

    total = qs.count()
    ventas = list(qs.order_by('-fecha_hora')[:LIMITE_RESULTADOS])
    total_facturado = sum((v.total for v in qs), start=0)
    return {
        "desde": fecha_desde.isoformat(),
        "hasta": fecha_hasta.isoformat(),
        "total_encontrado": total,
        "mostrando": len(ventas),
        "total_facturado_periodo": str(total_facturado),
        "ventas": [
            {
                "id": v.id,
                "fecha_hora": v.fecha_hora.isoformat(),
                "cliente": f"{v.cliente.nombre} {v.cliente.apellido}" if v.cliente else "Consumidor Final",
                "medio_pago": v.get_medio_pago_display(),
                "total": str(v.total),
                "vendedor": (v.vendedor.get_full_name() or v.vendedor.username) if v.vendedor else None,
                "items": [d.nombre_item for d in v.detalles.all()],
            }
            for v in ventas
        ],
    }


@_manejar_errores
async def ventas(fecha_desde: str = "", fecha_hasta: str = "") -> dict:
    """Ventas registradas en un rango de fechas (formato AAAA-MM-DD), con el total
    facturado en el período. Si no se pasa ninguna fecha, muestra los últimos 7 días."""
    desde, hasta, error = _parsear_rango_fechas(fecha_desde, fecha_hasta)
    if error:
        return error
    return await _ventas_sync(desde, hasta)


@sync_to_async
def _estado_caja_sync():
    from apps.ventas.models import CajaDiaria
    vet = veterinaria_o_error()

    qs = CajaDiaria.objects.select_related('usuario_apertura')
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    caja = qs.order_by('-fecha_apertura').first()

    if not caja:
        return {"hay_caja": False, "mensaje": "Todavía no se abrió ninguna caja en esta clínica."}

    return {
        "hay_caja": True,
        "estado": caja.get_estado_display(),
        "fecha_apertura": caja.fecha_apertura.isoformat(),
        "abierta_por": (caja.usuario_apertura.get_full_name() or caja.usuario_apertura.username) if caja.usuario_apertura else None,
        "monto_inicial": str(caja.monto_inicial),
        "total_vendido_efectivo": str(caja.total_efectivo),
        "total_vendido_digital": str(caja.total_digital_tarjetas),
        "total_general_ventas": str(caja.total_general_ventas),
        "total_gastos": str(caja.total_gastos),
    }


@_manejar_errores
async def estado_caja() -> dict:
    """Estado de la caja diaria más reciente de tu clínica: si está abierta o cerrada,
    quién la abrió, y los totales vendidos hasta el momento."""
    return await _estado_caja_sync()


@sync_to_async
def _compras_sync(fecha_desde, fecha_hasta):
    from apps.compras.models import Compra
    vet = veterinaria_o_error()

    qs = Compra.objects.select_related('proveedor').all()
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    qs = qs.filter(fecha_hora__date__gte=fecha_desde, fecha_hora__date__lte=fecha_hasta)

    total = qs.count()
    compras = list(qs.order_by('-fecha_hora')[:LIMITE_RESULTADOS])
    total_comprado = sum((c.total for c in qs), start=0)
    return {
        "desde": fecha_desde.isoformat(),
        "hasta": fecha_hasta.isoformat(),
        "total_encontrado": total,
        "mostrando": len(compras),
        "total_comprado_periodo": str(total_comprado),
        "compras": [
            {
                "id": c.id,
                "fecha_hora": c.fecha_hora.isoformat(),
                "proveedor": c.proveedor.nombre if c.proveedor else None,
                "numero_factura": c.numero_factura,
                "total": str(c.total),
            }
            for c in compras
        ],
    }


@_manejar_errores
async def compras(fecha_desde: str = "", fecha_hasta: str = "") -> dict:
    """Compras a proveedores registradas en un rango de fechas (formato AAAA-MM-DD),
    con el total gastado en el período. Si no se pasa ninguna fecha, muestra los
    últimos 7 días."""
    desde, hasta, error = _parsear_rango_fechas(fecha_desde, fecha_hasta)
    if error:
        return error
    return await _compras_sync(desde, hasta)


@sync_to_async
def _buscar_proveedores_sync(query):
    from apps.compras.models import Proveedor
    vet = veterinaria_o_error()

    qs = Proveedor.objects.filter(activo=True)
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    if query:
        qs = qs.filter(Q(nombre__icontains=query) | Q(contacto__icontains=query))

    total = qs.count()
    proveedores = list(qs.order_by('nombre')[:LIMITE_RESULTADOS])
    return {
        "total_encontrado": total,
        "mostrando": len(proveedores),
        "proveedores": [
            {
                "id": p.id,
                "nombre": p.nombre,
                "contacto": p.contacto,
                "telefono": p.telefono,
                "email": p.email,
            }
            for p in proveedores
        ],
    }


@_manejar_errores
async def buscar_proveedores(query: str = "") -> dict:
    """Busca proveedores de tu clínica por nombre o persona de contacto. Dejá 'query'
    vacío para listar los primeros proveedores sin filtrar."""
    return await _buscar_proveedores_sync(query)


@sync_to_async
def _internaciones_sync(solo_activas):
    from apps.historia_clinica.models import Internacion
    vet = veterinaria_o_error()

    qs = Internacion.objects.select_related('mascota', 'mascota__cliente', 'veterinario_responsable').all()
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)
    if solo_activas:
        qs = qs.filter(estado='INTERNADO')

    total = qs.count()
    internaciones = list(qs.order_by('-fecha_ingreso')[:LIMITE_RESULTADOS])
    return {
        "solo_activas": solo_activas,
        "total_encontrado": total,
        "mostrando": len(internaciones),
        "internaciones": [
            {
                "id": i.id,
                "paciente": i.mascota.nombre if i.mascota else None,
                "tutor": f"{i.mascota.cliente.nombre} {i.mascota.cliente.apellido}" if i.mascota and i.mascota.cliente else None,
                "box": i.box,
                "estado": i.get_estado_display(),
                "motivo_ingreso": i.motivo_ingreso,
                "veterinario_responsable": f"{i.veterinario_responsable.nombre} {i.veterinario_responsable.apellido}" if i.veterinario_responsable else None,
                "fecha_ingreso": i.fecha_ingreso.isoformat(),
                "fecha_alta_estimada": i.fecha_alta_estimada.isoformat() if i.fecha_alta_estimada else None,
                "fecha_alta_real": i.fecha_alta_real.isoformat() if i.fecha_alta_real else None,
            }
            for i in internaciones
        ],
    }


@_manejar_errores
async def internaciones(solo_activas: bool = True) -> dict:
    """Pacientes internados. Por defecto solo muestra las internaciones activas (en
    curso); pasá solo_activas=false para ver también las que ya tuvieron alta."""
    return await _internaciones_sync(solo_activas)


@sync_to_async
def _equipo_veterinarios_sync():
    from apps.turnos.models import Veterinario
    vet = veterinaria_o_error()

    qs = Veterinario.objects.filter(activo=True)
    if not _es_superuser_global(vet):
        qs = qs.filter(veterinaria=vet)

    veterinarios = list(qs.order_by('apellido', 'nombre')[:LIMITE_RESULTADOS])
    return {
        "cantidad": len(veterinarios),
        "veterinarios": [
            {
                "id": v.id,
                "nombre_completo": f"{v.nombre} {v.apellido}",
                "matricula": v.matricula,
                "telefono": v.telefono,
                "email": v.email,
            }
            for v in veterinarios
        ],
    }


@_manejar_errores
async def equipo_veterinarios() -> dict:
    """Lista los veterinarios/profesionales activos de tu clínica, con su matrícula
    y datos de contacto."""
    return await _equipo_veterinarios_sync()


@sync_to_async
def _datos_veterinaria_sync():
    vet = veterinaria_o_error()
    if vet is None:
        return {"encontrado": False, "mensaje": "Tu usuario no tiene una veterinaria asignada."}

    suscripcion = getattr(vet, 'suscripcion', None)
    return {
        "encontrado": True,
        "nombre": vet.nombre,
        "cuit": vet.cuit_rif,
        "telefono": vet.telefono,
        "direccion": vet.direccion,
        "email_contacto": vet.email_contacto,
        "suscripcion": {
            "plan": suscripcion.plan.nombre,
            "estado": suscripcion.get_estado_display(),
            "vencimiento": suscripcion.fecha_vencimiento.isoformat(),
        } if suscripcion else None,
    }


@_manejar_errores
async def datos_veterinaria() -> dict:
    """Datos de contacto de tu propia clínica (nombre, dirección, teléfono, CUIT) y
    el estado de tu suscripción a VeterSystem."""
    return await _datos_veterinaria_sync()
