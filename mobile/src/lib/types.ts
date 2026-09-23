// Formas de las respuestas de la API de Django (apps/api/serializers.py).

export type Paginado<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type Usuario = {
  username: string;
  nombre: string;
  rol: 'ADMIN' | 'VET' | 'RECEPCION' | null;
  rol_display: string | null;
  veterinaria: string | null;
  puede_atender: boolean;
};

export type EstadoTurno = 'PENDIENTE' | 'CONFIRMADO' | 'COMPLETADO' | 'CANCELADO';

export type Turno = {
  id: number;
  mascota: number;
  mascota_nombre: string;
  cliente_nombre: string;
  veterinario: number | null;
  veterinario_nombre: string | null;
  fecha_hora: string;
  motivo: string | null;
  estado: EstadoTurno;
  estado_display: string;
  observaciones: string | null;
};

export type Mascota = {
  id: number;
  cliente: number;
  cliente_nombre: string;
  cliente_telefono: string;
  nombre: string;
  especie: string;
  especie_display: string;
  raza: string | null;
  fecha_nacimiento: string | null;
  sexo: string;
  sexo_display: string;
  peso_kg: string | null;
  castrado: boolean;
  observaciones: string | null;
};

export type Consulta = {
  id: number;
  turno: number | null;
  veterinario_nombre: string | null;
  fecha_hora: string;
  peso_actual_kg: string | null;
  temperatura_c: string | null;
  frecuencia_cardiaca: number | null;
  frecuencia_respiratoria: number | null;
  motivo_consulta: string;
  anamnesis: string | null;
  examen_clinico: string | null;
  diagnostico: string;
  tratamiento: string;
  observaciones_privadas: string | null;
};

export type Vacuna = {
  id: number;
  nombre_vacuna: string;
  lote: string | null;
  fecha_aplicacion: string;
  fecha_proxima_dosis: string | null;
  proxima_dosis_vencida: boolean;
  veterinario_nombre: string | null;
  observaciones: string | null;
};

export type Desparasitacion = {
  id: number;
  tipo_display: string;
  producto: string;
  dosis: string | null;
  fecha_aplicacion: string;
  fecha_proxima_dosis: string | null;
  proxima_dosis_vencida: boolean;
};

export type ItemReceta = {
  medicamento: string;
  dosis: string;
  duracion: string;
  indicaciones: string;
};

export type Receta = {
  id: number;
  fecha_emision: string;
  diagnostico: string;
  observaciones: string;
  veterinario_nombre: string | null;
  items: (ItemReceta & { id: number })[];
};

export type Internacion = {
  id: number;
  box: string | null;
  motivo_ingreso: string;
  fecha_ingreso: string;
  estado_display: string;
  dias_internado: number;
};

export type Historia = {
  mascota: Mascota;
  consultas: Consulta[];
  vacunas: Vacuna[];
  desparasitaciones: Desparasitacion[];
  recetas: Receta[];
  internaciones_activas: Internacion[];
  resumen_ia: { texto: string; generado_el: string } | null;
};
