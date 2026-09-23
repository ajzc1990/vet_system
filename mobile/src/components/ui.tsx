import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps, PropsWithChildren, ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextProps,
  type ViewStyle,
} from 'react-native';

import { Radius, Spacing, type Theme } from '@/constants/theme';
import type { EstadoTurno } from '@/lib/types';
import { useTheme } from '@/lib/use-theme';

export type IconName = ComponentProps<typeof Ionicons>['name'];

type Variante = 'titulo' | 'subtitulo' | 'cuerpo' | 'secundario' | 'etiqueta';

export function Texto({ variante = 'cuerpo', style, ...props }: TextProps & { variante?: Variante }) {
  const t = useTheme();
  const base = {
    titulo: { fontSize: 24, fontWeight: '700' as const, color: t.text },
    subtitulo: { fontSize: 17, fontWeight: '600' as const, color: t.text },
    cuerpo: { fontSize: 15, color: t.text, lineHeight: 21 },
    secundario: { fontSize: 13, color: t.textSecondary, lineHeight: 18 },
    etiqueta: {
      fontSize: 12,
      fontWeight: '600' as const,
      color: t.textSecondary,
      textTransform: 'uppercase' as const,
      letterSpacing: 0.5,
    },
  }[variante];
  return <Text style={[base, style]} {...props} />;
}

export function Tarjeta({
  children,
  style,
  onPress,
}: PropsWithChildren<{ style?: StyleProp<ViewStyle>; onPress?: () => void }>) {
  const t = useTheme();
  const estilo = [styles.tarjeta, { backgroundColor: t.card, borderColor: t.border }, style];
  if (!onPress) return <View style={estilo}>{children}</View>;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [estilo, pressed && { opacity: 0.7 }]}>
      {children}
    </Pressable>
  );
}

export function Boton({
  titulo,
  onPress,
  icono,
  variante = 'primario',
  cargando,
  disabled,
  style,
}: {
  titulo: string;
  onPress: () => void;
  icono?: IconName;
  variante?: 'primario' | 'secundario' | 'peligro';
  cargando?: boolean;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const t = useTheme();
  const colores = {
    primario: { fondo: t.primary, texto: t.onPrimary },
    secundario: { fondo: t.primaryLight, texto: t.primaryDark },
    peligro: { fondo: t.dangerBg, texto: t.danger },
  }[variante];
  const inactivo = disabled || cargando;

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={inactivo}
      style={({ pressed }) => [
        styles.boton,
        { backgroundColor: colores.fondo, opacity: inactivo ? 0.6 : pressed ? 0.8 : 1 },
        style,
      ]}>
      {cargando ? (
        <ActivityIndicator color={colores.texto} />
      ) : (
        <>
          {icono && <Ionicons name={icono} size={18} color={colores.texto} />}
          <Text style={[styles.botonTexto, { color: colores.texto }]}>{titulo}</Text>
        </>
      )}
    </Pressable>
  );
}

export function Campo({
  etiqueta,
  error,
  style,
  ...props
}: TextInputProps & { etiqueta: string; error?: string }) {
  const t = useTheme();
  return (
    <View style={{ gap: Spacing.xs }}>
      <Texto variante="etiqueta">{etiqueta}</Texto>
      <TextInput
        placeholderTextColor={t.textSecondary}
        style={[
          styles.campo,
          { backgroundColor: t.card, borderColor: error ? t.danger : t.border, color: t.text },
          props.multiline && { minHeight: 80, textAlignVertical: 'top' },
          style,
        ]}
        {...props}
      />
      {error && <Texto style={{ color: t.danger, fontSize: 13 }}>{error}</Texto>}
    </View>
  );
}

function coloresEstado(t: Theme, estado: EstadoTurno) {
  return {
    PENDIENTE: { fondo: t.warningBg, texto: t.warning },
    CONFIRMADO: { fondo: t.primaryLight, texto: t.primaryDark },
    COMPLETADO: { fondo: t.successBg, texto: t.success },
    CANCELADO: { fondo: t.dangerBg, texto: t.danger },
  }[estado];
}

export function Insignia({
  texto,
  tono = 'neutro',
  estado,
}: {
  texto: string;
  tono?: 'neutro' | 'exito' | 'alerta' | 'peligro';
  estado?: EstadoTurno;
}) {
  const t = useTheme();
  const c = estado
    ? coloresEstado(t, estado)
    : {
        neutro: { fondo: t.primaryLight, texto: t.primaryDark },
        exito: { fondo: t.successBg, texto: t.success },
        alerta: { fondo: t.warningBg, texto: t.warning },
        peligro: { fondo: t.dangerBg, texto: t.danger },
      }[tono];
  return (
    <View style={[styles.insignia, { backgroundColor: c.fondo }]}>
      <Text style={[styles.insigniaTexto, { color: c.texto }]}>{texto}</Text>
    </View>
  );
}

/** Carga / error / vacío: los tres estados que toda lista de la API puede tener. */
export function EstadoCarga({
  cargando,
  error,
  vacio,
  mensajeVacio,
  iconoVacio = 'file-tray-outline',
  onReintentar,
}: {
  cargando: boolean;
  error: string | null;
  vacio?: boolean;
  mensajeVacio?: string;
  iconoVacio?: IconName;
  onReintentar?: () => void;
}) {
  const t = useTheme();
  if (cargando) {
    return (
      <View style={styles.centro}>
        <ActivityIndicator color={t.primary} size="large" />
      </View>
    );
  }
  if (error) {
    return (
      <View style={styles.centro}>
        <Ionicons name="cloud-offline-outline" size={40} color={t.textSecondary} />
        <Texto variante="secundario" style={{ textAlign: 'center' }}>
          {error}
        </Texto>
        {onReintentar && <Boton titulo="Reintentar" variante="secundario" onPress={onReintentar} />}
      </View>
    );
  }
  if (vacio) {
    return (
      <View style={styles.centro}>
        <Ionicons name={iconoVacio} size={40} color={t.textSecondary} />
        <Texto variante="secundario" style={{ textAlign: 'center' }}>
          {mensajeVacio}
        </Texto>
      </View>
    );
  }
  return null;
}

export function Seccion({ titulo, accion, children }: PropsWithChildren<{ titulo: string; accion?: ReactNode }>) {
  return (
    <View style={{ gap: Spacing.sm }}>
      <View style={styles.seccionCabecera}>
        <Texto variante="etiqueta">{titulo}</Texto>
        {accion}
      </View>
      {children}
    </View>
  );
}

export function Fila({ icono, children }: PropsWithChildren<{ icono: IconName }>) {
  const t = useTheme();
  return (
    <View style={styles.fila}>
      <Ionicons name={icono} size={15} color={t.textSecondary} />
      <Texto variante="secundario" style={{ flexShrink: 1 }}>
        {children}
      </Texto>
    </View>
  );
}

const styles = StyleSheet.create({
  tarjeta: {
    borderRadius: Radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    padding: Spacing.lg,
    gap: Spacing.sm,
  },
  boton: {
    minHeight: 48,
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  botonTexto: { fontSize: 16, fontWeight: '600' },
  campo: {
    borderWidth: 1,
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontSize: 16,
  },
  insignia: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  insigniaTexto: { fontSize: 12, fontWeight: '600' },
  centro: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
    padding: Spacing.xl,
    minHeight: 240,
  },
  seccionCabecera: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  fila: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, borderRadius: Radius.lg },
  fab: {
    position: 'absolute',
    right: Spacing.lg,
    bottom: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: 999,
    elevation: 4,
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 3 },
  },
});

/** Opciones tocables (especie, sexo, estado...). Con `valor === null` ninguna queda marcada. */
export function Chips<T extends string | number>({
  opciones,
  valor,
  onCambiar,
}: {
  opciones: { valor: T; etiqueta: string }[];
  valor: T | null;
  onCambiar: (valor: T) => void;
}) {
  const t = useTheme();
  return (
    <View style={styles.chips}>
      {opciones.map((o) => {
        const activo = o.valor === valor;
        return (
          <Pressable
            key={String(o.valor)}
            accessibilityRole="button"
            accessibilityState={{ selected: activo }}
            onPress={() => onCambiar(o.valor)}
            style={[styles.chip, { backgroundColor: activo ? t.primary : t.primaryLight }]}>
            <Text style={{ color: activo ? t.onPrimary : t.primaryDark, fontWeight: '600' }}>{o.etiqueta}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function BotonFlotante({ icono, etiqueta, onPress }: { icono: IconName; etiqueta: string; onPress: () => void }) {
  const t = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={etiqueta}
      onPress={onPress}
      style={({ pressed }) => [styles.fab, { backgroundColor: t.primary, opacity: pressed ? 0.85 : 1 }]}>
      <Ionicons name={icono} size={22} color={t.onPrimary} />
      <Text style={{ color: t.onPrimary, fontWeight: '700', fontSize: 15 }}>{etiqueta}</Text>
    </Pressable>
  );
}

