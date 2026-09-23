import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { EstadoCarga, Fila, Insignia, Tarjeta, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import type { InternacionDetalle, Paginado } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

const TONO_ESTADO: Record<string, 'exito' | 'alerta' | 'peligro' | 'neutro'> = {
  ESTABLE: 'neutro',
  MEJORANDO: 'exito',
  SIN_CAMBIOS: 'neutro',
  EMPEORANDO: 'alerta',
  CRITICO: 'peligro',
};

/** Sala de internación: pacientes internados ahora, con su último control. */
export default function Internados() {
  const t = useTheme();
  const { datos, error, cargando, refrescando, refrescar } = useApi<Paginado<InternacionDetalle>>(
    'internaciones/?activas=1',
  );

  return (
    <FlatList
      style={{ backgroundColor: t.background }}
      data={datos?.results ?? []}
      keyExtractor={(i) => String(i.id)}
      contentContainerStyle={styles.lista}
      refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={t.primary} />}
      ListEmptyComponent={
        <EstadoCarga cargando={cargando} error={error} vacio mensajeVacio="No hay pacientes internados."
          iconoVacio="bed-outline" onReintentar={refrescar} />
      }
      renderItem={({ item }) => {
        const ultimo = item.evoluciones[0];
        return (
          <Tarjeta onPress={() => router.push({ pathname: '/internacion/[id]', params: { id: item.id } })}>
            <View style={styles.cabecera}>
              <Texto variante="subtitulo">{item.mascota_nombre}</Texto>
              {item.box ? <Insignia texto={`Box ${item.box}`} /> : null}
            </View>
            <Texto variante="secundario" numberOfLines={2}>{item.motivo_ingreso}</Texto>
            <Fila icono="time-outline">
              {item.dias_internado === 1 ? '1 día' : `${item.dias_internado} días`} internado · {item.cliente_nombre}
            </Fila>
            {ultimo ? (
              <View style={styles.cabecera}>
                <Insignia texto={ultimo.estado_general_display} tono={TONO_ESTADO[ultimo.estado_general]} />
                <Texto variante="secundario">
                  Último control {new Date(ultimo.fecha_hora).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
                </Texto>
              </View>
            ) : (
              <Fila icono="alert-circle-outline">Sin controles registrados</Fila>
            )}
            <Ionicons name="chevron-forward" size={18} color={t.textSecondary} style={styles.flecha} />
          </Tarjeta>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  lista: { padding: Spacing.lg, gap: Spacing.md, flexGrow: 1 },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.sm },
  flecha: { position: 'absolute', right: Spacing.md, top: '50%' },
});
