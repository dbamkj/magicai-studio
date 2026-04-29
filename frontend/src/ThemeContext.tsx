/**
 * MagiCAi Studio — Theme Context (Light + Dark mode)
 *
 *   const { mode, isDark, toggle } = useTheme();
 *
 * Persists to AsyncStorage `magicai.themeMode`. Defaults to 'dark'.
 * `mode = 'system'` follows `useColorScheme()` (Appearance).
 *
 * Color tokens auto-swap via `useThemeColors()` — both legacy `theme.ts`
 * (dark-only) and `ui/theme.ts` (Premium Neon Glass) consumers can opt in.
 */
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { colors as DARK_TOKENS } from './ui/theme';

const KEY = 'magicai.themeMode';

export type ThemeMode = 'dark' | 'light' | 'system';

type ThemeContextValue = {
  mode: ThemeMode;
  effectiveMode: 'dark' | 'light';   // resolved (system → dark|light)
  isDark: boolean;
  setMode: (m: ThemeMode) => void;
  toggle: () => void;
  colors: typeof DARK_TOKENS;        // active palette (swaps in light)
};

// ---------- Light-mode token override (pastel aurora + white glass) ----------
const LIGHT_TOKENS: typeof DARK_TOKENS = {
  ...DARK_TOKENS,

  // Backdrop — pastel violet → mint → peach
  bgDeep:       '#FAF5FF',
  bgIndigo:     '#F3E8FF',
  bgViolet:     '#FFE4F0',
  bgFromBottom: ['#FAF5FF', '#F3E8FF', '#FFE4F0'] as const,
  bgFromTop:    ['#FFE4F0', '#F3E8FF', '#FAF5FF'] as const,

  // Surface (white glass)
  glassBg:        'rgba(255,255,255,0.65)',
  glassBgStrong:  'rgba(255,255,255,0.80)',
  glassBgSubtle:  'rgba(255,255,255,0.45)',
  glassBorder:    'rgba(15,12,41,0.10)',
  glassBorderHi:  'rgba(15,12,41,0.18)',

  // Text — dark on light
  text:       '#0F0C29',
  textMuted:  '#3F3D56',
  textDim:    '#64748B',
  textDimmer: '#94A3B8',
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const sysScheme = useColorScheme();        // 'light' | 'dark' | null
  const [mode, setModeState] = useState<ThemeMode>('dark');
  const [hydrated, setHydrated] = useState(false);

  // Hydrate from AsyncStorage once
  useEffect(() => {
    (async () => {
      try {
        const v = await AsyncStorage.getItem(KEY);
        if (v === 'light' || v === 'dark' || v === 'system') setModeState(v);
      } catch {}
      setHydrated(true);
    })();
  }, []);

  const effectiveMode: 'dark' | 'light' = useMemo(() => {
    if (mode === 'system') return (sysScheme === 'light' ? 'light' : 'dark');
    return mode;
  }, [mode, sysScheme]);

  const isDark = effectiveMode === 'dark';
  const colors = isDark ? DARK_TOKENS : LIGHT_TOKENS;

  const setMode = (m: ThemeMode) => {
    setModeState(m);
    AsyncStorage.setItem(KEY, m).catch(() => {});
  };
  const toggle = () => setMode(isDark ? 'light' : 'dark');

  const value = useMemo<ThemeContextValue>(() => ({
    mode, effectiveMode, isDark, setMode, toggle, colors,
  }), [mode, effectiveMode, isDark, colors]);

  // Don't gate render on hydration — first paint uses dark default,
  // then re-renders once AsyncStorage resolves (~10ms).
  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    // Fallback so screens never crash if Provider is missing.
    return {
      mode: 'dark',
      effectiveMode: 'dark',
      isDark: true,
      setMode: () => {},
      toggle: () => {},
      colors: DARK_TOKENS,
    };
  }
  return ctx;
}

/** Convenience hook — returns just the active palette. */
export function useThemeColors() {
  return useTheme().colors;
}
