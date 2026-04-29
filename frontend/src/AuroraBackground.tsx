/**
 * AuroraBackground — premium Aurora gradient with soft glowing blurred blobs.
 *
 * Drop-in replacement for `CosmicBackground`. Two usage patterns:
 *   1) Wrapper:    <AuroraBackground><SafeAreaView ...>...</SafeAreaView></AuroraBackground>
 *   2) Absolute overlay (when wrapped manually):
 *        <View style={{flex:1}}><AuroraBackground absolute />{...content}</View>
 *
 * Light, performant — uses 4 stacked LinearGradients + radial-feel blobs.
 * No heavy particle work.
 */
import React from 'react';
import { View, StyleSheet, Platform } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { aurora } from './theme';
import { useTheme } from './ThemeContext';

type Props = {
  /** When true, AuroraBackground renders as absolute fill (no flex container). */
  absolute?: boolean;
  /** Reduce vibrancy for input/legal screens (60% saturation feel). */
  variant?: 'full' | 'subtle';
  children?: React.ReactNode;
};

// Pastel light-mode aurora (used when ThemeContext.isDark === false)
const AURORA_LIGHT = {
  bg0:    '#FAF5FF',
  bg1:    '#F3E8FF',
  bg2:    '#FFE4F0',
  pink:   '#FDA4AF',
  purple: '#C4B5FD',
  blue:   '#7DD3FC',
  orange: '#FCD34D',
};

export default function AuroraBackground({ absolute = false, variant = 'full', children }: Props) {
  const { isDark } = useTheme();
  const palette = isDark ? aurora : AURORA_LIGHT;
  // Light mode uses softer blob opacity and a near-transparent overlay
  // so pastel reads cleanly without going milky.
  const blobOpacity = isDark
    ? (variant === 'full' ? 0.22 : 0.12)
    : (variant === 'full' ? 0.55 : 0.35);
  const overlayBg = isDark
    ? (variant === 'full' ? 'rgba(15,12,41,0.55)' : 'rgba(15,12,41,0.70)')
    : (variant === 'full' ? 'rgba(255,255,255,0.20)' : 'rgba(255,255,255,0.40)');

  // The decorative layer (gradients + blobs + overlay) — same in both modes.
  const Decor = (
    <>
      <LinearGradient
        colors={[palette.bg0, palette.bg1, palette.bg2]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      <View style={[s.blob, { top: -120, left: -120, opacity: blobOpacity }]}>
        <LinearGradient colors={[palette.pink, 'transparent']} style={s.blobGrad} start={{ x: 0.5, y: 0.5 }} end={{ x: 1, y: 1 }} />
      </View>
      <View style={[s.blob, { top: 120, right: -160, opacity: blobOpacity * 0.95 }]}>
        <LinearGradient colors={[palette.purple, 'transparent']} style={s.blobGrad} start={{ x: 0.5, y: 0.5 }} end={{ x: 1, y: 1 }} />
      </View>
      <View style={[s.blob, { bottom: -160, left: -80, opacity: blobOpacity * 0.85 }]}>
        <LinearGradient colors={[palette.blue, 'transparent']} style={s.blobGrad} start={{ x: 0.5, y: 0.5 }} end={{ x: 1, y: 1 }} />
      </View>
      <View style={[s.blob, { bottom: 60, right: -100, opacity: blobOpacity * 0.7, width: 280, height: 280 }]}>
        <LinearGradient colors={[palette.orange, 'transparent']} style={s.blobGrad} start={{ x: 0.5, y: 0.5 }} end={{ x: 1, y: 1 }} />
      </View>
      <View style={[StyleSheet.absoluteFill, { backgroundColor: overlayBg }]} />
    </>
  );

  if (absolute) {
    // Absolute overlay mode (caller controls layout)
    return <View style={[StyleSheet.absoluteFillObject, s.absRoot]} pointerEvents="none">{Decor}</View>;
  }

  // Wrapper mode — replicates CosmicBackground API
  return (
    <View style={[s.wrapRoot, { backgroundColor: palette.bg0 }]}>
      <View style={StyleSheet.absoluteFillObject} pointerEvents="none">{Decor}</View>
      {children}
    </View>
  );
}

const s = StyleSheet.create({
  wrapRoot: { flex: 1, backgroundColor: aurora.bg0 },
  absRoot: { overflow: 'hidden' },
  blob: {
    position: 'absolute',
    width: 360,
    height: 360,
    borderRadius: 360,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(60px)' } as any) : {}),
  },
  blobGrad: {
    width: '100%',
    height: '100%',
    borderRadius: 360,
  },
});
