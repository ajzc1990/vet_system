import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, StyleSheet, View } from 'react-native';

import { Formulario, useEnvio } from '@/components/formulario';
import { Boton, Campo, Chips, Texto } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/lib/use-theme';

const TIPOS = [
  { valor: 'OTRO', etiqueta: 'Foto clínica' },
  { valor: 'RADIOGRAFIA', etiqueta: 'Radiografía' },
  { valor: 'ECOGRAFIA', etiqueta: 'Ecografía' },
  { valor: 'ANALISIS_SANGRE', etiqueta: 'Laboratorio' },
  { valor: 'CITOLOGIA', etiqueta: 'Citología' },
];

type Foto = { uri: string; nombre: string; tipo: string };

export default function NuevoEstudio() {
  const t = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { enviar, enviando, errores } = useEnvio(`mascotas/${id}/estudios/`);
  const [foto, setFoto] = useState<Foto | null>(null);
  const [titulo, setTitulo] = useState('');
  const [tipo, setTipo] = useState('OTRO');
  const [observaciones, setObservaciones] = useState('');

  async function elegir(origen: 'camara' | 'galeria') {
    const permiso =
      origen === 'camara'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permiso.granted) {
      Alert.alert('Permiso necesario', `Habilitá el acceso a la ${origen === 'camara' ? 'cámara' : 'galería'} en los ajustes del celular.`);
      return;
    }
    // quality 0.7: una foto de celular queda en 1-3 MB, lejos del límite de 10 MB del servidor.
    const opciones: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.7 };
    const resultado =
      origen === 'camara'
        ? await ImagePicker.launchCameraAsync(opciones)
        : await ImagePicker.launchImageLibraryAsync(opciones);
    if (resultado.canceled) return;

    const asset = resultado.assets[0];
    // El servidor sólo acepta JPG/PNG/PDF: HEIC u otros formatos se mandan como JPG.
    const esPng = asset.mimeType === 'image/png';
    setFoto({
      uri: asset.uri,
      nombre: `estudio_${Date.now()}.${esPng ? 'png' : 'jpg'}`,
      tipo: esPng ? 'image/png' : 'image/jpeg',
    });
  }

  function guardar() {
    if (!foto) {
      Alert.alert('Falta la foto', 'Sacá una foto o elegila de la galería.');
      return;
    }
    const datos = new FormData();
    // React Native manda el archivo a partir de { uri, name, type }.
    datos.append('archivo', { uri: foto.uri, name: foto.nombre, type: foto.tipo } as unknown as Blob);
    datos.append('titulo', titulo.trim());
    datos.append('tipo_estudio', tipo);
    if (observaciones.trim()) datos.append('observaciones', observaciones.trim());
    enviar(datos, 'Estudio adjuntado');
  }

  return (
    <Formulario onGuardar={guardar} enviando={enviando} tituloBoton="Adjuntar a la historia" errorGeneral={errores.archivo}>
      {foto ? (
        <View style={{ gap: Spacing.sm }}>
          <Image source={{ uri: foto.uri }} style={[styles.vista, { backgroundColor: t.border }]} contentFit="cover" />
          <Boton titulo="Cambiar foto" icono="camera-reverse-outline" variante="secundario" onPress={() => elegir('camara')} />
        </View>
      ) : (
        <View style={styles.origenes}>
          <Boton titulo="Sacar foto" icono="camera" style={{ flex: 1 }} onPress={() => elegir('camara')} />
          <Boton titulo="Galería" icono="images-outline" variante="secundario" style={{ flex: 1 }}
            onPress={() => elegir('galeria')} />
        </View>
      )}

      <Campo etiqueta="Título *" placeholder="Herida en pata trasera, RX tórax..." value={titulo}
        onChangeText={setTitulo} error={errores.titulo} />

      <View style={{ gap: Spacing.xs }}>
        <Texto variante="etiqueta">Tipo</Texto>
        <Chips opciones={TIPOS} valor={tipo} onCambiar={setTipo} />
      </View>

      <Campo etiqueta="Informe / observaciones" multiline value={observaciones} onChangeText={setObservaciones}
        error={errores.observaciones} />
    </Formulario>
  );
}

const styles = StyleSheet.create({
  vista: { width: '100%', aspectRatio: 4 / 3, borderRadius: Radius.md },
  origenes: { flexDirection: 'row', gap: Spacing.sm },
});
