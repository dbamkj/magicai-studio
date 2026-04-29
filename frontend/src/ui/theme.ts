/**
 * MagiCAi Studio — Premium Neon Glass design tokens
 * (apimg1/apimg2 reference, frosted glass + aurora gradient)
 *
 * Use the `colors` and `spacing` exports throughout the app to keep
 * every screen aligned with the same visual language.
 */

export const colors = {
  // ---------- Backdrop ----------
  bgDeep:       '#0A0212',  // bottom of vertical gradient
  bgIndigo:     '#1A0C38',
  bgViolet:     '#3B1F6E',
  bgFromBottom: ['#0A0212', '#1A0C38', '#1E1B4B'] as const,
  bgFromTop:    ['#1E1B4B', '#1A0C38', '#0A0212'] as const,

  // ---------- Aurora glow palette ----------
  auroraPurple: '#AE29FF',
  auroraPink:   '#FF007F',
  auroraOrange: '#FF6B08',
  auroraCyan:   '#00C6FF',

  // ---------- Surface (glass) ----------
  glassBg:        'rgba(255,255,255,0.06)',
  glassBgStrong:  'rgba(255,255,255,0.10)',
  glassBgSubtle:  'rgba(255,255,255,0.04)',
  glassBorder:    'rgba(255,255,255,0.12)',
  glassBorderHi:  'rgba(255,255,255,0.22)',

  // ---------- Brand gradient (CTA) ----------
  brandFrom: '#FF6B08',  // orange-pink
  brandMid:  '#FF007F',  // hot pink
  brandTo:   '#AE29FF',  // electric purple
  brandGradient: ['#FF6B08', '#FF007F', '#AE29FF'] as const,

  // Secondary brand gradient (cool / cinematic)
  coolFrom: '#00C6FF',
  coolTo:   '#AE29FF',
  coolGradient: ['#00C6FF', '#AE29FF'] as const,

  // ---------- Text ----------
  text:         '#FFFFFF',
  textMuted:    '#E0E0E0',
  textDim:      '#94A3B8',
  textDimmer:   '#64748B',

  // Status
  success: '#10B981',
  warning: '#FBBF24',
  danger:  '#F87171',
  info:    '#60A5FA',
} as const;

export const radii = {
  xs: 8,
  sm: 12,
  md: 16,
  lg: 20,
  xl: 24,
  pill: 999,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 40,
} as const;

export const typography = {
  h1:    { fontSize: 32, fontWeight: '800' as const, letterSpacing: -0.5 },
  h2:    { fontSize: 24, fontWeight: '800' as const, letterSpacing: -0.3 },
  h3:    { fontSize: 20, fontWeight: '700' as const },
  body:  { fontSize: 15, fontWeight: '400' as const, lineHeight: 22 },
  bodyM: { fontSize: 15, fontWeight: '600' as const, lineHeight: 22 },
  small: { fontSize: 13, fontWeight: '400' as const, lineHeight: 18 },
  cap:   { fontSize: 11, fontWeight: '700' as const, letterSpacing: 0.6 },
} as const;

export const shadows = {
  // Soft purple aura
  glow: {
    shadowColor: colors.auroraPurple,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.45,
    shadowRadius: 20,
    elevation: 12,
  },
  glowOrange: {
    shadowColor: colors.auroraOrange,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.4,
    shadowRadius: 18,
    elevation: 10,
  },
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.35,
    shadowRadius: 16,
    elevation: 6,
  },
} as const;
