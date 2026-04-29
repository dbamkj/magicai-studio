/**
 * MagiCAi Studio — Aurora Design System Tokens
 *
 * Central source of truth for colors, gradients, glass styles, radii,
 * spacing, and typography. Import from here everywhere.
 */
import { Platform } from 'react-native';

// -------- Aurora deep background base ----------
export const aurora = {
  bg0: '#0F0C29',
  bg1: '#1A1446',
  bg2: '#2E1F5B',
  // accent blob colors
  pink: '#FF4D8D',
  purple: '#7B5CFF',
  blue: '#00C2FF',
  orange: '#FF9A3C',
};

// -------- Brand gradient (CTA buttons) ----------
export const brandGradient = ['#FF4D8D', '#FF9A3C', '#7B5CFF'] as const;
export const brandGradientCool = ['#7B5CFF', '#00C2FF'] as const;
export const brandGradientWarm = ['#FF4D8D', '#FF9A3C'] as const;

// -------- Glass tokens ----------
export const glass = {
  background: 'rgba(255,255,255,0.06)',
  backgroundStrong: 'rgba(255,255,255,0.10)',
  border: 'rgba(255,255,255,0.15)',
  borderStrong: 'rgba(255,255,255,0.22)',
  blur: 24,
};

// -------- Text tokens ----------
export const text = {
  primary: '#FFFFFF',
  secondary: '#CBD5E1',
  muted: '#94A3B8',
  faint: '#64748B',
  inverse: '#0F172A',
  accent: '#FF9A3C',
};

// -------- Radii (8pt grid) ----------
export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  pill: 999,
};

// -------- Spacing (8pt grid) ----------
export const space = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 40,
};

// -------- Shadows ----------
export const shadow = {
  soft: Platform.select({
    ios: { shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } },
    android: { elevation: 5 },
    default: { boxShadow: '0 6px 14px rgba(0,0,0,0.18)' },
  }) as any,
  glow: Platform.select({
    ios: { shadowColor: '#7B5CFF', shadowOpacity: 0.35, shadowRadius: 20, shadowOffset: { width: 0, height: 0 } },
    android: { elevation: 8 },
    default: { boxShadow: '0 0 24px rgba(123,92,255,0.35)' },
  }) as any,
};

// -------- Typography ----------
export const fontSize = {
  caption: 11,
  small: 12,
  body: 14,
  bodyLg: 16,
  h3: 18,
  h2: 22,
  h1: 28,
  display: 36,
};

export const fontWeight = {
  regular: '400' as const,
  medium: '600' as const,
  bold: '700' as const,
  black: '800' as const,
  display: '900' as const,
};

export default {
  aurora,
  brandGradient,
  brandGradientCool,
  brandGradientWarm,
  glass,
  text,
  radius,
  space,
  shadow,
  fontSize,
  fontWeight,
};
