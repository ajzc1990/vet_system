import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { Formulario, useEnvio } from '@/components/formulario';
import { Campo, Chips, Seccion } from '@/components/ui';

const CIERRES = [
  { valor: 'ALTA', etiqueta: 'Alta médica' },
  { valor: 'DERIVADO', etiqueta: 'Derivado' },
  { valor: 'FALLECIDO', etiqueta: 'Fallecimiento' },
];

export default function AltaInternacion() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { enviar, enviando, errores } = useEnvio(`internaciones/${id}/alta/`);
  const [estado, setEstado] = useState('ALTA');
  const [resumen, setResumen] = useState('');

  return (
    <Formulario
      onGuardar={() => enviar({ estado, resumen_alta: resumen.trim() }, 'Internación cerrada')}
      enviando={enviando}
      tituloBoton="Cerrar internación"
      errorGeneral={errores.detail ?? errores.estado}>
      <Seccion titulo="Motivo del cierre">
        <Chips opciones={CIERRES} valor={estado} onCambiar={setEstado} />
      </Seccion>
      <Campo
        etiqueta="Epicrisis / indicaciones para el hogar *"
        multiline
        style={{ minHeight: 140 }}
        value={resumen}
        onChangeText={setResumen}
        error={errores.resumen_alta}
      />
    </Formulario>
  );
}
