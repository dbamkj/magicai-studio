/**
 * AI Prompt Selection — V2.0 ChatGPT-style wizard.
 *
 * User types an idea → we call POST /api/generate-prompts → show:
 *   • Auto-detected context pill (category · mood · voice · scenes)
 *   • 3 Glassmorphism prompt cards (title · hook · voice · music · duration · mood)
 *     each with "Preview" + "Use This" actions
 *   • "Regenerate" pill + quick-idea chips
 *
 * Pipeline:  Idea → /api/generate-prompts (GPT-4o-mini)
 *         → user picks one → navigate('/create-wizard', { prompt: ... })
 *         → Creative Plan → Pixabay + Sarvam + BGM → MP4
 */

import React, { useCallback, useMemo, useRef, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform, Alert, Pressable,
} from 'react-native';
import { router, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import Animated, {
  FadeIn, FadeInDown, FadeOut, Layout,
} from 'react-native-reanimated';
import AuroraBackground from '../src/AuroraBackground';
import * as theme from '../src/theme';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type Detected = {
  category: string;
  mood: string;
  suggested_voice: string;
  scene_keywords: string[];
};

type PromptOption = {
  id: string;
  title: string;
  hook: string;
  voice_type: string;
  music_type: string;
  duration: number;
  mood: string;
  style_tag: string;
  hashtags?: string[];
  cta?: string;
};

type Response = {
  detected: Detected;
  prompts: PromptOption[];
  cached: boolean;
  tokens_used: number;
  source: 'llm' | 'cache' | 'fallback';
};

const LANGS = ['english', 'hindi', 'hinglish', 'tamil', 'telugu', 'marathi'] as const;
type Lang = typeof LANGS[number];

const QUICK_IDEAS = [
  'Krishna bhajan devotional reel',
  'Monday motivation for busy professionals',
  'Funny office dialogue in Hinglish',
  'Diwali festival greeting reel',
  'POV: you find old family photos',
  'Travel vlog — Himalayan sunrise',
];

const STYLE_ICON: Record<string, string> = {
  cinematic: '🎬', handheld: '📱', aesthetic: '🎨',
  documentary: '🎥', meme: '🤣',
};

const MOOD_COLORS: Record<string, string> = {
  spiritual: '#A78BFA', emotional: '#EC4899', energetic: '#F59E0B',
  nostalgic: '#60A5FA', romantic: '#F87171', inspiring: '#34D399',
  playful: '#FBBF24', dramatic: '#F43F5E',
};

export default function AIPromptsScreen() {
  const [idea, setIdea] = useState('');
  const [language, setLanguage] = useState<Lang>('english');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Response | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastCallRef = useRef<string>('');

  const canSubmit = idea.trim().length >= 3 && !loading;

  const fetchPrompts = useCallback(
    async (opts?: { forceRefresh?: boolean }) => {
      const trimmed = idea.trim();
      if (trimmed.length < 3) {
        setError('Type at least 3 characters.');
        return;
      }
      const callId = `${trimmed}|${language}|${opts?.forceRefresh ? 'R' : ''}|${Date.now()}`;
      lastCallRef.current = callId;
      setLoading(true); setError(null); setSelectedId(null);
      try {
        const { data } = await axios.post<Response>(
          `${BACKEND_URL}/api/generate-prompts`,
          {
            idea: trimmed,
            language,
            aspect: '9:16',
            force_refresh: !!opts?.forceRefresh,
          },
          { timeout: 45000 },
        );
        if (lastCallRef.current !== callId) return;    // stale
        setResult(data);
      } catch (e: any) {
        if (lastCallRef.current !== callId) return;
        const msg = e?.response?.data?.detail?.message
          || e?.response?.data?.detail
          || e?.message
          || 'Failed to generate prompts.';
        setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
      } finally {
        if (lastCallRef.current === callId) setLoading(false);
      }
    },
    [idea, language],
  );

  const onUseThis = useCallback((p: PromptOption) => {
    setSelectedId(p.id);
    // Pass the picked prompt into the creative-plan wizard.
    // We round-trip via query params — keep payload small; full prompt lives in
    // AsyncStorage so downstream screens can lift it richly without URL bloat.
    (async () => {
      try {
        const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
        await AsyncStorage.setItem(
          'magicai_picked_prompt_v1',
          JSON.stringify({ idea: idea.trim(), language, prompt: p, detected: result?.detected }),
        );
      } catch {}
      router.push({
        pathname: '/create-wizard',
        params: { fromPrompt: '1', promptId: p.id, title: p.title.slice(0, 80) },
      });
    })();
  }, [idea, language, result]);

  const onPreview = useCallback((p: PromptOption) => {
    Alert.alert(
      p.title,
      `HOOK\n${p.hook}\n\nVOICE  ·  ${p.voice_type}\nMUSIC  ·  ${p.music_type}\nDURATION  ·  ${p.duration}s\nMOOD  ·  ${p.mood}\nSTYLE  ·  ${p.style_tag}${p.cta ? `\n\nCTA  ·  ${p.cta}` : ''}${p.hashtags?.length ? `\n\n${p.hashtags.join('  ')}` : ''}`,
      [{ text: 'Close', style: 'cancel' }, { text: 'Use this', onPress: () => onUseThis(p) }],
    );
  }, [onUseThis]);

  const aspectLabel = useMemo(() => '9:16 (Reel)', []);

  return (
    <View style={s.root}>
      <AuroraBackground />
      <Stack.Screen options={{ headerShown: false }} />

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={s.flex1}
      >
        <ScrollView
          contentContainerStyle={s.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <View style={s.header}>
            <TouchableOpacity
              onPress={() => router.back()}
              hitSlop={14}
              style={s.backBtn}
            >
              <Ionicons name="chevron-back" size={22} color="#fff" />
            </TouchableOpacity>
            <View style={s.headerMiddle}>
              <Text style={s.eyebrow}>AI PROMPT WIZARD</Text>
              <Text style={s.title}>What do you want to create?</Text>
            </View>
          </View>

          {/* Input card */}
          <View style={s.inputCard}>
            <Text style={s.lbl}>✨ Your idea</Text>
            <TextInput
              value={idea}
              onChangeText={setIdea}
              placeholder="e.g. Krishna bhajan devotional reel"
              placeholderTextColor={theme.text.faint}
              style={s.input}
              multiline
              maxLength={400}
              returnKeyType="default"
              autoCorrect
            />

            {/* Language row */}
            <Text style={s.lbl}>🗣️ Language</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={s.langRow}
              contentContainerStyle={s.langRowContent}
            >
              {LANGS.map((l) => (
                <Pressable
                  key={l}
                  onPress={() => setLanguage(l)}
                  style={[s.langPill, language === l && s.langPillActive]}
                >
                  <Text style={[s.langPillText, language === l && s.langPillTextActive]}>
                    {l}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>

            <View style={s.rowBetween}>
              <Text style={s.muted}>{idea.trim().length}/400 chars</Text>
              <Text style={s.muted}>Aspect · {aspectLabel}</Text>
            </View>

            <TouchableOpacity
              onPress={() => fetchPrompts()}
              disabled={!canSubmit}
              activeOpacity={0.85}
              style={[s.cta, !canSubmit && s.ctaDisabled]}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <>
                  <Ionicons name="sparkles" size={18} color="#fff" style={{ marginRight: 8 }} />
                  <Text style={s.ctaText}>
                    {result ? '🔁 Regenerate 3 ideas' : '✨ Get 3 AI Prompts'}
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          {/* Quick idea chips */}
          {!result && !loading && (
            <Animated.View entering={FadeIn.duration(300)} style={s.quickBlock}>
              <Text style={s.quickTitle}>Try one of these:</Text>
              <View style={s.quickRow}>
                {QUICK_IDEAS.map((q) => (
                  <Pressable
                    key={q}
                    onPress={() => { setIdea(q); }}
                    style={s.quickChip}
                  >
                    <Text style={s.quickChipText}>{q}</Text>
                  </Pressable>
                ))}
              </View>
            </Animated.View>
          )}

          {/* Error banner */}
          {error && (
            <Animated.View entering={FadeInDown.duration(200)} style={s.errorBanner}>
              <Ionicons name="alert-circle" size={16} color="#FCA5A5" />
              <Text style={s.errorText}>{error}</Text>
            </Animated.View>
          )}

          {/* Loading skeleton */}
          {loading && (
            <Animated.View entering={FadeIn} exiting={FadeOut} style={s.loadingBlock}>
              <ActivityIndicator size="large" color={theme.aurora.pink} />
              <Text style={s.loadingText}>AI is crafting 3 prompt options…</Text>
              <Text style={s.loadingSub}>Analyzing category · mood · voice · scenes</Text>
            </Animated.View>
          )}

          {/* Detected context */}
          {result && !loading && (
            <Animated.View
              entering={FadeInDown.springify().damping(18)}
              layout={Layout}
              style={s.detectedCard}
            >
              <View style={s.detectedHeaderRow}>
                <Text style={s.detectedEyebrow}>
                  {result.cached ? '⚡ INSTANT (cached)' : `🧠 AI DETECTED · ${result.tokens_used} tokens`}
                </Text>
                <TouchableOpacity
                  onPress={() => fetchPrompts({ forceRefresh: true })}
                  disabled={loading}
                  style={s.regenPill}
                >
                  <Ionicons name="refresh" size={14} color="#fff" />
                  <Text style={s.regenPillText}>regenerate</Text>
                </TouchableOpacity>
              </View>
              <View style={s.detectedRow}>
                <InfoPill icon="🏷️" label={result.detected.category} />
                <InfoPill
                  icon="💫"
                  label={result.detected.mood}
                  color={MOOD_COLORS[result.detected.mood]}
                />
                <InfoPill icon="🎙️" label={result.detected.suggested_voice} />
              </View>
              <Text style={s.sceneKw}>
                Scene ideas: {result.detected.scene_keywords.join(' · ')}
              </Text>
            </Animated.View>
          )}

          {/* 3 Prompt cards */}
          {result && !loading && result.prompts.map((p, idx) => (
            <Animated.View
              key={p.id}
              entering={FadeInDown.delay(idx * 120).springify().damping(16)}
              layout={Layout}
              style={[
                s.promptCard,
                selectedId === p.id && s.promptCardSelected,
              ]}
            >
              <View style={s.promptHeader}>
                <View style={s.promptBadgeWrap}>
                  <Text style={s.promptBadge}>Option {idx + 1}</Text>
                </View>
                <Text style={s.promptStyle}>
                  {STYLE_ICON[p.style_tag] || '🎬'} {p.style_tag}
                </Text>
                <Text style={s.promptDuration}>{p.duration}s</Text>
              </View>

              <Text style={s.promptTitle}>{p.title}</Text>
              <Text style={s.promptHook}>“{p.hook}”</Text>

              <View style={s.metaGrid}>
                <MetaChip icon="🎙️" label="Voice" value={p.voice_type} />
                <MetaChip icon="🎵" label="Music" value={p.music_type} />
                <MetaChip
                  icon="💫"
                  label="Mood"
                  value={p.mood}
                  color={MOOD_COLORS[p.mood]}
                />
              </View>

              {p.hashtags && p.hashtags.length > 0 && (
                <Text style={s.hashtags}>
                  {p.hashtags.slice(0, 4).join('  ')}
                </Text>
              )}

              <View style={s.promptActions}>
                <TouchableOpacity
                  onPress={() => onPreview(p)}
                  style={s.previewBtn}
                  activeOpacity={0.8}
                >
                  <Ionicons name="eye-outline" size={16} color={theme.text.primary} />
                  <Text style={s.previewBtnText}>Preview</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() => onUseThis(p)}
                  style={s.useBtn}
                  activeOpacity={0.85}
                >
                  <Text style={s.useBtnText}>Use this ✨</Text>
                </TouchableOpacity>
              </View>
            </Animated.View>
          ))}

          {/* Footer hint */}
          {result && !loading && (
            <Text style={s.footerHint}>
              Not what you wanted? Edit your idea above & regenerate.
            </Text>
          )}

          <View style={{ height: 80 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

// ────────────────────────────── Sub-components ──────────────────────────────

function InfoPill({ icon, label, color }: { icon: string; label: string; color?: string }) {
  return (
    <View
      style={[
        s.infoPill,
        color ? { borderColor: `${color}55`, backgroundColor: `${color}22` } : null,
      ]}
    >
      <Text style={s.infoPillIcon}>{icon}</Text>
      <Text style={[s.infoPillText, color ? { color } : null]} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

function MetaChip({
  icon, label, value, color,
}: { icon: string; label: string; value: string; color?: string }) {
  return (
    <View style={s.metaChip}>
      <Text style={s.metaIcon}>{icon}</Text>
      <View style={s.flex1}>
        <Text style={s.metaLabel}>{label}</Text>
        <Text
          style={[s.metaValue, color ? { color } : null]}
          numberOfLines={1}
        >
          {value}
        </Text>
      </View>
    </View>
  );
}

// ────────────────────────────── Styles ──────────────────────────────────────

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.aurora.bg0 },
  flex1: { flex: 1 },
  scroll: {
    paddingTop: Platform.select({ ios: 64, android: 40, default: 32 }),
    paddingBottom: 40,
    paddingHorizontal: theme.space.md,
  },

  header: { flexDirection: 'row', alignItems: 'center', marginBottom: theme.space.lg, gap: theme.space.md },
  backBtn: {
    width: 40, height: 40, borderRadius: theme.radius.pill,
    backgroundColor: theme.glass.background,
    borderWidth: 1, borderColor: theme.glass.border,
    alignItems: 'center', justifyContent: 'center',
  },
  headerMiddle: { flex: 1 },
  eyebrow: {
    color: theme.aurora.orange, fontSize: 11, fontWeight: '800',
    letterSpacing: 1.5, marginBottom: 4,
  },
  title: {
    color: theme.text.primary, fontSize: 22, fontWeight: '800', lineHeight: 28,
  },

  inputCard: {
    backgroundColor: theme.glass.backgroundStrong,
    borderRadius: theme.radius.xl,
    borderWidth: 1, borderColor: theme.glass.border,
    padding: theme.space.md,
    marginBottom: theme.space.md,
    gap: theme.space.sm,
  },
  lbl: { color: theme.text.secondary, fontSize: 13, fontWeight: '700' },
  input: {
    backgroundColor: 'rgba(0,0,0,0.25)',
    borderRadius: theme.radius.lg,
    borderWidth: 1, borderColor: theme.glass.border,
    padding: theme.space.md,
    color: theme.text.primary, fontSize: 16,
    minHeight: 80, textAlignVertical: 'top',
  },

  langRow: { maxHeight: 44 },
  langRowContent: { gap: 8, paddingVertical: 4 },
  langPill: {
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.glass.background,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  langPillActive: {
    backgroundColor: `${theme.aurora.pink}33`,
    borderColor: theme.aurora.pink,
  },
  langPillText: { color: theme.text.muted, fontSize: 12, fontWeight: '700', textTransform: 'capitalize' },
  langPillTextActive: { color: '#fff' },

  rowBetween: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginTop: theme.space.xs,
  },
  muted: { color: theme.text.muted, fontSize: 11 },

  cta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: theme.aurora.pink,
    borderRadius: theme.radius.pill,
    paddingVertical: 14,
    marginTop: theme.space.sm,
    ...(theme.shadow.glow as any),
  },
  ctaDisabled: { opacity: 0.5 },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '800' },

  quickBlock: { marginBottom: theme.space.md },
  quickTitle: {
    color: theme.text.muted, fontSize: 12, fontWeight: '700',
    textTransform: 'uppercase', letterSpacing: 1,
    marginBottom: theme.space.sm, marginLeft: 4,
  },
  quickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  quickChip: {
    paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  quickChipText: { color: theme.text.secondary, fontSize: 12, fontWeight: '600' },

  errorBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: 'rgba(252,165,165,0.12)',
    borderWidth: 1, borderColor: 'rgba(252,165,165,0.35)',
    borderRadius: theme.radius.md,
    padding: 10, marginBottom: theme.space.sm,
  },
  errorText: { color: '#FCA5A5', fontSize: 13, flex: 1 },

  loadingBlock: { alignItems: 'center', paddingVertical: 40, gap: 10 },
  loadingText: { color: theme.text.primary, fontSize: 15, fontWeight: '700', marginTop: 6 },
  loadingSub: { color: theme.text.muted, fontSize: 12 },

  detectedCard: {
    backgroundColor: theme.glass.backgroundStrong,
    borderRadius: theme.radius.lg,
    borderWidth: 1, borderColor: `${theme.aurora.orange}55`,
    padding: theme.space.md,
    marginBottom: theme.space.md,
  },
  detectedHeaderRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: theme.space.sm,
  },
  detectedEyebrow: {
    color: theme.aurora.orange, fontSize: 10, fontWeight: '800', letterSpacing: 1.2,
  },
  regenPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  regenPillText: { color: '#fff', fontSize: 11, fontWeight: '700' },

  detectedRow: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8,
    marginBottom: theme.space.sm,
  },
  infoPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
    maxWidth: 180,
  },
  infoPillIcon: { fontSize: 12 },
  infoPillText: { color: theme.text.primary, fontSize: 12, fontWeight: '700' },
  sceneKw: { color: theme.text.muted, fontSize: 12, lineHeight: 18 },

  promptCard: {
    backgroundColor: theme.glass.backgroundStrong,
    borderRadius: theme.radius.xl,
    borderWidth: 1, borderColor: theme.glass.border,
    padding: theme.space.md,
    marginBottom: theme.space.md,
    ...(theme.shadow.soft as any),
  },
  promptCardSelected: {
    borderColor: theme.aurora.pink, borderWidth: 2,
  },
  promptHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginBottom: theme.space.sm,
  },
  promptBadgeWrap: {
    paddingHorizontal: 10, paddingVertical: 4,
    backgroundColor: `${theme.aurora.pink}33`,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: `${theme.aurora.pink}77`,
  },
  promptBadge: { color: '#fff', fontSize: 11, fontWeight: '800', letterSpacing: 0.8 },
  promptStyle: { color: theme.text.secondary, fontSize: 12, fontWeight: '600', textTransform: 'capitalize' },
  promptDuration: {
    marginLeft: 'auto',
    color: theme.aurora.orange, fontSize: 13, fontWeight: '800',
  },
  promptTitle: { color: theme.text.primary, fontSize: 18, fontWeight: '800', lineHeight: 24, marginBottom: 6 },
  promptHook: { color: theme.text.secondary, fontSize: 14, fontStyle: 'italic', lineHeight: 20, marginBottom: theme.space.sm },

  metaGrid: { flexDirection: 'row', gap: 8, marginBottom: theme.space.sm },
  metaChip: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 8,
    backgroundColor: 'rgba(0,0,0,0.2)',
    borderRadius: theme.radius.md,
    minWidth: 0,
  },
  metaIcon: { fontSize: 14 },
  metaLabel: { color: theme.text.faint, fontSize: 10, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8 },
  metaValue: { color: theme.text.primary, fontSize: 12, fontWeight: '700' },

  hashtags: { color: theme.aurora.blue, fontSize: 11, fontWeight: '700', marginBottom: theme.space.sm, letterSpacing: 0.3 },

  promptActions: { flexDirection: 'row', gap: 10, marginTop: 4 },
  previewBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 11,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  previewBtnText: { color: theme.text.primary, fontSize: 14, fontWeight: '700' },
  useBtn: {
    flex: 1.2, alignItems: 'center', justifyContent: 'center',
    paddingVertical: 11,
    backgroundColor: theme.aurora.pink,
    borderRadius: theme.radius.pill,
    ...(theme.shadow.glow as any),
  },
  useBtnText: { color: '#fff', fontSize: 14, fontWeight: '800' },

  footerHint: {
    color: theme.text.faint, fontSize: 12, textAlign: 'center',
    marginTop: theme.space.sm, marginBottom: theme.space.md,
  },
});
