import { Stack } from 'expo-router';

const modal = (title: string) => ({ title, presentation: 'modal' as const });

export default function AppLayout() {
  return (
    <Stack screenOptions={{ headerBackButtonDisplayMode: 'minimal' }}>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />

      <Stack.Screen name="mascota/[id]/index" options={{ title: 'Ficha del paciente' }} />
      <Stack.Screen name="mascota/[id]/consulta" options={modal('Nueva consulta')} />
      <Stack.Screen name="mascota/[id]/vacuna" options={modal('Registrar vacuna')} />
      <Stack.Screen name="mascota/[id]/receta" options={modal('Nueva receta')} />
      <Stack.Screen name="mascota/[id]/estudio" options={modal('Adjuntar estudio')} />
      <Stack.Screen name="mascota/[id]/desparasitacion" options={modal('Desparasitación')} />
      <Stack.Screen name="mascota/[id]/internar" options={modal('Internar paciente')} />
      <Stack.Screen name="mascota/[id]/editar" options={modal('Editar paciente')} />
      <Stack.Screen name="mascota/nueva" options={modal('Nueva mascota')} />

      <Stack.Screen name="cliente/nuevo" options={modal('Nuevo cliente')} />
      <Stack.Screen name="turno/[id]" options={modal('Turno')} />

      <Stack.Screen name="internacion/[id]/index" options={{ title: 'Internación' }} />
      <Stack.Screen name="internacion/[id]/evolucion" options={modal('Nuevo control')} />
      <Stack.Screen name="internacion/[id]/alta" options={modal('Cerrar internación')} />

      <Stack.Screen name="solicitudes" options={{ title: 'Solicitudes de turno web' }} />
    </Stack>
  );
}
