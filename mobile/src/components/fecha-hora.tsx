import Ionicons from '@expo/vector-icons/Ionicons';
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { Texto } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { fechaCorta, hora } from '@/lib/fechas';
import { useTheme } from '@/lib/use-theme';

type Props = {
  etiqueta: string;
  valor: Date | null;
  onCambiar: (valor: Date | null) => void;
  /** 'fecha' sólo pide el día; 'fechahora' también la hora (turnos). */
  modo?: 'fecha' | 'fechahora';
  /** Muestra "Quitar" para campos opcionales (fecha de nacimiento, próxima dosis...). */
  opcional?: boolean;
  error?: string;
};

/**
 * Selector nativo de fecha/hora: en Android abre el diálogo del sistema (API imperativa,
 * la recomendada por la librería) y en iOS muestra el selector compacto en línea.
 */
export function SelectorFechaHora({ etiqueta, valor, onCambiar, modo = 'fecha', opcional, error }: Props) {
  const t = useTheme();
  const base = valor ?? new Date();

  function combinar(elegida: Date, parte: 'date' | 'time') {
    const nueva = new Date(base);
    if (parte === 'date') nueva.setFullYear(elegida.getFullYear(), elegida.getMonth(), elegida.getDate());
    else nueva.setHours(elegida.getHours(), elegida.getMinutes(), 0, 0);
    onCambiar(nueva);
  }

  function abrirAndroid(parte: 'date' | 'time') {
    DateTimePickerAndroid.open({
      value: base,
      mode: parte,
      is24Hour: true,
      onValueChange: (_, elegida) => combinar(elegida, parte),
    });
  }

  return (
    <View style={{ gap: Spacing.xs }}>
      <View style={styles.cabecera}>
        <Texto variante="etiqueta">{etiqueta}</Texto>
        {opcional && valor && (
          <Pressable hitSlop={8} onPress={() => onCambiar(null)}>
            <Text style={{ color: t.danger, fontWeight: '600' }}>Quitar</Text>
          </Pressable>
        )}
      </View>

      {Platform.OS === 'ios' ? (
        <View style={styles.fila}>
          <DateTimePicker
            value={base}
            mode="date"
            display="compact"
            locale="es-AR"
            onValueChange={(_, elegida) => combinar(elegida, 'date')}
          />
          {modo === 'fechahora' && (
            <DateTimePicker
              value={base}
              mode="time"
              display="compact"
              locale="es-AR"
              onValueChange={(_, elegida) => combinar(elegida, 'time')}
            />
          )}
        </View>
      ) : (
        <View style={styles.fila}>
          <Boton
            icono="calendar-outline"
            texto={valor ? fechaCorta(valor.toISOString()) : 'Elegir fecha'}
            onPress={() => abrirAndroid('date')}
            error={!!error}
          />
          {modo === 'fechahora' && (
            <Boton
              icono="time-outline"
              texto={valor ? hora(valor.toISOString()) : 'Hora'}
              onPress={() => abrirAndroid('time')}
              error={!!error}
            />
          )}
        </View>
      )}
      {error && <Texto style={{ color: t.danger, fontSize: 13 }}>{error}</Texto>}
    </View>
  );
}

function Boton({ icono, texto, onPress, error }: {
  icono: 'calendar-outline' | 'time-outline';
  texto: string;
  onPress: () => void;
  error: boolean;
}) {
  const t = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.boton,
        { backgroundColor: t.card, borderColor: error ? t.danger : t.border, opacity: pressed ? 0.7 : 1 },
      ]}>
      <Ionicons name={icono} size={18} color={t.primary} />
      <Text style={{ color: t.text, fontSize: 16 }}>{texto}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  fila: { flexDirection: 'row', gap: Spacing.sm, alignItems: 'center' },
  boton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    borderWidth: 1,
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
  },
});
