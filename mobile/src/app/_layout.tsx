import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
  PlusJakartaSans_800ExtraBold,
  useFonts,
} from '@expo-google-fonts/plus-jakarta-sans';
import * as Notifications from 'expo-notifications';
import { DarkTheme, DefaultTheme, router, Stack, ThemeProvider, type Href } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';

import { Colors } from '@/constants/theme';
import { SesionProvider, useSesion } from '@/lib/session';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const scheme = useColorScheme();
  const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
  const c = scheme === 'dark' ? Colors.dark : Colors.light;
  const [fuentesListas] = useFonts({
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    PlusJakartaSans_800ExtraBold,
  });

  return (
    <ThemeProvider
      value={{
        ...base,
        colors: { ...base.colors, primary: c.primary, background: c.background, card: c.card, border: c.border, text: c.text },
      }}>
      <SesionProvider>
        <StatusBar style="auto" />
        <Navegador fuentesListas={fuentesListas} />
      </SesionProvider>
    </ThemeProvider>
  );
}

function Navegador({ fuentesListas }: { fuentesListas: boolean }) {
  const { usuario, cargando } = useSesion();

  // El splash queda visible hasta saber si hay un token guardado y cargar la
  // tipografía, así no parpadea el login ni se ve con la fuente del sistema un instante.
  useEffect(() => {
    if (!cargando && fuentesListas) SplashScreen.hide();
  }, [cargando, fuentesListas]);

  // Tocar una notificación (aun con la app cerrada) abre la pantalla que indica data.url.
  const respuesta = Notifications.useLastNotificationResponse();
  const logueado = !!usuario;
  useEffect(() => {
    if (!logueado || !respuesta) return;
    const url = respuesta.notification.request.content.data?.url;
    if (typeof url === 'string') router.push(url as Href);
    Notifications.clearLastNotificationResponse();
  }, [respuesta, logueado]);

  if (cargando || !fuentesListas) return null;

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!!usuario}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      <Stack.Protected guard={!usuario}>
        <Stack.Screen name="login" />
      </Stack.Protected>
    </Stack>
  );
}
