import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  StatusBar, ActivityIndicator, Image, Modal, Share, Dimensions,
  BackHandler, Alert, Pressable, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { useAuth } from '../src/AuthContext';
import MagicAiLogo from '../src/MagicAiLogo';
import AuroraBackground from '../src/AuroraBackground';
import BottomTabBar from '../src/components/BottomTabBar';
import axios from 'axios';
import { LinearGradient } from 'expo-linear-gradient';
import { Video, ResizeMode } from 'expo-av';
import { brandGradient } from '../src/theme';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const { width: SCREEN_W } = Dimensions.get('window');

/* ==================== HERO SLIDES ==================== */
const HOME_HERO_SLIDES = [
  {
    id: 'magic',
    title: 'Turn Ideas Into',
    titleAccent: 'Magic',
    subtitle: 'AI Videos, Avatars, Voice & more — in seconds!',
    cta: 'Create Reel',
    image: 'https://images.pexels.com/photos/32601772/pexels-photo-32601772.jpeg?w=600&h=600&fit=crop',
    fallbackImage: 'https://images.pexels.com/photos/9375018/pexels-photo-9375018.jpeg?w=600&h=600&fit=crop',
    route: '/create-wizard?mode=video',
    gradient: ['#FF4D8D', '#FF9A3C'] as const,
  },
  {
    id: 'avatar',
    title: 'Your Face,',
    titleAccent: 'Animated',
    subtitle: 'Cartoonize portraits in 12+ Pixar / Anime styles',
    cta: 'Make Avatar',
    image: 'https://images.unsplash.com/photo-1716504628105-bd76d91e85f2?w=600&h=600&fit=crop&q=85',
    fallbackImage: 'https://images.unsplash.com/photo-1622258567999-24d00a930ee8?w=600&h=600&fit=crop&q=85',
    route: '/cartoon-avatar',
    gradient: ['#7B5CFF', '#FF4D8D'] as const,
  },
  {
    id: 'divine',
    title: 'Divine',
    titleAccent: 'Transform',
    subtitle: 'Photo → Cinematic divine reel in one tap',
    cta: 'Try Now',
    image: 'https://images.pexels.com/photos/18364244/pexels-photo-18364244.jpeg?w=600&h=600&fit=crop',
    fallbackImage: 'https://images.pexels.com/photos/31104752/pexels-photo-31104752.jpeg?w=600&h=600&fit=crop',
    route: '/divine-transform',
    gradient: ['#FBBF24', '#FF4D8D'] as const,
  },
];

/* ==================== QUICK ACCESS TILES ==================== */
const QUICK_ACCESS = [
  {
    id: 'templates',
    title: 'Templates',
    subtitle: '1000+ Reels',
    icon: 'film' as const,
    gradient: ['#A78BFA', '#EC4899'] as const,        // purple → pink
    glowColor: '#A78BFA',
    route: '/marketplace',
    public: true,
  },
  {
    id: 'avatar',
    title: 'Avatar Studio',
    subtitle: 'Cartoon & Realistic',
    icon: 'happy' as const,
    gradient: ['#EC4899', '#7C3AED'] as const,        // pink → violet
    glowColor: '#EC4899',
    route: '/cartoon-avatar',
    public: false,
  },
  {
    id: 'ai-prompts',
    title: 'AI Prompts',
    subtitle: 'Let AI write your idea',
    icon: 'color-wand' as const,
    gradient: ['#7B5CFF', '#00C2FF'] as const,        // violet → cyan
    glowColor: '#7B5CFF',
    route: '/ai-prompts',
    public: true,
    badge: 'NEW',
  },
  {
    id: 'tools',
    title: 'AI Tools',
    subtitle: 'Voice, Swap, Enhance',
    icon: 'sparkles' as const,
    gradient: ['#F97316', '#FBBF24'] as const,        // orange → yellow
    glowColor: '#F97316',
    route: '/explore-tools',
    public: true,
  },
];

/* ==================== TRENDING TEMPLATES ==================== */
const TRENDING = [
  {
    id: 'krishna',
    title: 'Krishna Blessing',
    badge: 'NEW',
    badgeColor: '#A78BFA',
    uses: '12.5K uses',
    image: 'https://images.pexels.com/photos/32601772/pexels-photo-32601772.jpeg?w=400&h=500&fit=crop',
    route: '/templates?id=krishna_bhajan',
  },
  {
    id: 'motivation',
    title: 'Motivation Boost',
    badge: 'HOT',
    badgeColor: '#EC4899',
    uses: '8.7K uses',
    image: 'https://images.pexels.com/photos/3617500/pexels-photo-3617500.jpeg?w=400&h=500&fit=crop',
    route: '/templates?id=shiv_tandav',
  },
  {
    id: 'love',
    title: 'Love Vibes',
    badge: 'NEW',
    badgeColor: '#A78BFA',
    uses: '9.3K uses',
    image: 'https://images.pexels.com/photos/30276936/pexels-photo-30276936.jpeg?w=400&h=500&fit=crop',
    route: '/templates?id=wedding_lehenga',
  },
  {
    id: 'diya',
    title: 'Festival Diya',
    badge: 'TRENDING',
    badgeColor: '#FBBF24',
    uses: '7.1K uses',
    image: 'https://images.pexels.com/photos/31104752/pexels-photo-31104752.jpeg?w=400&h=500&fit=crop',
    route: '/templates?id=diwali_scene',
  },
];

/* ==================== Mask helpers ==================== */
const maskName = (name: string) => {
  if (!name) return '***';
  const parts = name.split(' ');
  return parts.map(part => {
    if (part.length <= 1) return '*';
    if (part.length <= 3) return part[0] + '*'.repeat(part.length - 1);
    return part[0] + '*'.repeat(part.length - 2) + part[part.length - 1];
  }).join(' ');
};

const maskEmail = (email: string) => {
  if (!email) return '***@***.***';
  const [local, domain] = email.split('@');
  const ml = local.length <= 2
    ? local[0] + '*'
    : local[0] + '*'.repeat(local.length - 2) + local[local.length - 1];
  const dp = domain.split('.');
  const md = dp[0].length <= 2
    ? dp[0][0] + '*'
    : dp[0][0] + '*'.repeat(dp[0].length - 2) + dp[0][dp[0].length - 1];
  return ml + '@' + md + '.' + dp.slice(1).join('.');
};

interface UsageData {
  lipsync: { total: number; completed: number };
  faceswap: { total: number; completed: number };
  headswap: { total: number; completed: number };
  bodyswap: { total: number; completed: number };
  total_projects: number;
  total_completed: number;
}

/* Routes that are always browsable (no auth required) */
const PUBLIC_ROUTES = new Set<string>([
  '/explore-tools', '/templates', '/marketplace', '/subscription', '/legal',
]);

/* Tier pretty-name mapping (handles the missing "creator" case from Phase 5) */
const TIER_LABEL: Record<string, { name: string; emoji: string; color: string }> = {
  guest:   { name: 'Guest',         emoji: '👤', color: '#64748B' },
  free:    { name: 'Free Plan',    emoji: '🆓', color: '#94A3B8' },
  starter: { name: 'Starter Pack', emoji: '⭐',  color: '#60A5FA' },
  creator: { name: 'Creator Pro',  emoji: '🎨', color: '#EC4899' },
  pro:     { name: 'Pro Studio',   emoji: '🚀', color: '#FBBF24' },
};

/* ==================== Quick-Action Sheet (Reel/Avatar/Voice) ==================== */
function QuickActionSheet({
  visible, onClose, onPick,
}: { visible: boolean; onClose: () => void; onPick: (route: string) => void }) {
  const actions = [
    { key: 'reel',   icon: 'film',     label: 'Reel',   sub: 'Text → AI Video',          color: '#FF4D8D', route: '/create-wizard?mode=video' },
    { key: 'avatar', icon: 'happy',    label: 'Avatar', sub: 'Cartoonize a portrait',    color: '#7B5CFF', route: '/cartoon-avatar' },
    { key: 'voice',  icon: 'mic',      label: 'Voice',  sub: 'Lip sync · Re-dub · TTS',  color: '#FF9A3C', route: '/lipsync' },
  ];
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={s.qaOverlay} onPress={onClose}>
        <Pressable style={s.qaSheet} onPress={(e) => e.stopPropagation()}>
          <View style={s.dragHandle} />
          <Text style={s.qaTitle}>Create new</Text>
          <Text style={s.qaSub}>Pick where to start the magic ✨</Text>
          <View style={{ gap: 10, marginTop: 14 }}>
            {actions.map(a => (
              <TouchableOpacity
                key={a.key}
                activeOpacity={0.85}
                onPress={() => { onClose(); onPick(a.route); }}
                style={s.qaAction}
              >
                <View style={[s.qaIcon, { backgroundColor: a.color + '22', borderColor: a.color + '55' }]}>
                  <Ionicons name={a.icon as any} size={22} color={a.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.qaActionTitle}>{a.label}</Text>
                  <Text style={s.qaActionSub}>{a.sub}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color="#475569" />
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity onPress={onClose} style={s.qaCancel} activeOpacity={0.7}>
            <Text style={s.qaCancelTxt}>Cancel</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

/* ==================== Hero Carousel ==================== */
function HeroCarousel({ onPick }: { onPick: (route: string) => void }) {
  const scrollRef = React.useRef<ScrollView>(null);
  const [idx, setIdx] = useState(0);
  const idxRef = React.useRef(0);
  const cardW = SCREEN_W - 32; // 16px padding each side

  React.useEffect(() => {
    const t = setInterval(() => {
      const next = (idxRef.current + 1) % HOME_HERO_SLIDES.length;
      idxRef.current = next;
      setIdx(next);
      scrollRef.current?.scrollTo({ x: next * cardW, animated: true });
    }, 5000);
    return () => clearInterval(t);
  }, [cardW]);

  return (
    <View style={{ marginBottom: 18 }}>
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        snapToInterval={cardW}
        decelerationRate="fast"
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 16 }}
        onMomentumScrollEnd={(e) => {
          const i = Math.round(e.nativeEvent.contentOffset.x / cardW);
          idxRef.current = i; setIdx(i);
        }}
      >
        {HOME_HERO_SLIDES.map((b) => (
          <View key={b.id} style={{ width: cardW }}>
            <View style={s.heroCard}>
              {/* Right-side image */}
              <Image
                source={{ uri: b.image }}
                style={s.heroImage}
                resizeMode="cover"
                onError={() => { /* fallback handled below if needed */ }}
              />
              {/* Vignette over image */}
              <LinearGradient
                colors={['rgba(15,12,41,0.95)', 'rgba(15,12,41,0.55)', 'rgba(15,12,41,0.0)']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                style={s.heroVignette}
              />
              {/* Content */}
              <View style={s.heroContent}>
                <Text style={s.heroTitle}>{b.title}</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' }}>
                  <Text style={[s.heroTitle, s.heroAccent]}>{b.titleAccent}</Text>
                  <Text style={s.heroSparkle}> ✨</Text>
                </View>
                <Text style={s.heroSubtitle}>{b.subtitle}</Text>

                <TouchableOpacity
                  activeOpacity={0.88}
                  onPress={() => onPick(b.route)}
                  style={s.heroCtaWrap}
                >
                  <LinearGradient
                    colors={[b.gradient[0], b.gradient[1]]}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                    style={s.heroCta}
                  >
                    <Ionicons name="add" size={16} color="#fff" />
                    <Text style={s.heroCtaText}>{b.cta}</Text>
                    <View style={s.heroCtaArrow}>
                      <Ionicons name="chevron-forward" size={14} color={b.gradient[0]} />
                    </View>
                  </LinearGradient>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        ))}
      </ScrollView>

      {/* Carousel dots */}
      <View style={s.dotsRow}>
        {HOME_HERO_SLIDES.map((_, i) => (
          <View
            key={i}
            style={[s.dot, i === idx && s.dotActive]}
          />
        ))}
      </View>
    </View>
  );
}

/* ==================== Onboarding Carousel ====================
 * Compact, embedded version of the full-screen `/onboarding` screen.
 * Shows a 3-slide auto-rotating "feature highlight" tour beneath Quick
 * Access on the Home screen so returning users can discover headline
 * capabilities (Cinematic AI Reels / Avatar Studio / 1-Tap Export).
 *
 * Behaviour:
 *  • Auto-rotates every 5 s.
 *  • Manual horizontal swipe is supported.
 *  • Each slide deeplinks to the relevant route on tap.
 *  • Last slide flips the CTA to "Get started" → /create-wizard.
 */
const ONBOARD_SLIDES = [
  {
    id: 'reels',
    badge: '✨ AI VIDEO',
    title: 'Cinematic Reels',
    accent: 'in seconds',
    desc: 'Type one idea — Smart Plan engine writes the script, picks scene-matched footage, and renders a 9:16 reel.',
    icon: 'film' as const,
    iconBg: '#7B5CFF',
    glow: ['#FF6B08', '#FF007F', '#AE29FF'] as const,
    chip: 'CINEMATIC SCENES',
    cta: 'Try Now',
    route: '/create-wizard?mode=video',
  },
  {
    id: 'voice',
    badge: '🎙 AI VOICE',
    title: 'Voice that',
    accent: 'feels human',
    desc: 'Sarvam AI Bulbul-v2 + emotion presets. Hindi, Hinglish, English & Indic voices ready for your reel.',
    icon: 'mic' as const,
    iconBg: '#EC4899',
    glow: ['#00C6FF', '#AE29FF', '#FF007F'] as const,
    chip: 'AI VOICE',
    cta: 'Hear Demo',
    route: '/create-wizard?mode=video',
  },
  {
    id: 'export',
    badge: '🚀 ONE-TAP',
    title: 'Export & share',
    accent: 'instantly',
    desc: 'Save MP4 to gallery, share to Reels & Shorts, or copy a watermark-free link with a single tap.',
    icon: 'cloud-download' as const,
    iconBg: '#10B981',
    glow: ['#FBBF24', '#FF6B08', '#FF007F'] as const,
    chip: '1-TAP EXPORT',
    cta: 'Get started',
    route: '/create-wizard',
  },
];

function OnboardingCarousel({ onPick }: { onPick: (route: string) => void }) {
  const scrollRef = React.useRef<ScrollView>(null);
  const [idx, setIdx] = useState(0);
  const idxRef = React.useRef(0);
  const cardW = SCREEN_W - 32;

  React.useEffect(() => {
    const t = setInterval(() => {
      const next = (idxRef.current + 1) % ONBOARD_SLIDES.length;
      idxRef.current = next;
      setIdx(next);
      scrollRef.current?.scrollTo({ x: next * cardW, animated: true });
    }, 5000);
    return () => clearInterval(t);
  }, [cardW]);

  return (
    <View style={{ marginBottom: 18 }}>
      <View style={[s.sectionHead, { paddingHorizontal: 16 }]}>
        <View style={s.sectionTitleRow}>
          <Text style={{ fontSize: 14 }}>🪄</Text>
          <Text style={s.sectionTitle}>Discover MagiCAi</Text>
        </View>
        <View style={s.viewAllRow}>
          <Text style={[s.viewAllTxt, { color: '#94A3B8' }]}>{idx + 1}/{ONBOARD_SLIDES.length}</Text>
        </View>
      </View>

      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        snapToInterval={cardW}
        decelerationRate="fast"
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 16 }}
        onMomentumScrollEnd={(e) => {
          const i = Math.round(e.nativeEvent.contentOffset.x / cardW);
          idxRef.current = i;
          setIdx(i);
        }}
      >
        {ONBOARD_SLIDES.map((b) => (
          <View
            key={b.id}
            style={{ width: cardW }}
          >
            <View style={s.onbCard}>
              {/* Aurora glow background */}
              <LinearGradient
                colors={[b.glow[0] + '55', b.glow[1] + '33', b.glow[2] + '22']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={StyleSheet.absoluteFillObject}
              />
              {/* Frosted glass overlay */}
              <View style={s.onbGlassOverlay} />
              {Platform.OS !== 'web' && (
                <BlurView intensity={20} tint="dark" style={StyleSheet.absoluteFill} />
              )}
              {/* Decorative floating play badges */}
              <View style={[s.onbFloater, s.onbFloaterTL, { backgroundColor: b.glow[2] + '33', borderColor: b.glow[2] + '55' }]}>
                <Ionicons name="play" size={11} color="#fff" />
              </View>
              <View style={[s.onbFloater, s.onbFloaterBL, { backgroundColor: '#00C6FF33', borderColor: '#00C6FF55' }]}>
                <Ionicons name="sparkles" size={11} color="#67E8F9" />
              </View>
              <View style={[s.onbFloater, s.onbFloaterTR, { backgroundColor: b.glow[0] + '44', borderColor: b.glow[0] + '66' }]}>
                <Ionicons name={b.icon} size={12} color="#fff" />
              </View>

              {/* Center hero medallion */}
              <View style={s.onbMedallionWrap} pointerEvents="none">
                <LinearGradient
                  colors={[b.glow[0], b.glow[1], b.glow[2]]}
                  start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                  style={s.onbMedallionGlow}
                />
                <View style={s.onbMedallion}>
                  <Ionicons name={b.icon} size={26} color="#fff" />
                </View>
              </View>

              {/* Content (left) */}
              <View style={s.onbContent}>
                <View style={s.onbBadge}>
                  <Text style={s.onbBadgeTxt}>{b.badge}</Text>
                </View>
                <Text style={s.onbTitle} numberOfLines={1}>{b.title}</Text>
                <Text style={[s.onbTitle, { color: '#FF9A3C' }]} numberOfLines={1}>{b.accent}</Text>
                <Text style={s.onbDesc} numberOfLines={2}>{b.desc}</Text>
              </View>
            </View>
          </View>
        ))}
      </ScrollView>

      {/* Dots */}
      <View style={s.dotsRow}>
        {ONBOARD_SLIDES.map((_, i) => (
          <View key={i} style={[s.dot, i === idx && s.dotActive]} />
        ))}
      </View>
    </View>
  );
}

/* ==================== Quick Access Grid ==================== */
function QuickAccess({ onPick }: { onPick: (route: string, isPublic: boolean) => void }) {
  const router = useRouter();
  return (
    <View style={{ paddingHorizontal: 16, marginBottom: 18 }}>
      <View style={s.sectionHead}>
        <View style={s.sectionTitleRow}>
          <Ionicons name="flash" size={14} color="#FBBF24" />
          <Text style={s.sectionTitle}>Quick Access</Text>
        </View>
      </View>

      <View style={s.qaGrid}>
        {QUICK_ACCESS.map(item => (
          <TouchableOpacity
            key={item.id}
            activeOpacity={0.85}
            onPress={() => onPick(item.route, item.public)}
            style={[s.qaTile, Platform.OS === 'web' ? { boxShadow: `0 8px 22px ${item.glowColor}55` as any } : { shadowColor: item.glowColor, shadowOpacity: 0.45, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } }]}
          >
            <LinearGradient
              colors={item.gradient as any}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={StyleSheet.absoluteFillObject}
            />
            {/* Subtle inner highlight (top-left) for 3D feel */}
            <LinearGradient
              colors={['rgba(255,255,255,0.22)', 'rgba(255,255,255,0)']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={StyleSheet.absoluteFillObject}
            />

            {/* Stylised icon medallion (top) */}
            <View style={s.qaIconMedallion}>
              <Ionicons name={item.icon} size={22} color="#fff" />
            </View>

            {/* Title + sub + arrow */}
            <View style={s.qaTileBody}>
              <Text style={s.qaTileTitle} numberOfLines={1}>{item.title}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 2 }}>
                <Text style={s.qaTileSub} numberOfLines={1}>{item.subtitle}</Text>
                <Ionicons name="chevron-forward" size={14} color="#fff" style={{ opacity: 0.92 }} />
              </View>
            </View>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

/* ==================== Trending Templates ==================== */
function TrendingRow({ onPick }: { onPick: (route: string) => void }) {
  const router = useRouter();
  return (
    <View style={{ marginBottom: 18 }}>
      <View style={[s.sectionHead, { paddingHorizontal: 16 }]}>
        <View style={s.sectionTitleRow}>
          <Text style={{ fontSize: 14 }}>🔥</Text>
          <Text style={s.sectionTitle}>Trending Templates</Text>
        </View>
        <TouchableOpacity onPress={() => router.push('/marketplace' as any)}>
          <View style={s.viewAllRow}>
            <Text style={s.viewAllTxt}>See All</Text>
            <Ionicons name="chevron-forward" size={12} color="#A78BFA" />
          </View>
        </TouchableOpacity>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 16, gap: 10 }}
      >
        {TRENDING.map(t => (
          <TouchableOpacity
            key={t.id}
            activeOpacity={0.88}
            style={s.trendCard}
            onPress={() => onPick(t.route)}
          >
            <Image source={{ uri: t.image }} style={StyleSheet.absoluteFillObject} resizeMode="cover" />
            <LinearGradient
              colors={['rgba(0,0,0,0.0)', 'rgba(0,0,0,0.85)']}
              style={StyleSheet.absoluteFillObject}
            />
            {/* Top-left badge */}
            <View style={[s.trendBadge, { backgroundColor: t.badgeColor + 'EE' }]}>
              <Text style={s.trendBadgeTxt}>{t.badge}</Text>
            </View>
            {/* Center play */}
            <View style={s.trendPlay}>
              <Ionicons name="play" size={16} color="#fff" style={{ marginLeft: 2 }} />
            </View>
            {/* Bottom info */}
            <View style={s.trendInfo}>
              <Text style={s.trendTitle} numberOfLines={1}>{t.title}</Text>
              <Text style={s.trendUses}>{t.uses}</Text>
            </View>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

/* ──────────── Inspiration — 2-col grid of mixed-category templates ────────────
 * Fetches featured marketplace templates from /api/marketplace/templates (no
 * auth required for GET) and picks up to 8 across different categories so the
 * user sees a varied palette: bhajan + viral + motivational + AI tools …
 *
 * On tap: calls /marketplace/templates/{id}/use to fetch the rich wizard
 * payload, persists it to sessionStorage as `mp_template_prefill`, then
 * routes to /create-wizard so the wizard auto-starts from this template.
 * (Mirrors the `useTemplate` flow in marketplace.tsx so behaviour is
 * identical whether the user enters from Home or from Marketplace.)
 */
function InspirationGrid({
  onAuthRequired,
}: {
  onAuthRequired: (route: string) => void;
}) {
  const router = useRouter();
  const { user } = useAuth();
  const [items, setItems] = useState<Array<{
    id: string; title: string; tagline?: string; category?: string; thumbnail?: string;
    plan_tier?: string; wizard_mode?: string; has_motion?: boolean;
  }>>([]);
  const [usingId, setUsingId] = useState<string | null>(null);
  const [previewItem, setPreviewItem] = useState<any | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/marketplace/templates?limit=40`, { timeout: 10000 });
        const all: any[] = r.data?.templates || r.data?.items || [];
        // Pick up to 8 templates across different categories so the grid
        // feels varied (not 8 bhajans). 2-col layout = 4 rows.
        const seen: Record<string, number> = {};
        const picked: any[] = [];
        for (const t of all) {
          const cat = (t.category || 'misc').toLowerCase();
          if ((seen[cat] || 0) >= 2) continue; // max 2 per category
          seen[cat] = (seen[cat] || 0) + 1;
          picked.push(t);
          if (picked.length >= 8) break;
        }
        if (alive) setItems(picked);
      } catch (_e) {
        // silent — the section just won't render
      }
    })();
    return () => { alive = false; };
  }, []);

  const handlePick = useCallback(async (t: any) => {
    if (usingId) return;
    // Guests must sign in before generating
    if (!user) {
      onAuthRequired('/create-wizard');
      return;
    }
    setUsingId(t.id);
    try {
      // Get the rich wizard payload for this template
      const r = await axios.post(
        `${BACKEND_URL}/api/marketplace/templates/${t.id}/use`,
        {},
        { timeout: 12000 },
      );
      const payload = r.data?.wizard_payload || {};
      // Persist for the wizard to pick up on mount
      try {
        if (typeof window !== 'undefined' && (window as any).sessionStorage) {
          (window as any).sessionStorage.setItem(
            'mp_template_prefill',
            JSON.stringify({ id: t.id, title: t.title, tagline: t.tagline, ...payload }),
          );
        }
      } catch {}

      const mode: string = payload.mode || t.wizard_mode || 'video';
      const prompt: string = (
        payload.prompt
          || (payload.prompts && payload.prompts[0])
          || payload.prefill_prompt
          || t.tagline
          || t.title
          || ''
      );
      router.push({
        pathname: '/create-wizard',
        params: {
          from: 'inspiration', // ← stays on idea step, prefills prompt
          id: t.id,
          mode,
          prompt,
          title: t.title,
          duration: String(payload.duration || t.duration || 10),
          aspectRatio: payload.aspect_ratio || '9:16',
          voiceId: payload.voice_id || t.voice_id || '',
          imageQuery: payload.image_query || '',
          musicMood: payload.music_mood || t.music_mood || 'cinematic_epic',
        } as any,
      });
    } catch (e) {
      // Network failure → fall back to template browse
      router.push('/marketplace');
    } finally {
      setUsingId(null);
    }
  }, [usingId, user, router, onAuthRequired]);

  if (!items.length) return null;

  const FALLBACK = 'https://images.pexels.com/photos/1749900/pexels-photo-1749900.jpeg?w=300&h=400&fit=crop';

  return (
    <View style={s.inspGrid}>
      {items.map(t => {
        const thumb = t.thumbnail && t.thumbnail.startsWith('http') ? t.thumbnail : FALLBACK;
        const tier = (t.plan_tier || 'free').toLowerCase();
        const isMotion = t.wizard_mode === 'video' || !!t.has_motion;
        const busy = usingId === t.id;
        const previewUrl: string | undefined = (t as any).preview_url;
        const fullPreview = previewUrl
          ? (previewUrl.startsWith('http') ? previewUrl : `${BACKEND_URL}${previewUrl}`)
          : undefined;
        return (
          <TouchableOpacity
            key={t.id}
            activeOpacity={0.88}
            disabled={!!usingId}
            style={[s.inspTile, busy && { opacity: 0.6 }]}
            onPress={() => setPreviewItem(t)}
          >
            {/* Always-visible thumbnail (poster). Re-enabled muted-loop
             * autoplay on tiles now that Round-2 media curation guarantees
             * each preview_url is a small Pixabay `tiny` mp4 (verified via
             * HEAD check). The poster image stays as a fallback under the
             * video, so there's no black flash. The full preview with audio
             * plays inside the fullscreen modal on tile tap. We removed
             * `usePoster` to cut the image→video transition delay and we
             * crank `progressUpdateIntervalMillis` low so the loop feels
             * instant (expo-av otherwise buffers ~250ms between loops). */}
            <Image source={{ uri: thumb }} style={StyleSheet.absoluteFillObject} resizeMode="cover" />
            {fullPreview ? (
              <Video
                source={{ uri: fullPreview }}
                style={StyleSheet.absoluteFillObject}
                useNativeControls={false}
                isLooping
                shouldPlay
                isMuted
                progressUpdateIntervalMillis={50}
                resizeMode={ResizeMode.COVER}
              />
            ) : null}
            <LinearGradient
              colors={['rgba(0,0,0,0)', 'rgba(0,0,0,0.85)']}
              style={StyleSheet.absoluteFillObject}
            />
            {/* Motion / static badge top-left */}
            <View style={[s.inspKind, isMotion ? { backgroundColor: '#EC4899EE' } : { backgroundColor: '#64748BEE' }]}>
              <Ionicons name={isMotion ? 'videocam' : 'image'} size={10} color="#fff" />
              <Text style={s.inspKindTxt}>{isMotion ? 'MOTION' : 'STATIC'}</Text>
            </View>
            {/* Tier badge top-right */}
            {tier !== 'free' && (
              <View style={s.inspTier}>
                <Text style={s.inspTierTxt}>{tier.toUpperCase()}</Text>
              </View>
            )}
            {/* Title bottom */}
            <Text style={s.inspTitle} numberOfLines={2}>{t.title}</Text>
            {busy && (
              <View style={[StyleSheet.absoluteFillObject, { alignItems: 'center', justifyContent: 'center' }]}>
                <ActivityIndicator size="small" color="#fff" />
              </View>
            )}
          </TouchableOpacity>
        );
      })}

      {/* Fullscreen preview modal — shown when user taps a tile.
       * Plays the preview video full-bleed with a "Recreate" CTA at bottom
       * that triggers handlePick(). Tapping outside / X closes it. */}
      <Modal
        transparent
        animationType="fade"
        visible={!!previewItem}
        onRequestClose={() => setPreviewItem(null)}
      >
        <View style={s.previewBackdrop}>
          {previewItem && (() => {
            const it = previewItem;
            const thumb = it.thumbnail && it.thumbnail.startsWith('http') ? it.thumbnail : undefined;
            const previewUrl: string | undefined = it.preview_url;
            const fullPreview = previewUrl
              ? (previewUrl.startsWith('http') ? previewUrl : `${BACKEND_URL}${previewUrl}`)
              : undefined;
            return (
              <View style={s.previewSheet}>
                <View style={s.previewMedia}>
                  {thumb ? (
                    <Image source={{ uri: thumb }} style={StyleSheet.absoluteFillObject} resizeMode="cover" />
                  ) : null}
                  {fullPreview ? (
                    <Video
                      source={{ uri: fullPreview }}
                      style={StyleSheet.absoluteFillObject}
                      useNativeControls={false}
                      isLooping
                      shouldPlay
                      isMuted={false}
                      resizeMode={ResizeMode.COVER}
                    />
                  ) : null}
                  <TouchableOpacity onPress={() => setPreviewItem(null)} style={s.previewClose} activeOpacity={0.85}>
                    <Ionicons name="close" size={22} color="#fff" />
                  </TouchableOpacity>
                </View>

                <View style={s.previewInfo}>
                  <Text style={s.previewTitle} numberOfLines={2}>{it.title}</Text>
                  {it.tagline ? <Text style={s.previewTag} numberOfLines={2}>{it.tagline}</Text> : null}
                </View>

                <TouchableOpacity
                  onPress={() => { const t = it; setPreviewItem(null); setTimeout(() => handlePick(t), 100); }}
                  style={s.previewCta}
                  activeOpacity={0.9}
                >
                  <Ionicons name="refresh" size={18} color="#0B1120" />
                  <Text style={s.previewCtaTxt}>Recreate</Text>
                </TouchableOpacity>
              </View>
            );
          })()}
        </View>
      </Modal>
    </View>
  );
}

/* ==================== Index (Home) ==================== */
export default function Index() {
  const router = useRouter();
  const { user, loading, logout, mode, refresh } = useAuth();
  const [profileOpen, setProfileOpen] = useState(false);
  const [showData, setShowData] = useState(false);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [authGateOpen, setAuthGateOpen] = useState(false);
  const [pendingRoute, setPendingRoute] = useState<string | null>(null);

  // Quick-Action sheet (FAB)
  const [qaOpen, setQaOpen] = useState(false);

  // Notifications bell
  const [notifications, setNotifications] = useState<any[]>([]);
  const [notifUnread, setNotifUnread] = useState<number>(0);
  const [notifOpen, setNotifOpen] = useState<boolean>(false);

  const loadNotifications = React.useCallback(async () => {
    if (!user) return;
    try {
      const token = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem('magicai_jwt_v1') : null;
      if (!token) return;
      const r = await axios.get(`${BACKEND_URL}/api/notifications?limit=20`, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 });
      setNotifications(r.data?.notifications || []);
      setNotifUnread(Number(r.data?.unread_count || 0));
    } catch {}
  }, [user]);

  React.useEffect(() => {
    if (!user) { setNotifications([]); setNotifUnread(0); return; }
    loadNotifications();
    const iv = setInterval(loadNotifications, 60 * 1000);
    return () => clearInterval(iv);
  }, [user, loadNotifications]);

  const markAllRead = async () => {
    if (!user) return;
    try {
      const token = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem('magicai_jwt_v1') : null;
      if (!token) return;
      await axios.post(`${BACKEND_URL}/api/notifications/mark-read`, {}, { headers: { Authorization: `Bearer ${token}` } });
      setNotifUnread(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch {}
  };

  // Gate: protected routes require login; guests see the auth-gate popup
  const requireAuth = React.useCallback((route: string) => {
    if (user) { router.push(route as any); return; }
    setPendingRoute(route);
    setAuthGateOpen(true);
  }, [user, router]);

  // Universal pick handler — respects PUBLIC_ROUTES; otherwise gates
  const onPick = React.useCallback((route: string, isPublic: boolean = false) => {
    const base = route.split('?')[0];
    if (isPublic || PUBLIC_ROUTES.has(base)) {
      router.push(route as any);
      return;
    }
    requireAuth(route);
  }, [router, requireAuth]);

  // Keep credits balance fresh
  useEffect(() => { if (user) refresh(); }, []);

  useEffect(() => {
    if (user) {
      axios.get(`${BACKEND_URL}/api/usage`).then(r => setUsage(r.data)).catch(() => {});
    }
  }, [user]);

  // Handle Android back button for profile modal
  useEffect(() => {
    if (!profileOpen) return;
    const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
      closeProfile();
      return true;
    });
    return () => backHandler.remove();
  }, [profileOpen]);

  const closeProfile = () => {
    setProfileOpen(false);
    setShowData(false);
  };

  const handleShareApp = async () => {
    const webUrl = BACKEND_URL || '';
    try {
      await Share.share({
        message: `Try MagiCAi Studio - AI-powered video creation!\n\nOpen: ${webUrl}\n\nOr install "Expo Go" app & scan the QR code to test on mobile.`,
        url: webUrl,
        title: 'MagiCAi Studio',
      });
    } catch (e) {}
  };

  const handleLogout = () => {
    Alert.alert(
      'Sign out?', 'You will need to log in again to use the app.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign out', style: 'destructive',
          onPress: async () => {
            closeProfile();
            await logout();
            Alert.alert('Signed out', 'You have been signed out.');
            router.replace('/login');
          },
        },
      ],
      { cancelable: true },
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <View style={s.center}>
          <ActivityIndicator size="large" color="#A78BFA" />
        </View>
      </SafeAreaView>
    );
  }

  const displayUser: { name: string; email: string; picture?: string } = user
    ? { name: user.name || user.email.split('@')[0], email: user.email }
    : { name: 'Guest', email: '' };

  const usageItems = [
    { label: 'Lip Sync', count: usage?.lipsync?.completed || 0, icon: 'mic', color: '#8B5CF6' },
    { label: 'Face Swap', count: usage?.faceswap?.completed || 0, icon: 'people', color: '#EC4899' },
    { label: 'Head Swap', count: usage?.headswap?.completed || 0, icon: 'person', color: '#F97316' },
    { label: 'Body Swap', count: usage?.bodyswap?.completed || 0, icon: 'shirt', color: '#06B6D4' },
  ];

  const tier = (user ? (user.subscription_tier || 'free') : 'guest') as keyof typeof TIER_LABEL;
  const tierMeta = TIER_LABEL[tier] || TIER_LABEL.free;

  return (
    <AuroraBackground>
      <SafeAreaView style={s.container} edges={['top']}>
        <StatusBar barStyle="light-content" />
        <ScrollView
          contentContainerStyle={s.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* ===== HEADER: hamburger | logo | credits/avatar ===== */}
          <View style={s.headerRow}>
            <TouchableOpacity
              testID="header-menu"
              activeOpacity={0.7}
              onPress={() => setProfileOpen(true)}
              style={s.headerMenu}
            >
              <Ionicons name="menu" size={22} color="#fff" />
            </TouchableOpacity>

            <View style={s.headerCenter}>
              {/* New colorful "MagiCAi Studio" wordmark image (matches hsi1.png) */}
              <Image
                source={require('../assets/logo/nw_glyph.png')}
                resizeMode="contain"
                style={s.headerGlyphImg}
              />
              <Image
                source={require('../assets/logo/nw_wordmark.png')}
                resizeMode="contain"
                style={{ width: 150, height: 56, marginLeft: 6 }}
              />
            </View>

            {user ? (
              <TouchableOpacity
                testID="credits-pill"
                activeOpacity={0.85}
                onPress={() => router.push('/buy' as any)}
                style={s.creditsPill}
              >
                <View style={s.creditsCoin}>
                  <Text style={{ fontSize: 12 }}>🪙</Text>
                </View>
                <Text style={s.creditsValue}>{user.credits_balance}</Text>
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                onPress={() => router.push({ pathname: '/login', params: { mode: 'login' } as any })}
                activeOpacity={0.85}
                style={s.signupBtnWrap}
              >
                <LinearGradient
                  colors={['#FF6B08', '#FF007F', '#AE29FF']}
                  start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                  style={s.signupBtn}
                >
                  <Ionicons name="log-in-outline" size={13} color="#fff" />
                  <Text style={s.signupBtnTxt}>Login</Text>
                </LinearGradient>
              </TouchableOpacity>
            )}
          </View>

          {/* Notifications bell (only if logged in) */}
          {user && notifUnread > 0 && (
            <TouchableOpacity
              testID="notif-pill"
              onPress={() => { setNotifOpen(true); markAllRead(); }}
              style={s.notifPill}
              activeOpacity={0.85}
            >
              <Ionicons name="notifications" size={14} color="#FBBF24" />
              <Text style={s.notifPillTxt}>
                {notifUnread} new notification{notifUnread > 1 ? 's' : ''}
              </Text>
              <Ionicons name="chevron-forward" size={12} color="#FBBF24" />
            </TouchableOpacity>
          )}

          {/* ===== HERO CAROUSEL ===== */}
          <HeroCarousel onPick={(route) => onPick(route, false)} />

          {/* ===== QUICK ACCESS ===== */}
          <QuickAccess onPick={onPick} />

          {/* ===== DISCOVER MAGIC AI (onboarding-style auto carousel) ===== */}
          <OnboardingCarousel onPick={(route) => onPick(route, false)} />

          {/* ===== FEATURED TOOL: Creator Wizard ===== */}
          <View style={{ paddingHorizontal: 16, marginBottom: 14 }}>
            <TouchableOpacity
              activeOpacity={0.88}
              onPress={() => requireAuth('/create-wizard')}
              style={s.featuredCard}
            >
              <BlurView intensity={Platform.OS === 'web' ? 0 : 25} tint="dark" style={StyleSheet.absoluteFill} />
              <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(123,92,255,0.16)', borderRadius: 18 }]} />
              <View style={s.featuredCrown}>
                <Ionicons name="sparkles" size={22} color="#FBBF24" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.featuredEyebrow}>Featured Tool</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 }}>
                  <Text style={s.featuredTitle}>Creator Wizard</Text>
                  <View style={s.newBadge}><Text style={s.newBadgeTxt}>NEW</Text></View>
                </View>
                <Text style={s.featuredSub}>Idea → 3 AI scripts → one-tap reel</Text>
              </View>
              <View style={s.featuredCta}>
                <Text style={s.featuredCtaTxt}>Try Now</Text>
                <Ionicons name="chevron-forward" size={14} color="#fff" />
              </View>
            </TouchableOpacity>
          </View>

          {/* ===== GO PREMIUM ===== */}
          <View style={{ paddingHorizontal: 16, marginBottom: 14 }}>
            <TouchableOpacity
              activeOpacity={0.88}
              onPress={() => requireAuth('/subscription')}
              style={{ borderRadius: 18, overflow: 'hidden' }}
            >
              <LinearGradient
                colors={['#FF4D8D', '#FF9A3C']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                style={s.premiumCard}
              >
                <View style={s.premiumDiamond}>
                  <Ionicons name="diamond" size={22} color="#fff" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.premiumTitle}>Go Premium</Text>
                  <Text style={s.premiumSub}>
                    Unlock HD, No Watermark,{'\n'}Faster Renders & More
                  </Text>
                </View>
                <View style={s.premiumCta}>
                  <Ionicons name="diamond" size={11} color="#FF4D8D" />
                  <Text style={s.premiumCtaTxt}>Upgrade Now</Text>
                  <Ionicons name="chevron-forward" size={12} color="#FF4D8D" />
                </View>
              </LinearGradient>
            </TouchableOpacity>
          </View>

          {/* ===== INSPIRATION GRID (9 templates across categories) ===== */}
          <View style={{ paddingHorizontal: 16, marginBottom: 14 }}>
            <View style={[s.sectionHead, { paddingHorizontal: 0 }]}>
              <View style={s.sectionTitleRow}>
                <Text style={{ fontSize: 14 }}>✨</Text>
                <Text style={s.sectionTitle}>Inspiration Reels</Text>
              </View>
              <TouchableOpacity onPress={() => router.push('/trending' as any)} style={s.seeAllBtn} activeOpacity={0.8}>
                <Text style={s.seeAllTxt}>See all</Text>
                <Ionicons name="chevron-forward" size={12} color="#A78BFA" />
              </TouchableOpacity>
            </View>
            <InspirationGrid
              onAuthRequired={(route: string) => requireAuth(route)}
            />
          </View>

          {/* Legal footer */}
          <View style={s.legalFooter}>
            <View style={s.legalLinkRow}>
              <Pressable onPress={() => router.push({ pathname: '/legal', params: { doc: 'terms' } } as any)}><Text style={s.legalLink}>Terms</Text></Pressable>
              <Text style={s.legalDot}>·</Text>
              <Pressable onPress={() => router.push({ pathname: '/legal', params: { doc: 'privacy' } } as any)}><Text style={s.legalLink}>Privacy</Text></Pressable>
              <Text style={s.legalDot}>·</Text>
              <Pressable onPress={() => router.push({ pathname: '/legal', params: { doc: 'refund' } } as any)}><Text style={s.legalLink}>Refunds</Text></Pressable>
              <Text style={s.legalDot}>·</Text>
              <Pressable onPress={() => router.push({ pathname: '/legal', params: { doc: 'aup' } } as any)}><Text style={s.legalLink}>AI Use</Text></Pressable>
              <Text style={s.legalDot}>·</Text>
              <Pressable onPress={() => router.push({ pathname: '/legal', params: { doc: 'contact' } } as any)}><Text style={s.legalLink}>Contact</Text></Pressable>
            </View>
            <Text style={s.legalCopyright}>© 2025 MagiCAi Studio · Made with ❤️ in India</Text>
          </View>

          {/* Spacer so content never hides behind floating tab bar */}
          <View style={{ height: 100 }} />
        </ScrollView>

        {/* ===== Notifications Sheet ===== */}
        <Modal visible={notifOpen} animationType="slide" transparent onRequestClose={() => setNotifOpen(false)}>
          <Pressable style={s.modalOverlay} onPress={() => setNotifOpen(false)}>
            <Pressable style={s.profileSheet} onPress={(e) => e.stopPropagation()}>
              <View style={s.dragHandle} />
              <View style={{ paddingHorizontal: 20, paddingTop: 4, paddingBottom: 12, flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="notifications" size={20} color="#A78BFA" />
                <Text style={{ color: '#fff', fontSize: 18, fontWeight: '800', marginLeft: 8, flex: 1 }}>Notifications</Text>
                <TouchableOpacity onPress={() => setNotifOpen(false)}>
                  <Ionicons name="close" size={22} color="#94A3B8" />
                </TouchableOpacity>
              </View>
              <ScrollView style={{ paddingHorizontal: 16, maxHeight: 420 }}>
                {notifications.length === 0 ? (
                  <View style={{ paddingVertical: 40, alignItems: 'center' }}>
                    <Ionicons name="happy" size={42} color="#475569" />
                    <Text style={{ color: '#94A3B8', fontSize: 14, marginTop: 10 }}>All caught up!</Text>
                  </View>
                ) : (
                  notifications.map((n, i) => (
                    <TouchableOpacity
                      key={(n.created_at || '') + '_' + i}
                      style={{ backgroundColor: n.read ? '#111827' : 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: n.read ? '#1F2937' : 'rgba(139,92,246,0.4)', borderRadius: 12, padding: 12, marginBottom: 8 }}
                      activeOpacity={0.85}
                      onPress={() => { setNotifOpen(false); if (n.cta_route) router.push(n.cta_route as any); }}
                    >
                      <Text style={{ color: '#E2E8F0', fontSize: 13, lineHeight: 19 }}>{n.body}</Text>
                      <Text style={{ color: '#64748B', fontSize: 10, marginTop: 6 }}>{n.created_at ? new Date(n.created_at).toLocaleString() : ''}</Text>
                    </TouchableOpacity>
                  ))
                )}
                <View style={{ height: 20 }} />
              </ScrollView>
            </Pressable>
          </Pressable>
        </Modal>

        {/* ===== Profile Sheet ===== */}
        <Modal visible={profileOpen} animationType="slide" transparent onRequestClose={closeProfile}>
          <Pressable style={s.modalOverlay} onPress={closeProfile}>
            <Pressable style={s.profileSheet} onPress={(e) => e.stopPropagation()}>
              <View style={s.dragHandle} />
              <View style={s.profileHeader}>
                {displayUser.picture ? (
                  <Image source={{ uri: displayUser.picture }} style={s.profileAvatar} />
                ) : (
                  <View style={[s.profileAvatar, s.profileAvatarPlaceholder]}>
                    <Ionicons name="person" size={28} color="#A78BFA" />
                  </View>
                )}
                <Text style={s.profileGreeting}>{user ? 'My Profile' : 'Guest Mode'}</Text>
              </View>

              <ScrollView style={s.profileBody} showsVerticalScrollIndicator={false}>
                {user ? (
                  <View style={s.profileSection}>
                    <View style={s.profileSectionHeader}>
                      <Text style={s.profileSectionTitle}>Personal Info</Text>
                      <TouchableOpacity onPress={() => setShowData(!showData)} style={s.revealBtn}>
                        <Ionicons name={showData ? 'eye-off' : 'eye'} size={16} color="#A78BFA" />
                        <Text style={s.revealBtnText}>{showData ? 'Hide' : 'Reveal'}</Text>
                      </TouchableOpacity>
                    </View>
                    <View style={s.infoRow}>
                      <Ionicons name="person-outline" size={16} color="#64748B" />
                      <Text style={s.infoLabel}>Name</Text>
                      <Text style={s.infoValue}>{showData ? user.name : maskName(user.name)}</Text>
                    </View>
                    <View style={s.infoRow}>
                      <Ionicons name="mail-outline" size={16} color="#64748B" />
                      <Text style={s.infoLabel}>Email</Text>
                      <Text style={s.infoValue}>{showData ? user.email : maskEmail(user.email)}</Text>
                    </View>
                  </View>
                ) : (
                  <View style={s.profileSection}>
                    <Text style={s.profileSectionTitle}>Sign In</Text>
                    <TouchableOpacity
                      style={s.googleBtn}
                      onPress={() => { closeProfile(); router.push('/login'); }}
                      activeOpacity={0.8}
                    >
                      <Ionicons name="log-in-outline" size={18} color="#fff" />
                      <Text style={s.googleBtnText}>Log in / Sign up</Text>
                    </TouchableOpacity>
                  </View>
                )}

                {user && (
                  <View style={[s.planCard, { borderColor: tierMeta.color + '55' }]}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <Ionicons name="diamond" size={16} color={tierMeta.color} />
                      <Text style={[s.planCardLabel, { color: tierMeta.color }]}>CURRENT PLAN</Text>
                    </View>
                    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                      <View>
                        <Text style={s.planCardTier}>{tierMeta.emoji} {tierMeta.name}</Text>
                        <Text style={s.planCardCredits}>🪙 {user.credits_balance} credits available</Text>
                      </View>
                      <TouchableOpacity
                        style={[s.planCtaBtn, tier === 'free' ? s.planCtaBtnUpgrade : s.planCtaBtnManage]}
                        onPress={() => { closeProfile(); router.push('/subscription'); }}
                        activeOpacity={0.85}
                      >
                        <Text style={tier === 'free' ? s.planCtaBtnUpgradeText : s.planCtaBtnManageText}>
                          {tier === 'free' ? '⚡ Upgrade' : 'Manage'}
                        </Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                )}

                <View style={s.profileSection}>
                  <Text style={s.profileSectionTitle}>Usage & Credits</Text>
                  <View style={s.usageGrid}>
                    {usageItems.map(item => (
                      <View key={item.label} style={s.usageItem}>
                        <View style={[s.usageIcon, { backgroundColor: item.color + '20' }]}>
                          <Ionicons name={item.icon as any} size={16} color={item.color} />
                        </View>
                        <Text style={s.usageCount}>{item.count}</Text>
                        <Text style={s.usageLabel}>{item.label}</Text>
                      </View>
                    ))}
                  </View>
                </View>

                <View style={s.profileActions}>
                  <TouchableOpacity style={s.actionBtn} onPress={() => { closeProfile(); router.push('/subscription'); }} activeOpacity={0.7}>
                    <Ionicons name="pricetags-outline" size={20} color="#FBBF24" />
                    <Text style={s.actionBtnText}>Plans & Pricing</Text>
                    <Ionicons name="chevron-forward" size={18} color="#475569" />
                  </TouchableOpacity>
                  <TouchableOpacity style={s.actionBtn} onPress={() => { closeProfile(); router.push('/projects'); }} activeOpacity={0.7}>
                    <Ionicons name="folder-outline" size={20} color="#60A5FA" />
                    <Text style={s.actionBtnText}>My Projects</Text>
                    <Ionicons name="chevron-forward" size={18} color="#475569" />
                  </TouchableOpacity>
                  {user?.is_admin && (
                    <TouchableOpacity style={s.actionBtn} onPress={() => { closeProfile(); router.push('/admin'); }} activeOpacity={0.7}>
                      <Ionicons name="shield-checkmark-outline" size={20} color="#FBBF24" />
                      <Text style={s.actionBtnText}>Admin Panel</Text>
                      <View style={s.adminBadge}><Text style={s.adminBadgeText}>{mode?.env || 'DEV'}</Text></View>
                      <Ionicons name="chevron-forward" size={18} color="#475569" />
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity style={s.actionBtn} onPress={handleShareApp} activeOpacity={0.7}>
                    <Ionicons name="share-social-outline" size={20} color="#A78BFA" />
                    <Text style={s.actionBtnText}>Share App</Text>
                    <Ionicons name="chevron-forward" size={18} color="#475569" />
                  </TouchableOpacity>
                  {user && (
                    <TouchableOpacity testID="logout-btn" style={[s.actionBtn, s.logoutAction]} onPress={handleLogout} activeOpacity={0.7}>
                      <Ionicons name="log-out-outline" size={20} color="#EF4444" />
                      <Text style={[s.actionBtnText, { color: '#EF4444' }]}>Sign Out</Text>
                      <Ionicons name="chevron-forward" size={18} color="#EF4444" />
                    </TouchableOpacity>
                  )}
                </View>

                <Text style={s.versionText}>MagiCAi Studio v1.0.0</Text>
              </ScrollView>
            </Pressable>
          </Pressable>
        </Modal>

        {/* ===== Auth Gate ===== */}
        <Modal visible={authGateOpen} animationType="fade" transparent onRequestClose={() => setAuthGateOpen(false)}>
          <View style={s.authGateOverlay}>
            <View style={s.authGateCard}>
              <View style={s.authGateIconWrap}>
                <Ionicons name="sparkles" size={32} color="#FBBF24" />
              </View>
              <Text style={s.authGateTitle}>Log in to create magic</Text>
              <Text style={s.authGateSub}>Sign up free to unlock AI tools, Divine Transform, Avatar Studio and more.</Text>
              <TouchableOpacity
                style={s.authGatePrimary}
                activeOpacity={0.88}
                onPress={() => {
                  setAuthGateOpen(false);
                  router.push({ pathname: '/login', params: { mode: 'register', next: pendingRoute || '' } as any });
                }}
              >
                <Text style={s.authGatePrimaryText}>Sign up free</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={s.authGateSecondary}
                activeOpacity={0.85}
                onPress={() => {
                  setAuthGateOpen(false);
                  router.push({ pathname: '/login', params: { mode: 'login', next: pendingRoute || '' } as any });
                }}
              >
                <Text style={s.authGateSecondaryText}>I already have an account</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.authGateClose} onPress={() => setAuthGateOpen(false)} activeOpacity={0.7}>
                <Text style={s.authGateCloseText}>Maybe later</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>

        {/* ===== Quick-Action Sheet (FAB) ===== */}
        <QuickActionSheet
          visible={qaOpen}
          onClose={() => setQaOpen(false)}
          onPick={(route) => onPick(route, false)}
        />
      </SafeAreaView>

      {/* Floating bottom tab bar */}
      <BottomTabBar active="home" onCreatePress={() => setQaOpen(true)} />
    </AuroraBackground>
  );
}

/* ==================== Styles ==================== */
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16 },

  scrollContent: { paddingTop: 8, paddingBottom: 24 },

  /* Header */
  headerRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingTop: 4, paddingBottom: 14, gap: 10,
  },
  headerMenu: {
    width: 38, height: 38, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
    alignItems: 'center', justifyContent: 'center',
  },
  headerCenter: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4 },
  headerGlyphImg: {
    width: 38, height: 38, borderRadius: 11,
    backgroundColor: '#000',
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.18)',
    ...Platform.select({
      web: { boxShadow: '0 0 18px rgba(168,85,247,0.55)' as any },
      default: {
        shadowColor: '#A855F7', shadowOpacity: 0.55,
        shadowRadius: 10, shadowOffset: { width: 0, height: 0 },
      },
    }),
  },
  headerGlyph: {
    width: 42, height: 42, borderRadius: 21,
    overflow: 'hidden',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.22)',
    ...Platform.select({
      web: { boxShadow: '0 0 16px rgba(236,72,153,0.5)' as any },
      default: { shadowColor: '#EC4899', shadowOpacity: 0.5, shadowRadius: 10, shadowOffset: { width: 0, height: 0 } },
    }),
  },
  headerGlyphM: {
    color: '#fff', fontSize: 26, fontWeight: '900',
    marginTop: -1, letterSpacing: 0.4,
    ...Platform.select({
      web: { textShadow: '0 1px 3px rgba(0,0,0,0.4)' as any },
      default: {},
    }),
  },
  headerBrand: {
    color: '#FFFFFF', fontSize: 18, fontWeight: '900', letterSpacing: 0.4, lineHeight: 20,
    ...Platform.select({
      web: { textShadow: '0 0 8px rgba(236,72,153,0.45)' as any },
      default: {},
    }),
  },
  headerTagline: {
    color: '#FBBF24', fontSize: 10, fontWeight: '700', letterSpacing: 0.2, marginTop: 1,
  },
  headerStudio: { color: '#A78BFA', fontSize: 8, fontWeight: '900', letterSpacing: 4, marginTop: 1 },
  creditsPill: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: 'rgba(251,191,36,0.14)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)',
    borderRadius: 999, paddingLeft: 3, paddingRight: 9, paddingVertical: 3, gap: 5,
  },
  creditsCoin: {
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: '#FBBF24',
    alignItems: 'center', justifyContent: 'center',
  },
  creditsValue: { color: '#FBBF24', fontWeight: '900', fontSize: 11, letterSpacing: 0.2 },
  signupBtnWrap: { borderRadius: 999, overflow: 'hidden', shadowColor: '#FF6B08', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.5, shadowRadius: 10, elevation: 6 },
  signupBtn: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, flexDirection: 'row', alignItems: 'center', gap: 4 },
  signupBtnTxt: { color: '#FFFFFF', fontWeight: '900', fontSize: 12, letterSpacing: 0.3 },

  notifPill: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(251,191,36,0.12)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.4)',
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 12,
    marginHorizontal: 16, marginBottom: 10,
  },
  notifPillTxt: { color: '#FBBF24', fontSize: 11, fontWeight: '700', flex: 1 },

  /* Hero */
  heroCard: {
    height: 220,
    borderRadius: 22,
    overflow: 'hidden',
    backgroundColor: 'rgba(30,27,75,0.7)',
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.18)',
  },
  heroImage: {
    position: 'absolute',
    right: -10, top: 0, bottom: 0,
    width: '58%',
    height: '100%',
  },
  heroVignette: { ...StyleSheet.absoluteFillObject },
  heroContent: {
    flex: 1, padding: 18, justifyContent: 'center',
    width: '64%',
  },
  heroTitle: { color: '#fff', fontSize: 26, fontWeight: '900', lineHeight: 30, letterSpacing: -0.4 },
  heroAccent: { color: '#FF4D8D' },
  heroSparkle: { color: '#FBBF24', fontSize: 22 },
  heroSubtitle: { color: 'rgba(255,255,255,0.78)', fontSize: 11.5, marginTop: 8, lineHeight: 16 },
  heroCtaWrap: { marginTop: 14, alignSelf: 'flex-start', borderRadius: 999, overflow: 'hidden' },
  heroCta: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingLeft: 12, paddingRight: 4, paddingVertical: 4, borderRadius: 999,
  },
  heroCtaText: { color: '#fff', fontSize: 13, fontWeight: '900', marginRight: 4, marginLeft: 2 },
  heroCtaArrow: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.95)',
    alignItems: 'center', justifyContent: 'center',
  },

  dotsRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 10 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.2)' },
  dotActive: { width: 22, backgroundColor: '#FF6B08' },

  /* Onboarding Carousel (embedded "Discover MagiCAi" tour) */
  onbCard: {
    height: 188,
    borderRadius: 22,
    overflow: 'hidden',
    backgroundColor: 'rgba(15,12,41,0.6)',
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.28)',
    ...Platform.select({
      web: { boxShadow: '0 10px 28px rgba(123,92,255,0.28)' as any },
      default: { shadowColor: '#7B5CFF', shadowOpacity: 0.45, shadowRadius: 14, shadowOffset: { width: 0, height: 6 } },
    }),
  },
  onbGlassOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(15,12,41,0.45)',
  },
  onbContent: {
    flex: 1, padding: 18, justifyContent: 'center',
    width: '62%',
  },
  onbBadge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.10)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.18)',
    paddingHorizontal: 9, paddingVertical: 4, borderRadius: 999, marginBottom: 8,
  },
  onbBadgeTxt: { color: '#fff', fontSize: 9, fontWeight: '900', letterSpacing: 0.6 },
  onbTitle: { color: '#fff', fontSize: 22, fontWeight: '900', lineHeight: 25, letterSpacing: -0.4 },
  onbDesc: { color: 'rgba(255,255,255,0.78)', fontSize: 11, lineHeight: 15, marginTop: 8 },
  onbCta: { marginTop: 12, alignSelf: 'flex-start', borderRadius: 999, overflow: 'hidden' },
  onbCtaInner: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingLeft: 12, paddingRight: 4, paddingVertical: 4, borderRadius: 999,
  },
  onbCtaTxt: { color: '#fff', fontSize: 12, fontWeight: '900', marginRight: 4, marginLeft: 2 },
  onbCtaArrow: {
    width: 24, height: 24, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.95)',
    alignItems: 'center', justifyContent: 'center',
  },
  /* Floating play badges */
  onbFloater: {
    position: 'absolute',
    width: 30, height: 30, borderRadius: 15,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
  },
  onbFloaterTL: { top: 16, left: 14, transform: [{ rotate: '-12deg' }] },
  onbFloaterBL: { bottom: 16, left: 22, transform: [{ rotate: '8deg' }] },
  onbFloaterTR: { top: 18, right: 22, transform: [{ rotate: '14deg' }] },
  /* Center medallion */
  onbMedallionWrap: {
    position: 'absolute', right: 18, top: '50%',
    width: 96, height: 96, marginTop: -48,
    alignItems: 'center', justifyContent: 'center',
  },
  onbMedallionGlow: {
    position: 'absolute', width: 96, height: 96, borderRadius: 22,
    opacity: 0.85,
    transform: [{ rotate: '-8deg' }],
  },
  onbMedallion: {
    width: 64, height: 64, borderRadius: 18,
    backgroundColor: 'rgba(15,12,41,0.65)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)',
    alignItems: 'center', justifyContent: 'center',
    transform: [{ rotate: '-8deg' }],
    ...Platform.select({
      web: { boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.3)' as any },
      default: {},
    }),
  },

  /* Sections */
  sectionHead: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 10,
  },
  sectionTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  sectionTitle: { color: '#F1F5F9', fontSize: 16, fontWeight: '800' },
  sectionSub: { color: '#64748B', fontSize: 11, marginTop: 2 },
  viewAllRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  viewAllTxt: { color: '#A78BFA', fontSize: 12, fontWeight: '800' },
  seeAllBtn: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  seeAllTxt: { color: '#A78BFA', fontSize: 12, fontWeight: '800' },
  /* Inspiration 2-col grid - use fixed-width tiles to guarantee 2 columns
   * across all platforms (RN Web sometimes ignores % widths inside flexWrap). */
  inspGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, justifyContent: 'flex-start' },
  inspTile: {
    width: Math.floor((Dimensions.get('window').width - 32 - 10) / 2),
    aspectRatio: 9 / 14,
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: '#1E1B4B',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    padding: 10,
    justifyContent: 'flex-end',
  },
  inspKind: {
    position: 'absolute', top: 8, left: 8,
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 6, paddingVertical: 3, borderRadius: 7,
  },
  inspKindTxt: { color: '#fff', fontSize: 9, fontWeight: '900', letterSpacing: 0.4 },
  inspTier: {
    position: 'absolute', top: 8, right: 8,
    paddingHorizontal: 6, paddingVertical: 3, borderRadius: 7,
    backgroundColor: '#FBBF24EE',
  },
  inspTierTxt: { color: '#0B1120', fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  inspTitle: { color: '#fff', fontSize: 13, fontWeight: '800', lineHeight: 16, zIndex: 2 },
  // Inspiration tile preview modal
  previewBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.92)',
    alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: 20,
  },
  previewSheet: {
    width: '100%', maxWidth: 420,
    backgroundColor: '#0F172A',
    borderRadius: 22,
    overflow: 'hidden',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
  },
  previewMedia: {
    width: '100%', aspectRatio: 9 / 16,
    backgroundColor: '#000',
    overflow: 'hidden',
  },
  previewClose: {
    position: 'absolute', top: 12, right: 12,
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(0,0,0,0.65)',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.18)',
  },
  previewInfo: { paddingHorizontal: 18, paddingTop: 14, paddingBottom: 10 },
  previewTitle: { color: '#fff', fontSize: 18, fontWeight: '900', letterSpacing: 0.2 },
  previewTag: { color: '#94A3B8', fontSize: 12, fontWeight: '600', marginTop: 6, lineHeight: 17 },
  previewCta: {
    margin: 16, marginTop: 4,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#FBBF24', borderRadius: 14, paddingVertical: 14,
  },
  previewCtaTxt: { color: '#0B1120', fontSize: 15, fontWeight: '900', letterSpacing: 0.4 },

  /* Quick Access — 2×2 grid on mobile so titles/subtitles fit */
  qaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  qaTile: {
    width: '48%', height: 132, borderRadius: 18, overflow: 'hidden',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.18)',
    backgroundColor: '#1E1B4B',
    padding: 12,
    justifyContent: 'space-between',
  },
  qaIconMedallion: {
    width: 38, height: 38, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.18)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.28)',
    alignItems: 'center', justifyContent: 'center',
    alignSelf: 'flex-start',
    ...Platform.select({
      web: { boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.35)' as any },
      default: {},
    }),
  },
  qaTileBody: {
    paddingTop: 4,
  },
  qaTileTitle: { color: '#fff', fontSize: 14, fontWeight: '900', letterSpacing: 0.2 },
  qaTileSub: { color: 'rgba(255,255,255,0.85)', fontSize: 11, fontWeight: '700', flex: 1, marginRight: 4 },

  /* Trending */
  trendCard: {
    width: 140, height: 188,
    borderRadius: 14, overflow: 'hidden',
    backgroundColor: '#1E1B4B',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  trendBadge: {
    position: 'absolute', top: 8, left: 8,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999,
  },
  trendBadgeTxt: { color: '#fff', fontSize: 9, fontWeight: '900', letterSpacing: 0.4 },
  trendPlay: {
    position: 'absolute', top: '40%', left: '40%',
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: 'rgba(0,0,0,0.45)',
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.5)',
    alignItems: 'center', justifyContent: 'center',
  },
  trendInfo: { position: 'absolute', left: 0, right: 0, bottom: 0, padding: 8 },
  trendTitle: { color: '#fff', fontSize: 12, fontWeight: '800' },
  trendUses: { color: 'rgba(255,255,255,0.65)', fontSize: 10, marginTop: 2 },

  /* Featured Tool */
  featuredCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 14, paddingHorizontal: 14,
    borderRadius: 18, overflow: 'hidden',
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.32)',
    backgroundColor: 'rgba(30,27,75,0.6)',
  },
  featuredCrown: {
    width: 44, height: 44, borderRadius: 12,
    backgroundColor: 'rgba(251,191,36,0.18)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.4)',
    alignItems: 'center', justifyContent: 'center',
  },
  featuredEyebrow: { color: '#A78BFA', fontSize: 10, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase' },
  featuredTitle: { color: '#fff', fontSize: 15, fontWeight: '900' },
  featuredSub: { color: 'rgba(255,255,255,0.7)', fontSize: 11, marginTop: 2 },
  featuredCta: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(123,92,255,0.55)',
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.18)',
  },
  featuredCtaTxt: { color: '#fff', fontSize: 11, fontWeight: '900' },

  newBadge: { backgroundColor: '#FBBF24', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  newBadgeTxt: { color: '#1F1029', fontSize: 8, fontWeight: '900', letterSpacing: 0.5 },

  /* Premium */
  premiumCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 16, paddingHorizontal: 14, borderRadius: 18,
  },
  premiumDiamond: {
    width: 44, height: 44, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.22)',
    alignItems: 'center', justifyContent: 'center',
  },
  premiumTitle: { color: '#fff', fontSize: 15, fontWeight: '900' },
  premiumSub: { color: 'rgba(255,255,255,0.92)', fontSize: 11, marginTop: 2, lineHeight: 14 },
  premiumCta: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#fff', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999,
  },
  premiumCtaTxt: { color: '#FF4D8D', fontSize: 11, fontWeight: '900', letterSpacing: 0.2 },

  /* Library */
  libraryCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: 'rgba(255,255,255,0.045)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 14, padding: 12,
  },
  libraryIconWrap: {
    width: 42, height: 42, borderRadius: 12,
    backgroundColor: 'rgba(16,185,129,0.18)',
    alignItems: 'center', justifyContent: 'center',
  },
  libraryTitle: { color: '#fff', fontSize: 13, fontWeight: '800' },
  librarySub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },

  /* Legal */
  legalFooter: { paddingTop: 18, paddingBottom: 8, alignItems: 'center', gap: 8 },
  legalLinkRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' },
  legalLink: { color: '#94A3B8', fontSize: 11, fontWeight: '600', paddingHorizontal: 6, paddingVertical: 2 },
  legalDot: { color: '#475569', fontSize: 11 },
  legalCopyright: { color: '#475569', fontSize: 10, marginTop: 2 },

  /* Profile sheet (modal) */
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  profileSheet: { backgroundColor: '#1E293B', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '82%', paddingBottom: 30 },
  dragHandle: { width: 40, height: 4, backgroundColor: '#475569', borderRadius: 2, alignSelf: 'center', marginTop: 12, marginBottom: 6 },
  profileHeader: { alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#334155' },
  profileAvatar: { width: 52, height: 52, borderRadius: 26, borderWidth: 2, borderColor: '#8B5CF640' },
  profileAvatarPlaceholder: { backgroundColor: '#334155', alignItems: 'center', justifyContent: 'center' },
  profileGreeting: { fontSize: 17, fontWeight: 'bold', color: '#fff', marginTop: 8 },
  profileBody: { paddingHorizontal: 20, paddingTop: 4 },
  profileSection: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#33415540' },
  profileSectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  profileSectionTitle: { fontSize: 13, fontWeight: '600', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.5 },
  revealBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: 'rgba(167,139,250,0.18)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8 },
  revealBtnText: { color: '#A78BFA', fontSize: 12, fontWeight: '600' },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8 },
  infoLabel: { color: '#64748B', fontSize: 13, width: 45 },
  infoValue: { color: '#E2E8F0', fontSize: 13, fontWeight: '500', flex: 1, textAlign: 'right' },
  usageGrid: { flexDirection: 'row', gap: 8 },
  usageItem: { flex: 1, backgroundColor: '#0F172A', borderRadius: 10, padding: 10, alignItems: 'center' },
  usageIcon: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginBottom: 4 },
  usageCount: { fontSize: 16, fontWeight: 'bold', color: '#fff' },
  usageLabel: { fontSize: 9, color: '#94A3B8', marginTop: 2 },
  profileActions: { paddingTop: 10, gap: 2 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, paddingHorizontal: 4 },
  actionBtnText: { flex: 1, fontSize: 14, color: '#E2E8F0', fontWeight: '500' },
  adminBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, borderWidth: 1, borderColor: 'rgba(251,191,36,0.55)', backgroundColor: 'rgba(251,191,36,0.12)', marginRight: 4 },
  adminBadgeText: { color: '#FBBF24', fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  logoutAction: { borderTopWidth: 1, borderTopColor: '#33415540', marginTop: 4, paddingTop: 12 },
  versionText: { textAlign: 'center', color: '#475569', fontSize: 11, marginTop: 10, marginBottom: 8 },
  googleBtn: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#7B5CFF', borderRadius: 14, paddingVertical: 14, paddingHorizontal: 20, marginTop: 12, justifyContent: 'center' },
  googleBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },

  /* Plan card */
  planCard: { backgroundColor: 'rgba(251,191,36,0.06)', borderWidth: 1, borderRadius: 14, padding: 14, marginVertical: 14 },
  planCardLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 0.8 },
  planCardTier: { color: '#F1F5F9', fontSize: 18, fontWeight: '800' },
  planCardCredits: { color: '#94A3B8', fontSize: 12, fontWeight: '600', marginTop: 2 },
  planCtaBtn: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10 },
  planCtaBtnUpgrade: { backgroundColor: '#FBBF24' },
  planCtaBtnUpgradeText: { color: '#1F1029', fontSize: 13, fontWeight: '900' },
  planCtaBtnManage: { borderWidth: 1, borderColor: 'rgba(167,139,250,0.5)', backgroundColor: 'rgba(167,139,250,0.12)' },
  planCtaBtnManageText: { color: '#A78BFA', fontSize: 13, fontWeight: '800' },

  /* Auth gate */
  authGateOverlay: { flex: 1, backgroundColor: 'rgba(15,12,41,0.78)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  authGateCard: { width: '100%', maxWidth: 380, backgroundColor: '#1E1B4B', borderRadius: 22, padding: 24, borderWidth: 1, borderColor: 'rgba(167,139,250,0.25)', alignItems: 'center' },
  authGateIconWrap: { width: 64, height: 64, borderRadius: 32, backgroundColor: 'rgba(251,191,36,0.15)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.35)', alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  authGateTitle: { color: '#F1F5F9', fontSize: 20, fontWeight: '800', textAlign: 'center' },
  authGateSub: { color: '#94A3B8', fontSize: 13, lineHeight: 19, textAlign: 'center', marginTop: 8, marginBottom: 20 },
  authGatePrimary: { width: '100%', backgroundColor: '#FBBF24', borderRadius: 14, paddingVertical: 14, alignItems: 'center', marginBottom: 10 },
  authGatePrimaryText: { color: '#1F1029', fontSize: 15, fontWeight: '900', letterSpacing: 0.3 },
  authGateSecondary: { width: '100%', borderWidth: 1, borderColor: 'rgba(167,139,250,0.55)', borderRadius: 14, paddingVertical: 13, alignItems: 'center' },
  authGateSecondaryText: { color: '#A78BFA', fontSize: 14, fontWeight: '800' },
  authGateClose: { marginTop: 14, padding: 6 },
  authGateCloseText: { color: '#64748B', fontSize: 12, fontWeight: '600' },

  /* Quick Action sheet */
  qaOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  qaSheet: {
    backgroundColor: '#1E1B4B',
    borderTopLeftRadius: 24, borderTopRightRadius: 24,
    paddingHorizontal: 20, paddingTop: 6, paddingBottom: 30,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  qaTitle: { color: '#fff', fontSize: 18, fontWeight: '900', textAlign: 'center', marginTop: 4 },
  qaSub: { color: '#94A3B8', fontSize: 12, textAlign: 'center', marginTop: 4 },
  qaAction: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    paddingVertical: 14, paddingHorizontal: 14, borderRadius: 14,
  },
  qaIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  qaActionTitle: { color: '#fff', fontSize: 15, fontWeight: '800' },
  qaActionSub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },
  qaCancel: {
    marginTop: 14, paddingVertical: 12, alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 12,
  },
  qaCancelTxt: { color: '#94A3B8', fontSize: 13, fontWeight: '700' },
});
