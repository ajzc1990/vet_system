import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Boton, BotonFlotante, EstadoCarga, Fila, Insignia, Tarjeta, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import { aISO, esHoy, hora, sumarDias, tituloDia } from '@/lib/fechas';
import { useSesion } from '@/lib/session';
import type { EstadoTurno, Paginado, Turno } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

export default function Agenda() {
  const t = useTheme();
  const insets = useSafeAreaInsets();
  const { usuario } = useSesion();
  const [dia, setDia] = useState(() => new Date());
  const { datos, error, cargando, refrescando, refrescar, setDatos } = useApi<Paginado<Turno>>(
    `turnos/?fecha=${aISO(dia)}`,
  );
  const [actualizando, setActualizando] = useState<number | null>(null);

  async function cambiarEstado(turno: Turno, estado: EstadoTurno) {
    setActualizando(turno.id);
    try {
      const actualizado = await api<Turno>(`turnos/${turno.id}/estado/`, { method: 'POST', body: { estado } });
      setDatos((d) => d && { ...d, results: d.results.map((x) => (x.id === turno.id ? actualizado : x)) });
    } catch (e) {
      Alert.alert('No se pudo actualizar el turno', e instanceof Error ? e.message : undefined);
    } finally {
      setActualizando(null);
    }
  }

  function confirmarCancelacion(turno: Turno) {
    Alert.alert('Cancelar turno', `¿Cancelar el turno de ${turno.mascota_nombre} a las ${hora(turno.fecha_hora)}?`, [
      { text: 'Volver', style: 'cancel' },
      { text: 'Cancelar turno', style: 'destructive', onPress: () => cambiarEstado(turno, 'CANCELADO') },
    ]);
  }

  const turnos = datos?.results ?? [];
  const activos = turnos.filter((x) => x.estado !== 'CANCELADO').length;

  return (
    <View style={{ flex: 1, backgroundColor: t.background }}>
      <View style={[styles.selectorDia, { backgroundColor: t.card, borderColor: t.border, paddingTop: insets.top + Spacing.md }]}>
        <Pressable hitSlop={12} onPress={() => setDia((d) => sumarDias(d, -1))} accessibilityLabel="Día anterior">
          <Ionicons name="chevron-back" size={24} color={t.primary} />
        </Pressable>
        <Pressable onPress={() => setDia(new Date())} style={{ alignItems: 'center' }}>
          <Texto variante="subtitulo">{tituloDia(dia)}</Texto>
          <Texto variante="secundario">
            {datos ? `${activos} ${activos === 1 ? 'turno' : 'turnos'}` : ' '}
            {!esHoy(dia) && ' · tocá para volver a hoy'}
          </Texto>
        </Pressable>
        <Pressable hitSlop={12} onPress={() => setDia((d) => sumarDias(d, 1))} accessibilityLabel="Día siguiente">
          <Ionicons name="chevron-forward" size={24} color={t.primary} />
        </Pressable>
      </View>

      <FlatList
        data={turnos}
        keyExtractor={(x) => String(x.id)}
        contentContainerStyle={styles.lista}
        refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={t.primary} />}
        ListEmptyComponent={
          <EstadoCarga
            cargando={cargando}
            error={error}
            vacio
            mensajeVacio="No hay turnos para este día."
            iconoVacio="calendar-clear-outline"
            onReintentar={refrescar}
          />
        }
        renderItem={({ item }) => {
          const abierto = item.estado === 'PENDIENTE' || item.estado === 'CONFIRMADO';
          return (
            <Tarjeta
              onPress={() => router.push({ pathname: '/mascota/[id]', params: { id: item.mascota } })}
              style={item.estado === 'CANCELADO' && { opacity: 0.55 }}>
              <View style={styles.cabecera}>
                <Texto variante="subtitulo">{hora(item.fecha_hora)}</Texto>
                <View style={styles.cabeceraDerecha}>
                  <Insignia texto={item.estado_display} estado={item.estado} />
                  <Pressable
                    hitSlop={10}
                    accessibilityLabel="Editar turno"
                    onPress={() => router.push({ pathname: '/turno/[id]', params: { id: item.id } })}>
                    <Ionicons name="create-outline" size={22} color={t.primary} />
                  </Pressable>
                </View>
              </View>
              <Texto style={{ fontWeight: '600' }}>{item.mascota_nombre}</Texto>
              <Fila icono="person-outline">{item.cliente_nombre}</Fila>
              {item.motivo ? <Fila icono="document-text-outline">{item.motivo}</Fila> : null}
              {item.veterinario_nombre ? <Fila icono="medkit-outline">{item.veterinario_nombre}</Fila> : null}

              {abierto && (
                <View style={styles.acciones}>
                  {usuario?.puede_atender && (
                    <Boton
                      titulo="Atender"
                      icono="play"
                      style={styles.accion}
                      onPress={() =>
                        router.push({
                          pathname: '/mascota/[id]/consulta',
                          params: { id: item.mascota, turno: item.id },
                        })
                      }
                    />
                  )}
                  {item.estado === 'PENDIENTE' && (
                    <Boton
                      titulo="Confirmar"
                      variante="secundario"
                      style={styles.accion}
                      cargando={actualizando === item.id}
                      onPress={() => cambiarEstado(item, 'CONFIRMADO')}
                    />
                  )}
                  <Pressable
                    hitSlop={8}
                    style={styles.cancelar}
                    onPress={() => confirmarCancelacion(item)}
                    accessibilityLabel="Cancelar turno">
                    <Ionicons name="close-circle-outline" size={26} color={t.danger} />
                  </Pressable>
                </View>
              )}
            </Tarjeta>
          );
        }}
      />
      <BotonFlotante
        icono="add"
        etiqueta="Turno"
        onPress={() => router.push({ pathname: '/turno/[id]', params: { id: 'nuevo', fecha: aISO(dia) } })}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  selectorDia: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  lista: { padding: Spacing.lg, paddingBottom: 96, gap: Spacing.md, flexGrow: 1 },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cabeceraDerecha: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  acciones: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.xs, alignItems: 'center' },
  accion: { flex: 1, minHeight: 40 },
  cancelar: { paddingHorizontal: Spacing.xs },
});
