import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { api } from '@/lib/api';

// Con la app abierta, las notificaciones igual se muestran como banner.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

let tokenActual: string | null = null;

/** Token de Expo de este celular (para darlo de baja al cerrar sesión). */
export function tokenPush() {
  return tokenActual;
}

export type EstadoNotificaciones = 'activas' | 'denegadas' | 'no-disponibles';

/**
 * Pide permiso, obtiene el token de Expo y lo registra en el servidor para este usuario.
 * Nunca lanza: sin permiso, en un emulador o en Expo Go (Android no soporta push ahí)
 * la app sigue funcionando igual, sólo que sin avisos.
 */
export async function registrarNotificaciones(): Promise<EstadoNotificaciones> {
  if (Platform.OS === 'web' || !Device.isDevice) return 'no-disponibles';

  try {
    if (Platform.OS === 'android') {
      // El servidor manda con channelId 'default'.
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Avisos de la clínica',
        importance: Notifications.AndroidImportance.HIGH,
        lightColor: '#6366f1',
      });
    }

    let { granted } = await Notifications.getPermissionsAsync();
    if (!granted) ({ granted } = await Notifications.requestPermissionsAsync());
    if (!granted) return 'denegadas';

    const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
    tokenActual = token;
    await api('dispositivos/', { method: 'POST', body: { token, plataforma: Platform.OS } });
    return 'activas';
  } catch {
    return 'no-disponibles';
  }
}
