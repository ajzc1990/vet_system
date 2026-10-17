# Servidor MCP de VeterSystem

Deja que Claude (o cualquier asistente compatible con MCP) conteste preguntas sobre
los datos de **tu propia clínica** en lenguaje natural: stock, pacientes, turnos,
historia clínica. Es de **solo lectura** — no puede crear ni modificar nada, todavía.

Cada clínica usa su propio token: nunca se mezclan datos entre veterinarias.

---

## 1. Instalación y puesta en marcha en el servidor

Esto ya corre junto al resto de VeterSystem en el mismo `docker-compose.yml` como
un servicio nuevo llamado `mcp` (proceso propio, separado de Gunicorn — el SDK de
MCP necesita un servidor async, y Gunicorn hoy sirve la app principal en modo
síncrono).

### Pasos para desplegar (en el VPS)

```bash
cd /var/www/vet_system_new
git pull --ff-only origin vet_system-master
docker compose up -d --build mcp
```

Esto construye la imagen (que ya incluye `mcp`, `uvicorn` y `httpx` en
`requirements.txt`) y levanta el contenedor `vetersystem_mcp`, escuchando en el
puerto 8001 **dentro de la red de Docker** (no está expuesto directo a internet;
nginx lo expone en `/mcp`).

### Nginx

**Importante**: el `nginx/default.conf` de este repo tiene el dominio de ejemplo
(`tu-dominio.com`) porque el archivo real del servidor se edita a mano (tiene el
dominio real) y no está sincronizado con git. Hay que agregar el bloque de abajo
**directamente en el servidor**, no hacer `git pull` de este archivo:

```nginx
location /mcp {
    proxy_pass http://mcp:8001/mcp;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_redirect off;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

Después: `docker compose restart nginx`.

### Variable de entorno `MCP_ALLOWED_HOSTS`

El SDK de MCP rechaza con error 421 cualquier request cuyo dominio no esté en una
lista blanca (protección contra DNS rebinding). Por defecto acepta
`vetersystem.com,www.vetersystem.com`. Si el dominio es otro, agregá al `.env`:

```
MCP_ALLOWED_HOSTS=tudominio.com,www.tudominio.com
```

---

## 2. Cómo lo conecta una veterinaria

1. Iniciar sesión en VeterSystem como siempre.
2. En el menú de usuario (abajo a la izquierda), ir a **"Mi Token de API / MCP"**.
3. Copiar el token que aparece ahí (es personal, uno por usuario — no por clínica).
4. En Claude, agregar un conector personalizado:
   - **URL del servidor:** `https://vetersystem.com/mcp`
   - **Autenticación:** pegar el token copiado.
5. Listo. Ya se le puede preguntar en lenguaje natural por los datos de su clínica.

Si alguien se va de la clínica o el token se filtró, desde esa misma pantalla se
puede "Regenerar token": el anterior deja de funcionar al instante.

---

## 3. Las herramientas (solo lectura)

| Herramienta | Para qué sirve | Ejemplo de pregunta |
|---|---|---|
| `buscar_productos` | Busca en el catálogo por nombre o categoría | *"¿Tenés Meloxicam en el catálogo?"* |
| `consultar_stock` | Stock actual de un producto y si está bajo mínimo | *"¿Cuántas pipetas antipulgas me quedan?"* |
| `productos_por_vencer` | Productos que vencen dentro de N días (default 30) | *"¿Qué productos vencen antes de fin de mes?"* |
| `buscar_paciente` | Busca una mascota por nombre, tutor, especie o raza | *"Buscá a Toby"* |
| `historial_paciente` | Consultas, vacunas, desparasitaciones y recetas de una mascota (necesita el ID) | *"¿Cuándo fue la última vacuna de Toby?"* |
| `buscar_cliente` | Busca un tutor por nombre, DNI o teléfono | *"Buscá al cliente con DNI 30123456"* |
| `turnos` | Turnos en un rango de fechas (default: hoy) | *"¿Qué turnos tengo hoy?"* |
| `ventas` | Ventas en un rango de fechas, con el total facturado (default: últimos 7 días) | *"¿Cuánto facturé esta semana?"* |
| `estado_caja` | Estado de la caja diaria más reciente | *"¿Está abierta la caja?"* |
| `compras` | Compras a proveedores en un rango de fechas (default: últimos 7 días) | *"¿Qué compramos este mes?"* |
| `buscar_proveedores` | Busca proveedores por nombre o contacto | *"Buscá el proveedor VetFarma"* |
| `internaciones` | Pacientes internados (activas por defecto) | *"¿Quién está internado hoy?"* |
| `equipo_veterinarios` | Lista los veterinarios activos de la clínica | *"¿Quiénes son los veterinarios de la clínica?"* |
| `datos_veterinaria` | Datos de contacto de tu clínica y estado de tu suscripción | *"¿Cuándo vence mi plan?"* |

Todas devuelven como máximo 20 resultados por llamada (con el total real
encontrado, por si hace falta acotar más la búsqueda).

---

## 4. Probarlo con MCP Inspector (antes de conectarlo a Claude)

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) es la
herramienta oficial para probar un servidor MCP a mano, sin necesidad de un
cliente real.

```bash
npx @modelcontextprotocol/inspector
```

Esto abre una página web local. Ahí:

1. **Transport Type:** `Streamable HTTP`
2. **URL:** `https://vetersystem.com/mcp` (o `http://localhost:8001/mcp` si lo
   estás probando en tu máquina)
3. **Authentication → Bearer Token:** tu token (el de "Mi Token de API / MCP")
4. Conectar, ir a la pestaña **Tools**, y probar cada herramienta con distintos
   parámetros.

Si algo fallara con un `401`, el problema es el token (vencido, mal copiado, o la
cuenta no está aprobada). Un `421` significa que el dominio no está en
`MCP_ALLOWED_HOSTS`.

---

## 5. Seguridad: cómo se garantiza que nunca se mezclan clínicas

- El token se valida contra el mismo sistema que ya usa la app móvil
  (`rest_framework.authtoken`), revisando en cada request que la cuenta siga
  aprobada (si se la revocan, el token deja de servir al instante, sin esperar
  a que expire nada).
- Cada una de las 7 herramientas filtra **siempre** por la veterinaria del
  dueño del token, usando el mismo patrón que ya usa el resto de la API REST
  (`apps.api.views.TenantReadOnlyViewSet`), no una lógica nueva.
- Hay un test automatizado (`mcp_server/tests.py`,
  `AislamientoMultiTenantTests`) que crea dos clínicas con productos,
  pacientes y turnos **con los mismos nombres a propósito**, y confirma que
  cada token solo ve los suyos — incluso pidiendo el historial de un paciente
  de la otra clínica por ID directamente, el caso más peligroso.

---

## 6. Qué falta para la próxima etapa (ya anticipado, no implementado)

El código quedó organizado para sumar herramientas que **modifiquen** datos
(crear un turno, descontar stock) más adelante, siempre pidiendo confirmación
explícita antes de ejecutar la acción. Por ahora todo lo que existe es de
solo lectura.
