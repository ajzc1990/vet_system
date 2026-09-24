import { useState } from 'react';
import { Alert, FlatList, Linking, RefreshControl, StyleSheet, View } from 'react-native';

import { Boton, Chips, EstadoCarga, Fila, Insignia, Tarjeta, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import { fechaCorta } from '@/lib/fechas';
import type { Paginado, SolicitudTurno } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

const FILTROS = [
  { valor: 'pendientes', etiqueta: 'Pendientes' },
  { valor: 'todas', etiqueta: 'Todas' },
] as const;

/** Pedidos de turno que los clientes hacen desde el Portal; llega un push por cada uno nuevo. */
export default function Solicitudes() {
  const t = useTheme();
  const [filtro, setFiltro] = useState<'pendientes' | 'todas'>('pendientes');
  const { datos, error, cargando, refrescando, refrescar, setDatos } = useApi<Paginado<SolicitudTurno>>(
    filtro === 'pendientes' ? 'solicitudes/?pendientes=1' : 'solicitudes/',
  );
  const [actualizando, setActualizando] = useState<number | null>(null);

  async function marcar(s: SolicitudTurno, estado: 'CONTACTADO' | 'DESCARTADO') {
    setActualizando(s.id);
    try {
      const actualizada = await api<SolicitudTurno>(`solicitudes/${s.id}/estado/`, { method: 'POST', body: { estado } });
      setDatos((d) => {
        if (!d) return d;
        const resultados = filtro === 'pendientes'
          ? d.results.filter((x) => x.id !== s.id)
          : d.results.map((x) => (x.id === s.id ? actualizada : x));
        return { ...d, results: resultados };
      });
    } catch (e) {
      Alert.alert('No se pudo actualizar', e instanceof Error ? e.message : undefined);
    } finally {
      setActualizando(null);
    }
  }

  function whatsapp(s: SolicitudTurno) {
    const telefono = s.telefono.replace(/\D/g, '');
    const mensaje = `Hola ${s.nombre_tutor.split(' ')[0]}! Te escribimos por el turno que pediste para ${s.nombre_mascota}.`;
    Linking.openURL(`https://wa.me/${telefono}?text=${encodeURIComponent(mensaje)}`);
  }

  return (
    <FlatList
      style={{ backgroundColor: t.background }}
      data={datos?.results ?? []}
      keyExtractor={(s) => String(s.id)}
      contentContainerStyle={styles.lista}
      refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={t.primary} />}
      ListHeaderComponent={<Chips opciones={[...FILTROS]} valor={filtro} onCambiar={setFiltro} />}
      ListEmptyComponent={
        <EstadoCarga cargando={cargando} error={error} vacio iconoVacio="mail-open-outline"
          mensajeVacio={filtro === 'pendientes' ? 'No hay solicitudes pendientes.' : 'Todavía no hubo solicitudes.'}
          onReintentar={refrescar} />
      }
      renderItem={({ item: s }) => (
        <Tarjeta>
          <View style={styles.cabecera}>
            <Texto variante="subtitulo">{s.nombre_mascota}</Texto>
            <Insignia texto={s.estado_display} tono={s.estado === 'PENDIENTE' ? 'alerta' : s.estado === 'CONTACTADO' ? 'exito' : 'neutro'} />
          </View>
          <Fila icono="person-outline">{s.nombre_tutor} · {s.telefono}</Fila>
          <Fila icono="calendar-outline">
            Quiere el {fechaCorta(s.fecha_deseada)} · {s.franja_preferida_display}
          </Fila>
          <Texto>{s.motivo}</Texto>
          <Texto variante="secundario">Pedido el {fechaCorta(s.creado_el)}</Texto>

          <View style={styles.acciones}>
            <Boton titulo="WhatsApp" icono="logo-whatsapp" variante="secundario" style={styles.accion} onPress={() => whatsapp(s)} />
            <Boton titulo="Llamar" icono="call" variante="secundario" style={styles.accion}
              onPress={() => Linking.openURL(`tel:${s.telefono.replace(/\D/g, '')}`)} />
          </View>
          {s.estado === 'PENDIENTE' && (
            <View style={styles.acciones}>
              <Boton titulo="Contactado" icono="checkmark" style={styles.accion} cargando={actualizando === s.id}
                onPress={() => marcar(s, 'CONTACTADO')} />
              <Boton titulo="Descartar" variante="peligro" style={styles.accion} disabled={actualizando === s.id}
                onPress={() => marcar(s, 'DESCARTADO')} />
            </View>
          )}
        </Tarjeta>
      )}
    />
  );
}

const styles = StyleSheet.create({
  lista: { padding: Spacing.lg, gap: Spacing.md, flexGrow: 1 },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.sm },
  acciones: { flexDirection: 'row', gap: Spacing.sm },
  accion: { flex: 1, minHeight: 42 },
});
