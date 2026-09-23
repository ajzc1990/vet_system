import { Stack } from 'expo-router';

export default function AppLayout() {
  return (
    <Stack screenOptions={{ headerBackButtonDisplayMode: 'minimal' }}>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="mascota/[id]/index" options={{ title: 'Ficha del paciente' }} />
      <Stack.Screen name="mascota/[id]/consulta" options={{ title: 'Nueva consulta', presentation: 'modal' }} />
      <Stack.Screen name="mascota/[id]/vacuna" options={{ title: 'Registrar vacuna', presentation: 'modal' }} />
      <Stack.Screen name="mascota/[id]/receta" options={{ title: 'Nueva receta', presentation: 'modal' }} />
    </Stack>
  );
}
