import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, TextInput, View } from 'react-native';

import { EstadoCarga, Tarjeta, Texto } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { edad } from '@/lib/fechas';
import type { Mascota, Paginado } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

const ICONO_ESPECIE: Record<string, keyof typeof Ionicons.glyphMap> = {
  CANINO: 'paw',
  FELINO: 'paw-outline',
};

export default function Pacientes() {
  const t = useTheme();
  const [busqueda, setBusqueda] = useState('');
  const [consulta, setConsulta] = useState('');

  // Espera a que el usuario deje de tipear para no disparar un request por letra.
  useEffect(() => {
    const id = setTimeout(() => setConsulta(busqueda.trim()), 350);
    return () => clearTimeout(id);
  }, [busqueda]);

  const { datos, error, cargando, refrescando, refrescar } = useApi<Paginado<Mascota>>(
    `mascotas/?q=${encodeURIComponent(consulta)}`,
  );

  return (
    <View style={{ flex: 1, backgroundColor: t.background }}>
      <View style={[styles.buscador, { backgroundColor: t.card, borderColor: t.border }]}>
        <Ionicons name="search" size={18} color={t.textSecondary} />
        <TextInput
          value={busqueda}
          onChangeText={setBusqueda}
          placeholder="Mascota, tutor o DNI"
          placeholderTextColor={t.textSecondary}
          style={[styles.input, { color: t.text }]}
          autoCorrect={false}
          clearButtonMode="while-editing"
          returnKeyType="search"
        />
      </View>

      <FlatList
        data={datos?.results ?? []}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={styles.lista}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={t.primary} />}
        ListHeaderComponent={
          datos && datos.count > datos.results.length ? (
            <Texto variante="secundario">
              Mostrando {datos.results.length} de {datos.count}. Afiná la búsqueda para encontrar al paciente.
            </Texto>
          ) : null
        }
        ListEmptyComponent={
          <EstadoCarga
            cargando={cargando}
            error={error}
            vacio
            mensajeVacio={consulta ? `Sin resultados para "${consulta}".` : 'Todavía no hay pacientes cargados.'}
            iconoVacio="paw-outline"
            onReintentar={refrescar}
          />
        }
        renderItem={({ item }) => {
          const años = edad(item.fecha_nacimiento);
          return (
            <Tarjeta onPress={() => router.push({ pathname: '/mascota/[id]', params: { id: item.id } })}>
              <View style={styles.fila}>
                <View style={[styles.avatar, { backgroundColor: t.primaryLight }]}>
                  <Ionicons name={ICONO_ESPECIE[item.especie] ?? 'paw'} size={22} color={t.primaryDark} />
                </View>
                <View style={{ flex: 1, gap: 2 }}>
                  <Texto variante="subtitulo">{item.nombre}</Texto>
                  <Texto variante="secundario">
                    {[item.especie_display, item.raza, años].filter(Boolean).join(' · ')}
                  </Texto>
                  <Texto variante="secundario">Tutor: {item.cliente_nombre}</Texto>
                </View>
                <Ionicons name="chevron-forward" size={20} color={t.textSecondary} />
              </View>
            </Tarjeta>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  buscador: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    margin: Spacing.lg,
    marginBottom: 0,
    paddingHorizontal: Spacing.md,
    borderRadius: Radius.md,
    borderWidth: StyleSheet.hairlineWidth,
  },
  input: { flex: 1, fontSize: 16, paddingVertical: Spacing.md },
  lista: { padding: Spacing.lg, gap: Spacing.md, flexGrow: 1 },
  fila: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
});
