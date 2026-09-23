import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { SelectorFechaHora } from '@/components/fecha-hora';
import { Formulario, numero, useEnvio } from '@/components/formulario';
import { Campo, Chips, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { aISO } from '@/lib/fechas';
import type { InternacionDetalle, Paginado, Veterinario } from '@/lib/types';
import { useApi } from '@/lib/use-api';

export default function Internar() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { enviar, enviando, errores } = useEnvio(`mascotas/${id}/internar/`);
  const veterinarios = useApi<Paginado<Veterinario>>('veterinarios/');
  const [f, setF] = useState({ box: '', motivo_ingreso: '', diagnostico_ingreso: '', dieta_indicaciones: '', costo: '' });
  const [responsable, setResponsable] = useState<number | null>(null);
  const [altaEstimada, setAltaEstimada] = useState<Date | null>(null);
  const campo = (nombre: keyof typeof f) => ({
    value: f[nombre],
    onChangeText: (v: string) => setF((prev) => ({ ...prev, [nombre]: v })),
  });

  function guardar() {
    enviar<InternacionDetalle>(
      {
        box: f.box.trim() || null,
        motivo_ingreso: f.motivo_ingreso.trim(),
        diagnostico_ingreso: f.diagnostico_ingreso.trim() || null,
        dieta_indicaciones: f.dieta_indicaciones.trim() || null,
        costo_dia_estadia: numero(f.costo) ?? '0',
        veterinario_responsable: responsable,
        fecha_alta_estimada: altaEstimada ? aISO(altaEstimada) : null,
      },
      'Paciente internado',
      { onExito: (i) => router.replace({ pathname: '/internacion/[id]', params: { id: i.id } }) },
    );
  }

  const opcionesVet = (veterinarios.datos?.results ?? []).map((v) => ({ valor: v.id, etiqueta: `${v.nombre} ${v.apellido}` }));

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Internar">
      <Campo etiqueta="Motivo de internación *" multiline {...campo('motivo_ingreso')} error={errores.motivo_ingreso} />
      <Campo etiqueta="Diagnóstico al ingreso" multiline {...campo('diagnostico_ingreso')} />
      <Campo etiqueta="Box / jaula" placeholder="Box 3" {...campo('box')} />
      {opcionesVet.length > 0 && (
        <View style={{ gap: Spacing.xs }}>
          <Texto variante="etiqueta">Veterinario responsable</Texto>
          <Chips opciones={opcionesVet} valor={responsable} onCambiar={setResponsable} />
        </View>
      )}
      <Campo etiqueta="Dieta e indicaciones" multiline {...campo('dieta_indicaciones')} />
      <SelectorFechaHora etiqueta="Alta estimada" valor={altaEstimada} onCambiar={setAltaEstimada} opcional />
      <Campo etiqueta="Costo por día de estadía" keyboardType="decimal-pad" {...campo('costo')}
        error={errores.costo_dia_estadia} />
    </Formulario>
  );
}
