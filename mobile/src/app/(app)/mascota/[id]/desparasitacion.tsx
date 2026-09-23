import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { SelectorFechaHora } from '@/components/fecha-hora';
import { Formulario, useEnvio } from '@/components/formulario';
import { Campo, Chips, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { aISO, sumarDias } from '@/lib/fechas';

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

export default function RegistrarDesparasitacion() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { enviar, enviando, errores } = useEnvio(`mascotas/${id}/desparasitaciones/`);
  const [tipo, setTipo] = useState('INTERNA');
  const [producto, setProducto] = useState('');
  const [dosis, setDosis] = useState('');
  const [aplicacion, setAplicacion] = useState<Date | null>(new Date());
  const [proxima, setProxima] = useState<Date | null>(sumarDias(new Date(), 90));

  function guardar() {
    enviar(
      {
        tipo,
        producto: producto.trim(),
        dosis: dosis.trim() || null,
        fecha_aplicacion: aplicacion ? aISO(aplicacion) : undefined,
        fecha_proxima_dosis: proxima ? aISO(proxima) : null,
      },
      'Desparasitación registrada',
    );
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Registrar">
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
