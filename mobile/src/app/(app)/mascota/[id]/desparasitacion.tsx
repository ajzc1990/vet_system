import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { SelectorFechaHora } from '@/components/fecha-hora';
import { Formulario, useEnvio } from '@/components/formulario';
import { Campo, Chips, EstadoCarga, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import { aISO, desdeISO, sumarDias } from '@/lib/fechas';
import type { Desparasitacion } from '@/lib/types';

const TIPOS = [
  { valor: 'INTERNA', etiqueta: 'Interna' },
  { valor: 'EXTERNA', etiqueta: 'Externa' },
  { valor: 'AMBAS', etiqueta: 'Ambas' },
];
const PROXIMA = [
  { valor: 0, etiqueta: 'Sin próxima' },
  { valor: 30, etiqueta: '30 días' },
  { valor: 90, etiqueta: '3 meses' },
  { valor: 180, etiqueta: '6 meses' },
];

/** Registrar una desparasitación o corregir una existente con ?editar=ID. */
export default function FormularioDesparasitacion() {
  const { id, editar } = useLocalSearchParams<{ id: string; editar?: string }>();
  const { enviar, enviando, errores } = useEnvio(editar ? `desparasitaciones/${editar}/` : `mascotas/${id}/desparasitaciones/`);
  const [cargando, setCargando] = useState(!!editar);
  const [tipo, setTipo] = useState('INTERNA');
  const [producto, setProducto] = useState('');
  const [dosis, setDosis] = useState('');
  const [aplicacion, setAplicacion] = useState<Date | null>(new Date());
  const [proxima, setProxima] = useState<Date | null>(sumarDias(new Date(), 90));

  useEffect(() => {
    if (!editar) return;
    api<Desparasitacion>(`desparasitaciones/${editar}/`)
      .then((d) => {
        setTipo(d.tipo);
        setProducto(d.producto);
        setDosis(d.dosis ?? '');
        setAplicacion(desdeISO(d.fecha_aplicacion));
        setProxima(d.fecha_proxima_dosis ? desdeISO(d.fecha_proxima_dosis) : null);
      })
      .finally(() => setCargando(false));
  }, [editar]);

  function guardar() {
    enviar(
      {
        tipo,
        producto: producto.trim(),
        dosis: dosis.trim() || null,
        fecha_aplicacion: aplicacion ? aISO(aplicacion) : undefined,
        fecha_proxima_dosis: proxima ? aISO(proxima) : null,
      },
      editar ? 'Desparasitación corregida' : 'Desparasitación registrada',
      { method: editar ? 'PATCH' : 'POST' },
    );
  }

  if (cargando) return <EstadoCarga cargando error={null} />;

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton={editar ? 'Guardar cambios' : 'Registrar'}>
      {editar && <Stack.Screen options={{ title: 'Editar desparasitación' }} />}
      <View style={{ gap: Spacing.xs }}>
        <Texto variante="etiqueta">Tipo</Texto>
        <Chips opciones={TIPOS} valor={tipo} onCambiar={setTipo} />
      </View>
      <Campo etiqueta="Producto *" placeholder="Total Full, Simparica, Bravecto..." value={producto}
        onChangeText={setProducto} error={errores.producto} />
      <Campo etiqueta="Dosis" placeholder="1 comprimido" value={dosis} onChangeText={setDosis} error={errores.dosis} />
      <SelectorFechaHora etiqueta="Fecha de aplicación" valor={aplicacion} onCambiar={setAplicacion}
        error={errores.fecha_aplicacion} />
      <View style={{ gap: Spacing.xs }}>
        <Chips
          opciones={PROXIMA}
          valor={null}
          onCambiar={(dias) => setProxima(dias ? sumarDias(aplicacion ?? new Date(), dias) : null)}
        />
        <SelectorFechaHora etiqueta="Próxima dosis" valor={proxima} onCambiar={setProxima} opcional
          error={errores.fecha_proxima_dosis} />
      </View>
    </Formulario>
  );
}
