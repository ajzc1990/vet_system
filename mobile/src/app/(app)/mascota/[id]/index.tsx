import Ionicons from '@expo/vector-icons/Ionicons';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Linking, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { Boton, EstadoCarga, Fila, Insignia, Seccion, Tarjeta, Texto, type IconName } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { edad, fechaCorta } from '@/lib/fechas';
import { useSesion } from '@/lib/session';
import type { Consulta, Historia } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

export default function FichaPaciente() {
  const t = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { usuario } = useSesion();
  const { datos: h, error, cargando, refrescando, refrescar } = useApi<Historia>(`mascotas/${id}/historia/`);

  if (!h) {
    return (
      <View style={{ flex: 1, backgroundColor: t.background }}>
        <EstadoCarga cargando={cargando} error={error} onReintentar={refrescar} />
      </View>
    );
  }

  const m = h.mascota;
  const telefono = m.cliente_telefono?.replace(/\D/g, '');
  const vacunasVencidas = h.vacunas.filter((v) => v.proxima_dosis_vencida);

  function irA(pantalla: 'consulta' | 'vacuna' | 'receta') {
    router.push({ pathname: `/mascota/[id]/${pantalla}`, params: { id } });
  }

  return (
    <ScrollView
      style={{ backgroundColor: t.background }}
      contentContainerStyle={styles.contenedor}
      refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={t.primary} />}>
      <Stack.Screen options={{ title: m.nombre }} />

      <Tarjeta>
        <Texto variante="titulo">{m.nombre}</Texto>
        <Texto variante="secundario">
          {[m.especie_display, m.raza, m.sexo_display, m.castrado ? 'castrado/a' : null].filter(Boolean).join(' · ')}
        </Texto>
        <View style={styles.datos}>
          <Dato icono="hourglass-outline" valor={edad(m.fecha_nacimiento) ?? '—'} etiqueta="Edad" />
          <Dato icono="barbell-outline" valor={m.peso_kg ? `${m.peso_kg} kg` : '—'} etiqueta="Peso" />
          <Dato icono="medical-outline" valor={String(h.consultas.length)} etiqueta="Consultas" />
        </View>
        {m.observaciones ? <Fila icono="alert-circle-outline">{m.observaciones}</Fila> : null}
      </Tarjeta>

      <Tarjeta>
        <Texto variante="etiqueta">Tutor</Texto>
        <Texto style={{ fontWeight: '600' }}>{m.cliente_nombre}</Texto>
        {telefono ? (
          <View style={styles.acciones}>
            <Boton titulo="Llamar" icono="call" variante="secundario" style={{ flex: 1 }}
              onPress={() => Linking.openURL(`tel:${telefono}`)} />
            <Boton titulo="WhatsApp" icono="logo-whatsapp" variante="secundario" style={{ flex: 1 }}
              onPress={() => Linking.openURL(`https://wa.me/${telefono}`)} />
          </View>
        ) : (
          <Texto variante="secundario">Sin teléfono cargado.</Texto>
        )}
      </Tarjeta>

      {h.internaciones_activas.map((i) => (
        <Tarjeta key={i.id} style={{ backgroundColor: t.warningBg, borderColor: t.warningBg }}>
          <Fila icono="bed-outline">
            Internado {i.dias_internado === 1 ? 'hace 1 día' : `hace ${i.dias_internado} días`}
            {i.box ? ` · Box ${i.box}` : ''}
          </Fila>
          <Texto>{i.motivo_ingreso}</Texto>
        </Tarjeta>
      ))}

      {h.resumen_ia && (
        <Tarjeta style={{ backgroundColor: t.primaryLight, borderColor: t.primaryLight }}>
          <Fila icono="sparkles-outline">Resumen clínico (IA) · {fechaCorta(h.resumen_ia.generado_el)}</Fila>
          <Texto>{h.resumen_ia.texto}</Texto>
        </Tarjeta>
      )}

      {usuario?.puede_atender && (
        <View style={styles.acciones}>
          <Boton titulo="Consulta" icono="add" style={{ flex: 1 }} onPress={() => irA('consulta')} />
          <Boton titulo="Vacuna" icono="shield-checkmark-outline" variante="secundario" style={{ flex: 1 }}
            onPress={() => irA('vacuna')} />
          <Boton titulo="Receta" icono="document-text-outline" variante="secundario" style={{ flex: 1 }}
            onPress={() => irA('receta')} />
        </View>
      )}

      <Seccion
        titulo="Vacunas"
        accion={vacunasVencidas.length > 0 && <Insignia tono="peligro" texto={`${vacunasVencidas.length} vencida(s)`} />}>
        {h.vacunas.length === 0 && <Texto variante="secundario">Sin vacunas registradas.</Texto>}
        {h.vacunas.map((v) => (
          <Tarjeta key={v.id}>
            <View style={styles.cabecera}>
              <Texto style={{ fontWeight: '600', flexShrink: 1 }}>{v.nombre_vacuna}</Texto>
              <Texto variante="secundario">{fechaCorta(v.fecha_aplicacion)}</Texto>
            </View>
            {v.fecha_proxima_dosis && (
              <Insignia
                tono={v.proxima_dosis_vencida ? 'peligro' : 'exito'}
                texto={`${v.proxima_dosis_vencida ? 'Vencida' : 'Próxima'}: ${fechaCorta(v.fecha_proxima_dosis)}`}
              />
            )}
          </Tarjeta>
        ))}
      </Seccion>

      <Seccion titulo="Consultas">
        {h.consultas.length === 0 && <Texto variante="secundario">Sin consultas registradas.</Texto>}
        {h.consultas.map((c) => (
          <TarjetaConsulta key={c.id} consulta={c} />
        ))}
      </Seccion>

      <Seccion titulo="Recetas">
        {h.recetas.length === 0 && <Texto variante="secundario">Sin recetas emitidas.</Texto>}
        {h.recetas.map((r) => (
          <Tarjeta key={r.id}>
            <View style={styles.cabecera}>
              <Texto style={{ fontWeight: '600', flexShrink: 1 }}>{r.diagnostico || 'Receta'}</Texto>
              <Texto variante="secundario">{fechaCorta(r.fecha_emision)}</Texto>
            </View>
            {r.items.map((i) => (
              <Fila key={i.id} icono="ellipse">
                {[i.medicamento, i.dosis, i.duracion].filter(Boolean).join(' · ')}
              </Fila>
            ))}
          </Tarjeta>
        ))}
      </Seccion>

      {h.desparasitaciones.length > 0 && (
        <Seccion titulo="Desparasitaciones">
          {h.desparasitaciones.map((d) => (
            <Tarjeta key={d.id}>
              <View style={styles.cabecera}>
                <Texto style={{ fontWeight: '600', flexShrink: 1 }}>{d.producto}</Texto>
                <Texto variante="secundario">{fechaCorta(d.fecha_aplicacion)}</Texto>
              </View>
              <Texto variante="secundario">{d.tipo_display}</Texto>
            </Tarjeta>
          ))}
        </Seccion>
      )}
    </ScrollView>
  );
}

function Dato({ icono, valor, etiqueta }: { icono: IconName; valor: string; etiqueta: string }) {
  const t = useTheme();
  return (
    <View style={styles.dato}>
      <Ionicons name={icono} size={18} color={t.primary} />
      <Texto style={{ fontWeight: '600' }}>{valor}</Texto>
      <Texto variante="secundario">{etiqueta}</Texto>
    </View>
  );
}

function TarjetaConsulta({ consulta: c }: { consulta: Consulta }) {
  const t = useTheme();
  const [abierta, setAbierta] = useState(false);
  const signos = [
    c.peso_actual_kg && `${c.peso_actual_kg} kg`,
    c.temperatura_c && `${c.temperatura_c} °C`,
    c.frecuencia_cardiaca && `FC ${c.frecuencia_cardiaca}`,
    c.frecuencia_respiratoria && `FR ${c.frecuencia_respiratoria}`,
  ].filter(Boolean);

  return (
    <Tarjeta onPress={() => setAbierta((a) => !a)}>
      <View style={styles.cabecera}>
        <Texto variante="secundario">{fechaCorta(c.fecha_hora)}</Texto>
        <Ionicons name={abierta ? 'chevron-up' : 'chevron-down'} size={18} color={t.textSecondary} />
      </View>
      <Texto style={{ fontWeight: '600' }}>{c.motivo_consulta}</Texto>
      <Texto variante="secundario" numberOfLines={abierta ? undefined : 2}>
        Dx: {c.diagnostico}
      </Texto>
      {abierta && (
        <View style={{ gap: Spacing.sm }}>
          {signos.length > 0 && <Fila icono="pulse-outline">{signos.join(' · ')}</Fila>}
          <Detalle titulo="Anamnesis" texto={c.anamnesis} />
          <Detalle titulo="Examen clínico" texto={c.examen_clinico} />
          <Detalle titulo="Tratamiento" texto={c.tratamiento} />
          <Detalle titulo="Notas internas" texto={c.observaciones_privadas} />
          {c.veterinario_nombre && <Fila icono="medkit-outline">{c.veterinario_nombre}</Fila>}
        </View>
      )}
    </Tarjeta>
  );
}

function Detalle({ titulo, texto }: { titulo: string; texto: string | null }) {
  if (!texto) return null;
  return (
    <View style={{ gap: 2 }}>
      <Texto variante="etiqueta">{titulo}</Texto>
      <Texto>{texto}</Texto>
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: Spacing.lg, gap: Spacing.lg },
  datos: { flexDirection: 'row', justifyContent: 'space-around', marginVertical: Spacing.sm },
  dato: { alignItems: 'center', gap: 2 },
  acciones: { flexDirection: 'row', gap: Spacing.sm },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.sm },
});
