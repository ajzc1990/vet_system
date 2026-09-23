const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

const dos = (n: number) => String(n).padStart(2, '0');

/** YYYY-MM-DD en hora local (toISOString usaría UTC y cambiaría el día después de las 21 hs). */
export function aISO(fecha: Date) {
  return `${fecha.getFullYear()}-${dos(fecha.getMonth() + 1)}-${dos(fecha.getDate())}`;
}

/** Parsea "YYYY-MM-DD" como fecha local (new Date("YYYY-MM-DD") la toma como UTC). */
export function desdeISO(iso: string) {
  const [a, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(a, m - 1, d);
}

export function sumarDias(fecha: Date, dias: number) {
  const nueva = new Date(fecha);
  nueva.setDate(nueva.getDate() + dias);
  return nueva;
}

export function esHoy(fecha: Date) {
  return aISO(fecha) === aISO(new Date());
}

export function tituloDia(fecha: Date) {
  const hoy = new Date();
  if (esHoy(fecha)) return 'Hoy';
  if (aISO(fecha) === aISO(sumarDias(hoy, 1))) return 'Mañana';
  if (aISO(fecha) === aISO(sumarDias(hoy, -1))) return 'Ayer';
  return `${DIAS[fecha.getDay()][0].toUpperCase()}${DIAS[fecha.getDay()].slice(1)} ${fecha.getDate()} ${MESES[fecha.getMonth()]}`;
}

export function hora(isoDateTime: string) {
  const f = new Date(isoDateTime);
  return `${dos(f.getHours())}:${dos(f.getMinutes())}`;
}

/** "12 mar 2026" para fechas (YYYY-MM-DD) o fechas con hora. */
export function fechaCorta(iso: string) {
  const f = iso.length <= 10 ? desdeISO(iso) : new Date(iso);
  return `${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()}`;
}

export function edad(fechaNacimiento: string | null) {
  if (!fechaNacimiento) return null;
  const nac = desdeISO(fechaNacimiento);
  const hoy = new Date();
  let meses = (hoy.getFullYear() - nac.getFullYear()) * 12 + hoy.getMonth() - nac.getMonth();
  if (hoy.getDate() < nac.getDate()) meses -= 1;
  if (meses < 12) return `${Math.max(meses, 0)} ${meses === 1 ? 'mes' : 'meses'}`;
  const anios = Math.floor(meses / 12);
  return `${anios} ${anios === 1 ? 'año' : 'años'}`;
}
