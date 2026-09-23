import { useColorScheme } from 'react-native';

import { Colors, type Theme } from '@/constants/theme';

export function useTheme(): Theme {
  const scheme = useColorScheme();
  return scheme === 'dark' ? Colors.dark : Colors.light;
}
