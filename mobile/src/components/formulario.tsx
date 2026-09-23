import { router } from 'expo-router';
import { useState, type PropsWithChildren } from 'react';
import { Alert, KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Boton, Texto } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { api, ApiError } from '@/lib/api';
import { useTheme } from '@/lib/use-theme';

/**
 * Estado de envío compartido por los formularios de alta (consulta, vacuna, receta):
 * POST a la API, errores por campo que devuelve DRF y volver a la ficha al terminar.
 */
export function useEnvio(ruta: string) {
  const [enviando, setEnviando] = useState(false);
  const [errores, setErrores] = useState<Record<string, string>>({});

  async function enviar(body: unknown, mensajeExito: string) {
    setEnviando(true);
    setErrores({});
    try {
      await api(ruta, { method: 'POST', body });
      router.back();
      Alert.alert(mensajeExito);
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.campos).length > 0) {
        setErrores(Object.fromEntries(Object.entries(e.campos).map(([k, v]) => [k, v[0]])));
      } else {
        Alert.alert('No se pudo guardar', e instanceof Error ? e.message : undefined);
      }
    } finally {
      setEnviando(false);
    }
  }

  return { enviar, enviando, errores, setErrores };
}

export function Formulario({
  children,
  onGuardar,
  enviando,
  tituloBoton = 'Guardar',
  errorGeneral,
}: PropsWithChildren<{ onGuardar: () => void; enviando: boolean; tituloBoton?: string; errorGeneral?: string }>) {
  const t = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: t.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 0}>
      <ScrollView
        contentContainerStyle={[styles.contenedor, { paddingBottom: insets.bottom + Spacing.xl }]}
        keyboardShouldPersistTaps="handled">
        {children}
        {errorGeneral && <Texto style={{ color: t.danger }}>{errorGeneral}</Texto>}
        <Boton titulo={tituloBoton} icono="checkmark" onPress={onGuardar} cargando={enviando} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

/** Acepta coma decimal (teclado numérico en español) y devuelve null si queda vacío. */
export function numero(valor: string) {
  const limpio = valor.trim().replace(',', '.');
  return limpio === '' ? null : limpio;
}

const styles = StyleSheet.create({
  contenedor: { padding: Spacing.lg, gap: Spacing.lg },
});
