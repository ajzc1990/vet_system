import { router, Stack, useLocalSearchParams } from 'expo-router';

import { FormularioMascota } from '@/components/formulario-mascota';

/** /mascota/nueva?cliente=ID&cliente_nombre=... */
export default function NuevaMascota() {
  const { cliente, cliente_nombre } = useLocalSearchParams<{ cliente: string; cliente_nombre?: string }>();
  return (
    <>
      <Stack.Screen options={{ title: cliente_nombre ? `Mascota de ${cliente_nombre}` : 'Nueva mascota' }} />
      <FormularioMascota
        clienteId={Number(cliente)}
        onGuardada={(m) => router.replace({ pathname: '/mascota/[id]', params: { id: m.id } })}
      />
    </>
  );
}
