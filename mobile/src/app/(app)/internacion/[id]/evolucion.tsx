import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Formulario, numero, useEnvio } from '@/components/formulario';
import { Campo, Chips, Seccion } from '@/components/ui';
import { Spacing } from '@/constants/theme';

const ESTADOS = [
  { valor: 'ESTABLE', etiqueta: 'Estable' },
  { valor: 'MEJORANDO', etiqueta: 'Mejorando' },
  { valor: 'SIN_CAMBIOS', etiqueta: 'Sin cambios' },
  { valor: 'EMPEORANDO', etiqueta: 'Empeorando' },
  { valor: 'CRITICO', etiqueta: 'Crítico' },
];

export default function NuevaEvolucion() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { enviar, enviando, errores } = useEnvio(`internaciones/${id}/evoluciones/`);
  const [estado, setEstado] = useState('ESTABLE');
  const [f, setF] = useState({ temp: '', fc: '', fr: '', peso: '', notas: '', medicacion: '' });
  const campo = (nombre: keyof typeof f) => ({
    value: f[nombre],
    onChangeText: (v: string) => setF((prev) => ({ ...prev, [nombre]: v })),
  });

  function guardar() {
    enviar(
      {
        estado_general: estado,
        temperatura_c: numero(f.temp),
        frecuencia_cardiaca: numero(f.fc),
        frecuencia_respiratoria: numero(f.fr),
        peso_kg: numero(f.peso),
        notas: f.notas.trim(),
        medicacion_administrada: f.medicacion.trim() || null,
      },
      'Control registrado',
    );
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Guardar control" errorGeneral={errores.detail}>
      <Seccion titulo="Estado general">
        <Chips opciones={ESTADOS} valor={estado} onCambiar={setEstado} />
      </Seccion>
      <Seccion titulo="Signos vitales">
        <View style={styles.grilla}>
          <View style={styles.celda}><Campo etiqueta="Temp. (°C)" keyboardType="decimal-pad" {...campo('temp')} error={errores.temperatura_c} /></View>
          <View style={styles.celda}><Campo etiqueta="Peso (kg)" keyboardType="decimal-pad" {...campo('peso')} error={errores.peso_kg} /></View>
          <View style={styles.celda}><Campo etiqueta="FC (lpm)" keyboardType="number-pad" {...campo('fc')} error={errores.frecuencia_cardiaca} /></View>
          <View style={styles.celda}><Campo etiqueta="FR (rpm)" keyboardType="number-pad" {...campo('fr')} error={errores.frecuencia_respiratoria} /></View>
        </View>
      </Seccion>
      <Campo etiqueta="Evolución / novedades *" multiline {...campo('notas')} error={errores.notas} />
      <Campo etiqueta="Medicación o procedimiento" placeholder="Ceftriaxona 25 mg/kg IV" {...campo('medicacion')}
        error={errores.medicacion_administrada} />
    </Formulario>
  );
}

const styles = StyleSheet.create({
  grilla: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.md },
  celda: { flexBasis: '46%', flexGrow: 1 },
});
