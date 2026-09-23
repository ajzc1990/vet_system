import { useState } from 'react';
import { StyleSheet, Switch, View } from 'react-native';

import { SelectorFechaHora } from '@/components/fecha-hora';
import { Formulario, numero, useEnvio } from '@/components/formulario';
import { Campo, Chips, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { aISO, desdeISO } from '@/lib/fechas';
import type { Mascota } from '@/lib/types';
import { useTheme } from '@/lib/use-theme';

const ESPECIES = [
  { valor: 'CANINO', etiqueta: 'Canino' },
  { valor: 'FELINO', etiqueta: 'Felino' },
  { valor: 'AVE', etiqueta: 'Ave' },
  { valor: 'OTRO', etiqueta: 'Otro' },
];
const SEXOS = [
  { valor: 'M', etiqueta: 'Macho' },
  { valor: 'H', etiqueta: 'Hembra' },
];

/** Alta (con `clienteId`) o edición (con `mascota`) de un paciente. */
export function FormularioMascota({
  clienteId,
  mascota,
  onGuardada,
}: {
  clienteId?: number;
  mascota?: Mascota;
  onGuardada: (mascota: Mascota) => void;
}) {
  const t = useTheme();
  const { enviar, enviando, errores } = useEnvio(mascota ? `mascotas/${mascota.id}/` : 'mascotas/');
  const [nombre, setNombre] = useState(mascota?.nombre ?? '');
  const [especie, setEspecie] = useState(mascota?.especie ?? 'CANINO');
  const [raza, setRaza] = useState(mascota?.raza ?? '');
  const [sexo, setSexo] = useState(mascota?.sexo ?? 'M');
  const [nacimiento, setNacimiento] = useState<Date | null>(
    mascota?.fecha_nacimiento ? desdeISO(mascota.fecha_nacimiento) : null,
  );
  const [peso, setPeso] = useState(mascota?.peso_kg ?? '');
  const [castrado, setCastrado] = useState(mascota?.castrado ?? false);
  const [observaciones, setObservaciones] = useState(mascota?.observaciones ?? '');

  function guardar() {
    enviar<Mascota>(
      {
        ...(mascota ? {} : { cliente: clienteId }),
        nombre: nombre.trim(),
        especie,
        raza: raza.trim() || null,
        sexo,
        fecha_nacimiento: nacimiento ? aISO(nacimiento) : null,
        peso_kg: numero(String(peso)),
        castrado,
        observaciones: observaciones.trim() || null,
      },
      mascota ? 'Datos actualizados' : 'Mascota registrada',
      { method: mascota ? 'PATCH' : 'POST', onExito: onGuardada },
    );
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton={mascota ? 'Guardar cambios' : 'Registrar mascota'}
      errorGeneral={errores.cliente}>
      <Campo etiqueta="Nombre *" value={nombre} onChangeText={setNombre} error={errores.nombre} />

      <View style={styles.grupo}>
        <Texto variante="etiqueta">Especie</Texto>
        <Chips opciones={ESPECIES} valor={especie} onCambiar={setEspecie} />
      </View>

      <Campo etiqueta="Raza" placeholder="Mestizo" value={raza} onChangeText={setRaza} error={errores.raza} />

      <View style={styles.grupo}>
        <Texto variante="etiqueta">Sexo</Texto>
        <Chips opciones={SEXOS} valor={sexo} onCambiar={setSexo} />
      </View>

      <SelectorFechaHora etiqueta="Fecha de nacimiento" valor={nacimiento} onCambiar={setNacimiento} opcional
        error={errores.fecha_nacimiento} />

      <Campo etiqueta="Peso (kg)" keyboardType="decimal-pad" value={String(peso)} onChangeText={setPeso}
        error={errores.peso_kg} />

      <View style={[styles.interruptor, { borderColor: t.border }]}>
        <Texto>Castrado/a</Texto>
        <Switch value={castrado} onValueChange={setCastrado} trackColor={{ true: t.primary }} />
      </View>

      <Campo etiqueta="Observaciones" placeholder="Alergias, carácter, antecedentes..." multiline
        value={observaciones} onChangeText={setObservaciones} error={errores.observaciones} />
    </Formulario>
  );
}

const styles = StyleSheet.create({
  grupo: { gap: Spacing.xs },
  interruptor: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
});
