/**
 * BrandLogo — unified MagiCAi Studio brand mark.
 *
 * Uses the new neon "μ" glyph + colorful "MagiCAi Studio" wordmark images
 * (nw_glyph.png, nw_wordmark.png). The earlier inline gradient-M is kept
 * as a CSS fallback for very small contexts (sm size, no glyphImage flag).
 *
 *   <BrandLogo />                              -> default md, image glyph + text
 *   <BrandLogo size="xl" stacked imageWordmark /> -> Login / Splash hero
 *   <BrandLogo size="sm" glyphOnly />           -> compact avatar/header
 */
import React from 'react';
import { View, Text, Image, StyleSheet, Platform } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

type Size = 'sm' | 'md' | 'lg' | 'xl';

const SIZES: Record<Size, { glyph: number; brand: number; tag: number; gap: number }> = {
  sm: { glyph: 32, brand: 14, tag: 9,  gap: 8  },
  md: { glyph: 44, brand: 20, tag: 11, gap: 10 },
  lg: { glyph: 72, brand: 28, tag: 12, gap: 12 },
  xl: { glyph: 120, brand: 34, tag: 14, gap: 16 },
};

type Props = {
  size?: Size;
  /** Show "Turn Ideas Into Magic ✨" line under the wordmark text. */
  tagline?: boolean | string;
  /** Stack glyph + wordmark vertically (centered) instead of side-by-side. */
  stacked?: boolean;
  /** Render only the glyph icon. */
  glyphOnly?: boolean;
  /** Render the colorful "MagiCAi Studio" image wordmark instead of plain text.
   *  The image already includes its own tagline so `tagline` is ignored. */
  imageWordmark?: boolean;
};

export default function BrandLogo({
  size = 'md',
  tagline = false,
  stacked = false,
  glyphOnly = false,
  imageWordmark = false,
}: Props) {
  const sz = SIZES[size];

  // Glyph: PNG of the new neon-μ logo. We use a circular crop on a subtle
  // glass background to keep it readable on both light and dark surfaces.
  const Glyph = (
    <View
      style={[
        s.glyph,
        {
          width: sz.glyph,
          height: sz.glyph,
          borderRadius: Math.round(sz.glyph * 0.28),
        },
      ]}
    >
      <Image
        source={require('../assets/logo/nw_glyph.png')}
        resizeMode="contain"
        style={{ width: '100%', height: '100%' }}
      />
    </View>
  );

  if (glyphOnly) return Glyph;

  if (imageWordmark) {
    // The colorful "MagiCAi Studio · TURN IDEAS INTO MAGIC · CREATE • INSPIRE
    // • MAGIC" wordmark from newappdsg.png. Aspect ratio ≈ 2.08 (1810×869).
    const wmH =
      size === 'xl' ? 132 :
      size === 'lg' ? 96  :
      size === 'md' ? 64  : 48;
    const wmW = Math.round(wmH * (1810 / 869));
    return (
      <View style={[s.row, stacked && s.stacked, { gap: sz.gap }]}>
        {Glyph}
        <Image
          source={require('../assets/logo/nw_wordmark.png')}
          resizeMode="contain"
          style={{ width: wmW, height: wmH }}
        />
      </View>
    );
  }

  const tagText = typeof tagline === 'string' ? tagline : 'Turn Ideas Into Magic ✨';

  return (
    <View style={[s.row, stacked && s.stacked, { gap: sz.gap }]}>
      {Glyph}
      <View style={stacked ? { alignItems: 'center', marginTop: 4 } : null}>
        <Text style={[s.brand, { fontSize: sz.brand }]}>MagiCAi Studio</Text>
        {tagline ? (
          <Text style={[s.tagline, { fontSize: sz.tag }]}>{tagText}</Text>
        ) : null}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },
  stacked: { flexDirection: 'column', alignItems: 'center' },
  glyph: {
    overflow: 'hidden',
    backgroundColor: '#000',
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.18)',
    alignItems: 'center', justifyContent: 'center',
    ...Platform.select({
      web: { boxShadow: '0 0 22px rgba(168,85,247,0.55)' as any },
      default: {
        shadowColor: '#A855F7',
        shadowOpacity: 0.55,
        shadowRadius: 14,
        shadowOffset: { width: 0, height: 0 },
      },
    }),
  },
  brand: {
    color: '#FFFFFF', fontWeight: '900', letterSpacing: 0.4,
    ...Platform.select({
      web: { textShadow: '0 0 10px rgba(236,72,153,0.5)' as any },
      default: {},
    }),
  },
  tagline: { color: '#FBBF24', fontWeight: '700', letterSpacing: 0.2, marginTop: 2 },
});
