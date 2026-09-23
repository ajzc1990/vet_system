import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { Tarjeta, Texto } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import type { Mascota, Paginado } from '@/lib/types';
import { useTheme } from '@/lib/use-theme';

export type MascotaElegida = Pick<Mascota, 'id' | 'nombre' | 'cliente_nombre'>;

/** Elegir un paciente buscando por mascota, tutor o DNI (para agendar un turno). */
export function BuscadorMascota({
  valor,
  onCambiar,
  error,
}: {
  valor: MascotaElegida | null;
  onCambiar: (mascota: MascotaElegida | null) => void;
  error?: string;
}) {
  const t = useTheme();
  const [texto, setTexto] = useState('');
  const [resultados, setResultados] = useState<Mascota[]>([]);
  const [buscando, setBuscando] = useState(false);

  useEffect(() => {
    const q = texto.trim();
    if (valor || q.length < 2) return;
    let vigente = true;
    const id = setTimeout(async () => {
      setBuscando(true);
      try {
        const r = await api<Paginado<Mascota>>(`mascotas/?q=${encodeURIComponent(q)}`);
        if (vigente) setResultados(r.results.slice(0, 8));
      } catch {
        if (vigente) setResultados([]);
      } finally {
        if (vigente) setBuscando(false);
      }
    }, 350);
    return () => {
      vigente = false;
      clearTimeout(id);
    };
  }, [texto, valor]);

  // Con menos de 2 letras no se busca: se muestran 0 resultados sin tocar el estado.
  const visibles = texto.trim().length < 2 ? [] : resultados;

  if (valor) {
    return (
      <View style={{ gap: Spacing.xs }}>
        <Texto variante="etiqueta">Paciente *</Texto>
        <Tarjeta style={styles.elegida}>
          <Ionicons name="paw" size={20} color={t.primary} />
          <View style={{ flex: 1 }}>
            <Texto style={{ fontWeight: '600' }}>{valor.nombre}</Texto>
            <Texto variante="secundario">{valor.cliente_nombre}</Texto>
          </View>
          <Pressable hitSlop={10} onPress={() => onCambiar(null)} accessibilityLabel="Cambiar paciente">
            <Texto style={{ color: t.primary, fontWeight: '600' }}>Cambiar</Texto>
          </Pressable>
        </Tarjeta>
      </View>
    );
  }

  return (
    <View style={{ gap: Spacing.xs }}>
      <Texto variante="etiqueta">Paciente *</Texto>
      <View style={[styles.buscador, { backgroundColor: t.card, borderColor: error ? t.danger : t.border }]}>
        <Ionicons name="search" size={18} color={t.textSecondary} />
        <TextInput
          value={texto}
          onChangeText={setTexto}
          placeholder="Buscar mascota, tutor o DNI"
          placeholderTextColor={t.textSecondary}
          style={[styles.input, { color: t.text }]}
          autoCorrect={false}
        />
        {buscando && <ActivityIndicator color={t.primary} />}
      </View>
      {error && <Texto style={{ color: t.danger, fontSize: 13 }}>{error}</Texto>}
      {visibles.map((m) => (
        <Pressable
          key={m.id}
          onPress={() => onCambiar({ id: m.id, nombre: m.nombre, cliente_nombre: m.cliente_nombre })}
          style={({ pressed }) => [styles.resultado, { borderColor: t.border, opacity: pressed ? 0.6 : 1 }]}>
          <Texto style={{ fontWeight: '600' }}>{m.nombre}</Texto>
          <Texto variante="secundario">
            {m.especie_display} · {m.cliente_nombre}
          </Texto>
        </Pressable>
      ))}
      {texto.trim().length >= 2 && !buscando && visibles.length === 0 && (
        <Texto variante="secundario">Sin resultados.</Texto>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  elegida: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  buscador: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderRadius: Radius.sm,
    borderWidth: 1,
  },
  input: { flex: 1, fontSize: 16, paddingVertical: Spacing.md },
  resultado: { paddingVertical: Spacing.sm, paddingHorizontal: Spacing.xs, borderBottomWidth: StyleSheet.hairlineWidth },
});
