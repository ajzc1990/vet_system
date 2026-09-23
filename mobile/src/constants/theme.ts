/**
 * Paleta alineada a la web de VeterSystem (variables --vs-* de templates/base.html).
 */

export const Colors = {
  light: {
    text: '#0f172a',
    textSecondary: '#64748b',
    background: '#f5f7fb',
    card: '#ffffff',
    border: '#e5e9f2',
    primary: '#6366f1',
    primaryDark: '#4f46e5',
    primaryLight: '#eef2ff',
    onPrimary: '#ffffff',
    success: '#059669',
    successBg: '#d1fae5',
    warning: '#b45309',
    warningBg: '#fef3c7',
    danger: '#dc2626',
    dangerBg: '#fee2e2',
  },
  dark: {
    text: '#f1f5f9',
    textSecondary: '#94a3b8',
    background: '#0f1420',
    card: '#161d2e',
    border: '#232c40',
    primary: '#818cf8',
    primaryDark: '#6366f1',
    primaryLight: '#1e2340',
    onPrimary: '#ffffff',
    success: '#34d399',
    successBg: '#0f2e25',
    warning: '#fbbf24',
    warningBg: '#33270d',
    danger: '#f87171',
    dangerBg: '#3a1616',
  },
} as const;

export type Theme = { [K in keyof typeof Colors.light]: string };

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
} as const;
