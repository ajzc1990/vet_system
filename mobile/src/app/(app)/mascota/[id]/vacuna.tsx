import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Formulario, useEnvio } from '@/components/formulario';
import { Campo, Seccion } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { aISO, desdeISO, sumarDias } from '@/lib/fechas';
import { useTheme } from '@/lib/use-theme';

// Esquemas habituales de revacunación, para no tener que tipear la fecha en el celular.
const ATAJOS = [
  { etiqueta: 'Sin próxima', dias: null },
  { etiqueta: '21 días', dias: 21 },
  { etiqueta: '30 días', dias: 30 },
  { etiqueta: '1 año', dias: 365 },
];

const SUGERENCIAS = ['Quíntuple', 'Séxtuple', 'Antirrábica', 'Triple felina', 'Tos de las perreras'];

export default function RegistrarVacuna() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { enviar, enviando, errores } = useEnvio(`mascotas/${id}/vacunas/`);
  const [nombre, setNombre] = useState('');
  const [lote, setLote] = useState('');
  const [aplicacion, setAplicacion] = useState(aISO(new Date()));
  const [proxima, setProxima] = useState(aISO(sumarDias(new Date(), 365)));
  const [observaciones, setObservaciones] = useState('');

  function aplicarAtajo(dias: number | null) {
    if (dias === null) return setProxima('');
    const base = /^\d{4}-\d{2}-\d{2}$/.test(aplicacion) ? desdeISO(aplicacion) : new Date();
    setProxima(aISO(sumarDias(base, dias)));
  }

  function guardar() {
    enviar(
      {
        nombre_vacuna: nombre.trim(),
        lote: lote.trim() || null,
        fecha_aplicacion: aplicacion,
        fecha_proxima_dosis: proxima || null,
        observaciones: observaciones.trim() || null,
      },
      'Vacuna registrada',
    );
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Registrar vacuna">
      <Campo etiqueta="Vacuna *" value={nombre} onChangeText={setNombre} error={errores.nombre_vacuna} />
      <View style={styles.chips}>
        {SUGERENCIAS.map((s) => (
          <Chip key={s} texto={s} activo={nombre === s} onPress={() => setNombre(s)} />
        ))}
      </View>

      <Campo etiqueta="N° de lote" value={lote} onChangeText={setLote} autoCapitalize="characters" error={errores.lote} />

      <Campo
        etiqueta="Fecha de aplicación (AAAA-MM-DD)"
        value={aplicacion}
        onChangeText={setAplicacion}
        keyboardType="numbers-and-punctuation"
        error={errores.fecha_aplicacion}
      />

      <Seccion titulo="Próxima dosis">
        <View style={styles.chips}>
          {ATAJOS.map((a) => (
            <Chip key={a.etiqueta} texto={a.etiqueta} onPress={() => aplicarAtajo(a.dias)}
              activo={a.dias === null ? proxima === '' : false} />
          ))}
        </View>
        <Campo
          etiqueta="Fecha (AAAA-MM-DD)"
          value={proxima}
          onChangeText={setProxima}
          placeholder="Sin revacunación"
          keyboardType="numbers-and-punctuation"
          error={errores.fecha_proxima_dosis}
        />
      </Seccion>

      <Campo etiqueta="Observaciones" value={observaciones} onChangeText={setObservaciones}
        error={errores.observaciones} />
    </Formulario>
  );
}

function Chip({ texto, activo, onPress }: { texto: string; activo: boolean; onPress: () => void }) {
  const t = useTheme();
  return (
    <Pressable onPress={onPress} style={[styles.chip, { backgroundColor: activo ? t.primary : t.primaryLight }]}>
      <Text style={{ color: activo ? t.onPrimary : t.primaryDark, fontWeight: '600' }}>{texto}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, borderRadius: Radius.lg },
});
