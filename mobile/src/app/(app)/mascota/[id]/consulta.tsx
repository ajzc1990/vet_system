import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Formulario, numero, useEnvio } from '@/components/formulario';
import { Campo, Insignia, Seccion } from '@/components/ui';
import { Spacing } from '@/constants/theme';

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

export default function NuevaConsulta() {
  // "turno" llega cuando se entra desde "Atender" en la agenda: la API lo marca completado.
  const { id, turno } = useLocalSearchParams<{ id: string; turno?: string }>();
  const [f, setF] = useState(VACIA);
  const { enviar, enviando, errores } = useEnvio(`mascotas/${id}/consultas/`);
  const campo = (nombre: keyof typeof VACIA) => ({
    value: f[nombre],
    onChangeText: (v: string) => setF((prev) => ({ ...prev, [nombre]: v })),
    error: errores[nombre],
  });

  function guardar() {
    enviar(
      {
        ...f,
        turno: turno ? Number(turno) : null,
        peso_actual_kg: numero(f.peso_actual_kg),
        temperatura_c: numero(f.temperatura_c),
        frecuencia_cardiaca: numero(f.frecuencia_cardiaca),
        frecuencia_respiratoria: numero(f.frecuencia_respiratoria),
      },
      'Consulta registrada',
    );
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Guardar consulta" errorGeneral={errores.turno}>
      {turno && <Insignia texto="Al guardar, el turno queda completado" tono="exito" />}

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
