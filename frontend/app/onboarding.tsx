/* Onboarding — Premium Neon Glass UI
 * 3-page swipe carousel introducing MagiCAi Studio.
 * Shown only once (gated by AsyncStorage 'magicai.onboarded').
 */
import React, { useRef, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Dimensions, NativeScrollEvent,
  NativeSyntheticEvent, StatusBar, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AuroraBackground from '../src/AuroraBackground';
import { useTheme } from '../src/ThemeContext';
import { NeonButton, GhostButton, GlassCard, GlassPill } from '../src/ui/Glass';
import { colors, spacing, typography } from '../src/ui/theme';

const ONBOARD_KEY = 'magicai.onboarded';
const { width: W, height: H } = Dimensions.get('window');

type Slide = {
  badge: string;
  emoji: string;
  title: string;
  highlight: string;
  desc: string;
  features: { icon: keyof typeof Ionicons.glyphMap; label: string; color: string }[];
  glow: 'purple' | 'orange' | 'cyan';
};

const SLIDES: Slide[] = [
  {
    badge: '✨ AI POWERED',
    emoji: '🎬',
    title: 'Create cinematic',
    highlight: 'reels in seconds',
    desc: 'Type one idea — our Smart Plan engine writes the script, fetches scene-matched footage, picks the perfect voice and music. All you do is press play.',
    features: [
      { icon: 'sparkles', label: 'Smart Plan engine', color: colors.auroraPurple },
      { icon: 'film',     label: 'Per-scene Pixabay clips', color: colors.auroraCyan },
      { icon: 'mic',      label: 'Emotion-tuned voice', color: colors.auroraOrange },
    ],
    glow: 'purple',
  },
  {
    badge: '🎨 STUDIO TIER',
    emoji: '🪄',
    title: 'Avatar Studio &',
    highlight: 'lip-sync magic',
    desc: 'Turn any photo into a talking AI character. Face-swap, lip-sync, and dialogue generation — all in one premium creator pipeline.',
    features: [
      { icon: 'happy',    label: 'Cartoon avatars', color: colors.auroraPurple },
      { icon: 'mic-circle', label: 'Lip-sync video', color: colors.auroraPink },
      { icon: 'swap-horizontal', label: 'Face swap', color: colors.auroraCyan },
    ],
    glow: 'orange',
  },
  {
    badge: '🚀 4 PLAN TIERS',
    emoji: '💎',
    title: 'Free to start',
    highlight: 'Pro when ready',
    desc: 'Start free — 30 credits monthly. Upgrade to Starter, Creator, or Pro for higher quality, faster renders, and exclusive premium templates.',
    features: [
      { icon: 'flash',    label: 'Free · 30 credits', color: colors.success },
      { icon: 'rocket',   label: 'Starter · 100 cr/mo', color: colors.info },
      { icon: 'sparkles', label: 'Creator · 380 cr/mo', color: colors.auroraPurple },
      { icon: 'diamond',  label: 'Pro · 500 cr/mo', color: colors.warning },
    ],
    glow: 'cyan',
  },
];

export default function Onboarding() {
  const router = useRouter();
  const { isDark } = useTheme();
  const titleColor = isDark ? colors.text : '#0F0C29';
  const descColor  = isDark ? colors.textMuted : '#3F3D56';
  const scrollRef = useRef<ScrollView>(null);
  const [idx, setIdx] = useState(0);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const x = e.nativeEvent.contentOffset.x;
    const i = Math.round(x / W);
    if (i !== idx) setIdx(i);
  };

  const finish = async () => {
    try { await AsyncStorage.setItem(ONBOARD_KEY, '1'); } catch {}
    router.replace('/login');
  };

  const next = () => {
    if (idx < SLIDES.length - 1) {
      scrollRef.current?.scrollTo({ x: (idx + 1) * W, animated: true });
    } else {
      finish();
    }
  };

  const skip = async () => { await finish(); };

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" />
      <AuroraBackground absolute />

      <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
        {/* Skip button */}
        <View style={s.topBar}>
          <View style={{ flex: 1 }} />
          <GhostButton label="Skip" onPress={skip} color={colors.textDim} />
        </View>

        {/* Carousel */}
        <ScrollView
          ref={scrollRef}
          horizontal pagingEnabled showsHorizontalScrollIndicator={false}
          onScroll={onScroll} scrollEventThrottle={16}
          style={{ flex: 1 }}
        >
          {SLIDES.map((slide, i) => (
            <SlideView key={i} slide={slide} titleColor={titleColor} descColor={descColor} />
          ))}
        </ScrollView>

        {/* Pagination dots */}
        <View style={s.dotsRow}>
          {SLIDES.map((_, i) => (
            <View
              key={i}
              style={[s.dot, i === idx && s.dotActive]}
            />
          ))}
        </View>

        {/* CTA */}
        <View style={s.ctaWrap}>
          <NeonButton
            label={idx === SLIDES.length - 1 ? 'Get started — it\'s free' : 'Next'}
            iconRight={idx === SLIDES.length - 1 ? 'arrow-forward' : 'chevron-forward'}
            onPress={next}
            size="lg"
          />
          {idx === SLIDES.length - 1 && (
            <Text style={s.ctaHint}>No credit card · 300 free credits to try everything</Text>
          )}
        </View>
      </SafeAreaView>
    </View>
  );
}

function SlideView({ slide, titleColor, descColor }: { slide: Slide; titleColor: string; descColor: string }) {
  return (
    <View style={s.slide}>
      {/* Hero glow circle */}
      <View style={s.heroWrap}>
        <LinearGradient
          colors={
            slide.glow === 'purple' ? ['#FF6B08', '#FF007F', '#AE29FF']
            : slide.glow === 'orange' ? ['#FF6B08', '#FBBF24', '#FF007F']
            : ['#00C6FF', '#AE29FF', '#FF007F']
          }
          start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={s.heroGlow}
        />
        <View style={s.heroInner}>
          <Text style={s.heroEmoji}>{slide.emoji}</Text>
        </View>
      </View>

      {/* Badge pill */}
      <GlassPill style={{ alignSelf: 'center', marginTop: spacing.lg }}>
        <Text style={[s.badgeTxt, { color: titleColor }]}>{slide.badge}</Text>
      </GlassPill>

      {/* Headlines */}
      <Text style={[s.title, { color: titleColor }]}>{slide.title}</Text>
      <Text style={s.titleHighlight}>{slide.highlight}</Text>

      {/* Description */}
      <Text style={[s.desc, { color: descColor }]}>{slide.desc}</Text>

      {/* Feature glass card */}
      <GlassCard style={s.featureCard} radius={20} borderHi glow={slide.glow}>
        {slide.features.map((f, i) => (
          <View key={i} style={[s.featureRow, i > 0 && s.featureRowDivider]}>
            <View style={[s.featureIcon, { backgroundColor: `${f.color}22`, borderColor: `${f.color}55` }]}>
              <Ionicons name={f.icon} size={16} color={f.color} />
            </View>
            <Text style={[s.featureLabel, { color: titleColor }]}>{f.label}</Text>
            <Ionicons name="checkmark-circle" size={16} color={colors.success} />
          </View>
        ))}
      </GlassCard>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bgDeep },

  topBar: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: spacing.md, paddingTop: spacing.sm,
  },

  slide: {
    width: W,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'flex-start',
    paddingTop: spacing.lg,
  },

  // Hero
  heroWrap: {
    width: 160, height: 160, alignItems: 'center', justifyContent: 'center',
    marginTop: 0,
  },
  heroGlow: {
    position: 'absolute', width: 160, height: 160, borderRadius: 80, opacity: 0.85,
  },
  heroInner: {
    width: 110, height: 110, borderRadius: 55,
    backgroundColor: 'rgba(10,2,18,0.7)',
    borderWidth: 1, borderColor: colors.glassBorderHi,
    alignItems: 'center', justifyContent: 'center',
  },
  heroEmoji: { fontSize: 56 },

  badgeTxt: { color: colors.text, fontSize: 11, fontWeight: '900', letterSpacing: 1 },

  // Headlines
  title: {
    color: colors.text, fontSize: 30, fontWeight: '800',
    textAlign: 'center', marginTop: spacing.md, letterSpacing: -0.5,
  },
  titleHighlight: {
    color: colors.auroraOrange, fontSize: 30, fontWeight: '800',
    textAlign: 'center', letterSpacing: -0.5,
  },
  desc: {
    color: colors.textMuted, fontSize: 15, lineHeight: 22,
    textAlign: 'center',
    marginTop: spacing.md, marginHorizontal: spacing.sm,
  },

  // Feature card
  featureCard: { width: '100%', marginTop: spacing.lg, paddingVertical: spacing.sm },
  featureRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 10,
  },
  featureRowDivider: { borderTopWidth: 1, borderColor: 'rgba(255,255,255,0.06)' },
  featureIcon: {
    width: 32, height: 32, borderRadius: 16,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
  },
  featureLabel: { flex: 1, color: colors.text, fontSize: 14, fontWeight: '600' },

  // Dots
  dotsRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 7, marginVertical: spacing.md,
  },
  dot: {
    width: 6, height: 6, borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.25)',
  },
  dotActive: {
    width: 22, backgroundColor: colors.auroraOrange,
  },

  // CTA
  ctaWrap: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md },
  ctaHint: {
    color: colors.textDim, fontSize: 12, textAlign: 'center', marginTop: 8,
  },
});
