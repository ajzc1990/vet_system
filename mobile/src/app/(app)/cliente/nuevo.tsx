import { router } from 'expo-router';
import { useState } from 'react';

import { Formulario, useEnvio } from '@/components/formulario';
import { Campo, Texto } from '@/components/ui';
import type { Cliente } from '@/lib/types';

/** Alta de tutor; al guardar sigue directo con la carga de su primera mascota. */
export default function NuevoCliente() {
  const { enviar, enviando, errores } = useEnvio('clientes/');
  const [f, setF] = useState({ nombre: '', apellido: '', dni: '', telefono: '', email: '', direccion: '' });
  const campo = (nombre: keyof typeof f) => ({
    value: f[nombre],
    onChangeText: (v: string) => setF((prev) => ({ ...prev, [nombre]: v })),
    error: errores[nombre],
  });

  function guardar() {
    const limpio = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v.trim()]));
    enviar<Cliente>(
      { ...limpio, email: limpio.email || null, direccion: limpio.direccion || null },
      '',
      {
        onExito: (c) =>
          router.replace({
            pathname: '/mascota/nueva',
            params: { cliente: c.id, cliente_nombre: `${c.nombre} ${c.apellido}` },
          }),
      },
    );
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Siguiente: cargar mascota">
      <Texto variante="secundario">Datos del tutor. En el paso siguiente cargás su mascota.</Texto>
      <Campo etiqueta="Nombre *" autoCapitalize="words" {...campo('nombre')} />
      <Campo etiqueta="Apellido *" autoCapitalize="words" {...campo('apellido')} />
      <Campo etiqueta="DNI *" keyboardType="number-pad" {...campo('dni')} />
      <Campo etiqueta="Teléfono / WhatsApp *" keyboardType="phone-pad" {...campo('telefono')} />
      <Campo etiqueta="Email" keyboardType="email-address" autoCapitalize="none" {...campo('email')} />
      <Campo etiqueta="Dirección" {...campo('direccion')} />
    </Formulario>
  );
}
