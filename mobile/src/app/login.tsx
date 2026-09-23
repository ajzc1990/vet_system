import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Boton, Campo, Texto } from '@/components/ui';
import { Radius, Spacing } from '@/constants/theme';
import { API_URL } from '@/lib/api';
import { useSesion } from '@/lib/session';
import { useTheme } from '@/lib/use-theme';

export default function Login() {
  const t = useTheme();
  const { iniciarSesion } = useSesion();
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function ingresar() {
    if (!usuario.trim() || !clave) {
      setError('Ingresá tu usuario y contraseña.');
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await iniciarSesion(usuario.trim(), clave);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar sesión.');
      setEnviando(false);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: t.background }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.contenedor} keyboardShouldPersistTaps="handled">
          <View style={styles.marca}>
            <Image source={require('@/assets/images/icon.png')} style={styles.logo} />
            <Texto variante="titulo">VeterSystem</Texto>
            <Texto variante="secundario">Ingresá con tu usuario de la clínica</Texto>
          </View>

          <View style={{ gap: Spacing.lg }}>
            <Campo
              etiqueta="Usuario"
              value={usuario}
              onChangeText={setUsuario}
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="username"
              textContentType="username"
              returnKeyType="next"
            />
            <Campo
              etiqueta="Contraseña"
              value={clave}
              onChangeText={setClave}
              secureTextEntry
              autoComplete="password"
              textContentType="password"
              returnKeyType="go"
              onSubmitEditing={ingresar}
            />
            {error && (
              <View style={[styles.error, { backgroundColor: t.dangerBg }]}>
                <Ionicons name="alert-circle" size={18} color={t.danger} />
                <Texto style={{ color: t.danger, flexShrink: 1 }}>{error}</Texto>
              </View>
            )}
            <Boton titulo="Ingresar" onPress={ingresar} cargando={enviando} />
          </View>

          {__DEV__ && (
            <Texto variante="secundario" style={{ textAlign: 'center' }}>
              Servidor: {API_URL}
            </Texto>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  contenedor: { flexGrow: 1, justifyContent: 'center', padding: Spacing.xl, gap: Spacing.xl },
  marca: { alignItems: 'center', gap: Spacing.sm },
  logo: { width: 80, height: 80, borderRadius: Radius.lg + 4, marginBottom: Spacing.sm },
  error: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.md,
    borderRadius: Radius.sm,
  },
});
