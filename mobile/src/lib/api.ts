/**
 * Cliente HTTP de la API de VeterSystem. La URL del servidor sale de EXPO_PUBLIC_API_URL
 * (ver .env.example); en desarrollo tiene que ser la IP de la PC en la red local, porque
 * "localhost" en el celular es el propio celular.
 */

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

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

export async function api<T>(ruta: string, opciones: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (token) headers.Authorization = `Token ${token}`;
  if (opciones.body !== undefined) headers['Content-Type'] = 'application/json';

  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}/api/${ruta.replace(/^\//, '')}`, {
      method: opciones.method ?? 'GET',
      headers,
      body: opciones.body !== undefined ? JSON.stringify(opciones.body) : undefined,
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
