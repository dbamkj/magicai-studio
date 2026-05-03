/**
 * AI Avatar Studio — 6-step unified wizard.
 *
 * Merges the legacy cartoon-avatar + talking-avatar flows into one polished
 * experience:
 *
 *   Step 1  Pick category (Indian / Funny / Spiritual / Influencer)
 *   Step 2  Pick avatar style (filtered by category, shows tagline + PRO lock)
 *   Step 3  Enter idea + language toggle (English / Hindi / Hinglish) + suggestions
 *   Step 4  AI-generated dialogue options — pick one
 *   Step 5  Personality-matched voice + early audio preview (Sarvam TTS)
 *   Step 6  Upload photo + Generate → cartoonize → create-talking-avatar → video
 *
 * The goal: "I made a talking avatar video in seconds."
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  Image, TextInput, Alert, Platform, KeyboardAvoidingView, Pressable,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { Audio } from 'expo-av';
import { Video, ResizeMode } from 'expo-av';

import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { useAuth } from '../src/AuthContext';
import AuthGateModal from '../src/components/AuthGateModal';
import { uploadImageFile } from '../src/uploadHelper';
import { Chip, GlassCard, GradientButton, GhostButton, FieldLabel } from '../src/ui';
import VoicePicker from '../src/VoicePicker';
import VoiceStylePicker from '../src/VoiceStylePicker';
import MotionPicker from '../src/MotionPicker';
import ResolutionPicker from '../src/ResolutionPicker';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;

// ────────────────────────── Types ──────────────────────────
type Style = {
  id: string;
  label: string;
  icon: string;
  tagline: string;
  premium: boolean;
  category: string;
  personality: {
    voice_id: string;
    voice_style: string;
    mood: string;
    bgm_style: string;
    tone: string;
  };
};

type Category = { id: string; label: string; icon: string };

type Dialogue = { id: string; text: string; tone: string };

type Language = 'english' | 'hindi' | 'hinglish';

// 4 idea-starters — one per category so they feel contextually relevant.
const IDEA_SUGGESTIONS: Record<string, string[]> = {
  indian: [
    'Happy Diwali wishes for my family',
    'Funny daily-life moment in Mumbai',
    'Cricket World Cup victory celebration',
    'Bollywood-style dramatic reveal',
  ],
  funny: [
    'Monday morning office meme',
    'When your code finally works',
    'Explaining memes to your parents',
    'Relatable gym-day struggle',
  ],
  spiritual: [
    'Morning gratitude reflection',
    'Divine blessings for a loved one',
    'Krishna leela short story',
    'Festival of lights spiritual message',
  ],
  influencer: [
    'Motivate my team before a big launch',
    '3 productivity hacks in 20 seconds',
    'Greet my subscribers on 100k milestone',
    'Product launch teaser — mysterious',
  ],
};

const LANG_OPTIONS: { id: Language; label: string }[] = [
  { id: 'english', label: 'English' },
  { id: 'hindi', label: 'हिंदी' },
  { id: 'hinglish', label: 'Hinglish' },
];

// Emotion chips — common to BOTH Cartoon and Talking modes (issue #2).
// These IDs match the EMOTIONS keys in /api/avatar (backend).
const EMOTION_CHIPS: { id: string; label: string; icon: string }[] = [
  { id: 'happy',      label: 'Happy',      icon: '😊' },
  { id: 'excited',    label: 'Excited',    icon: '🤩' },
  { id: 'confident',  label: 'Confident',  icon: '😎' },
  { id: 'playful',    label: 'Playful',    icon: '😋' },
  { id: 'mysterious', label: 'Mysterious', icon: '🕶️' },
  { id: 'peaceful',   label: 'Peaceful',   icon: '🧘' },
  { id: 'devotional', label: 'Devotional', icon: '🙏' },
  { id: 'fierce',     label: 'Fierce',     icon: '🔥' },
];

// ────────────────────────── Screen ──────────────────────────
export default function AvatarStudioScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const insets = useSafeAreaInsets();
  const userIsPro = !!user && (user.subscription_tier || 'free') !== 'free';

  const [showAuthGate, setShowAuthGate] = useState(false);
  const requireLogin = (): boolean => {
    if (!user) { setShowAuthGate(true); return false; }
    return true;
  };

  // ── Mode toggle (Cartoon vs Talking). Drives whether we cartoonize the
  // uploaded photo before lip-syncing, and which step machine renders.
  const [mode, setMode] = useState<'cartoon' | 'talking'>('cartoon');

  // ── Common — emotion + talking-mode field state ──
  // Issue #2: emotion is shared across both modes, picked right after style.
  const [emotion, setEmotion] = useState<string>('happy');
  // Issue #1: legacy talking-avatar fields restored for the Talking branch.
  const [tkVoiceId, setTkVoiceId]     = useState<string>('hi-IN-SwaraNeural');
  const [tkVoiceStyle, setTkVoiceStyle] = useState<string | null>(null);
  const [tkVoiceRate, setTkVoiceRate]   = useState<string | null>(null);
  const [tkVoicePitch, setTkVoicePitch] = useState<string | null>(null);
  const [tkMotion, setTkMotion]         = useState<string>('none');
  const [tkAspect, setTkAspect]         = useState<string>('9:16');
  const [tkRes, setTkRes]               = useState<string>('720p');

  // ── step 0..5 (zero-indexed) ──
  const [step, setStep] = useState(0);

  // ── step 1: styles ──
  const [styles, setStyles] = useState<Style[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState<string>('indian');
  const [styleId, setStyleId] = useState<string | null>(null);
  const [loadingStyles, setLoadingStyles] = useState(true);

  // ── step 2: idea + language ──
  const [idea, setIdea] = useState('');
  const [language, setLanguage] = useState<Language>('english');

  // ── step 3: dialogues ──
  const [dialogues, setDialogues] = useState<Dialogue[]>([]);
  const [dialogueId, setDialogueId] = useState<string | null>(null);
  const [loadingDialogues, setLoadingDialogues] = useState(false);
  const [dialogueErr, setDialogueErr] = useState<string | null>(null);

  // ── Dynamic idea suggestions — fetched when style/emotion/language changes.
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // ── step 4: voice + preview audio ──
  // Cartoon mode auto-matches the voice to the picked style, but the user
  // can override it before previewing (Issue from Session 25 cart4.jpeg).
  // `cartoonVoiceId === null` means "use the style default"; setting it to
  // a string selects an explicit Edge/Sarvam voice.
  const [cartoonVoiceId, setCartoonVoiceId] = useState<string | null>(null);
  const [cartoonVoiceStyle, setCartoonVoiceStyle] = useState<string | undefined>(undefined);
  const [audioBusy, setAudioBusy] = useState(false);
  const audioRef = useRef<Audio.Sound | null>(null);

  // ── step 5: image + generate ──
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  // Manual script — used in Talking mode OR as an override in Cartoon mode.
  const [manualScript, setManualScript] = useState('');
  const [generating, setGenerating] = useState(false);
  // Issue #6 — 5 cartoon variants picker. When the user opts in, we kick
  // off 5 parallel /api/avatar/cartoonize calls (one per emotion) and let
  // them pick the result they like best before generating the video.
  type Variant = { id: string; emotion: string; jobId?: string; status: 'pending' | 'completed' | 'failed'; imageUrl?: string; localPath?: string; error?: string };
  const [variants, setVariants] = useState<Variant[]>([]);
  const [variantsBusy, setVariantsBusy] = useState(false);
  const [pickedVariantPath, setPickedVariantPath] = useState<string | null>(null);

  // ── Phase 2a — dual-speaker (split-screen) state ──
  // `dualMode === null` means the user hasn't picked solo or dual yet, which
  // gates the auto dialogue fetch on Step 3 (per Session 25 round 5 feedback —
  // "do not generate the dialogues unless user does not chooses the mode").
  const [dualMode, setDualMode] = useState<boolean | null>(null);
  const [genderA, setGenderA] = useState<'male' | 'female' | 'neutral'>('neutral');
  const [genderB, setGenderB] = useState<'male' | 'female' | 'neutral'>('neutral');
  const [voiceAId, setVoiceAId] = useState<string>('en-US-JennyNeural');
  const [voiceBId, setVoiceBId] = useState<string>('en-US-GuyNeural');
  const [imageAUri, setImageAUri] = useState<string | null>(null);
  const [imageAPath, setImageAPath] = useState<string | null>(null);
  const [imageBUri, setImageBUri] = useState<string | null>(null);
  const [imageBPath, setImageBPath] = useState<string | null>(null);

  // ── Phase 2b (b3 hybrid) — AI-generated character variants ──
  // 4-card grid on Step 5 (dual mode). Each card polls its Nano-Banana
  // job; user taps one to "adopt" that image as imageAPath/imageBPath.
  type VariantJob = {
    job_id: string;
    role: 'A' | 'B';
    gender: 'male' | 'female' | 'neutral';
    status: 'queued' | 'processing' | 'completed' | 'failed';
    image_url?: string | null;
    error?: string | null;
  };
  const [variantJobs, setVariantJobs] = useState<VariantJob[]>([]);
  const [variantsKicking, setVariantsKicking] = useState(false);
  const [variantErr, setVariantErr] = useState<string | null>(null);
  const [pickedVariantA, setPickedVariantA] = useState<string | null>(null);
  const [pickedVariantB, setPickedVariantB] = useState<string | null>(null);

  // Round 11 — optional BGM style. null = no BGM (legacy default).
  // Maps directly to the backend bgm_style field on talking-avatar +
  // dual-lipsync request bodies. Catalog moods: cinematic_epic |
  // devotional | playful | motivational.
  const [bgmStyle, setBgmStyle] = useState<
    null | 'cinematic_epic' | 'devotional' | 'playful' | 'motivational'
  >(null);
  const BGM_OPTIONS: { id: typeof bgmStyle; label: string; icon: any }[] = [
    { id: null,                 label: 'No BGM',        icon: 'volume-mute-outline' },
    { id: 'cinematic_epic',     label: 'Cinematic',     icon: 'film-outline' },
    { id: 'devotional',         label: 'Devotional',    icon: 'leaf-outline' },
    { id: 'playful',            label: 'Playful',       icon: 'happy-outline' },
    { id: 'motivational',       label: 'Motivational',  icon: 'flash-outline' },
  ];
  const [inferBusy, setInferBusy] = useState(false);
  const [genStage, setGenStage] = useState<string>('');
  const [genProgress, setGenProgress] = useState(0);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultError, setResultError] = useState<string>('');
  const pollRef = useRef<any>(null);

  // ────────────────────────── Derived ──────────────────────────
  const activeStyle = styles.find(s => s.id === styleId) || null;
  const filteredStyles = styles.filter(s => s.category === categoryId);
  const pickedDialogue = dialogues.find(d => d.id === dialogueId) || null;

  // ────────────────────────── Load styles once ──────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API}/avatar/styles`, { timeout: 12000 });
        const ss: Style[] = r.data?.styles || [];
        setStyles(ss);
        setCategories(r.data?.categories || []);
        // auto-pick first free style in default category
        const firstFree = ss.find(s => s.category === 'indian' && !s.premium);
        if (firstFree) setStyleId(firstFree.id);
      } catch (e) {
        console.warn('avatar-studio: styles load failed', e);
      } finally {
        setLoadingStyles(false);
      }
    })();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      (async () => {
        try { if (audioRef.current) await audioRef.current.unloadAsync(); } catch {}
      })();
    };
  }, []);

  // Reset cartoon voice override whenever the user picks a different style —
  // a voice tuned for "Krishna" shouldn't carry over to "Comedian", etc.
  // Also clear stale dialogues so the user never sees a previous style's
  // dialogues "cached" on a fresh wizard run (Session 25 round 6 feedback).
  useEffect(() => {
    setCartoonVoiceId(null);
    setCartoonVoiceStyle(undefined);
    setDialogues([]);
    setDialogueId(null);
  }, [styleId]);

  // Same stale-dialogues guard for language + idea changes.
  useEffect(() => {
    setDialogues([]);
    setDialogueId(null);
  }, [language, idea]);

  // ────────────────────────── Dynamic idea suggestions (Issue #1) ──────────────────────────
  // Refetches whenever the user changes avatar style, emotion or language.
  // Debounced so rapid chip toggling doesn't spam the LLM.
  useEffect(() => {
    if (!styleId) return;
    let cancelled = false;
    const t = setTimeout(async () => {
      setLoadingSuggestions(true);
      try {
        const r = await axios.post(`${API}/avatar/suggestions`, {
          style_id: styleId,
          emotion,
          language,
        }, { timeout: 20000 });
        if (!cancelled) setSuggestions(r.data?.suggestions || []);
      } catch {
        // Fallback to static per-category if backend unreachable.
        if (!cancelled) setSuggestions(IDEA_SUGGESTIONS[categoryId] || []);
      } finally {
        if (!cancelled) setLoadingSuggestions(false);
      }
    }, 450);
    return () => { cancelled = true; clearTimeout(t); };
  }, [styleId, emotion, language, categoryId]);

  // ────────────────────────── Fetch dialogues ──────────────────────────
  // The backend caches by (style|idea|lang|count|emotion|mode|nonce). Passing
  // a fresh nonce per click guarantees the LLM is invoked again so the
  // "Regenerate options" button actually produces NEW dialogues rather
  // than returning the same cached batch.
  const fetchDialogues = useCallback(async (opts?: { force?: boolean }) => {
    if (!styleId || !idea.trim()) return;
    setLoadingDialogues(true); setDialogueErr(null); setDialogueId(null);
    try {
      const r = await axios.post(`${API}/avatar/dialogues`, {
        style_id: styleId,
        idea: idea.trim(),
        language,
        emotion,
        count: 3,
        mode: dualMode ? 'dual' : 'solo',
        // Always pass a nonce so the cache becomes a per-request bucket.
        // If `force=true` we add an extra random component for safety.
        nonce: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}${opts?.force ? '_f' : ''}`,
      }, { timeout: 45000 });
      const dlg: Dialogue[] = r.data?.dialogues || [];
      setDialogues(dlg);
      if (dlg.length) setDialogueId(dlg[0].id);
    } catch (e: any) {
      setDialogueErr(e?.response?.data?.detail || e?.message || 'Could not generate dialogues.');
    } finally {
      setLoadingDialogues(false);
    }
  }, [styleId, idea, language, emotion, dualMode]);

  // Auto-refetch dialogues when the user toggles solo↔dual on Step 3.
  // Also acts as the FIRST trigger — Step 3 starts empty (dualMode=null)
  // and the user MUST pick a mode to generate dialogues.
  useEffect(() => {
    if (dualMode === null) return;            // mode not yet chosen — wait
    if (step === 2 && styleId && idea.trim()) fetchDialogues();
  }, [dualMode]); // eslint-disable-line react-hooks/exhaustive-deps

  // ────────────────────────── Audio preview ──────────────────────────
  const playAudioPreview = useCallback(async () => {
    if (!pickedDialogue || !activeStyle) return;
    try {
      setAudioBusy(true);
      if (audioRef.current) {
        try { await audioRef.current.unloadAsync(); } catch {}
        audioRef.current = null;
      }
      // Helper — runs preview-audio for a single line and plays it.
      const speakLine = async (lineText: string, voiceId: string, voiceStyle?: string) => {
        const previewText = lineText.slice(0, 180);
        const r = await axios.post(
          `${API}/generate-prompts/preview-audio`,
          {
            text: previewText,
            voice_id: voiceId,
            voice_type: voiceId,
            voice_style: voiceStyle,
            language,
            max_seconds: 3.5,
          },
          { responseType: 'arraybuffer', timeout: 30000 },
        );
        const b64 = arrayBufferToBase64(r.data);
        const uri = `data:audio/mpeg;base64,${b64}`;
        const sound = new Audio.Sound();
        const loadStatus: any = await sound.loadAsync({ uri });
        audioRef.current = sound;
        // Session 33 — compute the actual cap from durationMillis (+1.5s
        // buffer) so long Hindi previews don't get cut off by the
        // previous hard-coded 12s timeout.
        const loadedMs = Number(loadStatus?.durationMillis) || 0;
        const dynamicCapMs = loadedMs > 0
          ? Math.min(Math.max(loadedMs + 1500, 4000), 60000)
          : 60000;  // generous 60s fallback if duration unknown
        await sound.playAsync();
        // Wait for playback to finish before moving on (dual-mode chains A→B).
        await new Promise<void>((resolve) => {
          let done = false;
          sound.setOnPlaybackStatusUpdate((status: any) => {
            if (done) return;
            if (status?.didJustFinish || status?.isLoaded === false) {
              done = true;
              resolve();
            }
          });
          setTimeout(() => { if (!done) { done = true; resolve(); } }, dynamicCapMs);
        });
        try { await sound.unloadAsync(); } catch {}
      };

      if (dualMode) {
        // Play Person A's first line with voiceA, then Person B's first
        // line with voiceB, so the user actually hears the voice contrast.
        const { aLine, bLine } = extractAB(pickedDialogue.text);
        if (aLine) await speakLine(aLine, voiceAId, activeStyle.personality.voice_style);
        if (bLine) await speakLine(bLine, voiceBId, activeStyle.personality.voice_style);
      } else {
        // Solo — play the ENTIRE dialogue (all lines), not just the first
        // sentence. Previous version split on [.!?।] and took [0], which
        // made Hindi 4-line dialogues play only the first short clause.
        const cleaned = stripDialogueCues(pickedDialogue.text).replace(/\s+/g, ' ').trim();
        const fullText = cleaned.slice(0, 500) || cleaned;
        const voice = cartoonVoiceId || activeStyle.personality.voice_id;
        await speakLine(fullText, voice, cartoonVoiceStyle || activeStyle.personality.voice_style);
      }
    } catch (e: any) {
      Alert.alert('Voice preview unavailable', 'You can still generate the video in the next step.');
    } finally {
      setAudioBusy(false);
    }
  }, [pickedDialogue, activeStyle, language, cartoonVoiceId, cartoonVoiceStyle, dualMode, voiceAId, voiceBId]);

  // ────────────────────────── Pick + upload image ──────────────────────────
  const pickAndUploadImage = useCallback(async () => {
    if (!requireLogin()) return;
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted && Platform.OS !== 'web') {
        Alert.alert('Permission needed', 'Please allow photo access.');
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.85,
      });
      if (res.canceled || !res.assets?.[0]) return;
      const asset = res.assets[0];
      setImageUri(asset.uri);
      setImageUploading(true);
      const up = await uploadImageFile(asset.uri);
      setImagePath(up?.file_path || up?.path || null);
    } catch (e: any) {
      Alert.alert('Upload failed', e?.message || 'Try again.');
    } finally {
      setImageUploading(false);
    }
  }, [user]);

  // ────────────────────────── 5-cartoon-variant generator (Issue #6) ──────────────────────────
  // Fires 5 parallel /api/avatar/cartoonize calls — one per emotion — and
  // polls all 5 jobs concurrently. Result is rendered as a 5-up grid; the
  // user picks one and that pre-cartoonized image_path is then used by
  // generate() (skipping the second cartoonize step).
  const generateVariants = useCallback(async () => {
    if (!requireLogin()) return;
    if (!imageUri) { Alert.alert('Upload a photo first'); return; }
    if (!activeStyle) { Alert.alert('Pick an avatar style first'); return; }

    setVariantsBusy(true);
    setPickedVariantPath(null);
    setVariants([]);

    const variantEmotions = ['happy', 'excited', 'confident', 'playful', 'peaceful'];
    try {
      const b64 = await fileToBase64(imageUri);
      const initial: Variant[] = variantEmotions.map((em, i) => ({
        id: `v${i + 1}`, emotion: em, status: 'pending',
      }));
      setVariants(initial);

      // Kick off all 5 cartoonize jobs — staggered by 400ms so the
      // Nano Banana endpoint doesn't hit a rate-limit burst on the
      // first cold-start call (was the root cause of "first time all
      // fail, retry works" bug reported in Session 33 round 2).
      const startResults: PromiseSettledResult<any>[] = [];
      for (let i = 0; i < variantEmotions.length; i++) {
        const em = variantEmotions[i];
        // Fire this one (don't await yet — we'll collect results below).
        const pending = axios.post(`${API}/avatar/cartoonize`, {
          image_b64: b64,
          style: activeStyle.id,
          emotion: em,
        }, { timeout: 30000 }).then(
          (v) => ({ status: 'fulfilled', value: v } as const),
          (r) => ({ status: 'rejected', reason: r } as const),
        );
        startResults.push(pending as any);
        if (i < variantEmotions.length - 1) {
          await new Promise(r => setTimeout(r, 400));
        }
      }
      const resolved = await Promise.all(startResults as any);

      const withJobIds: Variant[] = resolved.map((r: any, i: number) => {
        if (r.status === 'fulfilled' && r.value?.data?.job_id) {
          return { ...initial[i], jobId: r.value.data.job_id };
        }
        return { ...initial[i], status: 'failed', error: 'Could not start variant' };
      });
      setVariants([...withJobIds]);

      // Poll all variants in parallel up to 180s (Gemini Nano Banana
      // jobs can queue on rate-limits; last job often finishes ~100s in).
      const t0 = Date.now();
      const pending = new Set(withJobIds.filter(v => v.jobId && v.status === 'pending').map(v => v.id));

      while (pending.size > 0 && Date.now() - t0 < 180_000) {
        await new Promise(r => setTimeout(r, 2500));
        // Snapshot current state into a local var so we can update in batch.
        await Promise.allSettled(Array.from(pending).map(async (vid) => {
          const v = withJobIds.find(x => x.id === vid);
          if (!v?.jobId) return;
          try {
            const jr = await axios.get(`${API}/avatar/jobs/${v.jobId}`, { timeout: 10000 });
            const st = jr.data?.status;
            if (st === 'completed' && jr.data?.image_url) {
              const imgUrl = jr.data.image_url as string;
              const m = imgUrl.match(/\/serve-file\/([^/?#]+)/);
              const localPath = m ? `/api/uploads/${m[1]}` : null;
              const idx = withJobIds.findIndex(x => x.id === vid);
              if (idx >= 0) {
                withJobIds[idx] = { ...withJobIds[idx], status: 'completed', imageUrl: imgUrl, localPath: localPath || undefined };
                pending.delete(vid);
                setVariants([...withJobIds]);
              }
            } else if (st === 'failed') {
              const idx = withJobIds.findIndex(x => x.id === vid);
              if (idx >= 0) {
                withJobIds[idx] = { ...withJobIds[idx], status: 'failed', error: jr.data?.error || 'Render failed' };
                pending.delete(vid);
                setVariants([...withJobIds]);
              }
            }
          } catch { /* keep polling */ }
        }));
      }
      // Mark any that are still pending as timed-out.
      const final = withJobIds.map(v => v.status === 'pending' ? { ...v, status: 'failed' as const, error: 'Timed out' } : v);
      setVariants(final);
    } catch (e: any) {
      Alert.alert('Could not generate variants', e?.message || 'Try again later.');
    } finally {
      setVariantsBusy(false);
    }
  }, [imageUri, activeStyle, user]);

  // Retry a single failed variant — fires one cartoonize call and polls
  // just that job without touching the other 4 cards. Issue #3 follow-up.
  const retryVariant = useCallback(async (id: string) => {
    if (!activeStyle || !imageUri) return;
    const vIdx = variants.findIndex(x => x.id === id);
    if (vIdx < 0) return;
    const v = variants[vIdx];
    // Flip to pending in UI.
    const next = [...variants];
    next[vIdx] = { ...v, status: 'pending', error: undefined, imageUrl: undefined, localPath: undefined, jobId: undefined };
    setVariants(next);
    try {
      const b64 = await fileToBase64(imageUri);
      const cr = await axios.post(`${API}/avatar/cartoonize`, {
        image_b64: b64,
        style: activeStyle.id,
        emotion: v.emotion,
      }, { timeout: 30000 });
      const jobId = cr.data?.job_id;
      if (!jobId) throw new Error('no job_id');
      next[vIdx] = { ...next[vIdx], jobId };
      setVariants([...next]);
      // Poll this single job for up to 180s.
      const t0 = Date.now();
      while (Date.now() - t0 < 180_000) {
        await new Promise(r => setTimeout(r, 2500));
        try {
          const jr = await axios.get(`${API}/avatar/jobs/${jobId}`, { timeout: 10000 });
          const st = jr.data?.status;
          if (st === 'completed' && jr.data?.image_url) {
            const m = (jr.data.image_url as string).match(/\/serve-file\/([^/?#]+)/);
            next[vIdx] = {
              ...next[vIdx], status: 'completed',
              imageUrl: jr.data.image_url,
              localPath: m ? `/api/uploads/${m[1]}` : undefined,
            };
            setVariants([...next]);
            return;
          }
          if (st === 'failed') {
            next[vIdx] = { ...next[vIdx], status: 'failed', error: jr.data?.error || 'Render failed' };
            setVariants([...next]);
            return;
          }
        } catch {}
      }
      next[vIdx] = { ...next[vIdx], status: 'failed', error: 'Timed out' };
      setVariants([...next]);
    } catch (e: any) {
      next[vIdx] = { ...next[vIdx], status: 'failed', error: e?.message || 'Retry failed' };
      setVariants([...next]);
    }
  }, [variants, activeStyle, imageUri]);

  // ── Phase 2a dual mode: uploads for A and B + gender auto-infer ──
  const pickAndUploadDual = useCallback(async (slot: 'A' | 'B') => {
    if (!requireLogin()) return;
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted && Platform.OS !== 'web') { Alert.alert('Permission needed'); return; }
      const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.85 });
      if (res.canceled || !res.assets?.[0]) return;
      const asset = res.assets[0];
      if (slot === 'A') setImageAUri(asset.uri); else setImageBUri(asset.uri);
      const up = await uploadImageFile(asset.uri);
      const path = up?.file_path || up?.path || null;
      if (slot === 'A') setImageAPath(path); else setImageBPath(path);
    } catch (e: any) { Alert.alert('Upload failed', e?.message || 'Try again.'); }
  }, [user]);

  // Auto-infer A/B genders when a dialogue is picked in dual mode.
  useEffect(() => {
    if (!dualMode || !pickedDialogue) return;
    let cancelled = false;
    (async () => {
      setInferBusy(true);
      try {
        const r = await axios.post(`${API}/avatar/infer-genders`, { dialogue_text: pickedDialogue.text }, { timeout: 15000 });
        if (cancelled) return;
        const ga = (r.data?.A || 'neutral') as 'male'|'female'|'neutral';
        const gb = (r.data?.B || 'neutral') as 'male'|'female'|'neutral';
        setGenderA(ga); setGenderB(gb);
        // Auto-pick voice IDs based on inferred gender
        if (ga === 'male')   setVoiceAId('en-US-GuyNeural');
        if (ga === 'female') setVoiceAId('en-US-JennyNeural');
        if (gb === 'male')   setVoiceBId('en-US-GuyNeural');
        if (gb === 'female') setVoiceBId('en-US-JennyNeural');
      } catch {}
      finally { if (!cancelled) setInferBusy(false); }
    })();
    return () => { cancelled = true; };
  }, [dualMode, pickedDialogue?.id]);

  // ── Phase 2b: AI character variant grid (b3 hybrid) ──
  // Kicks 4 Nano-Banana character jobs (2 per role with gender variety),
  // then polls them concurrently. User taps a card to adopt the image.
  const generateDualVariants = useCallback(async () => {
    if (!styleId) return;
    setVariantsKicking(true);
    setVariantErr(null);
    setVariantJobs([]);
    setPickedVariantA(null);
    setPickedVariantB(null);
    try {
      const gA1 = genderA === 'neutral' ? 'male' : genderA;
      const gA2 = genderA === 'male' ? 'female' : genderA === 'female' ? 'male' : 'female';
      const gB1 = genderB === 'neutral' ? 'male' : genderB;
      const gB2 = genderB === 'male' ? 'female' : genderB === 'female' ? 'male' : 'female';
      const r = await axios.post(`${API}/avatar/generate-characters-batch`, {
        style_id: styleId,
        slots: [
          { role: 'A', gender: gA1 },
          { role: 'A', gender: gA2 },
          { role: 'B', gender: gB1 },
          { role: 'B', gender: gB2 },
        ],
      }, { timeout: 15000 });
      const jobs: VariantJob[] = (r.data?.jobs || []).map((j: any) => ({
        job_id: j.job_id, role: j.role, gender: j.gender,
        status: 'queued', image_url: null,
      }));
      setVariantJobs(jobs);
    } catch (e: any) {
      setVariantErr(e?.response?.data?.detail || e?.message || 'Could not start character generation.');
    } finally {
      setVariantsKicking(false);
    }
  }, [styleId, genderA, genderB]);

  // Poll every queued/processing variant job every 3s.
  useEffect(() => {
    const active = variantJobs.filter(v => v.status === 'queued' || v.status === 'processing');
    if (active.length === 0) return;
    let stopped = false;
    const tick = async () => {
      await Promise.all(active.map(async (job) => {
        try {
          const r = await axios.get(`${API}/avatar/jobs/${job.job_id}`, { timeout: 10000 });
          const d = r.data || {};
          if (stopped) return;
          if (d.status === 'completed' || d.status === 'failed') {
            setVariantJobs(prev => prev.map(v =>
              v.job_id === job.job_id
                ? { ...v, status: d.status, image_url: d.image_url || null, error: d.error || null }
                : v,
            ));
          } else if (d.status === 'processing' && job.status !== 'processing') {
            setVariantJobs(prev => prev.map(v =>
              v.job_id === job.job_id ? { ...v, status: 'processing' } : v,
            ));
          }
        } catch (e: any) {
          const s = e?.response?.status;
          if (s === 404) {
            setVariantJobs(prev => prev.map(v =>
              v.job_id === job.job_id ? { ...v, status: 'failed', error: 'Job not found' } : v,
            ));
          }
        }
      }));
    };
    const timer = setInterval(tick, 3000);
    tick();
    return () => { stopped = true; clearInterval(timer); };
  }, [variantJobs]);

  // Auto-kick variants when entering Step 5 in dual mode if none yet.
  useEffect(() => {
    if (dualMode && step === 4 && styleId && variantJobs.length === 0 && !variantsKicking) {
      generateDualVariants();
    }
  }, [dualMode, step, styleId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Adopt a completed variant for role A or B.
  const adoptVariant = useCallback((v: VariantJob) => {
    if (v.status !== 'completed' || !v.image_url) return;
    const displayUri = v.image_url.startsWith('http')
      ? v.image_url
      : `${BACKEND_URL}${v.image_url}`;
    if (v.role === 'A') {
      setPickedVariantA(v.job_id);
      setImageAPath(v.image_url);
      setImageAUri(displayUri);
    } else {
      setPickedVariantB(v.job_id);
      setImageBPath(v.image_url);
      setImageBUri(displayUri);
    }
  }, []);


  // Kick off the dual-lipsync split-screen pipeline.
  const generateDual = useCallback(async () => {
    if (!requireLogin()) return;
    if (!imageAPath || !imageBPath) { Alert.alert('Upload both Person A and Person B photos.'); return; }
    if (!pickedDialogue) { Alert.alert('Pick a dialogue first'); return; }
    setGenerating(true); setResultUrl(null); setResultError('');    setGenStage('Preparing split-screen pipeline…'); setGenProgress(5);
    try {
      const body = {
        image_a_path: imageAPath,
        image_b_path: imageBPath,
        script: pickedDialogue.text,
        voice_a_id: voiceAId,
        voice_b_id: voiceBId,
        motion: 'none',
        aspect_ratio: '16:9',
        resolution: userIsPro ? '720p' : '480p',
        style_hint: activeStyle?.id,
        // Round 11 — optional BGM mood. null → omitted by axios → backend
        // skips amix step entirely.
        ...(bgmStyle ? { bgm_style: bgmStyle } : {}),
      };
      const r = await axios.post(`${API}/avatar/dual-lipsync`, body, { timeout: 30000 });
      const pid = r.data?.project_id;
      if (!pid) throw new Error('No project id');
      // Round 6 polish — same resilient polling we gave the solo flow:
      // surfaces auth/network errors, hard-caps at 12 min, bails gracefully.
      const POLL_START = Date.now();
      const POLL_MAX_MS = 12 * 60 * 1000;
      let consecutiveErrors = 0;
      pollRef.current = setInterval(async () => {
        if (Date.now() - POLL_START > POLL_MAX_MS) {
          clearInterval(pollRef.current);
          setResultError('Dual render timed out after 12 minutes.'); setGenerating(false);
          return;
        }
        try {
          const j = await axios.get(`${API}/project/${pid}`, { timeout: 15000 });
          consecutiveErrors = 0;
          const prog = j.data?.progress || 0; const st = j.data?.status || '';
          setGenProgress(prog);
          if (prog >= 90) setGenStage('Finalizing split-screen…');
          else if (prog >= 55) setGenStage('Composing & lip-syncing…');
          else if (prog >= 40) setGenStage('Mixing dual voices…');
          else if (prog >= 18) setGenStage('Generating voice A + voice B…');
          if (st === 'completed') {
            clearInterval(pollRef.current);
            setResultUrl(j.data.result_url ? `${BACKEND_URL}${j.data.result_url}` : null);
            setGenerating(false);
          } else if (st === 'failed') {
            clearInterval(pollRef.current);
            setResultError(j.data?.error || 'Dual render failed'); setGenerating(false);
          }
        } catch (pollErr: any) {
          consecutiveErrors += 1;
          const status = pollErr?.response?.status;
          console.warn(`[dual-lipsync] poll err #${consecutiveErrors}`, status);
          if (status === 401 || status === 403) {
            clearInterval(pollRef.current);
            setResultError('Session expired — please sign in again.'); setGenerating(false);
            return;
          }
          if (consecutiveErrors >= 20) {
            clearInterval(pollRef.current);
            setResultError(`Lost connection to render server (${status || 'network'}). Please retry.`);
            setGenerating(false);
          }
        }
      }, 3000);
    } catch (e: any) {
      setResultError(e?.response?.data?.detail || e?.message || 'Dual generation failed');
      setGenerating(false);
    }
  }, [imageAPath, imageBPath, pickedDialogue, voiceAId, voiceBId, userIsPro, activeStyle, user]);

  // ────────────────────────── Generate video ──────────────────────────
  // Cartoon mode → cartoonize(photo) → create-talking-avatar(cartoon, voice)
  // Talking mode → create-talking-avatar(photo, voice)   [no cartoonize]
  const generate = useCallback(async () => {
    if (!requireLogin()) return;
    if (!imagePath) { Alert.alert('Upload a photo first'); return; }
    if (!activeStyle) { Alert.alert('Pick an avatar style first'); return; }

    // Script resolution: prefer AI dialogue; otherwise use free-typed script.
    const script = pickedDialogue?.text?.trim() || manualScript.trim();
    if (!script) { Alert.alert('Pick a dialogue or type a script first'); return; }

    setGenerating(true); setResultUrl(null); setResultError('');
    setGenProgress(5);

    try {
      const persona = activeStyle.personality;  // kept for future use; emotion handled via state
      let cartoonPath = imagePath;

      // ── CARTOON MODE: cartoonize the uploaded photo first ─────────
      // …unless the user already picked a variant on Step 4 — in that
      // case we use the picked cartoon image directly and skip a 2nd
      // cartoonize pass (saves ~25s and one MagicHour credit).
      if (mode === 'cartoon' && pickedVariantPath) {
        cartoonPath = pickedVariantPath;
        setGenStage('Using your picked variant…');
        setGenProgress(35);
      } else if (mode === 'cartoon') {
        setGenStage(`Cartoonizing in ${activeStyle.label} style…`);
        setGenProgress(10);
        try {
          // Read the uploaded file back as base64 for the cartoonize API
          // (it needs image_b64). We already have imageUri from the picker.
          const b64 = await fileToBase64(imageUri || '');
          const cr = await axios.post(`${API}/avatar/cartoonize`, {
            image_b64: b64,
            style: activeStyle.id,
            emotion: emotion || 'happy',
          }, { timeout: 30000 });
          const jobId = cr.data?.job_id;
          if (!jobId) throw new Error('Cartoonize: no job_id');

          // Poll the cartoonize job up to 90s.
          const t0 = Date.now();
          while (Date.now() - t0 < 90_000) {
            await new Promise(r => setTimeout(r, 2500));
            try {
              const jr = await axios.get(`${API}/avatar/jobs/${jobId}`, { timeout: 10000 });
              const st = jr.data?.status;
              if (st === 'completed' && jr.data?.image_url) {
                // image_url is a /api/serve-file/... path — extract the
                // filename and reuse it as a valid upload path for talking-avatar.
                const imgUrl = jr.data.image_url as string;
                const m = imgUrl.match(/\/serve-file\/([^/?#]+)/);
                if (m) {
                  cartoonPath = `/api/uploads/${m[1]}`;
                }
                break;
              }
              if (st === 'failed') {
                throw new Error(jr.data?.error || 'Cartoonize failed');
              }
            } catch (pollErr: any) {
              if ((pollErr?.message || '').includes('Cartoonize')) throw pollErr;
            }
          }
        } catch (e: any) {
          const msg = e?.response?.data?.detail || e?.message || 'Cartoonize failed';
          throw new Error(`Cartoonize: ${msg}`);
        }
        setGenProgress(35);
      }

      setGenStage('Generating your talking video…');
      // Mode-specific delivery payload — Talking mode uses the user's
      // explicit voice/style/motion/aspect/resolution (legacy avatar.tsx
      // semantics restored). Cartoon mode uses style personality.
      const persona2 = activeStyle.personality;
      const body = mode === 'cartoon' ? {
        image_path: cartoonPath,
        script,
        voice_id: cartoonVoiceId || persona2.voice_id,
        voice_style: cartoonVoiceStyle || persona2.voice_style,
        motion: 'ken_burns',
        aspect_ratio: '9:16',
        resolution: userIsPro ? '720p' : '480p',
        // Round 11 — optional BGM mood for solo cartoon avatars.
        ...(bgmStyle ? { bgm_style: bgmStyle } : {}),
        // Session 33 — Procedural cartoon lipsync. Cartoon mode MUST
        // skip MagicHour's v1.lip_sync (it injects photoreal features
        // onto cartoons, producing an uncanny realistic eye/mouth
        // artifact). Backend runs OpenCV+ffmpeg mouth animator instead.
        use_procedural_lipsync: true,
      } : {
        image_path: cartoonPath,
        script,
        voice_id: tkVoiceId,
        voice_style: tkVoiceStyle || undefined,
        voice_rate: tkVoiceRate || undefined,
        voice_pitch: tkVoicePitch || undefined,
        motion: tkMotion || 'none',
        aspect_ratio: tkAspect || '9:16',
        resolution: userIsPro ? tkRes : '480p',
        ...(bgmStyle ? { bgm_style: bgmStyle } : {}),
      };
      const r = await axios.post(`${API}/create-talking-avatar`, body, { timeout: 30000 });
      const pid = r.data?.project_id;
      if (!pid) throw new Error('No project id returned');

      // Poll /api/project/{pid} — with diagnostics + max-poll timeout so
      // we never silently hang at low progress (root cause of "stuck @ 5%"
      // bug from session 24).
      const POLL_START = Date.now();
      const POLL_MAX_MS = 12 * 60 * 1000; // 12 min hard cap
      let consecutiveErrors = 0;
      pollRef.current = setInterval(async () => {
        // Hard timeout check
        if (Date.now() - POLL_START > POLL_MAX_MS) {
          clearInterval(pollRef.current);
          setResultError('Generation timed out after 12 minutes. Please try again.');
          setGenerating(false);
          return;
        }
        try {
          const j = await axios.get(`${API}/project/${pid}`, { timeout: 15000 });
          consecutiveErrors = 0;
          const prog = j.data?.progress || 0;
          const st = j.data?.status || '';
          setGenProgress(Math.max(40, prog));
          if (prog >= 90) setGenStage('Finalizing & adding audio…');
          else if (prog >= 45) setGenStage('Lip-syncing to voice…');
          else if (prog >= 30) setGenStage('Composing avatar…');
          if (st === 'completed') {
            clearInterval(pollRef.current);
            setResultUrl(j.data.result_url ? `${BACKEND_URL}${j.data.result_url}` : null);
            setGenerating(false);
          } else if (st === 'failed') {
            clearInterval(pollRef.current);
            setResultError(j.data?.error || 'Render failed');
            setGenerating(false);
          }
        } catch (pollErr: any) {
          consecutiveErrors += 1;
          // Surface poll errors so the next agent can see what's happening
          // rather than silently hanging the UI at 5%.
          const status = pollErr?.response?.status;
          const detail = pollErr?.response?.data?.detail || pollErr?.message || 'unknown';
          console.warn(`[avatar-studio] poll err #${consecutiveErrors}`, status, String(detail).slice(0, 200));
          // Auth failure → bail out immediately, the user needs to log in again.
          if (status === 401 || status === 403) {
            clearInterval(pollRef.current);
            setResultError('Session expired — please sign in again.');
            setGenerating(false);
            return;
          }
          // After ~1 minute of consecutive failures, give up.
          if (consecutiveErrors >= 20) {
            clearInterval(pollRef.current);
            setResultError(`Lost connection to render server (${status || 'network'}). Please retry.`);
            setGenerating(false);
          }
        }
      }, 3000);
    } catch (e: any) {
      setResultError(e?.response?.data?.detail || e?.message || 'Generation failed');
      setGenerating(false);
    }
  }, [
    imagePath, imageUri, pickedDialogue, manualScript, activeStyle,
    userIsPro, user, mode,
    // Session 33 round 2 — these were MISSING, causing stale closures.
    // When the user picked a variant / BGM / voice, generate() still
    // saw them as null and either (a) re-cartoonized instead of using
    // the picked variant, (b) skipped BGM entirely, (c) used the
    // wrong voice.
    pickedVariantPath, bgmStyle,
    cartoonVoiceId, cartoonVoiceStyle, emotion,
    tkVoiceId, tkVoiceStyle, tkVoiceRate, tkVoicePitch,
    tkMotion, tkAspect, tkRes,
  ]);

  // ────────────────────────── Step navigation ──────────────────────────
  const next = () => setStep(s => Math.min(s + 1, 5));
  const back = () => setStep(s => Math.max(s - 1, 0));

  const canNextStep0 = !!styleId && (!activeStyle?.premium || userIsPro);
  const canNextStep1 = idea.trim().length >= 3;
  const canNextStep2 = !!dialogueId && dialogues.length > 0;
  const canNextStep3 = true; // voice auto-mapped
  const canNextStep4 = true; // audio preview optional

  const onNext = () => {
    if (step === 1) {
      // Advance to dialogue step — but DON'T fetch dialogues yet.
      // The user must first pick Solo or Dual on Step 3; dialogue
      // generation kicks off when that toggle is set (see useEffect
      // on dualMode below).
      next();
    } else {
      next();
    }
  };

  // ────────────────────────── Render ──────────────────────────
  return (
    <AuroraBackground>
      <SafeAreaView style={s.root} edges={['top']}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'padding'}
          style={s.flex1}
          keyboardVerticalOffset={0}
        >
          <GlassHeader
            icon="sparkles"
            title="AI Avatar Studio"
            subtitle={mode === 'cartoon'
              ? `Cartoon · Step ${step + 1} of 5 · ${STEP_TITLES[step]}`
              : `Talking · Upload a real photo and generate`}
            onBack={() => step === 0 ? router.back() : back()}
          />

          {/* Mode toggle — Cartoon vs Talking. The toggle lives above the
              stepper so switching modes resets the wizard cleanly. */}
          <View style={s.modeRow}>
            <Pressable
              onPress={() => { setMode('cartoon'); setStep(0); }}
              style={[s.modeBtn, mode === 'cartoon' && s.modeBtnActive]}
            >
              <Ionicons name="color-palette" size={16} color={mode === 'cartoon' ? '#fff' : '#CBD5E1'} />
              <Text style={[s.modeBtnText, mode === 'cartoon' && { color: '#fff' }]}>Cartoon Avatar</Text>
            </Pressable>
            <Pressable
              onPress={() => { setMode('talking'); setStep(0); }}
              style={[s.modeBtn, mode === 'talking' && s.modeBtnActive]}
            >
              <Ionicons name="happy" size={16} color={mode === 'talking' ? '#fff' : '#CBD5E1'} />
              <Text style={[s.modeBtnText, mode === 'talking' && { color: '#fff' }]}>Talking Avatar</Text>
            </Pressable>
          </View>

          {/* Stepper — only shown for cartoon mode; talking is single screen */}
          {mode === 'cartoon' && (
            <View style={s.stepperRow}>
              {STEP_TITLES.slice(0, 5).map((_, i) => (
                <View
                  key={i}
                  style={[
                    s.stepperDot,
                    i === step && s.stepperDotActive,
                    i < step && s.stepperDotDone,
                  ]}
                />
              ))}
            </View>
          )}

          <ScrollView
            contentContainerStyle={s.scroll}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* ═════════════════ STEP 0 — Avatar picker (Cartoon mode) ═════════════════ */}
            {mode === 'cartoon' && step === 0 && (
              <>
                <Text style={s.sectionTitle}>Choose your avatar</Text>
                <Text style={s.sectionSub}>Pick a category, then select a style that matches your vibe.</Text>

                <View style={s.catRow}>
                  {categories.map(c => (
                    <Chip
                      key={c.id}
                      label={`${c.icon}  ${c.label}`}
                      active={c.id === categoryId}
                      onPress={() => {
                        setCategoryId(c.id);
                        const first = styles.find(st => st.category === c.id && (!st.premium || userIsPro));
                        if (first) setStyleId(first.id);
                      }}
                      style={{ marginRight: 8, marginBottom: 8 }}
                    />
                  ))}
                </View>

                {loadingStyles ? (
                  <ActivityIndicator color="#A855F7" style={{ marginTop: 40 }} />
                ) : (
                  <>
                    <View style={s.avatarGrid}>
                      {filteredStyles.map(st => {
                        const locked = st.premium && !userIsPro;
                        const active = st.id === styleId;
                        return (
                          <Pressable
                            key={st.id}
                            onPress={() => {
                              if (locked) {
                                Alert.alert(
                                  'Premium avatar',
                                  `${st.label} is a MagiCAi Premium style. Upgrade to unlock.`,
                                  [
                                    { text: 'Cancel', style: 'cancel' },
                                    { text: 'Upgrade', onPress: () => router.push('/subscription' as any) },
                                  ],
                                );
                                return;
                              }
                              setStyleId(st.id);
                            }}
                            style={[
                              s.avatarCard,
                              active && s.avatarCardActive,
                              locked && { opacity: 0.6 },
                            ]}
                          >
                            <Text style={s.avatarIcon}>{st.icon}</Text>
                            <Text style={s.avatarLabel}>{st.label}</Text>
                            <Text style={s.avatarTag} numberOfLines={2}>{st.tagline}</Text>
                            {st.premium && (
                              <View style={s.proPill}>
                                <Ionicons name="diamond" size={9} color="#FBBF24" />
                                <Text style={s.proPillText}>PRO</Text>
                              </View>
                            )}
                            {active && !locked && (
                              <View style={s.activeCheck}>
                                <Ionicons name="checkmark-circle" size={18} color="#EC4899" />
                              </View>
                            )}
                          </Pressable>
                        );
                      })}
                    </View>

                    {/* Issue #2 — Emotion strip common to ALL avatar categories */}
                    <FieldLabel style={{ marginTop: 18 }}>Pick an emotion</FieldLabel>
                    <View style={s.catRow}>
                      {EMOTION_CHIPS.map(em => (
                        <Chip
                          key={em.id}
                          label={`${em.icon} ${em.label}`}
                          active={em.id === emotion}
                          onPress={() => setEmotion(em.id)}
                          style={{ marginRight: 8, marginBottom: 8 }}
                        />
                      ))}
                    </View>
                  </>
                )}
              </>
            )}

            {/* ═════════════════ STEP 1 — Idea + Language ═════════════════ */}
            {mode === 'cartoon' && step === 1 && (
              <>
                <Text style={s.sectionTitle}>What should your avatar say?</Text>
                <Text style={s.sectionSub}>
                  Describe your idea. We'll craft 3 dialogue options to pick from.
                </Text>

                <FieldLabel>Language</FieldLabel>
                <View style={s.catRow}>
                  {LANG_OPTIONS.map(l => (
                    <Chip
                      key={l.id}
                      label={l.label}
                      active={l.id === language}
                      onPress={() => setLanguage(l.id)}
                      style={{ marginRight: 8, marginBottom: 8 }}
                    />
                  ))}
                </View>

                <FieldLabel>Your idea</FieldLabel>
                <TextInput
                  value={idea}
                  onChangeText={setIdea}
                  placeholder={`e.g. ${IDEA_SUGGESTIONS[categoryId]?.[0] || 'Say hi to my team'}`}
                  placeholderTextColor="#64748B"
                  multiline
                  style={s.textarea}
                />

                <FieldLabel>Quick starts {loadingSuggestions && '· refreshing…'}</FieldLabel>
                <View style={[s.catRow, { marginBottom: 8 }]}>
                  {(suggestions.length > 0 ? suggestions : IDEA_SUGGESTIONS[categoryId] || []).map(sug => (
                    <Chip
                      key={sug}
                      label={sug}
                      onPress={() => setIdea(sug)}
                      style={{ marginRight: 8, marginBottom: 8 }}
                    />
                  ))}
                </View>
              </>
            )}

            {/* ═════════════════ STEP 2 — Dialogue options ═════════════════ */}
            {mode === 'cartoon' && step === 2 && (
              <>
                <Text style={s.sectionTitle}>Pick your dialogue</Text>
                <Text style={s.sectionSub}>
                  AI-crafted to match {activeStyle?.label}'s personality.
                </Text>

                {/* Solo / Dual mode toggle (Session 25 — moved from step 4).
                    Switching this regenerates dialogues so the user sees
                    one-speaker monologues vs A/B two-speaker scenes.
                    Round 5 — neither button is "active" until the user
                    actually picks; dialogue gen only fires after pick. */}
                <View style={[s.modeRow, { marginTop: 8, marginBottom: 12 }]}>
                  <Pressable
                    onPress={() => { setDualMode(false); setDialogueId(null); }}
                    style={[s.modeBtn, dualMode === false && s.modeBtnActive]}
                  >
                    <Ionicons name="person" size={14} color={dualMode === false ? '#fff' : '#CBD5E1'} />
                    <Text style={[s.modeBtnText, dualMode === false && { color: '#fff' }]}>Solo avatar</Text>
                  </Pressable>
                  <Pressable
                    onPress={() => { setDualMode(true); setDialogueId(null); }}
                    style={[s.modeBtn, dualMode === true && s.modeBtnActive]}
                  >
                    <Ionicons name="people" size={14} color={dualMode === true ? '#fff' : '#CBD5E1'} />
                    <Text style={[s.modeBtnText, dualMode === true && { color: '#fff' }]}>Dual (A + B)</Text>
                  </Pressable>
                </View>

                {dualMode === null && (
                  <View style={[s.centerBox, { paddingVertical: 24 }]}>
                    <Ionicons name="hand-left-outline" size={28} color="#A855F7" />
                    <Text style={s.centerBoxText}>Pick a mode above to generate your dialogue.</Text>
                  </View>
                )}

                {loadingDialogues && (
                  <View style={s.centerBox}>
                    <ActivityIndicator color="#A855F7" />
                    <Text style={s.centerBoxText}>Generating 3 dialogue options…</Text>
                  </View>
                )}

                {!!dialogueErr && (
                  <GlassCard style={{ marginTop: 12 }}>
                    <Text style={s.errorTitle}>Could not generate dialogues</Text>
                    <Text style={s.errorText}>{dialogueErr}</Text>
                    <View style={{ height: 12 }} />
                    <GhostButton label="Try again" icon="refresh" size="md" onPress={fetchDialogues} />
                  </GlassCard>
                )}

                {!loadingDialogues && !dialogueErr && dialogues.map((d, idx) => {
                  const active = d.id === dialogueId;
                  return (
                    <Pressable
                      key={d.id}
                      onPress={() => setDialogueId(d.id)}
                      style={[s.dialogueCard, active && s.dialogueCardActive]}
                    >
                      <View style={s.dialogueBadgeRow}>
                        <View style={[s.dialogueBadge, active && { backgroundColor: '#EC4899', borderColor: '#EC4899' }]}>
                          <Text style={[s.dialogueBadgeText, active && { color: '#fff' }]}>{idx + 1}</Text>
                        </View>
                        <Text style={s.dialogueTone}>{d.tone}</Text>
                      </View>
                      <Text style={s.dialogueText}>{d.text}</Text>
                    </Pressable>
                  );
                })}

                {!loadingDialogues && !dialogueErr && dialogues.length > 0 && (
                  <GhostButton
                    label="Regenerate options"
                    icon="refresh"
                    size="md"
                    onPress={fetchDialogues}
                    style={{ marginTop: 8 }}
                  />
                )}
              </>
            )}

            {/* ═════════════════ STEP 3 — Voice auto-mapped ═════════════════ */}
            {mode === 'cartoon' && step === 3 && activeStyle && (
              <>
                <Text style={s.sectionTitle}>Voice · Auto-matched</Text>
                <Text style={s.sectionSub}>
                  We've picked the voice that fits {activeStyle.label}'s personality. Listen first.
                </Text>

                <GlassCard glow>
                  <View style={s.voiceRow}>
                    <Text style={s.voiceIcon}>{activeStyle.icon}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={s.voiceLabel}>{activeStyle.label} voice</Text>
                      <Text style={s.voiceMeta}>
                        {activeStyle.personality.tone} · {activeStyle.personality.mood}
                      </Text>
                      <Text style={s.voiceMetaSub}>
                        {activeStyle.personality.voice_id}
                      </Text>
                    </View>
                  </View>
                </GlassCard>

                {pickedDialogue && (
                  <GlassCard style={{ marginTop: 12 }}>
                    <FieldLabel>Your picked dialogue</FieldLabel>
                    <Text style={s.quotedText}>"{pickedDialogue.text}"</Text>
                  </GlassCard>
                )}

                {/* Voice pickers (Session 25) — solo OR dual based on the
                    mode the user toggled on Step 3. Voice override is
                    optional; defaults to the auto-matched style voice. */}
                {!dualMode ? (
                  <>
                    <FieldLabel style={{ marginTop: 16 }}>Choose a different voice (optional)</FieldLabel>
                    <VoicePicker
                      selectedId={cartoonVoiceId || activeStyle.personality.voice_id}
                      onSelect={(id) => setCartoonVoiceId(id)}
                      languageFilter={language === 'english' ? 'english' : 'indian'}
                    />
                  </>
                ) : (
                  <>
                    <FieldLabel style={{ marginTop: 16 }}>Voice A (Person A)</FieldLabel>
                    <VoicePicker selectedId={voiceAId} onSelect={setVoiceAId}
                      languageFilter={language === 'english' ? 'english' : 'indian'} />
                    <FieldLabel style={{ marginTop: 14 }}>Voice B (Person B)</FieldLabel>
                    <VoicePicker selectedId={voiceBId} onSelect={setVoiceBId}
                      languageFilter={language === 'english' ? 'english' : 'indian'} />
                  </>
                )}

                <GradientButton
                  label={audioBusy ? 'Loading voice…' : 'Play voice preview'}
                  icon="play"
                  loading={audioBusy}
                  onPress={playAudioPreview}
                  style={{ marginTop: 16 }}
                  colors={['#6C3BFF', '#A855F7', '#EC4899']}
                />
                <Text style={s.voiceHint}>
                  Hear the voice before we generate your full video.
                </Text>
              </>
            )}

            {/* ═════════════════ STEP 4 — Photo + Generate ═════════════════ */}
            {mode === 'cartoon' && step === 4 && (
              <>
                {/* Dual-speaker UI branch — toggle moved to Step 3 (dialogue
                    picker), voice pickers moved to Step 4 (auto-matched).
                    This step is now PURELY photo upload + generate. */}
                {dualMode ? (
                  <>
                    <Text style={s.sectionTitle}>Two-speaker split-screen</Text>
                    <Text style={s.sectionSub}>
                      Upload both Person A and Person B. We'll split-screen them,
                      use voice A for A's lines and voice B for B's lines.
                      {inferBusy ? '  (auto-detecting genders…)' : ''}
                    </Text>

                    {/* Gender chips — used for character generation if user
                        skips upload. Kept here so the user can fine-tune
                        right before uploading their own portraits. */}
                    <FieldLabel>Person A · Gender</FieldLabel>
                    <View style={s.catRow}>
                      {(['male','female','neutral'] as const).map(g => (
                        <Chip key={'a'+g} label={g[0].toUpperCase()+g.slice(1)} active={genderA===g}
                          onPress={() => { setGenderA(g); if (g==='male') setVoiceAId('en-US-GuyNeural'); if (g==='female') setVoiceAId('en-US-JennyNeural'); }}
                          style={{ marginRight: 8, marginBottom: 8 }} />
                      ))}
                    </View>
                    <FieldLabel>Person B · Gender</FieldLabel>
                    <View style={s.catRow}>
                      {(['male','female','neutral'] as const).map(g => (
                        <Chip key={'b'+g} label={g[0].toUpperCase()+g.slice(1)} active={genderB===g}
                          onPress={() => { setGenderB(g); if (g==='male') setVoiceBId('en-US-GuyNeural'); if (g==='female') setVoiceBId('en-US-JennyNeural'); }}
                          style={{ marginRight: 8, marginBottom: 8 }} />
                      ))}
                    </View>

                    {/* ── Phase 2b: AI-generated character variants grid ── */}
                    <FieldLabel style={{ marginTop: 16 }}>
                      AI-generated character variants
                    </FieldLabel>
                    <Text style={s.sectionSub}>
                      Tap a card to use it. First two are for Person A, last two for Person B.
                    </Text>
                    <View style={s.variantGrid}>
                      {variantJobs.length === 0 && variantsKicking && (
                        <View style={s.variantPlaceholder}>
                          <ActivityIndicator color="#A855F7" />
                          <Text style={s.variantStatusText}>Starting AI artists…</Text>
                        </View>
                      )}
                      {variantJobs.length === 0 && !variantsKicking && (
                        <View style={s.variantPlaceholder}>
                          <Text style={s.variantStatusText}>
                            {variantErr || 'Character generation will start automatically.'}
                          </Text>
                        </View>
                      )}
                      {variantJobs.map((v) => {
                        const isPicked = (v.role === 'A' && pickedVariantA === v.job_id) ||
                                         (v.role === 'B' && pickedVariantB === v.job_id);
                        const done = v.status === 'completed' && !!v.image_url;
                        const failed = v.status === 'failed';
                        const displayUri = done && v.image_url
                          ? (v.image_url.startsWith('http') ? v.image_url : `${BACKEND_URL}${v.image_url}`)
                          : null;
                        return (
                          <Pressable
                            key={v.job_id}
                            onPress={() => done && adoptVariant(v)}
                            disabled={!done}
                            style={[
                              s.variantCard,
                              isPicked && s.variantCardPicked,
                              failed && { opacity: 0.5 },
                            ]}
                          >
                            {done && displayUri ? (
                              <Image source={{ uri: displayUri }} style={s.variantImg} resizeMode="cover" />
                            ) : failed ? (
                              <View style={s.variantCenter}>
                                <Ionicons name="alert-circle-outline" size={22} color="#EF4444" />
                                <Text style={s.variantErrText}>Failed</Text>
                              </View>
                            ) : (
                              <View style={s.variantCenter}>
                                <ActivityIndicator color="#A855F7" />
                                <Text style={s.variantStatusText}>Drawing…</Text>
                              </View>
                            )}
                            <View style={s.variantBadge}>
                              <Text style={s.variantBadgeText}>
                                {v.role} · {v.gender[0].toUpperCase()}
                              </Text>
                            </View>
                            {isPicked && (
                              <View style={s.variantCheck}>
                                <Ionicons name="checkmark-circle" size={22} color="#22C55E" />
                              </View>
                            )}
                          </Pressable>
                        );
                      })}
                    </View>

                    <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                      <Pressable
                        onPress={generateDualVariants}
                        disabled={variantsKicking}
                        style={[s.ghostBtn, variantsKicking && { opacity: 0.5 }]}
                      >
                        <Ionicons name="refresh" size={14} color="#A855F7" />
                        <Text style={s.ghostBtnText}>
                          {variantsKicking ? 'Starting…' : 'Regenerate variants'}
                        </Text>
                      </Pressable>
                    </View>

                    <View style={s.orDivider}>
                      <View style={s.orLine} />
                      <Text style={s.orText}>OR use your own photos</Text>
                      <View style={s.orLine} />
                    </View>

                    {/* Side-by-side upload slots */}
                    <FieldLabel style={{ marginTop: 6 }}>Upload portraits</FieldLabel>
                    <View style={{ flexDirection: 'row', gap: 10 }}>
                      {([
                        { slot: 'A' as const, uri: imageAUri, label: 'Person A' },
                        { slot: 'B' as const, uri: imageBUri, label: 'Person B' },
                      ]).map(slot => (
                        <Pressable key={slot.slot} onPress={() => pickAndUploadDual(slot.slot)}
                          style={[s.dualUpload, slot.uri && { borderColor: '#EC4899' }]}>
                          {slot.uri ? (
                            <Image source={{ uri: slot.uri }} style={{ width: '100%', height: '100%', borderRadius: 10 }} resizeMode="cover" />
                          ) : (
                            <>
                              <Ionicons name="cloud-upload-outline" size={28} color="#A855F7" />
                              <Text style={s.uploadSub}>{slot.label}</Text>
                            </>
                          )}
                        </Pressable>
                      ))}
                    </View>

                    <View style={{ height: 16 }} />
                    {/* Round 11 — BGM chip row (dual mode) */}
                    <FieldLabel>Background music (optional)</FieldLabel>
                    <View style={s.bgmRow}>
                      {BGM_OPTIONS.map((opt) => (
                        <Pressable
                          key={String(opt.id)}
                          onPress={() => setBgmStyle(opt.id as any)}
                          style={[s.bgmChip, bgmStyle === opt.id && s.bgmChipActive]}
                        >
                          <Ionicons name={opt.icon} size={13} color={bgmStyle === opt.id ? '#fff' : '#A855F7'} />
                          <Text style={[s.bgmChipText, bgmStyle === opt.id && { color: '#fff' }]}>
                            {opt.label}
                          </Text>
                        </Pressable>
                      ))}
                    </View>
                    <View style={{ height: 12 }} />

                    <GradientButton
                      label={generating ? 'Generating split-screen…' : 'Generate Dual Avatar Video'}
                      icon="people"
                      loading={generating}
                      disabled={!imageAPath || !imageBPath || !pickedDialogue || generating}
                      onPress={generateDual}
                    />
                    <Text style={s.resHint}>
                      V1 · split-screen image + combined A/B audio, single lipsync pass.
                      True independent dual-lipsync coming in Phase 2 (Pro tier).
                    </Text>

                    {/* Shared progress + result below */}
                    {generating && (
                      <GlassCard style={{ marginTop: 16 }}>
                        <View style={s.progressBar}><View style={[s.progressFill, { width: `${genProgress}%` }]} /></View>
                        <Text style={s.progressText}>{genStage} ({genProgress}%)</Text>
                      </GlassCard>
                    )}
                    {resultUrl && !generating && (
                      <GlassCard glow style={{ marginTop: 16 }}>
                        <FieldLabel>✨ Your dual avatar video is ready</FieldLabel>
                        <Video source={{ uri: resultUrl }} style={s.videoResult} useNativeControls resizeMode={ResizeMode.CONTAIN} shouldPlay isLooping />
                      </GlassCard>
                    )}
                    {!!resultError && !generating && (
                      <GlassCard style={{ marginTop: 16 }}>
                        <Text style={s.errorTitle}>Generation failed</Text>
                        <Text style={s.errorText}>{resultError}</Text>
                      </GlassCard>
                    )}

                    <View style={{ marginTop: 18 }}>
                      <GhostButton label="Back to voice preview" icon="chevron-back" size="md" onPress={back} disabled={generating} />
                    </View>
                  </>
                ) : (
                <>
                <Text style={s.sectionTitle}>Upload your photo</Text>
                <Text style={s.sectionSub}>We'll animate it with your picked voice + dialogue.</Text>

                {imageUri ? (
                  <GlassCard>
                    <Image source={{ uri: imageUri }} style={s.photoPreview} />
                    <View style={{ height: 12 }} />
                    <GhostButton
                      label="Change photo"
                      icon="refresh"
                      size="md"
                      onPress={pickAndUploadImage}
                    />
                    {imageUploading && (
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, justifyContent: 'center' }}>
                        <ActivityIndicator color="#A855F7" size="small" />
                        <Text style={s.uploadingText}>Uploading…</Text>
                      </View>
                    )}
                  </GlassCard>
                ) : (
                  <GlassCard onPress={pickAndUploadImage} style={s.uploadBox}>
                    <Ionicons name="cloud-upload-outline" size={38} color="#A855F7" />
                    <Text style={s.uploadTitle}>Tap to upload</Text>
                    <Text style={s.uploadSub}>JPG / PNG · portrait works best</Text>
                  </GlassCard>
                )}

                {/* Issue #6 — 5 cartoon variants picker */}
                {imagePath && (
                  <View style={{ marginTop: 16 }}>
                    <FieldLabel>Try 5 cartoon variants</FieldLabel>
                    <Text style={s.sectionSub}>
                      Skip the surprise — generate 5 quick previews in {activeStyle?.label} style
                      and pick your favorite before we make the talking video.
                    </Text>
                    {variants.length === 0 && (
                      <GradientButton
                        label={variantsBusy ? 'Cooking up 5 variants…' : 'Generate 5 cartoon previews'}
                        icon="grid"
                        loading={variantsBusy}
                        disabled={variantsBusy || generating}
                        onPress={generateVariants}
                        size="md"
                        colors={['#A855F7', '#EC4899']}
                      />
                    )}
                    {variants.length > 0 && (
                      <>
                        <View style={s.variantGrid}>
                          {variants.map(v => {
                            const isPicked = !!v.localPath && pickedVariantPath === v.localPath;
                            return (
                              <Pressable
                                key={v.id}
                                onPress={() => {
                                  if (v.status === 'completed' && v.localPath) {
                                    setPickedVariantPath(v.localPath);
                                  } else if (v.status === 'failed') {
                                    retryVariant(v.id);
                                  }
                                }}
                                style={[s.variantCard, isPicked && s.variantCardActive]}
                              >
                                {v.status === 'pending' && (
                                  <View style={s.variantPlaceholder}>
                                    <ActivityIndicator color="#A855F7" />
                                    <Text style={s.variantStatusText}>{v.emotion}</Text>
                                  </View>
                                )}
                                {v.status === 'completed' && v.imageUrl && (
                                  <>
                                    <Image
                                      source={{ uri: `${BACKEND_URL}${v.imageUrl}` }}
                                      style={s.variantImage}
                                      resizeMode="cover"
                                    />
                                    <View style={s.variantBadge}>
                                      <Text style={s.variantBadgeText}>{v.emotion}</Text>
                                    </View>
                                    {isPicked && (
                                      <View style={s.variantPickedBadge}>
                                        <Ionicons name="checkmark-circle" size={20} color="#fff" />
                                      </View>
                                    )}
                                  </>
                                )}
                                {v.status === 'failed' && (
                                  <View style={s.variantPlaceholder}>
                                    <Ionicons name="alert-circle-outline" size={22} color="#F87171" />
                                    <Text style={[s.variantStatusText, { color: '#F87171' }]}>retry</Text>
                                  </View>
                                )}
                              </Pressable>
                            );
                          })}
                        </View>
                        <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
                          <GhostButton
                            label="Regenerate variants"
                            icon="refresh"
                            size="sm"
                            disabled={variantsBusy || generating}
                            onPress={generateVariants}
                            style={{ flex: 1 }}
                          />
                          {pickedVariantPath && (
                            <GhostButton
                              label="Clear pick"
                              icon="close"
                              size="sm"
                              onPress={() => setPickedVariantPath(null)}
                              style={{ flex: 1 }}
                            />
                          )}
                        </View>
                        {pickedVariantPath && (
                          <Text style={[s.voiceHint, { marginTop: 8, color: '#34D399' }]}>
                            ✓ Variant picked — tap "Generate Avatar Video" below
                          </Text>
                        )}
                      </>
                    )}
                  </View>
                )}


                <View style={{ height: 20 }} />

                {/* Round 11 — BGM chip row (solo mode) */}
                <FieldLabel>Background music (optional)</FieldLabel>
                <View style={s.bgmRow}>
                  {BGM_OPTIONS.map((opt) => (
                    <Pressable
                      key={String(opt.id)}
                      onPress={() => setBgmStyle(opt.id as any)}
                      style={[s.bgmChip, bgmStyle === opt.id && s.bgmChipActive]}
                    >
                      <Ionicons name={opt.icon} size={13} color={bgmStyle === opt.id ? '#fff' : '#A855F7'} />
                      <Text style={[s.bgmChipText, bgmStyle === opt.id && { color: '#fff' }]}>
                        {opt.label}
                      </Text>
                    </Pressable>
                  ))}
                </View>
                <View style={{ height: 14 }} />

                {/* Generate CTA */}
                <GradientButton
                  label={generating ? 'Generating…' : 'Generate Avatar Video'}
                  icon="sparkles"
                  loading={generating}
                  disabled={!imagePath || generating}
                  onPress={generate}
                />

                {userIsPro ? (
                  <Text style={s.resHint}>720p HD · no watermark · Pro tier ✨</Text>
                ) : (
                  <Text style={s.resHint}>
                    Free tier · 480p with watermark. Upgrade for HD + no watermark.
                  </Text>
                )}

                {/* Progress */}
                {generating && (
                  <GlassCard style={{ marginTop: 16 }}>
                    <View style={s.progressBar}>
                      <View style={[s.progressFill, { width: `${genProgress}%` }]} />
                    </View>
                    <Text style={s.progressText}>{genStage} ({genProgress}%)</Text>
                  </GlassCard>
                )}

                {/* Result */}
                {resultUrl && !generating && (
                  <GlassCard glow style={{ marginTop: 16 }}>
                    <FieldLabel>✨ Your avatar is ready</FieldLabel>
                    <Video
                      source={{ uri: resultUrl }}
                      style={s.videoResult}
                      useNativeControls
                      resizeMode={ResizeMode.CONTAIN}
                      shouldPlay
                      isLooping
                    />
                    <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                      <GhostButton
                        label="Start over"
                        icon="refresh"
                        size="md"
                        onPress={() => { setStep(0); setResultUrl(null); setImagePath(null); setImageUri(null); }}
                        style={{ flex: 1 }}
                      />
                      <GradientButton
                        label="Open in Library"
                        icon="folder-open"
                        size="md"
                        onPress={() => router.push('/projects' as any)}
                        style={{ flex: 1 }}
                      />
                    </View>
                  </GlassCard>
                )}

                {!!resultError && !generating && (
                  <GlassCard style={{ marginTop: 16 }}>
                    <Text style={s.errorTitle}>Generation failed</Text>
                    <Text style={s.errorText}>{resultError}</Text>
                  </GlassCard>
                )}

                {/* Back to previous step — bottom placement (issue #3) */}
                <View style={{ marginTop: 18 }}>
                  <GhostButton
                    label="Back to voice preview"
                    icon="chevron-back"
                    size="md"
                    onPress={back}
                    disabled={generating}
                  />
                </View>
                </>
                )}
              </>
            )}

            {/* ═════════════════ TALKING MODE — single compact screen ═════════════════
                Upload a realistic photo + type/AI-generate a script + auto-mapped voice
                → directly call /api/create-talking-avatar (no cartoonize step). */}
            {mode === 'talking' && (
              <>
                <Text style={s.sectionTitle}>Make a realistic photo talk</Text>
                <Text style={s.sectionSub}>
                  Upload any portrait, type what it should say, and we'll lip-sync a
                  realistic talking video with a voice that matches your chosen vibe.
                </Text>

                {/* Emotion strip — common to both modes (issue #2) */}
                <FieldLabel>Pick an emotion</FieldLabel>
                <View style={s.catRow}>
                  {EMOTION_CHIPS.map(em => (
                    <Chip
                      key={em.id}
                      label={`${em.icon} ${em.label}`}
                      active={em.id === emotion}
                      onPress={() => setEmotion(em.id)}
                      style={{ marginRight: 8, marginBottom: 8 }}
                    />
                  ))}
                </View>

                {/* 1) Upload */}
                <FieldLabel style={{ marginTop: 14 }}>1 · Upload portrait</FieldLabel>
                {imageUri ? (
                  <GlassCard>
                    <Image source={{ uri: imageUri }} style={s.photoPreview} />
                    <View style={{ height: 10 }} />
                    <GhostButton label="Change photo" icon="refresh" size="md" onPress={pickAndUploadImage} />
                    {imageUploading && (
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, justifyContent: 'center' }}>
                        <ActivityIndicator color="#A855F7" size="small" />
                        <Text style={s.uploadingText}>Uploading…</Text>
                      </View>
                    )}
                  </GlassCard>
                ) : (
                  <GlassCard onPress={pickAndUploadImage} style={s.uploadBox}>
                    <Ionicons name="cloud-upload-outline" size={38} color="#A855F7" />
                    <Text style={s.uploadTitle}>Tap to upload</Text>
                    <Text style={s.uploadSub}>JPG / PNG · realistic portrait</Text>
                  </GlassCard>
                )}

                {/* 2) Script */}
                <FieldLabel style={{ marginTop: 16 }}>2 · What should they say?</FieldLabel>
                <TextInput
                  value={manualScript}
                  onChangeText={setManualScript}
                  placeholder="Type the dialogue… Add [pause:1.5] for a pause."
                  placeholderTextColor="#64748B"
                  multiline
                  style={s.textarea}
                />

                {/* 3) Voice picker — full legacy talking-avatar UX restored */}
                <FieldLabel>3 · Voice</FieldLabel>
                <VoicePicker selectedId={tkVoiceId} onSelect={setTkVoiceId} />

                <FieldLabel style={{ marginTop: 16 }}>Voice style (optional)</FieldLabel>
                <VoiceStylePicker
                  voiceId={tkVoiceId}
                  selectedStyle={tkVoiceStyle}
                  selectedRate={tkVoiceRate}
                  selectedPitch={tkVoicePitch}
                  onStyleChange={setTkVoiceStyle}
                  onRateChange={setTkVoiceRate}
                  onPitchChange={setTkVoicePitch}
                />

                <FieldLabel style={{ marginTop: 16 }}>Camera motion</FieldLabel>
                <MotionPicker selectedId={tkMotion} onSelect={setTkMotion} />

                <FieldLabel style={{ marginTop: 16 }}>Resolution</FieldLabel>
                <ResolutionPicker selectedId={tkRes} onSelect={setTkRes} />

                {/* Optional: which emotion strip is currently active */}
                <Text style={[s.voiceMeta, { marginTop: 10 }]}>
                  Emotion: {EMOTION_CHIPS.find(e => e.id === emotion)?.icon} {emotion}
                </Text>

                {/* 4) Generate */}
                <View style={{ height: 18 }} />
                <GradientButton
                  label={generating ? 'Generating…' : 'Generate Talking Video'}
                  icon="sparkles"
                  loading={generating}
                  disabled={!imagePath || !manualScript.trim() || generating}
                  onPress={generate}
                />
                {userIsPro ? (
                  <Text style={s.resHint}>720p HD · no watermark · Pro tier ✨</Text>
                ) : (
                  <Text style={s.resHint}>
                    Free tier · 480p with watermark. Upgrade for HD + no watermark.
                  </Text>
                )}

                {/* Shared progress + result + error UI */}
                {generating && (
                  <GlassCard style={{ marginTop: 16 }}>
                    <View style={s.progressBar}>
                      <View style={[s.progressFill, { width: `${genProgress}%` }]} />
                    </View>
                    <Text style={s.progressText}>{genStage} ({genProgress}%)</Text>
                  </GlassCard>
                )}
                {resultUrl && !generating && (
                  <GlassCard glow style={{ marginTop: 16 }}>
                    <FieldLabel>✨ Your talking avatar is ready</FieldLabel>
                    <Video
                      source={{ uri: resultUrl }}
                      style={s.videoResult}
                      useNativeControls
                      resizeMode={ResizeMode.CONTAIN}
                      shouldPlay
                      isLooping
                    />
                    <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                      <GhostButton
                        label="New video"
                        icon="refresh"
                        size="md"
                        onPress={() => { setResultUrl(null); setImagePath(null); setImageUri(null); setManualScript(''); }}
                        style={{ flex: 1 }}
                      />
                      <GradientButton
                        label="Open in Library"
                        icon="folder-open"
                        size="md"
                        onPress={() => router.push('/projects' as any)}
                        style={{ flex: 1 }}
                      />
                    </View>
                  </GlassCard>
                )}
                {!!resultError && !generating && (
                  <GlassCard style={{ marginTop: 16 }}>
                    <Text style={s.errorTitle}>Generation failed</Text>
                    <Text style={s.errorText}>{resultError}</Text>
                  </GlassCard>
                )}
              </>
            )}

            {/* ═════════════════ STEP 5 — Recap (hidden, we jump to result above) */}
          </ScrollView>

          {/* Bottom nav — only for steps 0..3 (step 4 has its own CTA) */}
          {/* Bottom nav — only for cartoon mode steps 0..3 (step 4 + talking mode have own CTAs) */}
          {mode === 'cartoon' && step < 4 && (
            <View style={[s.bottomNav, { paddingBottom: Math.max(insets.bottom + 8, 14) }]}>
              <GhostButton
                label="Back"
                icon="chevron-back"
                size="md"
                onPress={back}
                disabled={step === 0}
                style={{ flex: 1 }}
              />
              <GradientButton
                label={step === 3 ? 'Continue to upload' : 'Next'}
                iconRight="chevron-forward"
                size="md"
                onPress={onNext}
                disabled={
                  (step === 0 && !canNextStep0) ||
                  (step === 1 && !canNextStep1) ||
                  (step === 2 && !canNextStep2)
                }
                style={{ flex: 1.4 }}
              />
            </View>
          )}
        </KeyboardAvoidingView>

        <AuthGateModal
          visible={showAuthGate}
          onClose={() => setShowAuthGate(false)}
          reason="AI Avatar Studio"
          nextRoute="/avatar-studio"
        />
      </SafeAreaView>
    </AuroraBackground>
  );
}

// ────────────────────────── Helpers ──────────────────────────
const STEP_TITLES = [
  'Pick your avatar',
  'Your idea',
  'Pick a dialogue',
  'Voice preview',
  'Upload + generate',
  'Done',
];

/** Extract the first Person A line and first Person B line from a
 *  dialogue script. Used by dual-mode preview to play each voice. */
function extractAB(text: string): { aLine: string; bLine: string } {
  if (!text) return { aLine: '', bLine: '' };
  const clean = (t: string) => t
    .replace(/\[pause:[0-9.]+\]/gi, '')
    .replace(/\*[^*\n]+\*/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
  const lines = text.split(/\n|(?=\s[AB]:)/).map(l => l.trim()).filter(Boolean);
  let aLine = '', bLine = '';
  for (const l of lines) {
    const m = l.match(/^\s*([AB])\s*:\s*(.+)$/i);
    if (!m) continue;
    const speaker = m[1].toUpperCase();
    const content = clean(m[2]);
    if (speaker === 'A' && !aLine) aLine = content;
    else if (speaker === 'B' && !bLine) bLine = content;
    if (aLine && bLine) break;
  }
  return { aLine, bLine };
}

/** Strip dialogue cues for TTS preview — removes A:/B: prefixes,
 *  [pause:X.X] markers, and *action* asterisks. Keeps only the spoken
 *  words. Used by the cartoon-mode voice preview button. */
function stripDialogueCues(text: string): string {
  if (!text) return '';
  return text
    .replace(/^[ \t]*[A-Za-z]:\s*/gm, '')                 // strip "A:" / "B:" prefixes
    .replace(/\[pause:[0-9.]+\]/gi, '')                   // strip [pause:X.X]
    .replace(/\*[^*\n]+\*/g, '')                          // strip *action* cues
    .replace(/\n+/g, ' ')                                 // collapse newlines
    .replace(/\s{2,}/g, ' ')                              // collapse repeats
    .trim();
}

/** Convert an ArrayBuffer to base64 — used for audio preview playback. */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  if (typeof btoa === 'function') {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + chunk)));
    }
    return btoa(binary);
  }
  // RN fallback
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { Buffer } = require('buffer');
  return Buffer.from(buffer).toString('base64');
}

/** Read a local file URI (or web blob URI) as base64 without the data: prefix.
 *  Used by the Cartoon-mode generate flow — /api/avatar/cartoonize needs
 *  image_b64. */
async function fileToBase64(uri: string): Promise<string> {
  if (!uri) throw new Error('No image URI');
  // expo-file-system works for native file:// URIs.
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const FileSystem = require('expo-file-system');
    if (FileSystem && FileSystem.readAsStringAsync && uri.startsWith('file:')) {
      return await FileSystem.readAsStringAsync(uri, { encoding: 'base64' });
    }
  } catch {}
  // Web / fallback: fetch the blob and use FileReader.
  const resp = await fetch(uri);
  const blob = await resp.blob();
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('FileReader failed'));
    reader.onloadend = () => {
      const s = String(reader.result || '');
      const idx = s.indexOf(',');
      resolve(idx >= 0 ? s.slice(idx + 1) : s);
    };
    reader.readAsDataURL(blob);
  });
}

// ────────────────────────── Styles ──────────────────────────
const s = StyleSheet.create({
  root: { flex: 1 },
  flex1: { flex: 1 },
  scroll: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 140,
    gap: 10,
  },

  stepperRow: {
    flexDirection: 'row', gap: 6,
    paddingHorizontal: 20, marginTop: 2, marginBottom: 4,
  },
  stepperDot: {
    flex: 1, height: 4, borderRadius: 2,
    backgroundColor: 'rgba(255,255,255,0.08)',
  },
  stepperDotActive: { backgroundColor: '#EC4899' },
  stepperDotDone:   { backgroundColor: 'rgba(236,72,153,0.5)' },

  /* Mode toggle (Cartoon | Talking) */
  modeRow: {
    flexDirection: 'row', gap: 8,
    paddingHorizontal: 16, marginTop: 6, marginBottom: 10,
  },
  modeBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 11, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
  },
  modeBtnActive: {
    backgroundColor: 'rgba(168,85,247,0.22)',
    borderColor: '#A855F7',
  },
  modeBtnText: { color: '#CBD5E1', fontSize: 13, fontWeight: '800', letterSpacing: 0.2 },

  sectionTitle: {
    color: '#F8FAFC', fontSize: 22, fontWeight: '900',
    marginTop: 4, marginBottom: 4, letterSpacing: -0.3,
  },
  sectionSub: {
    color: '#94A3B8', fontSize: 13, lineHeight: 18, marginBottom: 14,
  },

  catRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 4 },

  /* Avatar grid */
  avatarGrid: {
    flexDirection: 'row', flexWrap: 'wrap',
    gap: 10, marginTop: 8,
  },
  avatarCard: {
    width: '48%', minHeight: 110,
    padding: 14, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
    alignItems: 'center',
    position: 'relative',
  },
  avatarCardActive: {
    borderColor: '#EC4899',
    backgroundColor: 'rgba(236,72,153,0.08)',
  },
  avatarIcon: { fontSize: 34, marginBottom: 6 },
  avatarLabel: { color: '#fff', fontSize: 14, fontWeight: '800', textAlign: 'center' },
  avatarTag:  { color: '#94A3B8', fontSize: 11, textAlign: 'center', marginTop: 4, lineHeight: 14 },
  proPill: {
    position: 'absolute', top: 8, right: 8,
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: 'rgba(251,191,36,0.18)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.5)',
  },
  proPillText: { color: '#FBBF24', fontSize: 9, fontWeight: '800', letterSpacing: 0.4 },
  activeCheck: { position: 'absolute', top: 8, left: 8 },

  /* Textarea (idea) */
  textarea: {
    minHeight: 90,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 12,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
    padding: 14,
    color: '#fff', fontSize: 14, lineHeight: 20,
    textAlignVertical: 'top',
    marginBottom: 14,
  },

  /* Dialogue cards */
  dialogueCard: {
    padding: 14, marginTop: 10,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 14,
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.10)',
  },
  dialogueCardActive: {
    borderColor: '#EC4899',
    backgroundColor: 'rgba(236,72,153,0.10)',
  },
  dialogueBadgeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  dialogueBadge: {
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.20)',
    alignItems: 'center', justifyContent: 'center',
  },
  dialogueBadgeText: { color: '#CBD5E1', fontSize: 11, fontWeight: '800' },
  dialogueTone: {
    color: '#FBBF24', fontSize: 10, fontWeight: '800',
    letterSpacing: 1, textTransform: 'uppercase',
  },
  dialogueText: { color: '#F1F5F9', fontSize: 15, lineHeight: 22 },

  /* Voice card */
  voiceRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  voiceIcon: { fontSize: 40 },
  voiceLabel: { color: '#fff', fontSize: 16, fontWeight: '800' },
  voiceMeta:  { color: '#94A3B8', fontSize: 12, marginTop: 2, textTransform: 'capitalize' },
  voiceMetaSub: { color: '#64748B', fontSize: 11, marginTop: 2, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  voiceHint: { color: '#64748B', fontSize: 11, textAlign: 'center', marginTop: 8 },
  quotedText: { color: '#E2E8F0', fontSize: 15, lineHeight: 22, fontStyle: 'italic' },

  /* Upload + generate */
  uploadBox: {
    alignItems: 'center', paddingVertical: 40,
    borderStyle: 'dashed' as any,
  },
  uploadTitle: { color: '#fff', fontSize: 15, fontWeight: '700', marginTop: 10 },
  uploadSub:   { color: '#94A3B8', fontSize: 12, marginTop: 4 },
  photoPreview: {
    width: '100%', aspectRatio: 9/16, borderRadius: 10,
    backgroundColor: 'rgba(0,0,0,0.3)',
    maxHeight: 360,
  },
  uploadingText: { color: '#94A3B8', fontSize: 12 },
  resHint: { color: '#94A3B8', fontSize: 11, textAlign: 'center', marginTop: 10, lineHeight: 16 },

  progressBar: {
    height: 6, borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.08)',
    overflow: 'hidden', marginBottom: 8,
  },
  progressFill: { height: '100%', backgroundColor: '#EC4899' },
  progressText: { color: '#CBD5E1', fontSize: 12, textAlign: 'center' },

  videoResult: { width: '100%', aspectRatio: 9/16, borderRadius: 10, backgroundColor: '#000', maxHeight: 420 },
  dualUpload: {
    flex: 1, aspectRatio: 3/4,
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.12)',
    borderStyle: 'dashed' as any, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden', gap: 6,
  },

  /* Variant picker (issue #6) */
  variantGrid: {
    flexDirection: 'row', flexWrap: 'wrap',
    gap: 8, marginTop: 8,
  },
  variantCard: {
    width: '31%', aspectRatio: 1,
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.10)',
    overflow: 'hidden',
    position: 'relative',
  },
  variantCardActive: {
    borderColor: '#34D399',
    backgroundColor: 'rgba(52,211,153,0.10)',
  },
  variantImage: { width: '100%', height: '100%' },
  variantPlaceholder: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 },
  variantStatusText: { color: '#94A3B8', fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  variantBadge: {
    position: 'absolute', bottom: 4, left: 4,
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: 6,
  },
  variantBadgeText: { color: '#fff', fontSize: 9, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.4 },
  variantPickedBadge: {
    position: 'absolute', top: 4, right: 4,
    backgroundColor: '#34D399',
    width: 24, height: 24, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center',
  },

  /* Misc */
  centerBox: {
    alignItems: 'center', gap: 10, paddingVertical: 30,
  },
  centerBoxText: { color: '#94A3B8', fontSize: 13 },

  errorTitle: { color: '#F87171', fontSize: 13, fontWeight: '800', marginBottom: 4 },
  errorText:  { color: '#CBD5E1', fontSize: 12, lineHeight: 16 },

  /* Bottom nav */
  bottomNav: {
    position: 'absolute', left: 0, right: 0, bottom: 0,
    flexDirection: 'row', gap: 10,
    paddingHorizontal: 16, paddingTop: 10, paddingBottom: Platform.OS === 'ios' ? 28 : 14,
    backgroundColor: 'rgba(10,1,24,0.88)',
    borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.06)',
  },

  /* Phase 2b — character variant grid */
  variantGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 10,
  },
  variantCard: {
    width: '48%',
    aspectRatio: 0.85,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: 'rgba(168,85,247,0.35)',
    backgroundColor: 'rgba(10,1,24,0.55)',
    overflow: 'hidden',
    position: 'relative',
  },
  variantCardPicked: {
    borderColor: '#22C55E',
    backgroundColor: 'rgba(34,197,94,0.10)',
  },
  variantImg: { width: '100%', height: '100%' },
  variantPlaceholder: {
    width: '100%',
    paddingVertical: 32,
    alignItems: 'center', justifyContent: 'center',
    borderRadius: 14,
    borderWidth: 1, borderColor: 'rgba(168,85,247,0.25)',
    backgroundColor: 'rgba(10,1,24,0.55)',
    gap: 8,
  },
  variantCenter: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4,
  },
  variantStatusText: { color: '#CBD5E1', fontSize: 12 },
  variantErrText: { color: '#EF4444', fontSize: 12 },
  variantBadge: {
    position: 'absolute', bottom: 6, left: 6,
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 8,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  variantBadgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  variantCheck: {
    position: 'absolute', top: 6, right: 6,
    backgroundColor: '#fff', borderRadius: 12,
  },

  /* Regenerate + or divider */
  ghostBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1, borderColor: 'rgba(168,85,247,0.4)',
    backgroundColor: 'rgba(168,85,247,0.08)',
  },
  ghostBtnText: { color: '#A855F7', fontSize: 12, fontWeight: '700' },
  orDivider: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    marginTop: 18, marginBottom: 6,
  },
  orLine: { flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.12)' },
  orText: { color: '#94A3B8', fontSize: 11, fontWeight: '700', letterSpacing: 1 },

  /* Round 11 — BGM chip row */
  bgmRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 6,
    marginBottom: 4,
  },
  bgmChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(168,85,247,0.4)',
    backgroundColor: 'rgba(168,85,247,0.08)',
  },
  bgmChipActive: {
    backgroundColor: '#A855F7',
    borderColor: '#A855F7',
  },
  bgmChipText: {
    color: '#A855F7',
    fontSize: 11,
    fontWeight: '700',
  },
});
