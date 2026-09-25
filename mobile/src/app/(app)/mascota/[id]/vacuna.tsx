import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { SelectorFechaHora } from '@/components/fecha-hora';
import { Formulario, useEnvio } from '@/components/formulario';
import { Campo, Chips, EstadoCarga, Seccion } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import { aISO, desdeISO, sumarDias } from '@/lib/fechas';
import type { Vacuna } from '@/lib/types';

// Esquemas habituales de revacunación, para no tener que buscar la fecha en el calendario.
const ATAJOS = [
  { valor: 0, etiqueta: 'Sin próxima' },
  { valor: 21, etiqueta: '21 días' },
  { valor: 30, etiqueta: '30 días' },
  { valor: 365, etiqueta: '1 año' },
];

const SUGERENCIAS = ['Quíntuple', 'Séxtuple', 'Antirrábica', 'Triple felina', 'Tos de las perreras'].map((s) => ({
  valor: s,
  etiqueta: s,
}));

/** Registrar una vacuna o corregir una existente con ?editar=ID_VACUNA. */
export default function FormularioVacuna() {
  const { id, editar } = useLocalSearchParams<{ id: string; editar?: string }>();
  const { enviar, enviando, errores } = useEnvio(editar ? `vacunas/${editar}/` : `mascotas/${id}/vacunas/`);
  const [cargando, setCargando] = useState(!!editar);
  const [nombre, setNombre] = useState('');
  const [lote, setLote] = useState('');
  const [aplicacion, setAplicacion] = useState<Date | null>(new Date());
  const [proxima, setProxima] = useState<Date | null>(sumarDias(new Date(), 365));
  const [observaciones, setObservaciones] = useState('');

  useEffect(() => {
    if (!editar) return;
    api<Vacuna>(`vacunas/${editar}/`)
      .then((v) => {
        setNombre(v.nombre_vacuna);
        setLote(v.lote ?? '');
        setAplicacion(desdeISO(v.fecha_aplicacion));
        setProxima(v.fecha_proxima_dosis ? desdeISO(v.fecha_proxima_dosis) : null);
        setObservaciones(v.observaciones ?? '');
      })
      .finally(() => setCargando(false));
  }, [editar]);

  function guardar() {
    enviar(
      {
        nombre_vacuna: nombre.trim(),
        lote: lote.trim() || null,
        fecha_aplicacion: aplicacion ? aISO(aplicacion) : undefined,
        fecha_proxima_dosis: proxima ? aISO(proxima) : null,
        observaciones: observaciones.trim() || null,
      },
      editar ? 'Vacuna corregida' : 'Vacuna registrada',
      { method: editar ? 'PATCH' : 'POST' },
    );
  }

  if (cargando) return <EstadoCarga cargando error={null} />;

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton={editar ? 'Guardar cambios' : 'Registrar vacuna'}>
      {editar && <Stack.Screen options={{ title: 'Editar vacuna' }} />}

      <Campo etiqueta="Vacuna *" value={nombre} onChangeText={setNombre} error={errores.nombre_vacuna} />
      <Chips opciones={SUGERENCIAS} valor={nombre} onCambiar={setNombre} />

      <Campo etiqueta="N° de lote" value={lote} onChangeText={setLote} autoCapitalize="characters" error={errores.lote} />

      <SelectorFechaHora etiqueta="Fecha de aplicación" valor={aplicacion} onCambiar={setAplicacion}
        error={errores.fecha_aplicacion} />

      <Seccion titulo="Próxima dosis">
        <View style={{ gap: Spacing.sm }}>
          <Chips
            opciones={ATAJOS}
            valor={null}
            onCambiar={(dias) => setProxima(dias ? sumarDias(aplicacion ?? new Date(), dias) : null)}
          />
          <SelectorFechaHora etiqueta="Fecha" valor={proxima} onCambiar={setProxima} opcional
            error={errores.fecha_proxima_dosis} />
        </View>
      </Seccion>

      <Campo etiqueta="Observaciones" value={observaciones} onChangeText={setObservaciones}
        error={errores.observaciones} />
    </Formulario>
  );
}
