# Power BI + VeterSystem

Hay dos formas de conectar Power BI, según quién lo use:

1. **Vos (dueño de VeterSystem)**: conexión directa a la base de datos, para ver
   todas las clínicas juntas (facturación total, cantidad de clínicas activas, etc.).
2. **Cada clínica**: conexión a la API REST (la misma que usa la app móvil), que
   ya filtra solo sus propios datos. No requiere nada nuevo del lado del servidor.

---

## 1. Tu reporte global (todas las clínicas)

Postgres en el VPS no está expuesto a internet — solo a `127.0.0.1` del propio
servidor, en el puerto **5433** (el 5432 lo usa otro proyecto del servidor). Para
llegar desde tu PC hace falta un túnel SSH.

### Paso 1: abrir el túnel (dejalo abierto mientras uses Power BI)

```bash
ssh -N -L 5433:localhost:5433 root@2.25.105.233
```

`-N` significa "no abras una shell, solo hacé el túnel". La terminal se queda
colgada ahí a propósito — es así, dejala abierta.

### Paso 2: conectar Power BI Desktop

1. **Obtener datos → Base de datos → PostgreSQL**.
2. Servidor: `localhost:5433`
3. Base de datos: `vetsoft_db`
4. Modo de datos: **Importar** (recomendado antes que DirectQuery, es más estable).
5. Credenciales → **Base de datos**: usuario `powerbi_readonly`, la contraseña que
   elegiste al crear el rol.
6. Elegí las tablas que te interesen. Las más útiles, con el nombre real en la base
   (Django las nombra `<app>_<modelo>`):

| Qué es | Tabla |
|---|---|
| Veterinarias (clínicas) | `usuarios_veterinaria` |
| Clientes / tutores | `clientes_cliente` |
| Mascotas | `clientes_mascota` |
| Turnos | `turnos_turno` |
| Ventas | `ventas_venta` |
| Detalle de cada venta | `ventas_detalleventa` |
| Productos / inventario | `inventario_producto` |
| Compras | `compras_compra` |
| Internaciones | `historia_clinica_internacion` |
| Consultas médicas | `historia_clinica_consultamedica` |

### Seguridad
- `powerbi_readonly` **no puede escribir ni borrar nada** — solo `SELECT`.
- El puerto nunca quedó expuesto a internet, solo accesible desde adentro del
  propio VPS (por eso hace falta el túnel SSH para llegar desde tu PC).
- Si en algún momento querés revocar el acceso: `DROP ROLE powerbi_readonly;`
  (hay que sacarle antes los permisos con `REVOKE`, o usar
  `DROP OWNED BY powerbi_readonly; DROP ROLE powerbi_readonly;`).

---

## 2. Reporte propio de cada clínica (vía API)

Cada clínica ya tiene su token personal en **"Mi Token de API / MCP"** (menú de
usuario). Ese token filtra automáticamente todo por su propia veterinaria — nunca
ve datos de otra clínica.

### Paso 1: función de Power Query para traer todas las páginas

La API devuelve de a 25 resultados por página. Pegá esta función una sola vez
(Inicio → Nueva Consulta → Consulta en Blanco → Editor Avanzado):

```
let
    ObtenerTodo = (url as text, token as text) as list =>
        let
            ObtenerPagina = (urlPagina as text) as record =>
                let
                    Origen = Json.Document(Web.Contents(urlPagina, [Headers=[Authorization="Bearer " & token]])),
                    Resultados = Origen[results],
                    Siguiente = Origen[next]
                in
                    [Resultados=Resultados, Siguiente=Siguiente],
            Paginas = List.Generate(
                () => ObtenerPagina(url),
                each _[Resultados] <> null,
                each if _[Siguiente] <> null then ObtenerPagina(_[Siguiente]) else [Resultados=null, Siguiente=null],
                each _[Resultados]
            )
        in
            List.Combine(List.RemoveNulls(Paginas))
in
    ObtenerTodo
```

Guardala con el nombre **`ObtenerTodo`**.

### Paso 2: usarla para cada tipo de dato

Nueva consulta en blanco, y en la barra de fórmulas:

```
= Table.FromRecords(ObtenerTodo("https://vetersystem.com/api/ventas/", "TU_TOKEN_ACA"))
```

Cambiá `/api/ventas/` por el endpoint que quieras:

| Dato | Endpoint |
|---|---|
| Ventas | `https://vetersystem.com/api/ventas/` |
| Clientes | `https://vetersystem.com/api/clientes/` |
| Mascotas | `https://vetersystem.com/api/mascotas/` |
| Productos | `https://vetersystem.com/api/productos/` |
| Turnos | `https://vetersystem.com/api/turnos/` |
| Consultas médicas | `https://vetersystem.com/api/consultas/` |
| Vacunas | `https://vetersystem.com/api/vacunas/` |
| Desparasitaciones | `https://vetersystem.com/api/desparasitaciones/` |
| Internaciones | `https://vetersystem.com/api/internaciones/` |
| Recetas | `https://vetersystem.com/api/recetas/` |
| Veterinarios | `https://vetersystem.com/api/veterinarios/` |

Repetí el paso 2 una vez por cada tipo de dato que quieran ver en el reporte.

### Seguridad
- Cada clínica solo puede ver (nunca escribir) sus propios datos — es la misma
  API, con el mismo filtrado por token, que ya usa la app móvil.
- Si el token se filtra o alguien deja la clínica, se regenera desde "Mi Token
  de API / MCP" y el anterior deja de funcionar al instante.
