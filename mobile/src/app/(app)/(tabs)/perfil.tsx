import Ionicons from '@expo/vector-icons/Ionicons';
import Constants from 'expo-constants';
import { useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';

import { Boton, Fila, Tarjeta, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { API_URL } from '@/lib/api';
import { useSesion } from '@/lib/session';
import { useTheme } from '@/lib/use-theme';

export default function Perfil() {
  const t = useTheme();
  const { usuario, cerrarSesion } = useSesion();
  const [saliendo, setSaliendo] = useState(false);

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

  if (!usuario) return null;

  return (
    <ScrollView style={{ backgroundColor: t.background }} contentContainerStyle={styles.contenedor}>
      <Tarjeta style={{ alignItems: 'center', paddingVertical: Spacing.xl }}>
        <View style={[styles.avatar, { backgroundColor: t.primaryLight }]}>
          <Ionicons name="person" size={36} color={t.primaryDark} />
        </View>
        <Texto variante="subtitulo">{usuario.nombre}</Texto>
        <Texto variante="secundario">@{usuario.username}</Texto>
      </Tarjeta>

      <Tarjeta>
        {usuario.veterinaria && <Fila icono="business-outline">{usuario.veterinaria}</Fila>}
        {usuario.rol_display && <Fila icono="shield-checkmark-outline">{usuario.rol_display}</Fila>}
        {!usuario.puede_atender && (
          <Fila icono="information-circle-outline">
            Tu rol no permite cargar consultas, vacunas ni recetas desde la app.
          </Fila>
        )}
      </Tarjeta>

      <Boton titulo="Cerrar sesión" icono="log-out-outline" variante="peligro" cargando={saliendo} onPress={confirmarSalida} />

      <Texto variante="secundario" style={{ textAlign: 'center' }}>
        VeterSystem móvil v{Constants.expoConfig?.version}
        {__DEV__ ? `\n${API_URL}` : ''}
      </Texto>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: Spacing.lg, gap: Spacing.lg },
  avatar: { width: 72, height: 72, borderRadius: 36, alignItems: 'center', justifyContent: 'center' },
});
