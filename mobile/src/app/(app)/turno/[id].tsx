import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { BuscadorMascota, type MascotaElegida } from '@/components/buscador-mascota';
import { SelectorFechaHora } from '@/components/fecha-hora';
import { Formulario, useEnvio } from '@/components/formulario';
import { Campo, Chips, EstadoCarga, Texto } from '@/components/ui';
import { api } from '@/lib/api';
import { desdeISO } from '@/lib/fechas';
import type { EstadoTurno, Paginado, Turno, Veterinario } from '@/lib/types';
import { useApi } from '@/lib/use-api';

const ESTADOS: { valor: EstadoTurno; etiqueta: string }[] = [
  { valor: 'PENDIENTE', etiqueta: 'Pendiente' },
  { valor: 'CONFIRMADO', etiqueta: 'Confirmado' },
  { valor: 'COMPLETADO', etiqueta: 'Completado' },
  { valor: 'CANCELADO', etiqueta: 'Cancelado' },
];

/** Próximo horario "redondo" (media hora) del día elegido, para no arrancar en 14:37. */
function horarioSugerido(fecha?: string) {
  const ahora = new Date();
  const base = fecha ? desdeISO(fecha) : ahora;
  const sugerido = new Date(base);
  if (fecha && base.toDateString() !== ahora.toDateString()) {
    sugerido.setHours(9, 0, 0, 0);
  } else {
    sugerido.setHours(ahora.getHours(), ahora.getMinutes() < 30 ? 30 : 60, 0, 0);
  }
  return sugerido;
}

/**
 * Alta y edición de turnos. /turno/nuevo acepta ?fecha=AAAA-MM-DD (desde la agenda) y
 * ?mascota=&mascota_nombre=&cliente_nombre= (desde la ficha del paciente).
 */
export default function FormularioTurno() {
  const params = useLocalSearchParams<{
    id: string;
    fecha?: string;
    mascota?: string;
    mascota_nombre?: string;
    cliente_nombre?: string;
  }>();
  const esNuevo = params.id === 'nuevo';
  const { enviar, enviando, errores } = useEnvio(esNuevo ? 'turnos/' : `turnos/${params.id}/`);
  const veterinarios = useApi<Paginado<Veterinario>>('veterinarios/');

  const [cargando, setCargando] = useState(!esNuevo);
  const [mascota, setMascota] = useState<MascotaElegida | null>(
    params.mascota
      ? { id: Number(params.mascota), nombre: params.mascota_nombre ?? '', cliente_nombre: params.cliente_nombre ?? '' }
      : null,
  );
  const [fechaHora, setFechaHora] = useState<Date | null>(() => (esNuevo ? horarioSugerido(params.fecha) : null));
  const [veterinario, setVeterinario] = useState<number | null>(null);
  const [motivo, setMotivo] = useState('');
  const [observaciones, setObservaciones] = useState('');
  const [estado, setEstado] = useState<EstadoTurno>('PENDIENTE');

  useEffect(() => {
    if (esNuevo) return;
    api<Turno>(`turnos/${params.id}/`)
      .then((turno) => {
        setMascota({ id: turno.mascota, nombre: turno.mascota_nombre, cliente_nombre: turno.cliente_nombre });
        setFechaHora(new Date(turno.fecha_hora));
        setVeterinario(turno.veterinario);
        setMotivo(turno.motivo ?? '');
        setObservaciones(turno.observaciones ?? '');
        setEstado(turno.estado);
      })
      .finally(() => setCargando(false));
  }, [esNuevo, params.id]);

  function guardar() {
    enviar(
      {
        mascota: mascota?.id ?? null,
        fecha_hora: fechaHora?.toISOString() ?? null,
        veterinario,
        motivo: motivo.trim() || null,
        observaciones: observaciones.trim() || null,
        ...(esNuevo ? {} : { estado }),
      },
      esNuevo ? 'Turno agendado' : 'Turno actualizado',
      { method: esNuevo ? 'POST' : 'PATCH' },
    );
  }

  if (cargando) return <EstadoCarga cargando error={null} />;

  const opcionesVet = [
    { valor: 0, etiqueta: 'Sin asignar' },
    ...(veterinarios.datos?.results ?? []).map((v) => ({ valor: v.id, etiqueta: `${v.nombre} ${v.apellido}` })),
  ];

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton={esNuevo ? 'Agendar turno' : 'Guardar cambios'}>
      <Stack.Screen options={{ title: esNuevo ? 'Nuevo turno' : 'Editar turno' }} />

      <BuscadorMascota valor={mascota} onCambiar={setMascota} error={errores.mascota} />

      <SelectorFechaHora
        etiqueta="Fecha y hora *"
        modo="fechahora"
        valor={fechaHora}
        onCambiar={setFechaHora}
        error={errores.fecha_hora}
      />

      {opcionesVet.length > 1 && (
        <View style={{ gap: 4 }}>
          <Texto variante="etiqueta">Veterinario</Texto>
          <Chips opciones={opcionesVet} valor={veterinario ?? 0} onCambiar={(v) => setVeterinario(v || null)} />
        </View>
      )}

      <Campo etiqueta="Motivo" placeholder="Vacunación, control, consulta..." value={motivo} onChangeText={setMotivo}
        error={errores.motivo} />

      {!esNuevo && (
        <View style={{ gap: 4 }}>
          <Texto variante="etiqueta">Estado</Texto>
          <Chips opciones={ESTADOS} valor={estado} onCambiar={setEstado} />
        </View>
      )}

      <Campo etiqueta="Observaciones" multiline value={observaciones} onChangeText={setObservaciones}
        error={errores.observaciones} />
    </Formulario>
  );
}
