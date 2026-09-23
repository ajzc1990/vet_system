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

  /**
   * Por defecto hace POST, vuelve a la pantalla anterior y avisa con `mensajeExito`.
   * `onExito` reemplaza la navegación (p. ej. ir a la mascota recién creada).
   */
  async function enviar<T = unknown>(
    body: unknown,
    mensajeExito: string,
    opciones: { method?: 'POST' | 'PATCH'; onExito?: (respuesta: T) => void } = {},
  ) {
    setEnviando(true);
    setErrores({});
    try {
      const respuesta = await api<T>(ruta, { method: opciones.method ?? 'POST', body });
      if (opciones.onExito) opciones.onExito(respuesta);
      else router.back();
      if (mensajeExito) Alert.alert(mensajeExito);
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.campos).length > 0) {
        const porCampo = Object.fromEntries(Object.entries(e.campos).map(([k, v]) => [k, v[0]]));
        setErrores(porCampo);
        // Un error de un campo que el formulario no muestra (o 'detail') igual tiene que verse.
        if (porCampo.detail || porCampo.non_field_errors) {
          Alert.alert('No se pudo guardar', porCampo.detail ?? porCampo.non_field_errors);
        }
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
