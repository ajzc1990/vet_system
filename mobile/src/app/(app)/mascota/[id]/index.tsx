import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Boton, EstadoCarga, Fila, Insignia, Seccion, Tarjeta, Texto, type IconName } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { api, compartirPdf } from '@/lib/api';
import { edad, fechaCorta } from '@/lib/fechas';
import { useSesion } from '@/lib/session';
import type { Consulta, Historia } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

type Accion = { icono: IconName; titulo: string; ruta: string };

const ACCIONES: Accion[] = [
  { icono: 'add-circle-outline', titulo: 'Consulta', ruta: 'consulta' },
  { icono: 'shield-checkmark-outline', titulo: 'Vacuna', ruta: 'vacuna' },
  { icono: 'document-text-outline', titulo: 'Receta', ruta: 'receta' },
  { icono: 'camera-outline', titulo: 'Estudio', ruta: 'estudio' },
  { icono: 'bug-outline', titulo: 'Desparasit.', ruta: 'desparasitacion' },
  { icono: 'bed-outline', titulo: 'Internar', ruta: 'internar' },
];

export default function FichaPaciente() {
  const t = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { usuario } = useSesion();
  const { datos: h, error, cargando, refrescando, refrescar, setDatos } = useApi<Historia>(`mascotas/${id}/historia/`);
  const [ocupado, setOcupado] = useState<string | null>(null);

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
  const internacion = h.internaciones_activas[0];
  const acciones = ACCIONES.filter((a) => a.ruta !== 'internar' || !internacion);

  /** Corre una acción async marcando qué botón está ocupado y mostrando el error si falla. */
  async function conEspera(clave: string, tarea: () => Promise<void>, tituloError: string) {
    setOcupado(clave);
    try {
      await tarea();
    } catch (e) {
      Alert.alert(tituloError, e instanceof Error ? e.message : undefined);
    } finally {
      setOcupado(null);
    }
  }

  function generarResumen() {
    conEspera('ia', async () => {
      const resumen = await api<Historia['resumen_ia']>(`mascotas/${id}/resumen-ia/`, { method: 'POST' });
      setDatos((d) => d && { ...d, resumen_ia: resumen });
    }, 'No se pudo generar el resumen');
  }

  return (
    <ScrollView
      style={{ backgroundColor: t.background }}
      contentContainerStyle={styles.contenedor}
      refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={t.primary} />}>
      <Stack.Screen
        options={{
          title: m.nombre,
          headerRight: () => (
            <Pressable hitSlop={10} accessibilityLabel="Editar datos del paciente"
              onPress={() => router.push({ pathname: '/mascota/[id]/editar', params: { id } })}>
              <Ionicons name="create-outline" size={22} color={t.primary} />
            </Pressable>
          ),
        }}
      />

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
        <View style={styles.acciones}>
          <Boton titulo="Agendar turno" icono="calendar-outline" variante="secundario" style={{ flex: 1 }}
            onPress={() => router.push({
              pathname: '/turno/[id]',
              params: { id: 'nuevo', mascota: m.id, mascota_nombre: m.nombre, cliente_nombre: m.cliente_nombre },
            })} />
          <Boton titulo="Otra mascota" icono="add" variante="secundario" style={{ flex: 1 }}
            onPress={() => router.push({
              pathname: '/mascota/nueva',
              params: { cliente: m.cliente, cliente_nombre: m.cliente_nombre },
            })} />
        </View>
      </Tarjeta>

      {internacion && (
        <Tarjeta style={{ backgroundColor: t.warningBg, borderColor: t.warningBg }}
          onPress={() => router.push({ pathname: '/internacion/[id]', params: { id: internacion.id } })}>
          <View style={styles.cabecera}>
            <Fila icono="bed-outline">
              Internado · {internacion.dias_internado === 1 ? '1 día' : `${internacion.dias_internado} días`}
              {internacion.box ? ` · Box ${internacion.box}` : ''}
            </Fila>
            <Ionicons name="chevron-forward" size={18} color={t.warning} />
          </View>
          <Texto>{internacion.motivo_ingreso}</Texto>
        </Tarjeta>
      )}

      {(h.resumen_ia || (usuario?.ia_habilitada && usuario.puede_atender)) && (
        <Tarjeta style={{ backgroundColor: t.primaryLight, borderColor: t.primaryLight }}>
          <View style={styles.cabecera}>
            <Fila icono="sparkles-outline">
              Resumen clínico (IA){h.resumen_ia ? ` · ${fechaCorta(h.resumen_ia.generado_el)}` : ''}
            </Fila>
            {usuario?.ia_habilitada && usuario.puede_atender && (
              <Pressable hitSlop={8} onPress={generarResumen} disabled={ocupado === 'ia'}>
                <Text style={{ color: t.primaryDark, fontWeight: '600' }}>
                  {ocupado === 'ia' ? 'Generando…' : h.resumen_ia ? 'Actualizar' : 'Generar'}
                </Text>
              </Pressable>
            )}
          </View>
          {h.resumen_ia ? (
            <Texto>{h.resumen_ia.texto}</Texto>
          ) : (
            <Texto variante="secundario">Un resumen de 5 líneas del historial, para leer antes de atender.</Texto>
          )}
        </Tarjeta>
      )}

      {usuario?.puede_atender && (
        <View style={styles.grilla}>
          {acciones.map((a) => (
            <Pressable
              key={a.ruta}
              accessibilityRole="button"
              onPress={() => router.push({ pathname: `/mascota/[id]/${a.ruta}` as '/mascota/[id]/consulta', params: { id } })}
              style={({ pressed }) => [styles.accion, { backgroundColor: t.card, borderColor: t.border, opacity: pressed ? 0.6 : 1 }]}>
              <Ionicons name={a.icono} size={24} color={t.primary} />
              <Text style={[styles.accionTexto, { color: t.text }]}>{a.titulo}</Text>
            </Pressable>
          ))}
        </View>
      )}

      <Seccion
        titulo="Vacunas"
        accion={
          <View style={styles.accionesSeccion}>
            {vacunasVencidas.length > 0 && <Insignia tono="peligro" texto={`${vacunasVencidas.length} vencida(s)`} />}
            {h.vacunas.length > 0 && (
              <BotonCompartir
                ocupado={ocupado === 'carnet'}
                onPress={() => conEspera('carnet',
                  () => compartirPdf(`mascotas/${id}/carnet-pdf/`, `Carnet_Vacunas_${m.nombre}.pdf`),
                  'No se pudo compartir el carnet')}
                etiqueta="Carnet"
              />
            )}
          </View>
        }>
        {h.vacunas.length === 0 && <Texto variante="secundario">Sin vacunas registradas.</Texto>}
        {h.vacunas.map((v) => (
          <Tarjeta key={v.id}>
            <View style={styles.cabecera}>
              <Texto style={{ fontWeight: '600', flexShrink: 1 }}>{v.nombre_vacuna}</Texto>
              <View style={styles.accionesSeccion}>
                <Texto variante="secundario">{fechaCorta(v.fecha_aplicacion)}</Texto>
                {usuario?.puede_atender && <BotonEditar ruta="vacuna" mascotaId={id} registroId={v.id} />}
              </View>
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
          <TarjetaConsulta key={c.id} consulta={c} mascotaId={id} puedeEditar={!!usuario?.puede_atender} />
        ))}
      </Seccion>

      <Seccion titulo="Recetas">
        {h.recetas.length === 0 && <Texto variante="secundario">Sin recetas emitidas.</Texto>}
        {h.recetas.map((r) => (
          <Tarjeta key={r.id}>
            <View style={styles.cabecera}>
              <Texto style={{ fontWeight: '600', flexShrink: 1 }}>{r.diagnostico || 'Receta'}</Texto>
              <BotonCompartir
                ocupado={ocupado === `receta-${r.id}`}
                onPress={() => conEspera(`receta-${r.id}`,
                  () => compartirPdf(`recetas/${r.id}/pdf/`, `Receta_${m.nombre}_${r.fecha_emision.slice(0, 10)}.pdf`),
                  'No se pudo compartir la receta')}
              />
            </View>
            <Texto variante="secundario">{fechaCorta(r.fecha_emision)}</Texto>
            {r.items.map((i) => (
              <Fila key={i.id} icono="ellipse">
                {[i.medicamento, i.dosis, i.duracion].filter(Boolean).join(' · ')}
              </Fila>
            ))}
          </Tarjeta>
        ))}
      </Seccion>

      {h.estudios.length > 0 && (
        <Seccion titulo="Estudios y fotos">
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: Spacing.sm }}>
            {h.estudios.map((e) => (
              <Pressable key={e.id} onPress={() => Linking.openURL(e.archivo)} style={styles.estudio}>
                {e.es_imagen ? (
                  <Image source={{ uri: e.archivo }} style={[styles.miniatura, { backgroundColor: t.border }]}
                    contentFit="cover" transition={150} />
                ) : (
                  <View style={[styles.miniatura, styles.pdf, { backgroundColor: t.primaryLight }]}>
                    <Ionicons name="document-attach-outline" size={32} color={t.primaryDark} />
                  </View>
                )}
                <Texto variante="secundario" numberOfLines={1}>{e.titulo}</Texto>
                <Texto variante="secundario" style={{ fontSize: 11 }}>{fechaCorta(e.fecha_estudio)}</Texto>
              </Pressable>
            ))}
          </ScrollView>
        </Seccion>
      )}

      {h.desparasitaciones.length > 0 && (
        <Seccion titulo="Desparasitaciones">
          {h.desparasitaciones.map((d) => (
            <Tarjeta key={d.id}>
              <View style={styles.cabecera}>
                <Texto style={{ fontWeight: '600', flexShrink: 1 }}>{d.producto}</Texto>
                <View style={styles.accionesSeccion}>
                  <Texto variante="secundario">{fechaCorta(d.fecha_aplicacion)}</Texto>
                  {usuario?.puede_atender && <BotonEditar ruta="desparasitacion" mascotaId={id} registroId={d.id} />}
                </View>
              </View>
              <Texto variante="secundario">{d.tipo_display}</Texto>
              {d.fecha_proxima_dosis && (
                <Insignia
                  tono={d.proxima_dosis_vencida ? 'peligro' : 'exito'}
                  texto={`${d.proxima_dosis_vencida ? 'Vencida' : 'Próxima'}: ${fechaCorta(d.fecha_proxima_dosis)}`}
                />
              )}
            </Tarjeta>
          ))}
        </Seccion>
      )}
    </ScrollView>
  );
}

function BotonEditar({ ruta, mascotaId, registroId }: {
  ruta: 'vacuna' | 'desparasitacion';
  mascotaId: string;
  registroId: number;
}) {
  const t = useTheme();
  return (
    <Pressable
      hitSlop={10}
      accessibilityLabel="Corregir"
      onPress={() => router.push({ pathname: `/mascota/[id]/${ruta}`, params: { id: mascotaId, editar: registroId } })}>
      <Ionicons name="create-outline" size={18} color={t.primary} />
    </Pressable>
  );
}

function BotonCompartir({ onPress, ocupado, etiqueta = 'PDF' }: { onPress: () => void; ocupado: boolean; etiqueta?: string }) {
  const t = useTheme();
  return (
    <Pressable hitSlop={8} onPress={onPress} disabled={ocupado} style={styles.compartir}
      accessibilityLabel={`Compartir ${etiqueta}`}>
      <Ionicons name={ocupado ? 'hourglass-outline' : 'share-social-outline'} size={18} color={t.primary} />
      <Text style={{ color: t.primary, fontWeight: '600' }}>{etiqueta}</Text>
    </Pressable>
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

function TarjetaConsulta({ consulta: c, mascotaId, puedeEditar }: {
  consulta: Consulta;
  mascotaId: string;
  puedeEditar: boolean;
}) {
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
          {puedeEditar && (
            <Boton titulo="Corregir consulta" icono="create-outline" variante="secundario"
              onPress={() => router.push({ pathname: '/mascota/[id]/consulta', params: { id: mascotaId, editar: c.id } })} />
          )}
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
  accionesSeccion: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: Spacing.sm },
  grilla: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  accion: {
    flexBasis: '31%',
    flexGrow: 1,
    alignItems: 'center',
    gap: Spacing.xs,
    paddingVertical: Spacing.md,
    borderRadius: Radius.md,
    borderWidth: StyleSheet.hairlineWidth,
  },
  accionTexto: { fontSize: 13, fontWeight: '600' },
  compartir: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  estudio: { width: 110, gap: 2 },
  miniatura: { width: 110, height: 110, borderRadius: Radius.sm },
  pdf: { alignItems: 'center', justifyContent: 'center' },
});
