import * as SecureStore from 'expo-secure-store';
import { createContext, use, useCallback, useEffect, useState, type PropsWithChildren } from 'react';
import { Platform } from 'react-native';

import { api, ApiError, configurarSesion } from '@/lib/api';
import type { Usuario } from '@/lib/types';

const CLAVE_TOKEN = 'vetersystem.token';

// SecureStore no existe en web; ahí (sólo para probar en el navegador) va a localStorage.
const almacen = {
  leer: () =>
    Platform.OS === 'web' ? Promise.resolve(localStorage.getItem(CLAVE_TOKEN)) : SecureStore.getItemAsync(CLAVE_TOKEN),
  guardar: (valor: string) =>
    Platform.OS === 'web' ? Promise.resolve(localStorage.setItem(CLAVE_TOKEN, valor)) : SecureStore.setItemAsync(CLAVE_TOKEN, valor),
  borrar: () =>
    Platform.OS === 'web' ? Promise.resolve(localStorage.removeItem(CLAVE_TOKEN)) : SecureStore.deleteItemAsync(CLAVE_TOKEN),
};

type Sesion = {
  usuario: Usuario | null;
  cargando: boolean;
  iniciarSesion: (username: string, password: string) => Promise<void>;
  cerrarSesion: () => Promise<void>;
};

const SesionContext = createContext<Sesion | null>(null);

export function useSesion() {
  const valor = use(SesionContext);
  if (!valor) throw new Error('useSesion debe usarse dentro de <SesionProvider />');
  return valor;
}

export function SesionProvider({ children }: PropsWithChildren) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  const olvidarSesion = useCallback(async () => {
    configurarSesion(null);
    setUsuario(null);
    await almacen.borrar();
  }, []);

  const verificarSesion = useCallback(async () => {
    try {
      setUsuario(await api<Usuario>('yo/'));
    } catch (e) {
      // Sin conexión no es motivo para desloguear; token inválido o cuenta desaprobada sí.
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) await olvidarSesion();
    }
  }, [olvidarSesion]);

  useEffect(() => {
    (async () => {
      const token = await almacen.leer();
      if (token) {
        configurarSesion(token, verificarSesion);
        await verificarSesion();
      }
      setCargando(false);
    })();
  }, [verificarSesion]);

  const iniciarSesion = useCallback(
    async (username: string, password: string) => {
      const { token } = await api<{ token: string }>('token/', {
        method: 'POST',
        body: { username, password },
      });
      configurarSesion(token, verificarSesion);
      const yo = await api<Usuario>('yo/');
      await almacen.guardar(token);
      setUsuario(yo);
    },
    [verificarSesion],
  );

  const cerrarSesion = useCallback(async () => {
    try {
      await api('logout/', { method: 'POST' });
    } catch {
      // Si el servidor no responde igual se cierra la sesión en el dispositivo.
    }
    await olvidarSesion();
  }, [olvidarSesion]);

  return (
    <SesionContext value={{ usuario, cargando, iniciarSesion, cerrarSesion }}>{children}</SesionContext>
  );
}
