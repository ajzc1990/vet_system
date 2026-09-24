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
  ia_habilitada: boolean;
};

export type Veterinario = { id: number; nombre: string; apellido: string; matricula: string };

export type Cliente = {
  id: number;
  nombre: string;
  apellido: string;
  dni: string;
  telefono: string;
  email: string | null;
  direccion: string | null;
  activo: boolean;
  mascotas: Mascota[];
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

export type Estudio = {
  id: number;
  titulo: string;
  tipo_estudio: string;
  tipo_estudio_display: string;
  archivo: string;
  es_imagen: boolean;
  fecha_estudio: string;
  observaciones: string | null;
};

export type Evolucion = {
  id: number;
  fecha_hora: string;
  estado_general: string;
  estado_general_display: string;
  peso_kg: string | null;
  temperatura_c: string | null;
  frecuencia_cardiaca: number | null;
  frecuencia_respiratoria: number | null;
  notas: string;
  medicacion_administrada: string | null;
  veterinario_nombre: string | null;
};

export type InternacionDetalle = {
  id: number;
  mascota: number;
  mascota_nombre: string;
  especie_display: string;
  cliente_nombre: string;
  cliente_telefono: string;
  veterinario_responsable_nombre: string | null;
  box: string | null;
  motivo_ingreso: string;
  diagnostico_ingreso: string | null;
  dieta_indicaciones: string | null;
  fecha_ingreso: string;
  fecha_alta_estimada: string | null;
  fecha_alta_real: string | null;
  estado: string;
  estado_display: string;
  resumen_alta: string | null;
  dias_internado: number;
  evoluciones: Evolucion[];
};

export type Historia = {
  mascota: Mascota;
  consultas: Consulta[];
  vacunas: Vacuna[];
  desparasitaciones: Desparasitacion[];
  recetas: Receta[];
  estudios: Estudio[];
  internaciones_activas: Internacion[];
  resumen_ia: { texto: string; generado_el: string } | null;
};

export type SolicitudTurno = {
  id: number;
  nombre_tutor: string;
  telefono: string;
  email: string | null;
  nombre_mascota: string;
  especie: string | null;
  motivo: string;
  fecha_deseada: string;
  franja_preferida: string;
  franja_preferida_display: string;
  estado: 'PENDIENTE' | 'CONTACTADO' | 'DESCARTADO';
  estado_display: string;
  creado_el: string;
};
