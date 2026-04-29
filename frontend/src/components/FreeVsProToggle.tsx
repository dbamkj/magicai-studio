/**
 * FreeVsProToggle — reusable side-by-side preview that demonstrates the visual
 * difference between Free (watermarked, 480p look) and Pro (clean, HD look).
 *
 * Strategy: pure UI/CSS — no extra AI calls. When user is NOT Pro and toggles
 * to Pro mode, we show the SAME image with a "PRO PREVIEW" overlay covering
 * the watermark corner + a slight saturation/brightness/contrast boost to
 * simulate the HD treatment, and we lock the download (CTA → /buy).
 *
 * Used by: cartoon-avatar.tsx (and later: avatar, faceswap, headswap, multiswap, etc.)
 */
import React, { useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, Pressable, Image, TouchableOpacity, Platform, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Video, ResizeMode } from 'expo-av';
import Animated, {
  useSharedValue, useAnimatedStyle, withTiming, withRepeat, withSequence,
} from 'react-native-reanimated';
export type FreeVsProToggleProps = {
  /** The media URL returned by the backend (already watermarked for free users) */
  mediaUrl: string;
  /** Currently only 'image' is supported. Reserved for future video preview. */
  mediaType?: 'image' | 'video';
  /** Whether the logged-in user already has Pro tier (starter/creator/pro). */
  userIsPro: boolean;
  /** Aspect ratio of the preview (default 9:16). */
  aspectRatio?: number;
  /** Tagline shown under the Free chip (default "Watermark · 480p · 10s"). */
  freeTagline?: string;
  /** Tagline shown under the Pro chip (default "Clean · HD · Faster"). */
  proTagline?: string;
  /** Callback when user taps Upgrade (e.g. router.push('/buy?tab=tier')). */
  onUpgrade: () => void;
  /** Callback when user taps Download (only fires if allowed). */
  onDownload?: () => void;
  /** Optional small label shown over the media (e.g. style + emotion meta). */
  metaLabel?: string;
};

type Mode = 'free' | 'pro';

export default function FreeVsProToggle({
  mediaUrl,
  mediaType = 'image',
  userIsPro,
  aspectRatio = 9 / 16,
  freeTagline = 'Watermark · 480p · 10s render',
  proTagline = 'Clean · HD · Faster render',
  onUpgrade,
  onDownload,
  metaLabel,
}: FreeVsProToggleProps) {
  const [mode, setMode] = useState<Mode>('free');

  // The "PRO" CTA download is locked unless user actually owns Pro.
  const downloadLocked = mode === 'pro' && !userIsPro;

  // Toggle pill indicator (slides between Free at left:3 and Pro at left:110)
  const TRACK_HALF = 107;

  // Subtle sparkle pulse when Pro is active
  const sparkle = useSharedValue(0.6);
  React.useEffect(() => {
    if (mode === 'pro') {
      sparkle.value = withRepeat(
        withSequence(withTiming(1, { duration: 700 }), withTiming(0.6, { duration: 700 })),
        -1, true
      );
    } else {
      sparkle.value = withTiming(0.6, { duration: 220 });
    }
  }, [mode, sparkle]);
  const sparkleStyle = useAnimatedStyle(() => ({ opacity: sparkle.value }));

  const switchMode = (m: Mode) => {
    setMode(m);
  };

  // "HD" filter for Pro preview — purely cosmetic UI trickery
  const proImageStyle = useMemo(() => {
    if (mode !== 'pro') return null;
    // RN doesn't support CSS filter natively on iOS/Android, but we can fake
    // the effect with overlaid gradients. On web, we can use the filter prop.
    return Platform.OS === 'web'
      // @ts-expect-error - web-only CSS prop
      ? { filter: 'saturate(1.32) contrast(1.12) brightness(1.06)' }
      : { transform: [{ scale: 1.04 }] };  // tiny zoom to give native a "richer crop" feel
  }, [mode]);

  const handleDownload = () => {
    if (downloadLocked) {
      Alert.alert(
        'Pro feature',
        'Clean HD download is a Pro perk. Upgrade to remove the watermark and unlock HD exports.',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Upgrade to Pro', onPress: onUpgrade },
        ],
      );
      return;
    }
    onDownload?.();
  };

  return (
    <View style={s.wrap}>
      {/* ---------- Animated segmented toggle ---------- */}
      <View style={s.toggleRow}>
        <View style={s.toggleTrack}>
          {/* Two static indicators (left: 3 for Free, left: 110 for Pro) — toggle via opacity */}
          <View style={[s.toggleIndicator, { left: 3, opacity: mode === 'free' ? 1 : 0 }]}>
            <LinearGradient
              colors={['#475569', '#334155']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={StyleSheet.absoluteFill}
            />
          </View>
          <View style={[s.toggleIndicator, { left: 3 + TRACK_HALF, opacity: mode === 'pro' ? 1 : 0 }]}>
            <LinearGradient
              colors={['#FBBF24', '#F59E0B']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={StyleSheet.absoluteFill}
            />
          </View>
          <Pressable onPress={() => switchMode('free')} style={s.toggleBtn} hitSlop={6}>
            <Text style={[s.toggleTxt, mode === 'free' && s.toggleTxtActive]}>Free</Text>
          </Pressable>
          <Pressable onPress={() => switchMode('pro')} style={s.toggleBtn} hitSlop={6}>
            <Ionicons
              name="diamond"
              size={11}
              color={mode === 'pro' ? '#0B1120' : '#94A3B8'}
              style={{ marginRight: 4 }}
            />
            <Text style={[s.toggleTxt, mode === 'pro' && s.toggleTxtActivePro]}>Pro</Text>
          </Pressable>
        </View>
      </View>

      {/* ---------- Tagline under toggle ---------- */}
      <Text style={s.tagline}>
        {mode === 'free' ? freeTagline : proTagline}
      </Text>

      {/* ---------- Media preview ---------- */}
      <View style={[s.mediaWrap, { aspectRatio }]}>
        {/* The actual image (or video placeholder) */}
        {mediaType === 'image' && (
          <Image
            source={{ uri: mediaUrl }}
            resizeMode="contain"
            style={[s.media, proImageStyle as any]}
          />
        )}
        {mediaType === 'video' && (
          <Video
            source={{ uri: mediaUrl }}
            style={[s.media, proImageStyle as any]}
            resizeMode={ResizeMode.CONTAIN}
            useNativeControls
            shouldPlay={false}
            isLooping={false}
          />
        )}

        {/* PRO mode visual treatment overlays (purely cosmetic) */}
        {mode === 'pro' && (
          <>
            {/* Subtle vignette/saturation overlay for native (since CSS filter is web-only) */}
            {Platform.OS !== 'web' && (
              <LinearGradient
                colors={['rgba(255,200,80,0.06)', 'rgba(255,255,255,0)', 'rgba(80,150,255,0.06)']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={StyleSheet.absoluteFill}
                pointerEvents="none"
              />
            )}

            {/* WIDE gradient strip across the bottom — fully hides the
                "MagiCAi" watermark which spans ~25% of the bottom-right area
                in the rendered _wm.png. The strip fades from transparent on
                the left to opaque dark with the gold "HD" badge on the right. */}
            <View style={s.proCoverStrip} pointerEvents="none">
              <LinearGradient
                colors={['rgba(0,0,0,0)', 'rgba(0,0,0,0.55)', 'rgba(0,0,0,0.92)']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                style={StyleSheet.absoluteFill}
              />
              <View style={s.proCoverBadge}>
                <Ionicons name="sparkles" size={11} color="#0B1120" />
                <Text style={s.proCoverTxt}>HD</Text>
              </View>
            </View>

            {/* Animated sparkle ring */}
            <Animated.View style={[s.sparkleRing, sparkleStyle]} pointerEvents="none" />

            {/* Top-right "PRO PREVIEW" pill if user is not actually pro */}
            {!userIsPro && (
              <View style={s.proPreviewPill}>
                <Ionicons name="lock-closed" size={9} color="#0B1120" />
                <Text style={s.proPreviewTxt}>PRO PREVIEW</Text>
              </View>
            )}
          </>
        )}

        {/* FREE mode: small "AI" pill top-left + visible "MagiCAi" watermark
            in the bottom-right so paid testers and free users alike see the
            "Watermarked" preview faithfully (in case the backend wm hasn't
            been baked in yet). */}
        {mode === 'free' && (
          <>
            <View style={s.aiPill}>
              <Text style={s.aiPillTxt}>AI</Text>
            </View>
            <View style={s.freeWmBadge} pointerEvents="none">
              <Ionicons name="sparkles" size={10} color="#FBBF24" />
              <Text style={s.freeWmTxt}>MagiCAi</Text>
            </View>
          </>
        )}

        {/* Optional meta label at bottom */}
        {!!metaLabel && (
          <View style={s.metaBar} pointerEvents="none">
            <Text style={s.metaTxt} numberOfLines={1}>{metaLabel}</Text>
          </View>
        )}
      </View>

      {/* ---------- Feature comparison row ---------- */}
      <View style={s.compareRow}>
        <FeatureCol
          active={mode === 'free'}
          tone="free"
          title="Free"
          items={['480p resolution', 'MagiCAi watermark', '~10s render', 'Standard quality']}
        />
        <FeatureCol
          active={mode === 'pro'}
          tone="pro"
          title="Pro"
          items={['1080p HD', 'No watermark', '~5s render (2× faster)', 'Boosted colours & sharpness']}
        />
      </View>

      {/* ---------- Download / Upgrade CTA ---------- */}
      {downloadLocked ? (
        <TouchableOpacity activeOpacity={0.85} onPress={onUpgrade} style={s.upgradeCta}>
          <LinearGradient
            colors={['#FBBF24', '#F59E0B']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
            style={s.upgradeGrad}
          >
            <Ionicons name="diamond" size={14} color="#0B1120" />
            <Text style={s.upgradeTxt}>Upgrade to Pro · Unlock HD</Text>
          </LinearGradient>
        </TouchableOpacity>
      ) : (
        !!onDownload && (
          <TouchableOpacity activeOpacity={0.85} onPress={handleDownload} style={s.dlCta}>
            <Ionicons name="download-outline" size={15} color="#fff" />
            <Text style={s.dlTxt}>
              Download {mode === 'pro' ? 'HD (Clean)' : 'Free (Watermarked)'}
            </Text>
          </TouchableOpacity>
        )
      )}
    </View>
  );
}

/* ---------- Feature column ---------- */
function FeatureCol({
  active, tone, title, items,
}: { active: boolean; tone: 'free' | 'pro'; title: string; items: string[]; }) {
  const accent = tone === 'pro' ? '#FBBF24' : '#94A3B8';
  return (
    <View style={[
      s.col,
      active && (tone === 'pro' ? s.colActivePro : s.colActiveFree),
    ]}>
      <View style={s.colHeader}>
        {tone === 'pro' && <Ionicons name="diamond" size={11} color={accent} />}
        <Text style={[s.colTitle, { color: accent }]}>{title}</Text>
      </View>
      {items.map((it, i) => (
        <View key={i} style={s.featureRow}>
          <Ionicons
            name={tone === 'pro' ? 'checkmark-circle' : 'ellipse-outline'}
            size={11}
            color={tone === 'pro' ? '#FBBF24' : '#64748B'}
          />
          <Text style={[s.featureTxt, tone === 'pro' && { color: '#E2E8F0' }]} numberOfLines={2}>
            {it}
          </Text>
        </View>
      ))}
    </View>
  );
}

/* ============ styles ============ */
const s = StyleSheet.create({
  wrap: { width: '100%' },

  // Toggle
  toggleRow: { alignItems: 'center', marginBottom: 6 },
  toggleTrack: {
    flexDirection: 'row', backgroundColor: '#0F172A', borderRadius: 999,
    padding: 3, borderWidth: 1, borderColor: '#1E293B',
    width: 220, height: 38, position: 'relative',
  },
  toggleIndicator: {
    position: 'absolute', top: 3, width: 107, height: 30,
    borderRadius: 999, overflow: 'hidden',
  },
  toggleBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    zIndex: 2,
  },
  toggleTxt: { color: '#94A3B8', fontWeight: '800', fontSize: 12, letterSpacing: 0.3 },
  toggleTxtActive: { color: '#fff' },
  toggleTxtActivePro: { color: '#0B1120' },

  tagline: {
    color: '#94A3B8', fontSize: 11, textAlign: 'center', marginTop: 4,
    marginBottom: 10, fontWeight: '600',
  },

  // Media
  mediaWrap: {
    width: '100%', backgroundColor: '#000', borderRadius: 16, overflow: 'hidden',
    alignItems: 'center', justifyContent: 'center', position: 'relative',
  },
  media: { width: '100%', height: '100%' },

  proCoverStrip: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    height: 56, flexDirection: 'row',
    alignItems: 'flex-end', justifyContent: 'flex-end',
    paddingHorizontal: 10, paddingBottom: 10,
  },
  proCoverBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8,
    backgroundColor: '#FBBF24',
  },
  proCoverTxt: { color: '#0B1120', fontSize: 11, fontWeight: '900', letterSpacing: 0.6 },

  sparkleRing: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    borderRadius: 16, borderWidth: 2, borderColor: 'rgba(251,191,36,0.55)',
  },

  proPreviewPill: {
    position: 'absolute', top: 8, right: 8,
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6,
    backgroundColor: 'rgba(251,191,36,0.95)',
  },
  proPreviewTxt: { color: '#0B1120', fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },

  aiPill: {
    position: 'absolute', top: 8, left: 8,
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5,
    backgroundColor: 'rgba(0,0,0,0.55)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.18)',
  },
  aiPillTxt: { color: '#fff', fontSize: 9, fontWeight: '900', letterSpacing: 0.6 },

  /* UI watermark for FREE mode — visible regardless of whether the
     backend baked one in (defensive against paid testers / failures). */
  freeWmBadge: {
    position: 'absolute', bottom: 12, right: 12,
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6,
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.5)',
  },
  freeWmTxt: { color: '#FBBF24', fontSize: 10, fontWeight: '900', letterSpacing: 0.4 },

  metaBar: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    paddingVertical: 6, paddingHorizontal: 10,
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  metaTxt: { color: '#fff', fontSize: 11, fontWeight: '700' },

  // Compare
  compareRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  col: {
    flex: 1, padding: 10, borderRadius: 12,
    backgroundColor: '#0F172A', borderWidth: 1, borderColor: '#1E293B',
  },
  colActiveFree: { borderColor: '#64748B', backgroundColor: 'rgba(100,116,139,0.1)' },
  colActivePro: { borderColor: '#FBBF24', backgroundColor: 'rgba(251,191,36,0.08)' },
  colHeader: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 },
  colTitle: { fontSize: 12, fontWeight: '900', letterSpacing: 0.4 },
  featureRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 5, marginTop: 4 },
  featureTxt: { flex: 1, color: '#94A3B8', fontSize: 10, lineHeight: 13, fontWeight: '600' },

  // CTAs
  upgradeCta: { marginTop: 14, borderRadius: 12, overflow: 'hidden' },
  upgradeGrad: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 13,
  },
  upgradeTxt: { color: '#0B1120', fontWeight: '900', fontSize: 13, letterSpacing: 0.3 },

  dlCta: {
    marginTop: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 13, borderRadius: 12, backgroundColor: '#1E293B',
    borderWidth: 1, borderColor: '#334155',
  },
  dlTxt: { color: '#fff', fontWeight: '800', fontSize: 13 },
});
