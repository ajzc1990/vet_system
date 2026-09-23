import { router, useLocalSearchParams } from 'expo-router';

import { FormularioMascota } from '@/components/formulario-mascota';
import { EstadoCarga } from '@/components/ui';
import type { Mascota } from '@/lib/types';
import { useApi } from '@/lib/use-api';

export default function EditarMascota() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { datos, error, cargando, refrescar } = useApi<Mascota>(`mascotas/${id}/`);

  if (!datos) return <EstadoCarga cargando={cargando} error={error} onReintentar={refrescar} />;
  return <FormularioMascota mascota={datos} onGuardada={() => router.back()} />;
}
