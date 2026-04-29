/* Phase-2 — Quick-Reel Template Marketplace screen
 *
 * Read-only marketplace of curated quick-reel presets (24 seed templates).
 * Tap "Use Template" → POST /api/marketplace/templates/{id}/use →
 * navigate to the wizard with deep-link params that auto-fill steps and skip to generation.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  Image, Dimensions, RefreshControl, StatusBar, Pressable, TextInput, Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import axios from 'axios';
import BottomTabBar from '../src/components/BottomTabBar';
import { useTheme } from '../src/ThemeContext';
import { useAuth } from '../src/AuthContext';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import AuthGateModal from '../src/components/AuthGateModal';

const API = (process.env.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_BACKEND_URL || '') + '/api';
const RECENT_KEY = 'mp_recent_used_v1';
const MAX_RECENT = 6;
const { width: SCREEN_W } = Dimensions.get('window');
const CARD_W = (SCREEN_W - 16 * 2 - 12) / 2;   // 2-col grid w/ 16px gutter

/** Cross-platform persistent storage shim (AsyncStorage on native, localStorage on web). */
async function persistGet(key: string): Promise<string | null> {
  try {
    if (typeof window !== 'undefined' && (window as any).localStorage) {
      return (window as any).localStorage.getItem(key);
    }
    const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
    return await AsyncStorage.getItem(key);
  } catch { return null; }
}
async function persistSet(key: string, val: string) {
  try {
    if (typeof window !== 'undefined' && (window as any).localStorage) {
      (window as any).localStorage.setItem(key, val); return;
    }
    const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
    await AsyncStorage.setItem(key, val);
  } catch {}
}

type Category = { id: string; label: string; emoji: string; color: string; order: number };
type PlanTier = 'free' | 'starter' | 'creator' | 'pro';
type Template = {
  id: string;
  title: string;
  tagline?: string;
  emoji?: string;
  thumbnail?: string;
  category: string;
  wizard_mode: 'video' | 'images';
  voice_id?: string;
  voice_style?: string;
  music_mood?: string;
  duration?: number;
  is_featured?: boolean;
  is_trending?: boolean;
  usage_count?: number;
  view_count?: number;
  plan_tier?: PlanTier;
  prompts?: string[];
};

const TIER_META: Record<PlanTier, { label: string; bg: string; fg: string; icon: any }> = {
  free:    { label: 'FREE',    bg: '#10B981', fg: '#0B1120', icon: 'flash' },
  starter: { label: 'STARTER', bg: '#3B82F6', fg: '#FFFFFF', icon: 'rocket' },
  creator: { label: 'CREATOR', bg: '#A78BFA', fg: '#0B1120', icon: 'sparkles' },
  pro:     { label: 'PRO',     bg: '#FBBF24', fg: '#0B1120', icon: 'diamond' },
};

const SORT_OPTIONS: { id: 'trending' | 'new' | 'featured'; label: string; icon: any }[] = [
  { id: 'trending', label: 'Trending', icon: 'flame' },
  { id: 'new',      label: 'New',      icon: 'sparkles' },
  { id: 'featured', label: 'Featured', icon: 'star' },
];


export default function MarketplaceScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const userTier = (user?.subscription_tier || 'free').toLowerCase();
  const TIER_RANK: Record<string, number> = { free: 0, starter: 1, creator: 2, pro: 3 };
  const { isDark } = useTheme();
  const titleColor = isDark ? '#FFFFFF' : '#0F0C29';
  const subColor = isDark ? '#94A3B8' : '#64748B';
  const [categories, setCategories] = useState<Category[]>([]);
  const [activeCat, setActiveCat] = useState<string>('all');
  const [sort, setSort] = useState<'trending' | 'new' | 'featured'>('trending');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [usingId, setUsingId] = useState<string | null>(null);

  // Polish: search + recently-used
  const [search, setSearch] = useState('');
  const [authGateOpen, setAuthGateOpen] = useState(false);
  const [gateReason, setGateReason] = useState('');
  const [recentIds, setRecentIds] = useState<string[]>([]);

  // ----- load recent IDs once -----
  useEffect(() => {
    (async () => {
      const raw = await persistGet(RECENT_KEY);
      if (raw) {
        try { setRecentIds(JSON.parse(raw)); } catch {}
      }
    })();
  }, []);

  // ----- load categories once -----
  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API}/marketplace/categories`, { timeout: 12000 });
        setCategories(r.data?.categories || []);
      } catch (e) {
        console.warn('categories load failed', e);
      }
    })();
  }, []);

  // ----- load templates whenever filters change -----
  const loadTemplates = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = { sort, limit: 48 };
      if (activeCat !== 'all') params.category = activeCat;
      const r = await axios.get(`${API}/marketplace/templates`, { params, timeout: 15000 });
      setTemplates(r.data?.templates || []);
    } catch (e) {
      console.warn('templates load failed', e);
      setTemplates([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeCat, sort]);

  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadTemplates();
  }, [loadTemplates]);

  // ----- "Use Template" → wizard prefill OR direct to AI Video Gen for video mode -----
  const useTemplate = useCallback(async (t: Template) => {
    if (usingId) return;
    // ── Guest gate: Guests can BROWSE templates but must sign in to USE them ──
    if (!user) {
      setGateReason('Using this template');
      setAuthGateOpen(true);
      return;
    }
    // ── Plan-tier paywall gate (block BEFORE doing the API call) ──
    const tplTier = (t.plan_tier || 'free').toLowerCase();
    if ((TIER_RANK[tplTier] ?? 0) > (TIER_RANK[userTier] ?? 0)) {
      Alert.alert(
        `${tplTier.toUpperCase()} template`,
        `This template requires the ${tplTier.toUpperCase()} plan or higher. Upgrade to unlock it and many more premium reels.`,
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'View plans', onPress: () => router.push('/subscription') },
        ],
      );
      return;
    }
    setUsingId(t.id);
    try {
      const r = await axios.post(`${API}/marketplace/templates/${t.id}/use`, {}, { timeout: 12000 });
      const payload = r.data?.wizard_payload;
      if (!payload) throw new Error('Empty payload');

      // Persist the prefill for the wizard to consume on next mount (keeps URL clean).
      try {
        if (typeof window !== 'undefined' && (window as any).sessionStorage) {
          (window as any).sessionStorage.setItem(
            'mp_template_prefill',
            JSON.stringify({ id: t.id, title: t.title, tagline: t.tagline, ...payload }),
          );
        }
      } catch {}

      // Track in Recently Used
      try {
        const next = [t.id, ...recentIds.filter(x => x !== t.id)].slice(0, MAX_RECENT);
        setRecentIds(next);
        await persistSet(RECENT_KEY, JSON.stringify(next));
      } catch {}

      const mode: string = payload.mode || t.wizard_mode || 'video';
      // Prefer the rich prompt the backend now ships back (idea+script+image_query
      // composed into a single prefill string). Fall back to first prompts[]
      // entry, then tagline, then title.
      const prompt: string = (
        payload.prompt
          || (payload.prompts && payload.prompts[0])
          || payload.prefill_prompt
          || t.tagline
          || t.title
          || ''
      );

      // Templates route to AI Video Gen (/videogen) with the rich prompt
      // pre-filled into its idea/prompt box. Free users will see the tier
      // paywall banner inside /videogen but the prompt will be pre-populated
      // so they can immediately upgrade and run it. (Earlier this routed
      // through /create-wizard but the user explicitly asked to land on AI
      // Video Gen so they can pick model/resolution/duration.)
      try {
        if (typeof window !== 'undefined' && (window as any).sessionStorage) {
          (window as any).sessionStorage.setItem(
            'videogen_template_prefill',
            JSON.stringify({
              id: t.id, title: t.title, prompt, mode,
              duration: payload.duration || t.duration || 10,
              aspectRatio: payload.aspect_ratio || '9:16',
              voiceId: payload.voice_id || t.voice_id || '',
              musicMood: payload.music_mood || t.music_mood || 'cinematic_epic',
            }),
          );
        }
      } catch {}
      router.push({
        pathname: '/videogen',
        params: {
          from: 'template',
          id: t.id,
          mode,
          prompt,
          title: t.title,
          duration: String(payload.duration || t.duration || 10),
          aspectRatio: payload.aspect_ratio || '9:16',
        } as any,
      });
      return;
    } catch (e: any) {
      console.warn('use_template failed', e?.message);
    } finally {
      setUsingId(null);
    }
  }, [router, usingId, recentIds, user, userTier]);

  // ----- derived: search filter applied client-side -----
  const filteredTemplates = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter(t => {
      return (
        (t.title || '').toLowerCase().includes(q) ||
        (t.tagline || '').toLowerCase().includes(q) ||
        (t.category || '').toLowerCase().includes(q)
      );
    });
  }, [templates, search]);

  // ----- recently-used templates: lookup by id, preserve order -----
  const recentTemplates = useMemo(() => {
    if (!recentIds.length || !templates.length) return [];
    const map = new Map(templates.map(t => [t.id, t]));
    return recentIds.map(id => map.get(id)).filter(Boolean) as Template[];
  }, [recentIds, templates]);

  const visibleCount = filteredTemplates.length;
  const activeCatMeta = useMemo(
    () => categories.find(c => c.id === activeCat),
    [categories, activeCat],
  );

  return (
    <View style={{ flex: 1 }}>
    <SafeAreaView style={s.root} edges={['top']}>
      <StatusBar barStyle="light-content" />

      {/* Premium glass header */}
      <GlassHeader
        icon="grid"
        title="Templates"
        subtitle={`${activeCatMeta ? `${activeCatMeta.emoji}  ${activeCatMeta.label}` : 'All categories'} · ${visibleCount} reels`}
        onBack={() => router.back()}
        right={
          <View style={s.freeBadge}>
            <Ionicons name="flash" size={11} color="#0B1120" />
            <Text style={s.freeBadgeTxt}>FREE</Text>
          </View>
        }
        style={{ paddingHorizontal: 12 }}
      />

      {/* Search bar */}
      <View style={s.searchWrap}>
        <Ionicons name="search" size={14} color="#94A3B8" />
        <TextInput
          value={search}
          onChangeText={setSearch}
          placeholder="Search reels (e.g. krishna, monday, sunset)"
          placeholderTextColor="#475569"
          style={s.searchInput}
          autoCorrect={false}
          autoCapitalize="none"
        />
        {search.length > 0 && (
          <Pressable onPress={() => setSearch('')} hitSlop={6}>
            <Ionicons name="close-circle" size={16} color="#64748B" />
          </Pressable>
        )}
      </View>

      {/* Sort chips */}
      <View style={s.sortRow}>
        {SORT_OPTIONS.map(opt => {
          const active = sort === opt.id;
          return (
            <Pressable
              key={opt.id}
              onPress={() => setSort(opt.id)}
              style={[s.sortChip, active && s.sortChipActive]}
            >
              <Ionicons name={opt.icon} size={12} color={active ? '#fff' : '#94A3B8'} />
              <Text style={[s.sortChipTxt, active && { color: '#fff' }]}>{opt.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {/* Recently Used (only when user has used templates and not searching) */}
      {recentTemplates.length > 0 && search.trim() === '' && (
        <View style={s.recentWrap}>
          <View style={s.recentHeader}>
            <Ionicons name="time-outline" size={13} color="#94A3B8" />
            <Text style={s.recentLabel}>Recently used</Text>
          </View>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingHorizontal: 16, gap: 8 }}
          >
            {recentTemplates.map(t => (
              <Pressable
                key={'rec_' + t.id}
                onPress={() => useTemplate(t)}
                style={s.recentChip}
                disabled={!!usingId}
              >
                <Text style={{ fontSize: 14 }}>{t.emoji || '🎬'}</Text>
                <Text style={s.recentChipTxt} numberOfLines={1}>{t.title}</Text>
                {usingId === t.id && <ActivityIndicator size="small" color="#A78BFA" />}
              </Pressable>
            ))}
          </ScrollView>
        </View>
      )}

      {/* Category tabs (horizontal pills) */}
      <View style={s.catWrap}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={s.catRow}
        >
          <CatPill
            label="All"
            emoji="✨"
            active={activeCat === 'all'}
            color="#8B5CF6"
            onPress={() => setActiveCat('all')}
          />
          {categories.map(c => (
            <CatPill
              key={c.id}
              label={c.label}
              emoji={c.emoji}
              color={c.color}
              active={activeCat === c.id}
              onPress={() => setActiveCat(c.id)}
            />
          ))}
        </ScrollView>
      </View>

      {/* Grid */}
      {loading && templates.length === 0 ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color="#8B5CF6" />
          <Text style={s.dim}>Loading templates…</Text>
        </View>
      ) : filteredTemplates.length === 0 ? (
        <View style={s.center}>
          <Ionicons name="search-outline" size={42} color="#475569" />
          <Text style={s.dim}>
            {search.trim() ? `No templates match "${search}"` : 'No templates in this category yet.'}
          </Text>
          <TouchableOpacity onPress={() => { setActiveCat('all'); setSearch(''); }}>
            <Text style={s.linkBtn}>Browse all →</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 6, paddingBottom: 110 }}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#8B5CF6"
            />
          }
        >
          <View style={s.grid}>
            {filteredTemplates.map(t => (
              <TemplateCard
                key={t.id}
                tpl={t}
                category={categories.find(c => c.id === t.category)}
                busy={usingId === t.id}
                onUse={() => useTemplate(t)}
              />
            ))}
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
    <BottomTabBar active="templates" />
    <AuthGateModal
      visible={authGateOpen}
      onClose={() => setAuthGateOpen(false)}
      reason={gateReason}
      nextRoute="/marketplace"
    />
    </View>
  );
}


/* ========== Category Pill ========== */
function CatPill({ label, emoji, active, color, onPress }: {
  label: string; emoji: string; active: boolean; color: string; onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[s.catPill, active && { backgroundColor: color, borderColor: color }]}>
      <Text style={s.catPillEmoji}>{emoji}</Text>
      <Text style={[s.catPillTxt, active && { color: '#fff' }]}>{label}</Text>
    </Pressable>
  );
}


/* ========== Template Card ========== */
function TemplateCard({ tpl, category, busy, onUse }: {
  tpl: Template; category?: Category; busy: boolean; onUse: () => void;
}) {
  const tint = category?.color || '#8B5CF6';
  return (
    <View style={[s.card, { width: CARD_W }]}>
      {/* Visual area */}
      <View style={[s.cardThumb, { backgroundColor: tint + '22' }]}>
        {tpl.thumbnail ? (
          <Image
            source={{ uri: tpl.thumbnail }}
            resizeMode="cover"
            style={{ width: '100%', height: '100%' }}
          />
        ) : (
          <LinearGradient
            colors={[tint, '#0B1120']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}
          >
            <Text style={{ fontSize: 38 }}>{tpl.emoji || category?.emoji || '🎬'}</Text>
          </LinearGradient>
        )}

        {/* corner badges (Top-LEFT: status, Top-RIGHT: plan tier) */}
        <View style={s.cardBadges}>
          {tpl.is_featured && (
            <View style={[s.cardBadge, { backgroundColor: '#FBBF24' }]}>
              <Ionicons name="star" size={9} color="#0B1120" />
              <Text style={s.cardBadgeTxt}>Featured</Text>
            </View>
          )}
          {tpl.is_trending && (
            <View style={[s.cardBadge, { backgroundColor: '#EF4444' }]}>
              <Ionicons name="flame" size={9} color="#fff" />
              <Text style={[s.cardBadgeTxt, { color: '#fff' }]}>Trending</Text>
            </View>
          )}
        </View>

        {/* Plan tier pill (top-right) */}
        {tpl.plan_tier && (() => {
          const meta = TIER_META[tpl.plan_tier] || TIER_META.free;
          return (
            <View style={[s.tierPill, { backgroundColor: meta.bg }]}>
              <Ionicons name={meta.icon} size={9} color={meta.fg} />
              <Text style={[s.tierPillTxt, { color: meta.fg }]}>{meta.label}</Text>
            </View>
          );
        })()}
      </View>

      {/* Body */}
      <View style={s.cardBody}>
        <Text style={s.cardTitle} numberOfLines={1}>{tpl.title}</Text>
        <Text style={s.cardSub} numberOfLines={2}>{tpl.tagline || ''}</Text>

        <View style={s.cardMeta}>
          <Ionicons name="film-outline" size={10} color="#94A3B8" />
          <Text style={s.cardMetaTxt}>{((tpl.duration || 10) | 0)}s · 9:16</Text>
          {(tpl.usage_count || 0) > 0 && (
            <>
              <Text style={s.cardMetaSep}> · </Text>
              <Ionicons name="people-outline" size={10} color="#94A3B8" />
              <Text style={s.cardMetaTxt}>{tpl.usage_count}</Text>
            </>
          )}
        </View>

        <TouchableOpacity
          activeOpacity={0.85}
          onPress={onUse}
          disabled={busy}
          style={[s.useBtn, busy && { opacity: 0.6 }]}
        >
          {busy ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <>
              <Ionicons name="flash" size={11} color="#fff" />
              <Text style={s.useBtnTxt}>Use Template</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}


/* ============ STYLES ============ */
const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0B1120' },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 10, gap: 10,
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '800' },
  headerSub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },
  freeBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#10B981', borderRadius: 10,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  freeBadgeTxt: { color: '#0B1120', fontSize: 9, fontWeight: '900', letterSpacing: 0.4 },

  /* Search bar */
  searchWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginHorizontal: 16, marginTop: 4, marginBottom: 4,
    paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: '#1E293B', borderRadius: 12,
    borderWidth: 1, borderColor: '#334155',
  },
  searchInput: {
    flex: 1, color: '#fff', fontSize: 13,
    padding: 0,
  },

  /* Recently Used */
  recentWrap: { paddingTop: 6, paddingBottom: 4 },
  recentHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 16, marginBottom: 6,
  },
  recentLabel: { color: '#94A3B8', fontSize: 11, fontWeight: '700', letterSpacing: 0.3 },
  recentChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(139,92,246,0.12)',
    borderWidth: 1, borderColor: 'rgba(139,92,246,0.4)',
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12,
    maxWidth: 180,
  },
  recentChipTxt: { color: '#E2E8F0', fontSize: 11, fontWeight: '700' },

  sortRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, marginTop: 6, marginBottom: 4 },
  sortChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#1E293B', borderRadius: 14,
    paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: '#334155',
  },
  sortChipActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  sortChipTxt: { color: '#94A3B8', fontSize: 11, fontWeight: '700' },

  catWrap: { paddingTop: 6, paddingBottom: 8 },
  catRow: { paddingHorizontal: 16, gap: 8, paddingRight: 22 },
  catPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 7,
    borderRadius: 16, backgroundColor: '#1E293B',
    borderWidth: 1, borderColor: '#334155',
  },
  catPillEmoji: { fontSize: 13 },
  catPillTxt: { color: '#94A3B8', fontSize: 12, fontWeight: '700' },

  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'flex-start' },
  card: {
    backgroundColor: '#111827', borderRadius: 14, overflow: 'hidden',
    borderWidth: 1, borderColor: '#1F2937',
  },
  cardThumb: { width: '100%', aspectRatio: 9/16, position: 'relative' },
  cardBadges: { position: 'absolute', top: 6, left: 6, flexDirection: 'column', gap: 4 },
  cardBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6,
  },
  cardBadgeTxt: { color: '#0B1120', fontSize: 8, fontWeight: '900', letterSpacing: 0.2 },

  /* Plan-tier pill (top-right of card thumb) */
  tierPill: {
    position: 'absolute', top: 6, right: 6,
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8,
  },
  tierPillTxt: { fontSize: 8, fontWeight: '900', letterSpacing: 0.5 },

  cardBody: { padding: 10 },
  cardTitle: { color: '#fff', fontSize: 13, fontWeight: '800', marginBottom: 2 },
  cardSub: { color: '#94A3B8', fontSize: 10, lineHeight: 13, marginBottom: 6, minHeight: 26 },
  cardMeta: { flexDirection: 'row', alignItems: 'center', gap: 3, marginBottom: 8 },
  cardMetaTxt: { color: '#94A3B8', fontSize: 10 },
  cardMetaSep: { color: '#475569', fontSize: 10 },
  useBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    backgroundColor: '#8B5CF6', borderRadius: 10, paddingVertical: 8,
  },
  useBtnTxt: { color: '#fff', fontSize: 11, fontWeight: '800', letterSpacing: 0.2 },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10, padding: 24 },
  dim: { color: '#94A3B8', fontSize: 13 },
  linkBtn: { color: '#8B5CF6', fontSize: 13, fontWeight: '700', marginTop: 4 },
});
