import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Formulario, numero, useEnvio } from '@/components/formulario';
import { Campo, EstadoCarga, Insignia, Seccion } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import type { Consulta } from '@/lib/types';

const VACIA = {
  motivo_consulta: '',
  anamnesis: '',
  examen_clinico: '',
  diagnostico: '',
  tratamiento: '',
  observaciones_privadas: '',
  peso_actual_kg: '',
  temperatura_c: '',
  frecuencia_cardiaca: '',
  frecuencia_respiratoria: '',
};

/**
 * Nueva consulta (con ?turno= cuando se entra desde "Atender" en la agenda: la API lo
 * marca completado) o corrección de una existente con ?editar=ID_CONSULTA.
 */
export default function FormularioConsulta() {
  const { id, turno, editar } = useLocalSearchParams<{ id: string; turno?: string; editar?: string }>();
  const [f, setF] = useState(VACIA);
  const [cargando, setCargando] = useState(!!editar);
  const { enviar, enviando, errores } = useEnvio(editar ? `consultas/${editar}/` : `mascotas/${id}/consultas/`);
  const campo = (nombre: keyof typeof VACIA) => ({
    value: f[nombre],
    onChangeText: (v: string) => setF((prev) => ({ ...prev, [nombre]: v })),
    error: errores[nombre],
  });

  useEffect(() => {
    if (!editar) return;
    api<Consulta>(`consultas/${editar}/`)
      .then((c) =>
        setF(
          Object.fromEntries(
            Object.keys(VACIA).map((k) => [k, c[k as keyof Consulta] == null ? '' : String(c[k as keyof Consulta])]),
          ) as typeof VACIA,
        ),
      )
      .finally(() => setCargando(false));
  }, [editar]);

  function guardar() {
    enviar(
      {
        ...f,
        ...(editar ? {} : { turno: turno ? Number(turno) : null }),
        peso_actual_kg: numero(f.peso_actual_kg),
        temperatura_c: numero(f.temperatura_c),
        frecuencia_cardiaca: numero(f.frecuencia_cardiaca),
        frecuencia_respiratoria: numero(f.frecuencia_respiratoria),
      },
      editar ? 'Consulta corregida' : 'Consulta registrada',
      { method: editar ? 'PATCH' : 'POST' },
    );
  }

  if (cargando) return <EstadoCarga cargando error={null} />;

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton={editar ? 'Guardar cambios' : 'Guardar consulta'}
      errorGeneral={errores.turno}>
      {editar && <Stack.Screen options={{ title: 'Editar consulta' }} />}
      {turno && !editar && <Insignia texto="Al guardar, el turno queda completado" tono="exito" />}

      <Seccion titulo="Signos vitales">
        <View style={styles.grilla}>
          <View style={styles.celda}>
            <Campo etiqueta="Peso (kg)" keyboardType="decimal-pad" {...campo('peso_actual_kg')} />
          </View>
          <View style={styles.celda}>
            <Campo etiqueta="Temp. (°C)" keyboardType="decimal-pad" {...campo('temperatura_c')} />
          </View>
          <View style={styles.celda}>
            <Campo etiqueta="FC (lpm)" keyboardType="number-pad" {...campo('frecuencia_cardiaca')} />
          </View>
          <View style={styles.celda}>
            <Campo etiqueta="FR (rpm)" keyboardType="number-pad" {...campo('frecuencia_respiratoria')} />
          </View>
        </View>
      </Seccion>

      <Campo etiqueta="Motivo de consulta *" multiline {...campo('motivo_consulta')} />
      <Campo etiqueta="Anamnesis / síntomas" multiline {...campo('anamnesis')} />
      <Campo etiqueta="Examen clínico" multiline {...campo('examen_clinico')} />
      <Campo etiqueta="Diagnóstico *" multiline {...campo('diagnostico')} />
      <Campo etiqueta="Tratamiento e indicaciones *" multiline {...campo('tratamiento')} />
      <Campo etiqueta="Notas internas" placeholder="Sólo las ve el equipo de la clínica" multiline
        {...campo('observaciones_privadas')} />
    </Formulario>
  );
}

const styles = StyleSheet.create({
  grilla: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md },
  celda: { flexBasis: '46%', flexGrow: 1 },
});
