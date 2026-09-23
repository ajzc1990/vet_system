import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
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

  return (
    <ThemeProvider
      value={{
        ...base,
        colors: { ...base.colors, primary: c.primary, background: c.background, card: c.card, border: c.border, text: c.text },
      }}>
      <SesionProvider>
        <StatusBar style="auto" />
        <Navegador />
      </SesionProvider>
    </ThemeProvider>
  );
}

function Navegador() {
  const { usuario, cargando } = useSesion();

  // El splash queda visible hasta saber si hay un token guardado, así no parpadea el login.
  useEffect(() => {
    if (!cargando) SplashScreen.hide();
  }, [cargando]);

  if (cargando) return null;

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
