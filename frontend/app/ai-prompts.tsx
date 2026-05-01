/**
 * AI Prompts — V2.0 True Chat Architecture (Phase C+ & C++).
 *
 * Hybrid ChatGPT-style conversation surface:
 *   • Scrollable message list (FlatList) — each generation = a new turn
 *     (user idea bubble + AI reply containing detected-context card + 3
 *     prompt option cards stacked vertically inside the same bubble).
 *   • Fixed bottom composer with: language picker, style boost toggles
 *     (Emotional / Cinematic), Send button, suggestion chips on empty.
 *   • Debounce auto-fire: if the user pauses typing 800ms with ≥ 12 chars,
 *     we auto-call /api/generate-prompts (cache + LRU keep this cheap).
 *   • Skeleton loading bubble while LLM is thinking.
 *   • "Recommended" badge on the highest-scored prompt option.
 *   • Per-prompt "Preview" plays a 2-sec Sarvam TTS hook clip via expo-av.
 *   • 429 rate-limit → inline AI bubble with reset time + Upgrade CTA.
 *
 * Picking a prompt → write `mp_template_prefill` → push /create-wizard.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, KeyboardAvoidingView, Platform, Pressable,
  FlatList, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import Animated, {
  FadeIn, FadeInDown, FadeOut,
  useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming,
} from 'react-native-reanimated';
import { Audio } from 'expo-av';
import AuroraBackground from '../src/AuroraBackground';
import * as theme from '../src/theme';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

// ─── Types ─────────────────────────────────────────────────────────────────

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
  score?: number;
};

type StyleBoost = 'default' | 'emotional' | 'cinematic';

type RateLimit = {
  used: number;
  limit: number;
  remaining: number;
  reset_at: string;
  blocked?: boolean;
  retry_after_s?: number;
  tier?: string;
};

type ApiSuccess = {
  detected: Detected;
  prompts: PromptOption[];
  cached: boolean;
  tokens_used: number;
  source: 'llm' | 'cache' | 'fallback';
  style_boost: StyleBoost;
  rate_limit: RateLimit;
};

type Lang = 'english' | 'hindi' | 'hinglish' | 'tamil' | 'telugu' | 'marathi';
const LANGS: Lang[] = ['english', 'hindi', 'hinglish', 'tamil', 'telugu', 'marathi'];

// User turn: the idea they sent
// AI turn: result | loading | error | rate_limited
type UserMsg = {
  id: string;
  role: 'user';
  text: string;
  language: Lang;
  style_boost: StyleBoost;
  ts: number;
};

type AiMsg = {
  id: string;
  role: 'ai';
  ts: number;
  status: 'loading' | 'success' | 'error' | 'rate_limited' | 'welcome';
  // success
  detected?: Detected;
  prompts?: PromptOption[];
  source?: 'llm' | 'cache' | 'fallback';
  tokens_used?: number;
  style_boost?: StyleBoost;
  // error
  error?: string;
  // rate_limited
  rate_limit?: RateLimit;
  // ref to the user turn
  parentUserId?: string;
};

type ChatMsg = UserMsg | AiMsg;

// ─── Constants ─────────────────────────────────────────────────────────────

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

const DEBOUNCE_MS = 800;
const MIN_AUTO_FIRE_LEN = 12;

// ─── Mappers (LLM-free fields → existing pipeline IDs) ─────────────────────

function mapVoiceToId(voiceType: string, language: string): string {
  const v = (voiceType || '').toLowerCase();
  const isFemale = /female|anushka|manisha|vidya|jenny|inspiring_female|confident_female|gentle_female|enthusiastic_female/.test(v);
  const lang = (language || 'english').toLowerCase();
  if (['hindi', 'hinglish', 'tamil', 'telugu', 'marathi'].includes(lang)) {
    if (v.includes('warm') || v.includes('calm') || v.includes('storyteller'))
      return isFemale ? 'sarvam:manisha' : 'sarvam:meera';
    if (v.includes('energetic') || v.includes('confident'))
      return isFemale ? 'sarvam:anushka' : 'sarvam:arvind';
    return isFemale ? 'sarvam:manisha' : 'sarvam:meera';
  }
  if (v.includes('warm') || v.includes('calm') || v.includes('storyteller'))
    return isFemale ? 'en-US-JennyNeural' : 'en-US-GuyNeural';
  if (v.includes('energetic') || v.includes('confident'))
    return isFemale ? 'en-US-AriaNeural' : 'en-US-ChristopherNeural';
  return isFemale ? 'en-US-JennyNeural' : 'en-US-GuyNeural';
}

function mapMusicToMood(musicType: string): string {
  const m = (musicType || '').toLowerCase();
  if (m.includes('sacred') || m.includes('devotional') || m.includes('bhajan'))  return 'devotional_peaceful';
  if (m.includes('cinematic') || m.includes('orchestral') || m.includes('epic')) return 'cinematic_epic';
  if (m.includes('upbeat') || m.includes('energetic') || m.includes('electronic')) return 'upbeat_pop';
  if (m.includes('lofi') || m.includes('aesthetic') || m.includes('chill'))      return 'aesthetic_lofi';
  if (m.includes('emotional') || m.includes('melodic') || m.includes('soft'))    return 'emotional_piano';
  if (m.includes('inspirational') || m.includes('uplifting'))                    return 'inspirational_ambient';
  return 'cinematic_epic';
}

function mapStyleToMotion(styleTag: string): string {
  const s = (styleTag || '').toLowerCase();
  if (s === 'cinematic' || s === 'documentary') return 'smooth_pan';
  if (s === 'handheld' || s === 'meme')         return 'handheld';
  if (s === 'aesthetic')                         return 'slow_zoom';
  return 'auto';
}

function formatRelativeReset(iso?: string): string {
  if (!iso) return 'shortly';
  try {
    const dt = new Date(iso);
    const now = new Date();
    const diffMs = dt.getTime() - now.getTime();
    if (diffMs <= 0) return 'now';
    const m = Math.ceil(diffMs / 60000);
    if (m < 60) return `in ~${m} min`;
    const h = Math.ceil(m / 60);
    return `in ~${h}h`;
  } catch {
    return 'shortly';
  }
}

// Tiny pure-JS base64 encoder for native fallback when btoa is missing.
const B64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function encodeBase64(input: string): string {
  let out = '';
  let i = 0;
  while (i < input.length) {
    const c1 = input.charCodeAt(i++) & 0xff;
    const c2 = input.charCodeAt(i++) & 0xff;
    const c3 = input.charCodeAt(i++) & 0xff;
    const e1 = c1 >> 2;
    const e2 = ((c1 & 3) << 4) | (c2 >> 4);
    const e3 = ((c2 & 15) << 2) | (c3 >> 6);
    const e4 = c3 & 63;
    out += B64_CHARS[e1] + B64_CHARS[e2];
    out += i - 1 > input.length ? '=' : B64_CHARS[e3];
    out += i > input.length ? '=' : B64_CHARS[e4];
  }
  return out;
}

// ─── Screen ────────────────────────────────────────────────────────────────

export default function AIPromptsScreen() {
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      id: 'welcome',
      role: 'ai',
      ts: Date.now(),
      status: 'welcome',
    },
  ]);
  const [input, setInput] = useState('');
  const [language, setLanguage] = useState<Lang>('english');
  const [styleBoost, setStyleBoost] = useState<StyleBoost>('default');
  const [isLoading, setIsLoading] = useState(false);

  const scrollRef = useRef<ScrollView>(null);
  const lastCallRef = useRef<string>('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Audio preview (singleton) ──
  const soundRef = useRef<Audio.Sound | null>(null);
  const [playingPromptId, setPlayingPromptId] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (soundRef.current) {
        soundRef.current.unloadAsync().catch(() => {});
      }
    };
  }, []);

  // Audio session config (iOS) — speakers, no recording.
  useEffect(() => {
    Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      staysActiveInBackground: false,
      shouldDuckAndroid: true,
    }).catch(() => {});
  }, []);

  const scrollToEnd = useCallback(() => {
    // Only scroll when there are actual conversation messages, not just
    // the welcome bubble. Otherwise the ScrollView's auto-scroll on web
    // would shift the entire page down by hundreds of pixels.
    if (messages.length <= 1) return;
    requestAnimationFrame(() => {
      scrollRef.current?.scrollToEnd({ animated: true });
    });
  }, [messages.length]);

  // ── Send turn ─────────────────────────────────────────────────────────
  const sendTurn = useCallback(
    async (rawIdea: string, opts?: { forceRefresh?: boolean; isAuto?: boolean }) => {
      const idea = rawIdea.trim();
      if (idea.length < 3) return;

      const userId = `u_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const aiId = `a_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const callKey = `${idea}|${language}|${styleBoost}|${opts?.forceRefresh ? 'R' : ''}`;
      lastCallRef.current = callKey;

      setMessages((prev) => [
        // Drop stale loading bubbles from prior auto-fire so we never stack
        ...prev.filter((m) => !(m.role === 'ai' && m.status === 'loading')),
        {
          id: userId, role: 'user', text: idea, language, style_boost: styleBoost,
          ts: Date.now(),
        } as UserMsg,
        {
          id: aiId, role: 'ai', status: 'loading',
          ts: Date.now(), parentUserId: userId,
        } as AiMsg,
      ]);
      setIsLoading(true);
      scrollToEnd();

      try {
        const { data } = await axios.post<ApiSuccess>(
          `${BACKEND_URL}/api/generate-prompts`,
          {
            idea, language, aspect: '9:16',
            style_boost: styleBoost,
            force_refresh: !!opts?.forceRefresh,
          },
          { timeout: 45000 },
        );

        // Stale-call guard — if the user has sent a newer turn, ignore this
        if (lastCallRef.current !== callKey) return;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiId
              ? ({
                  ...m,
                  status: 'success',
                  detected: data.detected,
                  prompts: data.prompts,
                  source: data.source,
                  tokens_used: data.tokens_used,
                  style_boost: data.style_boost,
                  rate_limit: data.rate_limit,
                } as AiMsg)
              : m,
          ),
        );
      } catch (e: any) {
        if (lastCallRef.current !== callKey) return;
        const status = e?.response?.status;
        const detail = e?.response?.data?.detail;

        if (status === 429 && detail && typeof detail === 'object') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiId
                ? ({
                    ...m,
                    status: 'rate_limited',
                    rate_limit: detail.rate_limit,
                    error: detail.message || 'Rate limit reached.',
                  } as AiMsg)
                : m,
            ),
          );
        } else {
          const msg =
            (typeof detail === 'string' ? detail : detail?.message)
            || e?.message
            || 'Failed to generate prompts.';
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiId
                ? ({ ...m, status: 'error', error: typeof msg === 'string' ? msg : JSON.stringify(msg) } as AiMsg)
                : m,
            ),
          );
        }
      } finally {
        if (lastCallRef.current === callKey) setIsLoading(false);
        scrollToEnd();
      }
    },
    [language, styleBoost, scrollToEnd],
  );

  // ── Debounce auto-fire (Phase C+ #2) ─────────────────────────────────
  const scheduleAutoFire = useCallback(
    (text: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      const t = text.trim();
      if (t.length < MIN_AUTO_FIRE_LEN) return;
      debounceRef.current = setTimeout(() => {
        // Only auto-fire if user hasn't already sent this exact idea this session
        const alreadySent = messages.some(
          (m) => m.role === 'user' && (m as UserMsg).text === t,
        );
        if (!alreadySent && !isLoading) {
          sendTurn(t, { isAuto: true });
        }
      }, DEBOUNCE_MS);
    },
    [messages, isLoading, sendTurn],
  );

  const onChangeIdea = useCallback(
    (txt: string) => {
      setInput(txt);
      scheduleAutoFire(txt);
    },
    [scheduleAutoFire],
  );

  const onSend = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const t = input.trim();
    if (!t) return;
    sendTurn(t);
    setInput('');
  }, [input, sendTurn]);

  const onRegenerate = useCallback(
    (idea: string) => {
      sendTurn(idea, { forceRefresh: true });
    },
    [sendTurn],
  );

  // ── Pick "Use this" ──────────────────────────────────────────────────
  const onUseThis = useCallback(
    async (p: PromptOption, ideaText: string, det?: Detected) => {
      try {
        const prefill = {
          id: `aiprompt_${p.id}_${Date.now()}`,
          title: p.title,
          tagline: p.hook,
          idea: ideaText,
          script: p.hook || ideaText,
          image_query:
            (det?.scene_keywords || []).slice(0, 3).join(' ') || p.title,
          mode: 'video',
          total_duration: Math.max(10, Math.min(30, p.duration || 20)),
          voice_id: mapVoiceToId(p.voice_type, language),
          voice_style: 'story',
          music_mood: mapMusicToMood(p.music_type),
          motion: mapStyleToMotion(p.style_tag),
          aspect_ratio: '9:16',
          lang: language,
          ai_prompt_meta: {
            prompt_id: p.id,
            hook: p.hook,
            mood: p.mood,
            style_tag: p.style_tag,
            hashtags: p.hashtags || [],
            cta: p.cta || '',
            detected_category: det?.category || '',
            detected_mood: det?.mood || '',
            style_boost: styleBoost,
          },
        };
        try {
          if (typeof window !== 'undefined' && (window as any).sessionStorage) {
            (window as any).sessionStorage.setItem(
              'mp_template_prefill', JSON.stringify(prefill),
            );
          }
        } catch {}
        try {
          const { default: AsyncStorage } = await import(
            '@react-native-async-storage/async-storage'
          );
          await AsyncStorage.setItem(
            'magicai_picked_prompt_v1',
            JSON.stringify({ idea: ideaText, language, prompt: p, detected: det, prefill }),
          );
        } catch {}
      } catch {}
      router.push({
        pathname: '/create-wizard',
        params: { fromPrompt: '1', promptId: p.id },
      });
    },
    [language, styleBoost],
  );

  // ── Audio preview (Phase C+ #6) ──────────────────────────────────────
  const onPreview = useCallback(
    async (p: PromptOption) => {
      try {
        // If something is playing — stop it
        if (soundRef.current) {
          try { await soundRef.current.unloadAsync(); } catch {}
          soundRef.current = null;
        }
        if (playingPromptId === p.id) {
          setPlayingPromptId(null);
          return;
        }
        setPlayingPromptId(p.id);
        const base = (BACKEND_URL || '').replace(/\/$/, '');
        // Native expo-av can play remote URIs directly. We POST to fetch the
        // mp3, but expo-av doesn't support POST — so use a fetch+blob URI on
        // web, and a temp-file approach on native via base64 data URI.
        const resp = await fetch(`${base}/api/generate-prompts/preview-audio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: p.hook || p.title || 'Hello from MagiCAi',
            voice_type: p.voice_type,
            language,
            max_seconds: 2.5,
          }),
        });
        if (!resp.ok) throw new Error(`tts ${resp.status}`);
        const buf = await resp.arrayBuffer();

        let uri: string;
        if (Platform.OS === 'web') {
          const blob = new Blob([buf], { type: 'audio/mpeg' });
          uri = URL.createObjectURL(blob);
        } else {
          // base64 data URI for native (small clip — fine inline)
          const bytes = new Uint8Array(buf);
          let bin = '';
          for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
          // btoa is available on Hermes/JSC; fall back to a tiny pure-JS encoder otherwise.
          const b64 = (typeof btoa === 'function') ? btoa(bin) : encodeBase64(bin);
          uri = `data:audio/mpeg;base64,${b64}`;
        }

        const { sound } = await Audio.Sound.createAsync(
          { uri },
          { shouldPlay: true, volume: 1.0 },
        );
        soundRef.current = sound;
        sound.setOnPlaybackStatusUpdate((status) => {
          if (!status.isLoaded) return;
          if (status.didJustFinish) {
            setPlayingPromptId(null);
            sound.unloadAsync().catch(() => {});
            soundRef.current = null;
          }
        });
      } catch (e) {
        setPlayingPromptId(null);
        soundRef.current = null;
        // soft-fail — not worth a big modal
      }
    },
    [language, playingPromptId],
  );

  // ── Pick suggestion (welcome) ────────────────────────────────────────
  const onPickSuggestion = useCallback(
    (s: string) => {
      setInput('');
      sendTurn(s);
    },
    [sendTurn],
  );

  // Highest-scored prompt id within an AI message — for "Recommended" badge
  const recommendedIdFor = useCallback((m: AiMsg) => {
    if (!m.prompts || m.prompts.length === 0) return null;
    const sorted = [...m.prompts].sort(
      (a, b) => (b.score ?? 0) - (a.score ?? 0),
    );
    return sorted[0].id;
  }, []);

  // ── Renderers ─────────────────────────────────────────────────────────
  const renderItem = useCallback(
    ({ item, index }: { item: ChatMsg; index: number }) => {
      if (item.role === 'user') {
        return <UserBubble msg={item} />;
      }
      // AI bubble
      const ai = item;
      const parentUser = ai.parentUserId
        ? (messages.find((m) => m.id === ai.parentUserId) as UserMsg | undefined)
        : undefined;
      const ideaText = parentUser?.text || '';
      const recId = recommendedIdFor(ai);

      return (
        <AiBubble
          msg={ai}
          recommendedId={recId}
          onUseThis={(p) => onUseThis(p, ideaText, ai.detected)}
          onPreview={onPreview}
          playingPromptId={playingPromptId}
          onRegenerate={() => onRegenerate(ideaText)}
          onPickSuggestion={onPickSuggestion}
          onUpgrade={() => router.push('/subscription')}
          isLast={index === messages.length - 1}
        />
      );
    },
    [
      messages,
      onUseThis,
      onPreview,
      playingPromptId,
      onRegenerate,
      onPickSuggestion,
      recommendedIdFor,
    ],
  );

  const aspectLabel = useMemo(() => '9:16 · Reel', []);

  return (
    <View style={s.root}>
      <AuroraBackground absolute />

      <SafeAreaView style={s.flex1} edges={['top', 'left', 'right']}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={s.flex1}
          keyboardVerticalOffset={0}
        >
        {/* Header */}
        <View style={s.header}>
          <TouchableOpacity
            onPress={() => router.back()}
            hitSlop={14}
            style={s.iconBtn}
          >
            <Ionicons name="chevron-back" size={22} color="#fff" />
          </TouchableOpacity>
          <View style={s.headerMiddle}>
            <Text style={s.eyebrow}>AI PROMPT WIZARD · CHAT</Text>
            <Text style={s.title}>What do you want to create?</Text>
          </View>
          <TouchableOpacity
            onPress={() => {
              setMessages([{ id: 'welcome', role: 'ai', ts: Date.now(), status: 'welcome' }]);
              setInput('');
            }}
            hitSlop={14}
            style={s.iconBtn}
          >
            <Ionicons name="refresh-outline" size={20} color="#fff" />
          </TouchableOpacity>
        </View>

        {/* Message list — ScrollView so content always anchors at TOP and
             grows downward, no flex tricks needed. Reliable on iOS/Android/web. */}
        <ScrollView
          ref={scrollRef}
          style={s.flex1}
          contentContainerStyle={s.listContent}
          showsVerticalScrollIndicator={false}
          onContentSizeChange={scrollToEnd}
          keyboardShouldPersistTaps="handled"
        >
          {messages.map((m, idx) => (
            <View key={m.id}>
              {renderItem({ item: m, index: idx })}
            </View>
          ))}
        </ScrollView>

        {/* Bottom composer */}
        <View style={s.composerWrap}>
          {/* Style boost row */}
          <View style={s.boostRow}>
            <BoostChip
              label="Default"
              icon="sparkles-outline"
              active={styleBoost === 'default'}
              onPress={() => setStyleBoost('default')}
            />
            <BoostChip
              label="Emotional"
              icon="heart-outline"
              active={styleBoost === 'emotional'}
              onPress={() => setStyleBoost('emotional')}
              activeColor={theme.aurora.pink}
            />
            <BoostChip
              label="Cinematic"
              icon="film-outline"
              active={styleBoost === 'cinematic'}
              onPress={() => setStyleBoost('cinematic')}
              activeColor={theme.aurora.purple}
            />
            <View style={s.boostSpacer} />
            <Text style={s.aspectLabel}>{aspectLabel}</Text>
          </View>

          {/* Language picker (compact horizontal) */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={s.langStrip}
            contentContainerStyle={s.langStripContent}
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

          {/* Input row */}
          <View style={s.composer}>
            <TextInput
              value={input}
              onChangeText={onChangeIdea}
              placeholder="Type your idea… (auto-suggests after 800ms)"
              placeholderTextColor={theme.text.faint}
              style={s.composerInput}
              multiline
              maxLength={400}
              onSubmitEditing={onSend}
              blurOnSubmit={false}
            />
            <TouchableOpacity
              onPress={onSend}
              disabled={input.trim().length < 3 || isLoading}
              activeOpacity={0.85}
              style={[
                s.sendBtn,
                (input.trim().length < 3 || isLoading) && s.sendBtnDisabled,
              ]}
            >
              {isLoading ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Ionicons name="arrow-up" size={20} color="#fff" />
              )}
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
        </SafeAreaView>
      </View>
  );
}

// ─── Components ────────────────────────────────────────────────────────────

function UserBubble({ msg }: { msg: UserMsg }) {
  return (
    <Animated.View entering={FadeInDown.duration(220)} style={s.userRow}>
      <View style={s.userBubble}>
        <Text style={s.userText}>{msg.text}</Text>
        {msg.style_boost && msg.style_boost !== 'default' ? (
          <View style={s.userMetaRow}>
            <Text style={s.userMetaText}>
              {msg.style_boost === 'emotional' ? '❤️ emotional' : '🎬 cinematic'}
              {' · '}{msg.language}
            </Text>
          </View>
        ) : (
          <Text style={s.userMetaText}>{msg.language}</Text>
        )}
      </View>
      <View style={s.avatarUser}>
        <Text style={s.avatarUserText}>YOU</Text>
      </View>
    </Animated.View>
  );
}

type AiBubbleProps = {
  msg: AiMsg;
  recommendedId: string | null;
  onUseThis: (p: PromptOption) => void;
  onPreview: (p: PromptOption) => void;
  playingPromptId: string | null;
  onRegenerate: () => void;
  onPickSuggestion: (s: string) => void;
  onUpgrade: () => void;
  isLast: boolean;
};

function AiBubble({
  msg, recommendedId, onUseThis, onPreview, playingPromptId,
  onRegenerate, onPickSuggestion, onUpgrade,
}: AiBubbleProps) {
  return (
    <Animated.View entering={FadeInDown.duration(280)} style={s.aiRow}>
      <View style={s.avatarAI}>
        <Ionicons name="sparkles" size={14} color="#fff" />
      </View>
      <View style={s.aiBubble}>
        {msg.status === 'welcome' && <WelcomeBlock onPick={onPickSuggestion} />}

        {msg.status === 'loading' && <LoadingBlock />}

        {msg.status === 'error' && (
          <View>
            <Text style={s.aiText}>
              ⚠️ {msg.error || 'Something went wrong.'}
            </Text>
            <Pressable onPress={onRegenerate} style={s.regenChip}>
              <Ionicons name="refresh" size={13} color="#fff" />
              <Text style={s.regenChipText}>Try again</Text>
            </Pressable>
          </View>
        )}

        {msg.status === 'rate_limited' && (
          <RateLimitBlock msg={msg} onUpgrade={onUpgrade} />
        )}

        {msg.status === 'success' && msg.detected && msg.prompts && (
          <SuccessBlock
            msg={msg}
            recommendedId={recommendedId}
            onUseThis={onUseThis}
            onPreview={onPreview}
            playingPromptId={playingPromptId}
            onRegenerate={onRegenerate}
          />
        )}
      </View>
    </Animated.View>
  );
}

function WelcomeBlock({ onPick }: { onPick: (s: string) => void }) {
  return (
    <View>
      <Text style={s.aiText}>
        Hi 👋 I'm your AI creative producer. Type any idea and I'll craft 3
        ready-to-shoot reel concepts — voice, music, mood and all.
      </Text>
      <Text style={s.aiSubtle}>Try one of these to start:</Text>
      <View style={s.suggestionsWrap}>
        {QUICK_IDEAS.map((q) => (
          <Pressable key={q} onPress={() => onPick(q)} style={s.suggestionChip}>
            <Text style={s.suggestionChipText}>{q}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function LoadingBlock() {
  return (
    <View>
      <View style={s.loadingHeader}>
        <TypingDots />
        <Text style={s.aiSubtleInline}>Crafting 3 prompt options…</Text>
      </View>
      {/* 3 skeleton cards */}
      <SkeletonCard delay={0} />
      <SkeletonCard delay={120} />
      <SkeletonCard delay={240} />
    </View>
  );
}

function RateLimitBlock({ msg, onUpgrade }: { msg: AiMsg; onUpgrade: () => void }) {
  const reset = formatRelativeReset(msg.rate_limit?.reset_at);
  const used = msg.rate_limit?.used ?? 0;
  const limit = msg.rate_limit?.limit ?? 20;
  return (
    <View>
      <Text style={s.aiText}>
        🚦 You've hit your hourly limit ({used}/{limit} ideas). Resets {reset}.
      </Text>
      <Text style={s.aiSubtle}>
        Want unlimited ideas, faster renders & no watermark? Upgrade to Pro.
      </Text>
      <View style={s.rateActions}>
        <Pressable onPress={onUpgrade} style={s.upgradeBtn}>
          <Ionicons name="star" size={14} color="#fff" />
          <Text style={s.upgradeBtnText}>Upgrade</Text>
        </Pressable>
      </View>
    </View>
  );
}

function SuccessBlock({
  msg, recommendedId, onUseThis, onPreview, playingPromptId, onRegenerate,
}: {
  msg: AiMsg;
  recommendedId: string | null;
  onUseThis: (p: PromptOption) => void;
  onPreview: (p: PromptOption) => void;
  playingPromptId: string | null;
  onRegenerate: () => void;
}) {
  const det = msg.detected!;
  const cached = msg.source === 'cache';
  return (
    <View>
      <View style={s.detectedHeader}>
        <Text style={s.detectedEyebrow}>
          {cached ? '⚡ INSTANT' : `🧠 AI · ${msg.tokens_used ?? 0} tok`}
          {msg.style_boost && msg.style_boost !== 'default'
            ? ` · ${msg.style_boost === 'emotional' ? '❤️ emotional' : '🎬 cinematic'}`
            : ''}
        </Text>
        <Pressable onPress={onRegenerate} hitSlop={8} style={s.regenChip}>
          <Ionicons name="refresh" size={13} color="#fff" />
          <Text style={s.regenChipText}>regenerate</Text>
        </Pressable>
      </View>

      <View style={s.detectedRow}>
        <InfoPill icon="🏷️" label={det.category} />
        <InfoPill
          icon="💫"
          label={det.mood}
          color={MOOD_COLORS[det.mood]}
        />
        <InfoPill icon="🎙️" label={det.suggested_voice} />
      </View>
      <Text style={s.sceneKw}>
        Scene ideas: {det.scene_keywords.join(' · ')}
      </Text>

      {msg.prompts!.map((p, idx) => (
        <PromptCard
          key={p.id}
          p={p}
          idx={idx}
          isRecommended={recommendedId === p.id}
          onUse={() => onUseThis(p)}
          onPreview={() => onPreview(p)}
          isPlaying={playingPromptId === p.id}
        />
      ))}
    </View>
  );
}

function PromptCard({
  p, idx, isRecommended, onUse, onPreview, isPlaying,
}: {
  p: PromptOption; idx: number; isRecommended: boolean;
  onUse: () => void; onPreview: () => void; isPlaying: boolean;
}) {
  return (
    <Animated.View
      entering={FadeInDown.delay(idx * 90).duration(280)}
      style={[s.promptCard, isRecommended && s.promptCardRecommended]}
    >
      {isRecommended && (
        <View style={s.recommendedBadge}>
          <Ionicons name="star" size={11} color="#fff" />
          <Text style={s.recommendedBadgeText}>RECOMMENDED</Text>
        </View>
      )}

      <View style={s.promptHeader}>
        <View style={s.optionPill}>
          <Text style={s.optionPillText}>Option {idx + 1}</Text>
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
          onPress={onPreview}
          style={s.previewBtn}
          activeOpacity={0.85}
        >
          {isPlaying ? (
            <Ionicons name="stop" size={15} color={theme.text.primary} />
          ) : (
            <Ionicons name="play" size={15} color={theme.text.primary} />
          )}
          <Text style={s.previewBtnText}>
            {isPlaying ? 'Stop' : 'Preview'}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={onUse}
          style={s.useBtn}
          activeOpacity={0.85}
        >
          <Text style={s.useBtnText}>Use this ✨</Text>
        </TouchableOpacity>
      </View>
    </Animated.View>
  );
}

// ─── Tiny components ───────────────────────────────────────────────────────

function BoostChip({
  label, icon, active, onPress, activeColor,
}: {
  label: string; icon: any; active: boolean;
  onPress: () => void; activeColor?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        s.boostChip,
        active && {
          backgroundColor: `${activeColor || theme.aurora.orange}25`,
          borderColor: activeColor || theme.aurora.orange,
        },
      ]}
    >
      <Ionicons name={icon} size={13} color={active ? '#fff' : theme.text.muted} />
      <Text style={[s.boostChipText, active && { color: '#fff', fontWeight: '800' }]}>
        {label}
      </Text>
    </Pressable>
  );
}

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
      <View style={{ flex: 1, minWidth: 0 }}>
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

function TypingDots() {
  const d1 = useSharedValue(0.35);
  const d2 = useSharedValue(0.35);
  const d3 = useSharedValue(0.35);

  useEffect(() => {
    const cfg = { duration: 360 };
    d1.value = withRepeat(withSequence(withTiming(1, cfg), withTiming(0.35, cfg)), -1);
    d2.value = withRepeat(withSequence(
      withTiming(0.35, cfg), withTiming(1, cfg), withTiming(0.35, cfg),
    ), -1);
    d3.value = withRepeat(withSequence(
      withTiming(0.35, cfg), withTiming(0.35, cfg),
      withTiming(1, cfg), withTiming(0.35, cfg),
    ), -1);
  }, [d1, d2, d3]);

  const s1 = useAnimatedStyle(() => ({ opacity: d1.value, transform: [{ scale: 0.8 + d1.value * 0.4 }] }));
  const s2 = useAnimatedStyle(() => ({ opacity: d2.value, transform: [{ scale: 0.8 + d2.value * 0.4 }] }));
  const s3 = useAnimatedStyle(() => ({ opacity: d3.value, transform: [{ scale: 0.8 + d3.value * 0.4 }] }));

  return (
    <View style={s.typingDotsRow}>
      <Animated.View style={[s.typingDot, s1]} />
      <Animated.View style={[s.typingDot, s2]} />
      <Animated.View style={[s.typingDot, s3]} />
    </View>
  );
}

function SkeletonCard({ delay }: { delay: number }) {
  const o = useSharedValue(0.4);
  useEffect(() => {
    const cfg = { duration: 1100 };
    o.value = withRepeat(
      withSequence(withTiming(0.85, cfg), withTiming(0.4, cfg)),
      -1,
    );
  }, [o]);
  const animStyle = useAnimatedStyle(() => ({ opacity: o.value }));

  return (
    <Animated.View
      entering={FadeIn.delay(delay).duration(220)}
      style={s.skeletonCard}
    >
      <Animated.View style={[s.skeletonLine, { width: '40%' }, animStyle]} />
      <Animated.View style={[s.skeletonLine, { width: '88%', height: 18 }, animStyle]} />
      <Animated.View style={[s.skeletonLine, { width: '70%', height: 14 }, animStyle]} />
      <View style={s.skeletonRow}>
        <Animated.View style={[s.skeletonChip, animStyle]} />
        <Animated.View style={[s.skeletonChip, animStyle]} />
        <Animated.View style={[s.skeletonChip, animStyle]} />
      </View>
    </Animated.View>
  );
}

// ─── Styles ────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.aurora.bg0 },
  flex1: { flex: 1 },

  /* Header */
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingTop: Platform.select({ ios: 56, android: 36, default: 28 }),
    paddingHorizontal: theme.space.md,
    paddingBottom: theme.space.sm,
    gap: theme.space.sm,
  },
  iconBtn: {
    width: 38, height: 38, borderRadius: theme.radius.pill,
    backgroundColor: theme.glass.background,
    borderWidth: 1, borderColor: theme.glass.border,
    alignItems: 'center', justifyContent: 'center',
  },
  headerMiddle: { flex: 1 },
  eyebrow: {
    color: theme.aurora.orange, fontSize: 10, fontWeight: '800',
    letterSpacing: 1.2, marginBottom: 2,
  },
  title: {
    color: theme.text.primary, fontSize: 18, fontWeight: '800', lineHeight: 22,
  },

  /* List */
  listContent: {
    flexGrow: 1,
    paddingHorizontal: theme.space.md,
    paddingBottom: theme.space.md,
    gap: theme.space.sm,
  },

  /* User bubble */
  userRow: {
    flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'flex-end',
    gap: 8, marginVertical: 6,
  },
  userBubble: {
    maxWidth: '78%',
    backgroundColor: `${theme.aurora.orange}1F`,
    borderWidth: 1, borderColor: `${theme.aurora.orange}66`,
    borderRadius: theme.radius.lg,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14, paddingVertical: 10,
  },
  userText: { color: theme.text.primary, fontSize: 14, lineHeight: 20, fontWeight: '600' },
  userMetaRow: { marginTop: 4 },
  userMetaText: { color: theme.text.muted, fontSize: 10, fontWeight: '600', marginTop: 4, textTransform: 'capitalize' },
  avatarUser: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: theme.aurora.orange,
    alignItems: 'center', justifyContent: 'center',
  },
  avatarUserText: { color: '#fff', fontSize: 8, fontWeight: '800', letterSpacing: 0.5 },

  /* AI bubble */
  aiRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    marginVertical: 6,
  },
  avatarAI: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: theme.aurora.pink,
    alignItems: 'center', justifyContent: 'center',
    marginTop: 2,
  },
  aiBubble: {
    flex: 1,
    backgroundColor: theme.glass.backgroundStrong,
    borderWidth: 1, borderColor: theme.glass.borderStrong,
    borderRadius: theme.radius.lg,
    borderTopLeftRadius: 4,
    paddingHorizontal: 14, paddingVertical: 12,
  },
  aiText: { color: theme.text.primary, fontSize: 14, lineHeight: 20, fontWeight: '500' },
  aiSubtle: { color: theme.text.muted, fontSize: 12, marginTop: 8, fontStyle: 'italic' },
  aiSubtleInline: { color: theme.text.muted, fontSize: 13, fontWeight: '600' },

  loadingHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: theme.space.sm },
  typingDotsRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  typingDot: {
    width: 6, height: 6, borderRadius: 999, backgroundColor: theme.aurora.pink,
  },

  /* Welcome */
  suggestionsWrap: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8,
  },
  suggestionChip: {
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  suggestionChipText: { color: theme.text.secondary, fontSize: 11, fontWeight: '600' },

  /* Error / Rate-limited */
  regenChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 5,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
    alignSelf: 'flex-start', marginTop: 8,
  },
  regenChipText: { color: '#fff', fontSize: 11, fontWeight: '700' },

  rateActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  upgradeBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 9,
    backgroundColor: theme.aurora.pink,
    borderRadius: theme.radius.pill,
  },
  upgradeBtnText: { color: '#fff', fontSize: 13, fontWeight: '800' },

  /* Detected */
  detectedHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: theme.space.sm,
  },
  detectedEyebrow: {
    color: theme.aurora.orange, fontSize: 10, fontWeight: '800', letterSpacing: 1,
  },
  detectedRow: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6,
  },
  infoPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 5,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
    maxWidth: 200,
  },
  infoPillIcon: { fontSize: 11 },
  infoPillText: { color: theme.text.primary, fontSize: 11, fontWeight: '700' },
  sceneKw: { color: theme.text.muted, fontSize: 11, lineHeight: 16, marginBottom: theme.space.sm },

  /* Prompt cards */
  promptCard: {
    backgroundColor: 'rgba(0,0,0,0.18)',
    borderRadius: theme.radius.lg,
    borderWidth: 1, borderColor: theme.glass.border,
    padding: 12,
    marginTop: theme.space.sm,
  },
  promptCardRecommended: {
    borderColor: theme.aurora.orange,
    borderWidth: 1.5,
    backgroundColor: `${theme.aurora.orange}10`,
  },
  recommendedBadge: {
    position: 'absolute', top: -10, left: 12,
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3,
    backgroundColor: theme.aurora.orange,
    borderRadius: theme.radius.pill,
    zIndex: 5,
  },
  recommendedBadgeText: { color: '#fff', fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },

  promptHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginBottom: 6,
  },
  optionPill: {
    paddingHorizontal: 8, paddingVertical: 3,
    backgroundColor: `${theme.aurora.pink}33`,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: `${theme.aurora.pink}77`,
  },
  optionPillText: { color: '#fff', fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
  promptStyle: { color: theme.text.secondary, fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  promptDuration: { marginLeft: 'auto', color: theme.aurora.orange, fontSize: 12, fontWeight: '800' },

  promptTitle: { color: theme.text.primary, fontSize: 15, fontWeight: '800', lineHeight: 20, marginBottom: 4 },
  promptHook: { color: theme.text.secondary, fontSize: 13, fontStyle: 'italic', lineHeight: 18, marginBottom: 8 },

  metaGrid: { flexDirection: 'row', gap: 6, marginBottom: 8 },
  metaChip: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 8, paddingVertical: 6,
    backgroundColor: 'rgba(0,0,0,0.25)',
    borderRadius: theme.radius.md,
    minWidth: 0,
  },
  metaIcon: { fontSize: 12 },
  metaLabel: { color: theme.text.faint, fontSize: 9, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  metaValue: { color: theme.text.primary, fontSize: 11, fontWeight: '700' },

  hashtags: { color: theme.aurora.blue, fontSize: 10, fontWeight: '700', marginBottom: 8, letterSpacing: 0.3 },

  promptActions: { flexDirection: 'row', gap: 8 },
  previewBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 9,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  previewBtnText: { color: theme.text.primary, fontSize: 13, fontWeight: '700' },
  useBtn: {
    flex: 1.2, alignItems: 'center', justifyContent: 'center',
    paddingVertical: 9,
    backgroundColor: theme.aurora.pink,
    borderRadius: theme.radius.pill,
  },
  useBtnText: { color: '#fff', fontSize: 13, fontWeight: '800' },

  /* Skeleton */
  skeletonCard: {
    backgroundColor: 'rgba(0,0,0,0.18)',
    borderRadius: theme.radius.lg,
    borderWidth: 1, borderColor: theme.glass.border,
    padding: 12, marginTop: theme.space.sm,
    gap: 8,
  },
  skeletonLine: {
    height: 12, borderRadius: 6,
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  skeletonRow: { flexDirection: 'row', gap: 6 },
  skeletonChip: {
    flex: 1, height: 28, borderRadius: theme.radius.md,
    backgroundColor: 'rgba(255,255,255,0.08)',
  },

  /* Composer */
  composerWrap: {
    paddingHorizontal: theme.space.md,
    paddingTop: theme.space.sm,
    paddingBottom: Platform.select({ ios: theme.space.lg, android: theme.space.md, default: theme.space.md }) as number,
    backgroundColor: 'rgba(15,12,41,0.85)',
    borderTopWidth: 1, borderTopColor: theme.glass.border,
  },
  boostRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  boostSpacer: { flex: 1 },
  aspectLabel: { color: theme.text.muted, fontSize: 10, fontWeight: '700' },

  boostChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: theme.glass.background,
    borderRadius: theme.radius.pill,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  boostChipText: { color: theme.text.muted, fontSize: 11, fontWeight: '700' },

  langStrip: { maxHeight: 36, marginBottom: 6 },
  langStripContent: { gap: 6, paddingVertical: 2 },
  langPill: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.glass.background,
    borderWidth: 1, borderColor: theme.glass.border,
  },
  langPillActive: {
    backgroundColor: `${theme.aurora.pink}33`,
    borderColor: theme.aurora.pink,
  },
  langPillText: { color: theme.text.muted, fontSize: 11, fontWeight: '700', textTransform: 'capitalize' },
  langPillTextActive: { color: '#fff' },

  composer: {
    flexDirection: 'row', alignItems: 'flex-end', gap: 8,
  },
  composerInput: {
    flex: 1,
    minHeight: 44, maxHeight: 120,
    backgroundColor: 'rgba(0,0,0,0.30)',
    borderRadius: theme.radius.lg,
    borderWidth: 1, borderColor: theme.glass.border,
    paddingHorizontal: 14, paddingVertical: 10,
    color: theme.text.primary, fontSize: 14,
    textAlignVertical: 'top',
  },
  sendBtn: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: theme.aurora.pink,
    alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.45 },
});
