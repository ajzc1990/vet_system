import Ionicons from '@expo/vector-icons/Ionicons';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Formulario, useEnvio } from '@/components/formulario';
import { Boton, Campo, Tarjeta, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import type { ItemReceta } from '@/lib/types';
import { useTheme } from '@/lib/use-theme';

const ITEM_VACIO: ItemReceta = { medicamento: '', dosis: '', duracion: '', indicaciones: '' };

export default function NuevaReceta() {
  const t = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { enviar, enviando, errores } = useEnvio(`mascotas/${id}/recetas/`);
  const [diagnostico, setDiagnostico] = useState('');
  const [observaciones, setObservaciones] = useState('');
  const [items, setItems] = useState<ItemReceta[]>([{ ...ITEM_VACIO }]);

  function editarItem(indice: number, campo: keyof ItemReceta, valor: string) {
    setItems((prev) => prev.map((it, i) => (i === indice ? { ...it, [campo]: valor } : it)));
  }

  function guardar() {
    enviar(
      {
        diagnostico: diagnostico.trim(),
        observaciones: observaciones.trim(),
        items: items.filter((i) => i.medicamento.trim()),
      },
      'Receta emitida',
    );
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Emitir receta" errorGeneral={errores.items}>
      <Campo etiqueta="Diagnóstico" value={diagnostico} onChangeText={setDiagnostico} error={errores.diagnostico} />

      {items.map((item, i) => (
        <Tarjeta key={i}>
          <View style={styles.cabecera}>
            <Texto variante="etiqueta">Medicamento {i + 1}</Texto>
            {items.length > 1 && (
              <Pressable hitSlop={10} accessibilityLabel="Quitar medicamento"
                onPress={() => setItems((prev) => prev.filter((_, j) => j !== i))}>
                <Ionicons name="trash-outline" size={20} color={t.danger} />
              </Pressable>
            )}
          </View>
          <Campo etiqueta="Medicamento *" value={item.medicamento} onChangeText={(v) => editarItem(i, 'medicamento', v)} />
          <View style={styles.fila}>
            <View style={{ flex: 1 }}>
              <Campo etiqueta="Dosis" placeholder="1 comp. c/12 h" value={item.dosis}
                onChangeText={(v) => editarItem(i, 'dosis', v)} />
            </View>
            <View style={{ flex: 1 }}>
              <Campo etiqueta="Duración" placeholder="7 días" value={item.duracion}
                onChangeText={(v) => editarItem(i, 'duracion', v)} />
            </View>
          </View>
          <Campo etiqueta="Indicaciones" placeholder="Con alimento" value={item.indicaciones}
            onChangeText={(v) => editarItem(i, 'indicaciones', v)} />
        </Tarjeta>
      ))}

      <Boton titulo="Agregar medicamento" icono="add" variante="secundario"
        onPress={() => setItems((prev) => [...prev, { ...ITEM_VACIO }])} />

      <Campo etiqueta="Observaciones" multiline value={observaciones} onChangeText={setObservaciones}
        error={errores.observaciones} />
    </Formulario>
  );
}

const styles = StyleSheet.create({
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  fila: { flexDirection: 'row', gap: Spacing.md },
});
