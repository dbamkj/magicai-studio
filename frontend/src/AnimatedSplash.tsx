/**
 * AnimatedSplash — premium app open experience.
 *
 * Sequence (~1.8s total):
 *   0.00–0.40s  Logo fade in (0 → 1) + scale (0.85 → 1.0)
 *   0.40–0.90s  Soft glow expands (scale 1 → 1.05) + sparkle ✨
 *   0.90–1.40s  Glow stabilizes, tagline fades in
 *   1.40–1.80s  Fade-out + slight slide-up → onDone()
 *
 * Sound chime is optional and gated behind a prop. Default OFF.
 * Built to render OVER the AuroraBackground.
 */
import React, { useEffect } from 'react';
import { View, Text, Image, StyleSheet, Dimensions, Platform } from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle, withTiming, withSequence, withDelay,
  Easing, runOnJS,
} from 'react-native-reanimated';
import { Audio } from 'expo-av';
import AuroraBackground from './AuroraBackground';
// MagicAiLogo removed — splash now renders a clean gradient M glyph
// (see glyphCircle/glyphM styles below) to eliminate the rectangle that was
// baked into the mai_mark_transparent.png raster asset.
import { text as colors, brandGradient } from './theme';
import { LinearGradient } from 'expo-linear-gradient';

const { width: W, height: H } = Dimensions.get('window');

type Props = {
  /** Called when fade-out completes — caller should hide the splash. */
  onDone: () => void;
  /** Optional: play a soft chime (requires App Sounds toggle). */
  playChime?: boolean;
};

export default function AnimatedSplash({ onDone, playChime = false }: Props) {
  // Logo opacity & scale
  const logoOpacity = useSharedValue(0);
  const logoScale = useSharedValue(0.85);
  // Glow ring scale & opacity
  const glowScale = useSharedValue(0.6);
  const glowOpacity = useSharedValue(0);
  // Sparkle opacity
  const sparkleOpacity = useSharedValue(0);
  // Tagline opacity
  const taglineOpacity = useSharedValue(0);
  // Whole-screen fade-out + slide
  const rootOpacity = useSharedValue(1);
  const rootTranslateY = useSharedValue(0);

  useEffect(() => {
    // 0.00–0.40s logo in
    logoOpacity.value = withTiming(1, { duration: 400, easing: Easing.out(Easing.cubic) });
    logoScale.value = withTiming(1.0, { duration: 400, easing: Easing.out(Easing.cubic) });

    // 0.40–0.90s glow expand & sparkle
    glowOpacity.value = withDelay(380, withTiming(0.65, { duration: 320 }));
    glowScale.value = withDelay(380, withSequence(
      withTiming(1.10, { duration: 320, easing: Easing.out(Easing.quad) }),
      withTiming(1.05, { duration: 220, easing: Easing.inOut(Easing.quad) }),
    ));
    sparkleOpacity.value = withDelay(450, withSequence(
      withTiming(1, { duration: 180 }),
      withTiming(0, { duration: 320 }),
    ));

    // 0.90s tagline fade in
    taglineOpacity.value = withDelay(900, withTiming(1, { duration: 450 }));

    // Hold the splash visible longer (~3.0s total) before fade-out so users
    // can take in the brand. Was 1.4s — bumped to 2.6s.
    rootOpacity.value = withDelay(2600, withTiming(0, { duration: 450, easing: Easing.in(Easing.cubic) }, (finished) => {
      if (finished) runOnJS(onDone)();
    }));
    rootTranslateY.value = withDelay(2600, withTiming(-20, { duration: 450, easing: Easing.in(Easing.cubic) }));

    // Optional chime — best-effort, fail-silent.
    if (playChime) {
      (async () => {
        try {
          await Audio.setAudioModeAsync({
            playsInSilentModeIOS: false, // respect silent switch
            staysActiveInBackground: false,
            shouldDuckAndroid: true,
          });
          const { sound } = await Audio.Sound.createAsync(
            require('../assets/sounds/splash_chime.mp3'),
            { volume: 0.55, shouldPlay: true },
          );
          // Auto-cleanup after the chime finishes (≈1.4s)
          setTimeout(() => { sound.unloadAsync().catch(() => {}); }, 3000);
        } catch {
          // Silently ignore — sounds are non-essential
        }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rootStyle = useAnimatedStyle(() => ({
    opacity: rootOpacity.value,
    transform: [{ translateY: rootTranslateY.value }],
  }));
  const logoWrapStyle = useAnimatedStyle(() => ({
    opacity: logoOpacity.value,
    transform: [{ scale: logoScale.value }],
  }));
  const glowStyle = useAnimatedStyle(() => ({
    opacity: glowOpacity.value,
    transform: [{ scale: glowScale.value }],
  }));
  const sparkleStyle = useAnimatedStyle(() => ({ opacity: sparkleOpacity.value }));
  const taglineStyle = useAnimatedStyle(() => ({ opacity: taglineOpacity.value }));

  return (
    <Animated.View style={[StyleSheet.absoluteFill, s.root, rootStyle]}>
      <AuroraBackground absolute variant="full" />
      <View style={s.center}>
        {/* Soft glow ring behind logo */}
        <Animated.View style={[s.glowRing, glowStyle]}>
          <LinearGradient
            colors={[brandGradient[0], brandGradient[2], 'transparent']}
            start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={StyleSheet.absoluteFill}
          />
        </Animated.View>

        {/* New neon-μ logo image (replaces the old gradient-M glyph). */}
        <Animated.View style={[s.logoWrap, logoWrapStyle]}>
          <Image
            source={require('../assets/logo/nw_glyph.png')}
            resizeMode="contain"
            style={{ width: 140, height: 140 }}
          />
          {/* Sparkle */}
          <Animated.Text style={[s.sparkle, sparkleStyle]}>✨</Animated.Text>
        </Animated.View>

        {/* Wordmark image — full colorful "MagiCAi Studio" mark */}
        <Animated.View style={[{ marginTop: 18, alignItems: 'center' }, taglineStyle]}>
          <Image
            source={require('../assets/logo/nw_wordmark.png')}
            resizeMode="contain"
            style={{ width: 280, height: 134 }}
          />
        </Animated.View>
      </View>
    </Animated.View>
  );
}

const s = StyleSheet.create({
  root: { backgroundColor: '#0F0C29' },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    width: 140, height: 140,
  },
  glyphCircle: {
    width: 118, height: 118, borderRadius: 59,
    overflow: 'hidden',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.18)',
    ...Platform.select({
      web: { boxShadow: '0 0 32px rgba(236,72,153,0.55), 0 0 12px rgba(167,139,250,0.45)' as any },
      default: { shadowColor: '#EC4899', shadowOpacity: 0.55, shadowRadius: 24, shadowOffset: { width: 0, height: 0 } },
    }),
  },
  glyphM: {
    color: '#fff',
    fontSize: 72,
    fontWeight: '900',
    textAlign: 'center',
    marginTop: -2,
    letterSpacing: 0.5,
    ...Platform.select({
      web: { textShadow: '0 2px 6px rgba(0,0,0,0.35)' as any },
      default: {},
    }),
  },
  glowRing: {
    position: 'absolute',
    width: 220, height: 220, borderRadius: 220,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(28px)' } as any) : {}),
  },
  sparkle: {
    position: 'absolute',
    top: -8, right: -10,
    fontSize: 28,
  },
  brand: {
    color: colors.primary,
    fontSize: 26,
    fontWeight: '900',
    letterSpacing: 0.4,
    textAlign: 'center',
  },
  tagline: {
    color: colors.secondary,
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.3,
    marginTop: 6,
    textAlign: 'center',
  },
});
