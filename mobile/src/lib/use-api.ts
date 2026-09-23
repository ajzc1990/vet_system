import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

import { api } from '@/lib/api';

/**
 * GET a la API que se vuelve a pedir cada vez que la pantalla toma foco (así, al volver
 * de cargar una consulta, la ficha ya muestra la nueva) y con pull-to-refresh.
 */
export function useApi<T>(ruta: string | null) {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [refrescando, setRefrescando] = useState(false);
  const ultimaRuta = useRef(ruta);

  const cargar = useCallback(async () => {
    if (!ruta) return;
    ultimaRuta.current = ruta;
    try {
      const respuesta = await api<T>(ruta);
      // Si la ruta cambió mientras esperábamos (p. ej. otra búsqueda), se descarta.
      if (ultimaRuta.current === ruta) {
        setDatos(respuesta);
        setError(null);
      }
    } catch (e) {
      if (ultimaRuta.current === ruta) setError(e instanceof Error ? e.message : 'Error inesperado.');
    } finally {
      if (ultimaRuta.current === ruta) setCargando(false);
    }
  }, [ruta]);

  useFocusEffect(
    useCallback(() => {
      cargar();
    }, [cargar]),
  );

  const refrescar = useCallback(async () => {
    setRefrescando(true);
    await cargar();
    setRefrescando(false);
  }, [cargar]);

  return { datos, error, cargando, refrescando, refrescar, setDatos };
}
