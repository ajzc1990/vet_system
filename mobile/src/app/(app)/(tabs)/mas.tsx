import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState, type ReactNode } from 'react';
import { Alert, Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { Boton, Fila, Insignia, Seccion, Tarjeta, Texto, type IconName } from '@/components/ui';
import { VersionApp } from '@/components/version-app';
import { Spacing } from '@/constants/theme';
import { API_URL } from '@/lib/api';
import { useSesion } from '@/lib/session';
import type { Paginado, SolicitudTurno } from '@/lib/types';
import { useApi } from '@/lib/use-api';
import { useTheme } from '@/lib/use-theme';

type EnlaceWeb = { icono: IconName; titulo: string; ruta: string; soloAdmin?: boolean };

// Lo que es trabajo de escritorio queda en la web: la app sólo abre la página.
const EN_LA_WEB: EnlaceWeb[] = [
  { icono: 'cube-outline', titulo: 'Inventario y stock', ruta: '/inventario/' },
  { icono: 'cart-outline', titulo: 'Ventas y caja', ruta: '/ventas/' },
  { icono: 'bag-handle-outline', titulo: 'Compras y proveedores', ruta: '/compras/' },
  { icono: 'notifications-outline', titulo: 'Centro de recordatorios', ruta: '/dashboard/recordatorios/' },
  { icono: 'stats-chart-outline', titulo: 'Panel general', ruta: '/dashboard/' },
  { icono: 'business-outline', titulo: 'Configurar clínica', ruta: '/usuarios/mi-veterinaria/', soloAdmin: true },
  { icono: 'card-outline', titulo: 'Mi suscripción', ruta: '/usuarios/mi-suscripcion/', soloAdmin: true },
];

export default function Mas() {
  const t = useTheme();
  const { usuario, notificaciones, cerrarSesion } = useSesion();
  const [saliendo, setSaliendo] = useState(false);
  const solicitudes = useApi<Paginado<SolicitudTurno>>('solicitudes/?pendientes=1');

  function confirmarSalida() {
    Alert.alert('Cerrar sesión', 'Vas a tener que volver a ingresar tu usuario y contraseña.', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Cerrar sesión',
        style: 'destructive',
        onPress: async () => {
          setSaliendo(true);
          await cerrarSesion();
        },
      },
    ]);
  }

  function abrirWeb(ruta: string) {
    WebBrowser.openBrowserAsync(`${API_URL}${ruta}`, { toolbarColor: t.card, controlsColor: t.primary });
  }

  if (!usuario) return null;

  const esAdmin = usuario.rol === 'ADMIN';
  const pendientes = solicitudes.datos?.count ?? 0;

  return (
    <ScrollView style={{ backgroundColor: t.background }} contentContainerStyle={styles.contenedor}>
      <Tarjeta style={styles.usuario}>
        <View style={[styles.avatar, { backgroundColor: t.primaryLight }]}>
          <Ionicons name="person" size={28} color={t.primaryDark} />
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Texto variante="subtitulo">{usuario.nombre}</Texto>
          <Texto variante="secundario">{[usuario.rol_display, usuario.veterinaria].filter(Boolean).join(' · ')}</Texto>
        </View>
      </Tarjeta>

      <Seccion titulo="Clínica">
        <Tarjeta style={styles.sinPadding}>
          <FilaMenu icono="mail-unread-outline" titulo="Solicitudes de turno web" onPress={() => router.push('/solicitudes')}
            extra={pendientes > 0 ? <Insignia tono="alerta" texto={String(pendientes)} /> : undefined} />
        </Tarjeta>
      </Seccion>

      <Seccion titulo="En la web">
        <Tarjeta style={styles.sinPadding}>
          {EN_LA_WEB.filter((e) => !e.soloAdmin || esAdmin).map((e, i) => (
            <FilaMenu key={e.ruta} icono={e.icono} titulo={e.titulo} onPress={() => abrirWeb(e.ruta)} externo separador={i > 0} />
          ))}
        </Tarjeta>
        <Texto variante="secundario">Se abren en el navegador. La primera vez iniciá sesión con tu mismo usuario.</Texto>
      </Seccion>

      <Seccion titulo="Notificaciones">
        <Tarjeta>
          {notificaciones === 'activas' && (
            <Fila icono="checkmark-circle-outline">Activas: te avisamos de solicitudes web y el resumen del día.</Fila>
          )}
          {notificaciones === 'denegadas' && (
            <>
              <Fila icono="notifications-off-outline">Desactivadas. Habilitalas en los ajustes del celular.</Fila>
              <Boton titulo="Abrir ajustes" variante="secundario" onPress={() => Linking.openSettings()} />
            </>
          )}
          {(notificaciones === 'no-disponibles' || notificaciones === null) && (
            <Fila icono="information-circle-outline">No disponibles en este dispositivo.</Fila>
          )}
        </Tarjeta>
      </Seccion>

      {!usuario.puede_atender && (
        <Fila icono="information-circle-outline">
          Tu rol no permite cargar consultas, vacunas ni recetas desde la app.
        </Fila>
      )}

      <Seccion titulo="Versión de la app">
        <VersionApp />
      </Seccion>

      <Boton titulo="Cerrar sesión" icono="log-out-outline" variante="peligro" cargando={saliendo} onPress={confirmarSalida} />

      {__DEV__ && (
        <Texto variante="secundario" style={{ textAlign: 'center' }}>{API_URL}</Texto>
      )}
    </ScrollView>
  );
}

function FilaMenu({ icono, titulo, onPress, extra, externo, separador }: {
  icono: IconName;
  titulo: string;
  onPress: () => void;
  extra?: ReactNode;
  externo?: boolean;
  separador?: boolean;
}) {
  const t = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.fila,
        separador && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: t.border },
        pressed && { opacity: 0.6 },
      ]}>
      <Ionicons name={icono} size={20} color={t.primary} />
      <Texto style={{ flex: 1 }}>{titulo}</Texto>
      {extra}
      <Ionicons name={externo ? 'open-outline' : 'chevron-forward'} size={18} color={t.textSecondary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: Spacing.lg, gap: Spacing.lg },
  usuario: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  avatar: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center' },
  sinPadding: { padding: 0, gap: 0 },
  fila: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md },
});
