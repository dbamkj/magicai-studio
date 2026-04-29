import React from 'react';
import { View, Text, Image, StyleSheet, Platform } from 'react-native';

/**
 * MagicAi Logo — M-only icon (cropped from source) with optional wordmark + taglines
 * rendered as live text so they scale crisply at any size.
 *
 * Batch 3 change: per user feedback, the raster asset now contains only
 * the stylized 'M' with sparkles and gradient. The "MagiCAi Studio" wordmark
 * and the two taglines are drawn as text, matching the neon purple-pink-amber
 * gradient theme of the M itself.
 *
 * Usage:
 *   <MagicAiLogo size={64} />                                // M only
 *   <MagicAiLogo size={64} showWordmark />                   // M + "MagiCAi Studio"
 *   <MagicAiLogo size={96} showWordmark showTagline />       // full brand lockup
 */

type Variant = 'play' | 'wave' | 'raster';

export default function MagicAiLogo({
  size = 72,
  showWordmark = false,
  showTagline = false,
  // back-compat
  variant,
}: {
  size?: number;
  showWordmark?: boolean;
  showTagline?: boolean;
  variant?: Variant;
}) {
  const textSize = Math.max(10, Math.round(size * 0.28));
  const subSize = Math.max(7, Math.round(size * 0.12));
  return (
    <View style={s.wrap}>
      <Image
        source={require('../assets/logo/mai_mark_transparent.png')}
        resizeMode="contain"
        style={{
          width: size,
          height: size,
          ...Platform.select({
            web: { filter: 'drop-shadow(0 0 14px rgba(236,72,153,0.55)) drop-shadow(0 0 6px rgba(139,92,246,0.45))' as any },
            default: {},
          }),
        }}
      />
      {showWordmark && (
        <View style={{ alignItems: 'center', marginTop: Math.round(size * 0.08) }}>
          <Text
            style={[
              s.wordmark,
              {
                fontSize: textSize,
                // Neon purple-pink-amber gradient effect via text-shadow on web;
                // on native we use solid color + glow via shadow (close enough).
                ...Platform.select({
                  web: {
                    backgroundImage: 'linear-gradient(90deg,#A78BFA 0%,#EC4899 50%,#FBBF24 100%)' as any,
                    WebkitBackgroundClip: 'text' as any,
                    WebkitTextFillColor: 'transparent' as any,
                    backgroundClip: 'text' as any,
                    textShadow: '0 0 18px rgba(236,72,153,0.35)' as any,
                  },
                  default: { color: '#EC4899' },
                }),
              },
            ]}
          >
            MagiCAi <Text style={{ color: '#FBBF24' }}>Studio</Text>
          </Text>
          {showTagline && (
            <>
              <Text style={[s.tagline, { fontSize: subSize, marginTop: 4 }]}>
                ✨ AI Reels · Divine Transforms · Story Mode
              </Text>
              <Text style={[s.tagline, { fontSize: subSize, color: '#A78BFA', marginTop: 2 }]}>
                Cinematic videos in one tap
              </Text>
            </>
          )}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center' },
  wordmark: {
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  tagline: {
    color: '#CBD5E1',
    fontWeight: '600',
    letterSpacing: 0.3,
    textAlign: 'center',
  },
});
