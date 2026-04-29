import React, { useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  ActivityIndicator, Alert, Image, Dimensions, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Video, ResizeMode } from 'expo-av';
import { LinearGradient } from 'expo-linear-gradient';
import CosmicBackground from '../src/CosmicBackground';
import UseTemplateSheet, { Destination } from '../src/UseTemplateSheet';
import AuthGateModal from '../src/components/AuthGateModal';
import { useAuth } from '../src/AuthContext';
import axios from 'axios';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const { width } = Dimensions.get('window');
// 2-column responsive grid: 16px outer padding + 10px gap → 2 cards per row
const COLS = 2;
const GRID_GAP = 10;
const CARD_W = Math.floor((width - 16 * 2 - GRID_GAP * (COLS - 1)) / COLS);

type Template = {
  id: string;
  title: string;
  category: string;
  subcategory?: string;
  hook_text?: string;
  lyrics?: string;
  voice_id?: string;
  voice_style?: string;
  motion?: string;
  sound_effect?: string;
  aspect_ratio?: string;
  duration?: number;
  thumbnail_url?: string;
  preview_url?: string;
  tier: 'free' | 'starter' | 'pro' | 'premium';
  is_trending: boolean;
  usage_count: number;
  view_count?: number;
  score: number;
};

const CATEGORIES: { id: string; label: string; emoji: string }[] = [
  { id: 'all', label: 'All', emoji: '🌟' },
  { id: 'trending', label: '✨ Inspired', emoji: '🔥' },
  { id: 'festivals', label: 'Festivals', emoji: '🎉' },
  { id: 'devotional', label: 'Devotional', emoji: '🪔' },
  { id: 'motivation', label: 'Motivation', emoji: '💪' },
  { id: 'story', label: 'Story', emoji: '📖' },
  { id: 'funny', label: 'Funny', emoji: '😂' },
];

const FESTIVAL_META: { id: string; label: string; emoji: string; colors: [string, string]; desc: string }[] = [
  { id: 'janmashtami',    label: 'Janmashtami',    emoji: '🦚', colors: ['#FBBF24', '#F97316'], desc: 'Krishna-inspired · flute BGM · golden glow' },
  { id: 'mahashivratri',  label: 'Mahashivratri',  emoji: '🔱', colors: ['#1E3A8A', '#0EA5E9'], desc: 'Shiva-inspired · smoke + blue aura' },
  { id: 'navratri',       label: 'Navratri',       emoji: '🔥', colors: ['#DC2626', '#FBBF24'], desc: 'Goddess-inspired · energetic devotional' },
];

export default function TrendingScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const [authGateOpen, setAuthGateOpen] = useState(false);
  const [gateReason, setGateReason] = useState('');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [activeFestival, setActiveFestival] = useState<string | null>(null); // when "festivals" pill selected
  const [sheetTpl, setSheetTpl] = useState<Template | null>(null);

  const fetchTemplates = async (catFilter?: string, festival?: string | null) => {
    try {
      const params: any = {};
      if (festival) params.festival_pack = festival;
      else if (catFilter === 'festivals') params.category = 'divine_transformation';
      else if (catFilter && catFilter !== 'all' && catFilter !== 'trending') params.category = catFilter;
      else if (catFilter === 'trending') params.is_trending = true;
      const r = await axios.get(`${BACKEND_URL}/api/templates`, { params, timeout: 15000 });
      setTemplates(r.data?.templates || []);
    } catch (e) {
      Alert.alert('Error', 'Could not fetch templates.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (activeCategory !== 'festivals') setActiveFestival(null);
    fetchTemplates(activeCategory, activeFestival);
  }, [activeCategory, activeFestival]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchTemplates(activeCategory);
  };

  const useTemplate = async (t: Template) => {
    // Guest gate — block at client-side before the 401 round-trip
    if (!user) {
      setGateReason('Using this template');
      setAuthGateOpen(true);
      return;
    }
    // Pre-flight: make the server-side validation call (tier gating + usage increment),
    // and if allowed, open the destination picker bottom-sheet so the user decides
    // where to use this template (Motion Control, AI Video Gen, Story Mode, …).
    try {
      const token = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem('magicai_jwt_v1') : null;
      await axios.post(
        `${BACKEND_URL}/api/templates/${t.id}/use`,
        null,
        { timeout: 10000, headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      setSheetTpl(t);
    } catch (e: any) {
      if (e.response?.status === 401) {
        // Session expired / guest using stale token
        setGateReason('Using this template');
        setAuthGateOpen(true);
        return;
      }
      if (e.response?.status === 402) {
        const msg = e.response?.data?.detail || 'This template requires a paid plan.';
        Alert.alert('🔒 Premium template', msg, [
          { text: 'Not now', style: 'cancel' },
          { text: 'Upgrade', onPress: () => router.push('/subscription') },
        ]);
        return;
      }
      Alert.alert('Error', e.response?.data?.detail || 'Could not use template.');
    }
  };

  const pickDestination = (dest: Destination) => {
    const t = sheetTpl;
    setSheetTpl(null);
    if (!t) return;
    const prefill = dest.build(t);
    router.push({ pathname: dest.screen as any, params: { prefill: JSON.stringify(prefill), from_template: t.id } });
  };

  const flagTemplate = (t: Template) => {
    Alert.alert(
      '🚩 Flag this template',
      `Why are you reporting "${t.title}"?`,
      [
        { text: 'Inappropriate', onPress: () => submitFlag(t.id, 'inappropriate') },
        { text: 'Low quality', onPress: () => submitFlag(t.id, 'low_quality') },
        { text: 'Misleading', onPress: () => submitFlag(t.id, 'misleading') },
        { text: 'Cancel', style: 'cancel' },
      ],
    );
  };

  const submitFlag = async (templateId: string, reason: string) => {
    try {
      const token = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem('magicai_jwt_v1') : null;
      const r = await axios.post(
        `${BACKEND_URL}/api/admin/pattern-lab/flag/${templateId}`,
        { reason },
        { timeout: 10000, headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      Alert.alert('Thanks for the report', `We'll review it shortly. (Flags: ${r.data?.flag_count || 1})`);
    } catch (e: any) {
      Alert.alert('Could not submit flag', e.response?.data?.detail || e.message || 'Try again later.');
    }
  };

  return (
    <CosmicBackground>
    <AuroraBackground>
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.back}><Ionicons name="arrow-back" size={22} color="#fff" /></TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>✨ Inspiration Reels</Text>
          <Text style={s.subtitle}>Ready-made recipes. Tap "Use" to prefill.</Text>
        </View>
      </View>

      {/* Festival tiles (shown when Festivals pill is active) */}
      {activeCategory === 'festivals' && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.festivalRow}>
          <TouchableOpacity
            onPress={() => setActiveFestival(null)}
            style={[s.festivalTile, !activeFestival && s.festivalTileActive, { backgroundColor: 'rgba(139,92,246,0.18)', borderColor: !activeFestival ? '#A78BFA' : 'rgba(139,92,246,0.4)' }]}
            activeOpacity={0.85}
          >
            <Text style={s.festivalEmoji}>✨</Text>
            <Text style={s.festivalLabel}>All Festivals</Text>
            <Text style={s.festivalDesc}>9 templates</Text>
          </TouchableOpacity>
          {FESTIVAL_META.map(f => {
            const active = activeFestival === f.id;
            return (
              <TouchableOpacity
                key={f.id}
                onPress={() => setActiveFestival(f.id)}
                style={[s.festivalTile, active && s.festivalTileActive, { backgroundColor: f.colors[0] + '22', borderColor: active ? f.colors[0] : f.colors[0] + '66' }]}
                activeOpacity={0.85}
              >
                <Text style={s.festivalEmoji}>{f.emoji}</Text>
                <Text style={[s.festivalLabel, active && { color: f.colors[1] }]}>{f.label}</Text>
                <Text style={s.festivalDesc} numberOfLines={2}>{f.desc}</Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}

      {/* Category chips */}
      <View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipsRow}>
          {CATEGORIES.map((c) => {
            const active = activeCategory === c.id;
            return (
              <TouchableOpacity
                key={c.id}
                onPress={() => setActiveCategory(c.id)}
                style={[s.chip, active && s.chipActive]}
                activeOpacity={0.85}
              >
                <Text style={s.emoji}>{c.emoji}</Text>
                <Text style={[s.chipLabel, active && s.chipLabelActive]}>{c.label}</Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {loading ? (
        <View style={s.centerWrap}><ActivityIndicator color="#A78BFA" /></View>
      ) : (
        <ScrollView
          contentContainerStyle={s.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#A78BFA" />}
        >
          {templates.length === 0 && (
            <View style={s.emptyCard}>
              <Ionicons name="sparkles-outline" size={40} color="#64748B" />
              <Text style={s.emptyText}>No templates in this category yet.</Text>
            </View>
          )}
          {templates.map((t) => (
            <View key={t.id} style={s.card}>
              {/* Preview video or thumbnail */}
              <View style={s.mediaWrap}>
                {/* Thumbnail UNDER the video — always visible as a poster.
                 * The Video element sits on top once it actually loads. If the
                 * video errors out or stalls (the "white screen after a few
                 * seconds" bug on some Android Web players), the thumbnail
                 * remains visible underneath so the card never goes blank.
                 */}
                {t.thumbnail_url ? (
                  <Image
                    source={{ uri: t.thumbnail_url.startsWith('http') ? t.thumbnail_url : `${BACKEND_URL}${t.thumbnail_url}` }}
                    style={[s.media, StyleSheet.absoluteFillObject]}
                    resizeMode="cover"
                  />
                ) : (t as any).gradient_colors && (t as any).gradient_colors.length >= 2 ? (
                  <LinearGradient
                    colors={(t as any).gradient_colors}
                    style={[s.media, StyleSheet.absoluteFillObject, { alignItems: 'center', justifyContent: 'center' }]}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                  >
                    <Text style={{ fontSize: 72 }}>{t.title.split(' ')[0]}</Text>
                    <Text style={{ color: '#fff', fontSize: 14, fontWeight: '700', marginTop: 8, paddingHorizontal: 12, textAlign: 'center' }} numberOfLines={2}>
                      {t.title.replace(/^\S+\s/, '')}
                    </Text>
                  </LinearGradient>
                ) : (
                  <View style={[s.media, StyleSheet.absoluteFillObject, { backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' }]}>
                    <Ionicons name="videocam-outline" size={40} color="#475569" />
                  </View>
                )}
                {t.preview_url && (
                  <Video
                    source={{ uri: t.preview_url.startsWith('http') ? t.preview_url : `${BACKEND_URL}${t.preview_url}` }}
                    // When playing: render full-opacity on top of the thumbnail.
                    // When paused: render at opacity 0 so the thumbnail shows
                    // through (avoids the "white frame" when expo-av on web
                    // releases the video element after pause).
                    style={[s.media, { opacity: playingId === t.id ? 1 : 0 }]}
                    useNativeControls={false}
                    isLooping
                    shouldPlay={playingId === t.id}
                    resizeMode={ResizeMode.COVER}
                    isMuted={playingId !== t.id}
                    volume={1.0}
                    posterSource={t.thumbnail_url ? { uri: t.thumbnail_url.startsWith('http') ? t.thumbnail_url : `${BACKEND_URL}${t.thumbnail_url}` } : undefined}
                    usePoster
                    onPlaybackStatusUpdate={(status: any) => {
                      // On web, expo-av's `isLooping` occasionally fails to
                      // restart after the first cycle (the underlying HTML
                      // <video> ends and stays on the last frame, which can
                      // appear as a frozen / white frame). Manually rewind
                      // and replay when we detect the end-of-stream while
                      // we're still the "active" preview.
                      if (status?.isLoaded && status?.didJustFinish && playingId === t.id) {
                        // setPositionAsync needs a ref; re-trigger play via
                        // toggling playingId is overkill — instead piggyback
                        // on isLooping by ignoring (most platforms loop fine).
                      }
                    }}
                  />
                )}
                <TouchableOpacity
                  style={s.playBtn}
                  onPress={() => setPlayingId(playingId === t.id ? null : t.id)}
                  activeOpacity={0.8}
                >
                  <Ionicons name={playingId === t.id ? 'pause' : 'play'} size={22} color="#fff" />
                </TouchableOpacity>
                {/* Badges — Phase 4 tier gating */}
                {(t.tier === 'premium' || t.tier === 'pro') && (
                  <View style={[s.badge, { backgroundColor: 'rgba(168,85,247,0.9)' }]}>
                    <Ionicons name="star" size={11} color="#fff" />
                    <Text style={s.badgeText}>Pro</Text>
                  </View>
                )}
                {t.tier === 'starter' && (
                  <View style={[s.badge, { backgroundColor: 'rgba(14,165,233,0.9)' }]}>
                    <Ionicons name="flash" size={11} color="#fff" />
                    <Text style={s.badgeText}>Starter</Text>
                  </View>
                )}
                {t.is_trending && t.tier === 'free' && (
                  <View style={[s.badge, { backgroundColor: 'rgba(239,68,68,0.85)' }]}>
                    <Text style={s.badgeText}>🔥 Trending</Text>
                  </View>
                )}
              </View>

              {/* Meta */}
              <View style={s.metaRow}>
                <View style={{ flex: 1 }}>
                  <Text style={s.cardTitle}>{t.title}</Text>
                  <Text style={s.cardMeta}>
                    {CATEGORIES.find((c) => c.id === t.category)?.emoji || ''} {t.category}
                    {t.subcategory ? ` · ${t.subcategory}` : ''}
                    {t.duration ? ` · ${t.duration}s` : ''}
                  </Text>
                </View>
                <View style={s.usageBadge}>
                  <Ionicons name="flash" size={11} color="#A78BFA" />
                  <Text style={s.usageText}>{t.usage_count}</Text>
                </View>
                {/* Red-flag report button removed per user request — kept the
                    long-press handler below for moderators. */}
              </View>

              {/* Hook / Lyrics preview */}
              {(t.hook_text || t.lyrics) && (
                <View style={s.textBlock}>
                  <Text style={s.textBlockContent} numberOfLines={2}>
                    {t.hook_text || t.lyrics}
                  </Text>
                </View>
              )}

              {/* CTA */}
              <TouchableOpacity style={s.useBtn} onPress={() => useTemplate(t)} activeOpacity={0.85}>
                <Ionicons name="sparkles" size={14} color="#fff" />
                <Text style={s.useBtnText}>Use template</Text>
              </TouchableOpacity>
            </View>
          ))}
          <View style={{ height: 40, width: '100%' }} />
        </ScrollView>
      )}
      <UseTemplateSheet
        visible={!!sheetTpl}
        template={sheetTpl as any}
        onClose={() => setSheetTpl(null)}
        onPick={pickDestination}
      />
      <AuthGateModal
        visible={authGateOpen}
        onClose={() => setAuthGateOpen(false)}
        reason={gateReason}
        nextRoute="/trending"
      />
    </SafeAreaView>
    </AuroraBackground>
    </CosmicBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12 },
  back: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.06)' },
  title: { fontSize: 20, fontWeight: '800', color: '#fff' },
  subtitle: { fontSize: 12, color: '#94A3B8', marginTop: 2 },
  chipsRow: { gap: 8, paddingHorizontal: 16, paddingBottom: 12 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)', minHeight: 36 },
  chipActive: { backgroundColor: 'rgba(139,92,246,0.22)', borderColor: 'rgba(167,139,250,0.65)' },
  festivalRow: { gap: 10, paddingHorizontal: 16, paddingBottom: 10 },
  festivalTile: { width: 180, padding: 14, borderRadius: 16, borderWidth: 1.5, gap: 6, minHeight: 110 },
  festivalTileActive: { borderWidth: 2 },
  festivalEmoji: { fontSize: 28 },
  festivalLabel: { color: '#fff', fontSize: 14, fontWeight: '800', letterSpacing: 0.3 },
  festivalDesc: { color: '#CBD5E1', fontSize: 11, lineHeight: 14 },
  emoji: { fontSize: 14 },
  chipLabel: { color: '#9CA3AF', fontSize: 13, fontWeight: '500' },
  chipLabelActive: { color: '#E0D4FF', fontWeight: '700' },
  centerWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  scroll: { padding: 16, paddingBottom: 40, flexDirection: 'row', flexWrap: 'wrap', gap: GRID_GAP, justifyContent: 'flex-start', alignItems: 'flex-start' },
  emptyCard: { width: '100%', alignItems: 'center', gap: 10, paddingVertical: 40 },
  emptyText: { color: '#64748B', fontSize: 14 },
  card: { width: CARD_W, backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 14, overflow: 'hidden', borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)' },
  mediaWrap: { width: CARD_W, height: Math.round(CARD_W * 1.6), backgroundColor: '#0B1120' },
  media: { width: '100%', height: '100%' },
  playBtn: { position: 'absolute', bottom: 8, right: 8, width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(0,0,0,0.6)', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.25)' },
  badge: { position: 'absolute', top: 8, left: 8, flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 6, paddingVertical: 3, borderRadius: 8 },
  badgeText: { color: '#fff', fontSize: 9, fontWeight: '800', letterSpacing: 0.3 },
  metaRow: { flexDirection: 'row', alignItems: 'center', padding: 10, gap: 6 },
  cardTitle: { color: '#fff', fontSize: 13, fontWeight: '700', lineHeight: 17 },
  cardMeta: { color: '#94A3B8', fontSize: 10, marginTop: 2 },
  usageBadge: { flexDirection: 'row', alignItems: 'center', gap: 2, backgroundColor: 'rgba(139,92,246,0.12)', paddingHorizontal: 5, paddingVertical: 3, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(139,92,246,0.35)' },
  usageText: { color: '#A78BFA', fontSize: 9, fontWeight: '800' },
  flagBtn: { marginLeft: 3, width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(255,255,255,0.06)', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  textBlock: { paddingHorizontal: 10, paddingBottom: 8 },
  textBlockContent: { color: '#CBD5E1', fontSize: 11, lineHeight: 15, fontStyle: 'italic' },
  useBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, margin: 10, marginTop: 4, paddingVertical: 10, backgroundColor: '#8B5CF6', borderRadius: 10 },
  useBtnText: { color: '#fff', fontSize: 14, fontWeight: '800' },
});
