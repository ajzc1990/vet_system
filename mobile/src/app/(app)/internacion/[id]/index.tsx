import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Linking, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { Boton, EstadoCarga, Fila, Insignia, Seccion, Tarjeta, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { compartirPdf } from '@/lib/api';
import { fechaCorta, hora } from '@/lib/fechas';
import { useSesion } from '@/lib/session';
import type { InternacionDetalle } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

export default function DetalleInternacion() {
  const t = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { usuario } = useSesion();
  const { datos: i, error, cargando, refrescando, refrescar } = useApi<InternacionDetalle>(`internaciones/${id}/`);
  const [compartiendo, setCompartiendo] = useState(false);

  if (!i) return <EstadoCarga cargando={cargando} error={error} onReintentar={refrescar} />;

  const activa = i.estado === 'INTERNADO';
  const telefono = i.cliente_telefono?.replace(/\D/g, '');

  async function informe() {
    setCompartiendo(true);
    try {
      await compartirPdf(`internaciones/${i!.id}/informe-pdf/`, `Internacion_${i!.mascota_nombre}.pdf`);
    } catch (e) {
      Alert.alert('No se pudo compartir', e instanceof Error ? e.message : undefined);
    } finally {
      setCompartiendo(false);
    }
  }

  return (
    <ScrollView
      style={{ backgroundColor: t.background }}
      contentContainerStyle={styles.contenedor}
      refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={t.primary} />}>
      <Stack.Screen options={{ title: `Internación · ${i.mascota_nombre}` }} />

      <Tarjeta>
        <View style={styles.cabecera}>
          <Texto variante="titulo">{i.mascota_nombre}</Texto>
          <Insignia texto={i.estado_display} tono={activa ? 'alerta' : 'exito'} />
        </View>
        <Fila icono="calendar-outline">
          Ingreso {fechaCorta(i.fecha_ingreso)} {hora(i.fecha_ingreso)} · {i.dias_internado} día(s)
        </Fila>
        {i.box ? <Fila icono="bed-outline">Box {i.box}</Fila> : null}
        {i.veterinario_responsable_nombre ? <Fila icono="medkit-outline">{i.veterinario_responsable_nombre}</Fila> : null}
        {i.fecha_alta_estimada ? <Fila icono="flag-outline">Alta estimada {fechaCorta(i.fecha_alta_estimada)}</Fila> : null}
        <Texto style={{ marginTop: Spacing.sm }}>{i.motivo_ingreso}</Texto>
        {i.diagnostico_ingreso ? <Texto variante="secundario">Dx: {i.diagnostico_ingreso}</Texto> : null}
        {i.dieta_indicaciones ? <Fila icono="nutrition-outline">{i.dieta_indicaciones}</Fila> : null}
      </Tarjeta>

      {!activa && i.resumen_alta ? (
        <Tarjeta style={{ backgroundColor: t.successBg, borderColor: t.successBg }}>
          <Texto variante="etiqueta">Epicrisis</Texto>
          <Texto>{i.resumen_alta}</Texto>
        </Tarjeta>
      ) : null}

      {activa && usuario?.puede_atender && (
        <View style={styles.acciones}>
          <Boton titulo="Nuevo control" icono="add" style={{ flex: 1 }}
            onPress={() => router.push({ pathname: '/internacion/[id]/evolucion', params: { id: i.id } })} />
          <Boton titulo="Dar alta" icono="exit-outline" variante="secundario" style={{ flex: 1 }}
            onPress={() => router.push({ pathname: '/internacion/[id]/alta', params: { id: i.id } })} />
        </View>
      )}

      <View style={styles.acciones}>
        <Boton titulo="Informe PDF" icono="share-outline" variante="secundario" style={{ flex: 1 }}
          cargando={compartiendo} onPress={informe} />
        {telefono ? (
          <Boton titulo="Avisar al tutor" icono="logo-whatsapp" variante="secundario" style={{ flex: 1 }}
            onPress={() => Linking.openURL(`https://wa.me/${telefono}`)} />
        ) : null}
      </View>

      <Seccion titulo={`Controles (${i.evoluciones.length})`}>
        {i.evoluciones.length === 0 && <Texto variante="secundario">Todavía no hay controles registrados.</Texto>}
        {i.evoluciones.map((e) => {
          const signos = [
            e.temperatura_c && `${e.temperatura_c} °C`,
            e.frecuencia_cardiaca && `FC ${e.frecuencia_cardiaca}`,
            e.frecuencia_respiratoria && `FR ${e.frecuencia_respiratoria}`,
            e.peso_kg && `${e.peso_kg} kg`,
          ].filter(Boolean);
          return (
            <Tarjeta key={e.id}>
              <View style={styles.cabecera}>
                <Texto variante="secundario">{fechaCorta(e.fecha_hora)} · {hora(e.fecha_hora)}</Texto>
                <Insignia texto={e.estado_general_display} />
              </View>
              <Texto>{e.notas}</Texto>
              {signos.length > 0 && <Fila icono="pulse-outline">{signos.join(' · ')}</Fila>}
              {e.medicacion_administrada ? <Fila icono="medical-outline">{e.medicacion_administrada}</Fila> : null}
              {e.veterinario_nombre ? <Fila icono="person-outline">{e.veterinario_nombre}</Fila> : null}
            </Tarjeta>
          );
        })}
      </Seccion>

      <Boton titulo="Ver ficha del paciente" icono="paw-outline" variante="secundario"
        onPress={() => router.push({ pathname: '/mascota/[id]', params: { id: i.mascota } })} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: Spacing.lg, gap: Spacing.lg },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.sm },
  acciones: { flexDirection: 'row', gap: Spacing.sm },
});
