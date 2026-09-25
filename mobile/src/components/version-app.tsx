import Constants from 'expo-constants';
import * as Updates from 'expo-updates';
import { useState } from 'react';
import { Alert } from 'react-native';

import { Boton, Fila, Tarjeta } from '@/components/ui';
import { fechaCorta, hora } from '@/lib/fechas';

/**
 * Versión instalada y botón para bajar y aplicar en el momento la última actualización
 * (EAS Update), sin esperar a que el celular la busque solo al abrir la app.
 */
export function VersionApp() {
  const [buscando, setBuscando] = useState(false);

  const origen = !Updates.isEnabled
    ? 'modo desarrollo'
    : Updates.isEmbeddedLaunch || !Updates.createdAt
      ? 'la incluida en la instalación'
      : `actualización del ${fechaCorta(Updates.createdAt.toISOString())} ${hora(Updates.createdAt.toISOString())}`;

  async function buscar() {
    if (!Updates.isEnabled) {
      Alert.alert('No disponible', 'Las actualizaciones sólo funcionan en la app instalada, no en Expo Go.');
      return;
    }
    setBuscando(true);
    try {
      const { isAvailable } = await Updates.checkForUpdateAsync();
      if (!isAvailable) {
        Alert.alert('Todo al día', 'Ya tenés la última versión de VeterSystem.');
        return;
      }
      await Updates.fetchUpdateAsync();
      Alert.alert('Actualización descargada', 'La app se va a reiniciar para aplicarla.', [
        { text: 'Reiniciar ahora', onPress: () => Updates.reloadAsync() },
      ]);
    } catch (e) {
      Alert.alert('No se pudo actualizar', e instanceof Error ? e.message : 'Revisá la conexión a internet.');
    } finally {
      setBuscando(false);
    }
  }

  return (
    <Tarjeta>
      <Fila icono="phone-portrait-outline">
        VeterSystem {Constants.expoConfig?.version} · {origen}
      </Fila>
      {Updates.channel ? <Fila icono="git-branch-outline">Canal: {Updates.channel}</Fila> : null}
      <Boton titulo="Buscar actualización" icono="cloud-download-outline" variante="secundario"
        cargando={buscando} onPress={buscar} />
    </Tarjeta>
  );
}
