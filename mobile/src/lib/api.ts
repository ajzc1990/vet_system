/**
 * Cliente HTTP de la API de VeterSystem.
 *
 * Las builds instaladas (APK / tiendas) apuntan SIEMPRE a producción. EXPO_PUBLIC_API_URL
 * (ver .env.example) sólo se usa en desarrollo con Expo Go: así un `eas update` publicado
 * desde una PC con .env.local de pruebas no puede dejar a los clientes apuntando a una IP local.
 */

const PRODUCCION = 'https://vetersystem.com';

export const API_URL = (
  __DEV__ ? (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000') : PRODUCCION
).replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public campos: Record<string, string[]> = {},
  ) {
    super(message);
  }
}

let token: string | null = null;
let alExpirarSesion: (() => void) | null = null;

export function configurarSesion(nuevoToken: string | null, onExpira?: () => void) {
  token = nuevoToken;
  if (onExpira) alExpirarSesion = onExpira;
}

/** Convierte la respuesta de error de DRF ({detail} o {campo: [errores]}) en un mensaje legible. */
function armarError(status: number, cuerpo: unknown): ApiError {
  if (cuerpo && typeof cuerpo === 'object') {
    const datos = cuerpo as Record<string, unknown>;
    if (typeof datos.detail === 'string') return new ApiError(datos.detail, status);

    const campos: Record<string, string[]> = {};
    for (const [campo, errores] of Object.entries(datos)) {
      // Errores anidados (p. ej. de un ítem de receta) llegan como objetos: mensaje genérico.
      if (Array.isArray(errores)) {
        campos[campo] = errores.map((e) => (typeof e === 'string' ? e : 'Revisá los datos ingresados.'));
      }
    }
    const primero = Object.values(campos)[0]?.[0];
    if (primero) return new ApiError(primero, status, campos);
  }
  return new ApiError(`Error del servidor (${status}).`, status);
}

function url(ruta: string) {
  return `${API_URL}/api/${ruta.replace(/^\//, '')}`;
}

/** body: objeto (se manda como JSON) o FormData (multipart, para subir archivos). */
export async function api<T>(ruta: string, opciones: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) headers.Authorization = `Token ${token}`;
  const esFormulario = opciones.body instanceof FormData;
  // Con FormData el Content-Type (y su boundary) lo arma fetch solo.
  if (opciones.body !== undefined && !esFormulario) headers['Content-Type'] = 'application/json';

  let respuesta: Response;
  try {
    respuesta = await fetch(url(ruta), {
      method: opciones.method ?? 'GET',
      headers,
      body:
        opciones.body === undefined
          ? undefined
          : esFormulario
            ? (opciones.body as FormData)
            : JSON.stringify(opciones.body),
    });
  } catch {
    throw new ApiError(`No se pudo conectar con el servidor (${API_URL}).`, 0);
  }

  if (respuesta.status === 204) return undefined as T;

  const cuerpo = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    // DRF responde 403 tanto por token revocado/usuario desaprobado como por falta de rol
    // (recepción intentando cargar una consulta): la sesión revalida con /yo/ y sólo vuelve
    // al login si el token realmente dejó de servir.
    if ((respuesta.status === 401 || respuesta.status === 403) && token && ruta !== 'yo/') {
      alExpirarSesion?.();
    }
    throw armarError(respuesta.status, cuerpo);
  }
  return cuerpo as T;
}

/** Descarga un PDF de la API al caché del celular y abre el menú de compartir (WhatsApp, mail...). */
export async function compartirPdf(ruta: string, nombreArchivo: string) {
  const { File, Paths } = await import('expo-file-system');
  const Sharing = await import('expo-sharing');

  const destino = new File(Paths.cache, nombreArchivo.replace(/[^\w.-]+/g, '_'));
  let archivo: InstanceType<typeof File>;
  try {
    archivo = await File.downloadFileAsync(url(ruta), destino, {
      headers: token ? { Authorization: `Token ${token}` } : {},
      idempotent: true,
    });
  } catch {
    throw new ApiError('No se pudo descargar el PDF.', 0);
  }
  if (!(await Sharing.isAvailableAsync())) {
    throw new ApiError('Este dispositivo no permite compartir archivos.', 0);
  }
  await Sharing.shareAsync(archivo.uri, { mimeType: 'application/pdf', dialogTitle: nombreArchivo });
}
