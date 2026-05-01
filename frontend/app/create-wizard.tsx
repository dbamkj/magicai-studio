/**
 * Creator Wizard — 0-MH Instant Reel flow.
 *
 * Steps:
 *   1) Idea input
 *   2) 3 AI-generated concept cards (tap to select)
 *   3) Progress (polling /api/wizard/job/:id)
 *   4) Preview + lean edits (swap BGM, edit script, regenerate images)
 *   5) MH Cinematic upsell
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput,
  KeyboardAvoidingView, Platform, ActivityIndicator, Share, Dimensions,
  StatusBar, Alert, Modal, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Video, ResizeMode, Audio } from 'expo-av';
import axios from 'axios';
import BottomTabBar from '../src/components/BottomTabBar';
import { useAuth } from '../src/AuthContext';
import { useTierGuard } from '../src/useTierGuard';
import { saveAssetToDevice, suggestFileName } from '../src/downloadHelper';
import AuthGateModal from '../src/components/AuthGateModal';
import GlassHeader from '../src/components/GlassHeader';
import ModelPicker, { MODELS, getModel, type ReelModelId } from '../src/components/ModelPicker';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const { width: W } = Dimensions.get('window');

type Option = {
  title: string;
  tone: string;
  script: string;
  image_query: string;
  voice_style?: string;
  music_mood?: string;
  motion?: string;
};

type BGM = { id: string; name: string; mood?: string; bpm?: number; url: string };

type JobState = {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  stage?: string;
  progress?: number;
  result_url?: string | null;
  error?: string | null;
  duration?: number;
  has_voice?: boolean;
  has_bgm?: boolean;
};

type Step = 'idea' | 'options' | 'plan' | 'progress' | 'preview' | 'upsell';

type ReelMode = 'video' | 'images';

type CreativePlan = {
  creative_plan_id: string;
  hook: string;
  script: string[];
  scene_keywords: string[];
  voice_style: string;
  bgm_style: string;
  mood: string;
  source?: string;
};

const VOICE_PRESETS = [
  { id: 'en-US-JennyNeural', name: 'Jenny (English F)' },
  { id: 'en-US-GuyNeural', name: 'Guy (English M)' },
  { id: 'hi-IN-SwaraNeural', name: 'Swara (Hindi F)' },
  { id: 'hi-IN-MadhurNeural', name: 'Madhur (Hindi M)' },
];

export default function CreateWizard() {
  const router = useRouter();
  const { user } = useAuth();
  const tier = useTierGuard();
  const params = useLocalSearchParams<{ mode?: string; from?: string; id?: string; prompt?: string; title?: string }>();
  const [authGateOpen, setAuthGateOpen] = useState(false);
  const [gateReason, setGateReason] = useState('');
  const [step, setStep] = useState<Step>('idea');
  const [idea, setIdea] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Phase-1: reel-mode toggle ⇒ ⚡ Pixabay stock video (default, free, instant)
  // vs. 🎨 AI Image (Pixabay images + ken-burns motion). Both are free.
  const [reelMode, setReelMode] = useState<ReelMode>(
    (params?.mode === 'images') ? 'images' : 'video',
  );

  // Sprint 36 — Magic Hour-style model dropdown.
  // Default to Kling Pro (free for all). The picker keeps `reelMode` synced
  // with the model's pipeline. Premium models trigger an upgrade alert.
  const initialModelId: ReelModelId = (params?.mode === 'images') ? 'minimax_hailuo' : 'kling_pro';
  const [modelId, setModelId] = useState<ReelModelId>(initialModelId);
  const [resolution, setResolution] = useState<'720p' | '1080p' | '4K'>('1080p');

  // Phase-2 marketplace deep-link: when `from=template`, the source screen has
  // stashed the wizard payload in sessionStorage under `mp_template_prefill`.
  // We auto-start the reel on mount and jump straight to the progress screen.
  const [templateMeta, setTemplateMeta] = useState<{ id: string; title: string; tagline?: string } | null>(null);
  // V2.0 — AI Prompt metadata surfaced on the progress screen when arriving
  // from /ai-prompts. Populated by the auto-start useEffect below.
  const [aiPromptMeta, setAiPromptMeta] = useState<{
    prompt_id?: string;
    hook?: string;
    mood?: string;
    style_tag?: string;
    hashtags?: string[];
    cta?: string;
    detected_category?: string;
    detected_mood?: string;
  } | null>(null);

  const [options, setOptions] = useState<Option[]>([]);
  const [selected, setSelected] = useState<Option | null>(null);

  // Editable after selection
  const [editedScript, setEditedScript] = useState('');
  const [voiceId, setVoiceId] = useState('en-US-JennyNeural');
  const [bgmList, setBgmList] = useState<BGM[]>([]);
  const [bgmUrl, setBgmUrl] = useState<string | undefined>(undefined);

  // Image swap (step 4 lean edit)
  const [imagesModalOpen, setImagesModalOpen] = useState(false);
  const [imagePool, setImagePool] = useState<{ url: string; preview: string; tags?: string; user?: string }[]>([]);
  const [pickedImages, setPickedImages] = useState<string[]>([]);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageSearch, setImageSearch] = useState('');

  const [job, setJob] = useState<JobState | null>(null);
  const pollTimer = useRef<any>(null);

  // Sprint 30 — Creative Plan state (Smart Plan flow)
  const [plan, setPlan] = useState<CreativePlan | null>(null);
  const [planBusy, setPlanBusy] = useState(false);
  // Multi-Scene Story Engine — duration & scene count selector
  // Sprint 36: now driven by the ModelPicker so all models share the same
  // duration state. Smart Plan still derives sceneCount from this value.
  const [storyDuration, setStoryDuration] = useState<number>(20);
  // 15s → 4 scenes (3.75s each), 20s → 5 scenes (4s each), 30s → 6 scenes (5s each)
  const sceneCount = storyDuration <= 15 ? 4 : storyDuration <= 20 ? 5 : 6;
  // Sprint 30b — voice/script language selector (drives both LLM language and
  // automatic neural-voice swap on the backend)
  const [storyLang, setStoryLang] = useState<'english' | 'hindi' | 'hinglish'>('english');

  // Audio preview (for BGM chips)
  const bgmSoundRef = useRef<Audio.Sound | null>(null);
  const [bgmPlayingId, setBgmPlayingId] = useState<string | null>(null);

  useEffect(() => {
    // Prefetch BGM list once
    axios.get(`${BACKEND_URL}/api/wizard/bgm-catalog`)
      .then(r => setBgmList(r.data?.tracks || []))
      .catch(() => {});
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current);
      (async () => {
        if (bgmSoundRef.current) {
          try { await bgmSoundRef.current.unloadAsync(); } catch {}
        }
      })();
    };
  }, []);

  // ── Inspiration tile prefill — fills the idea box but does NOT auto-run ──
  // (Marketplace "Use template" routes to /videogen instead so this branch
  // is now Inspiration-only.)
  useEffect(() => {
    if (params?.from !== 'inspiration') return;
    const promptText = String(params.prompt || params.title || '').trim();
    if (promptText) {
      setIdea(promptText);
      setStep('idea');
    }
  }, [params?.from, params?.prompt, params?.title]);

  // Phase-2 — auto-launch when arriving from /marketplace?from=template&id=...
  //         OR from /ai-prompts?fromPrompt=1 (V2.0 ChatGPT-style prompt wizard).
  // Both paths write `mp_template_prefill` into sessionStorage and expect the
  // wizard to jump straight to step='progress' → fire the render.
  useEffect(() => {
    const fromTemplate = params?.from === 'template';
    const fromAIPrompt = String(params?.fromPrompt || '') === '1';
    if (!fromTemplate && !fromAIPrompt) return;
    // 🔒 Guest gate — block auto-start when not signed in
    if (!user) {
      setGateReason(fromAIPrompt ? 'Creating your AI video' : 'Generating this template');
      setAuthGateOpen(true);
      return;
    }
    let prefill: any = null;
    try {
      if (typeof window !== 'undefined' && (window as any).sessionStorage) {
        const raw = (window as any).sessionStorage.getItem('mp_template_prefill');
        if (raw) prefill = JSON.parse(raw);
      }
    } catch {}
    if (!prefill) return;
    setTemplateMeta({
      id: prefill.id,
      title: prefill.title,
      tagline: prefill.tagline || prefill.script || '',
    });
    // populate state for polish (so the progress screen shows the right idea text)
    setIdea(prefill.idea || prefill.title || '');
    setReelMode((prefill.mode === 'images') ? 'images' : 'video');
    setVoiceId(prefill.voice_id || 'en-US-JennyNeural');
    // Stash AI-prompt metadata in React state so the progress screen can
    // render the hook + hashtags + mood while the job renders.
    if (prefill.ai_prompt_meta) {
      setAiPromptMeta(prefill.ai_prompt_meta);
    }
    // Auto-start the reel without going through prompt-generation/edit steps.
    (async () => {
      try {
        setStep('progress');
        setBusy(true);
        const body: any = {
          idea: prefill.idea || prefill.title,
          title: prefill.title,
          script: prefill.script || prefill.idea || prefill.title,
          image_query: prefill.image_query || prefill.title,
          mode: prefill.mode || 'video',
          total_duration: Number(prefill.total_duration || 10),
          voice_id: prefill.voice_id || 'en-US-JennyNeural',
          voice_style: prefill.voice_style || 'story',
          music_mood: prefill.music_mood || 'cinematic_epic',
          motion: prefill.motion || 'auto',
          aspect_ratio: prefill.aspect_ratio || '9:16',
          duration_per_shot: 2.5,
          user_tier: user?.subscription_tier || 'free',
          lang: prefill.lang || storyLang,
        };
        const r = await axios.post(`${BACKEND_URL}/api/wizard/create-reel`, body, { timeout: 30000 });
        const jid = r.data?.job_id;
        if (jid) {
          setJob({ job_id: jid, status: 'queued', progress: 0 } as any);
          startPolling(jid);
        } else {
          setErr(fromAIPrompt ? 'Could not start reel from your prompt.' : 'Could not start reel from template.');
          setStep('idea');
        }
      } catch (e: any) {
        setErr(e?.response?.data?.detail || e?.message || (fromAIPrompt ? 'Failed to render your AI prompt.' : 'Failed to start template reel.'));
        setStep('idea');
      } finally {
        setBusy(false);
        // clear the prefill so refresh of /create-wizard doesn't re-run it
        try {
          if (typeof window !== 'undefined' && (window as any).sessionStorage) {
            (window as any).sessionStorage.removeItem('mp_template_prefill');
          }
        } catch {}
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ------- Step 1: idea → 3 options ------- */
  const fetchOptions = useCallback(async () => {
    // 🔒 Guest gate
    if (!user) {
      setGateReason('Generating AI concepts');
      setAuthGateOpen(true);
      return;
    }
    const i = idea.trim();
    if (i.length < 5) { setErr('Please describe your idea (at least 5 chars).'); return; }
    setErr(null); setBusy(true);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/wizard/prompts`, { idea: i, lang: storyLang }, { timeout: 45000 });
      const opts: Option[] = r.data?.options || [];
      if (!opts.length) throw new Error('AI returned no options — try a different idea.');
      setOptions(opts);
      setStep('options');
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to generate concepts.');
    } finally { setBusy(false); }
  }, [idea, user, storyLang, router]);

  /* ------- Sprint 30: Smart Plan (Creative Plan Engine) ------- */
  const fetchCreativePlan = useCallback(async () => {
    const i = idea.trim();
    if (i.length < 5) { setErr('Please describe your idea (at least 5 chars).'); return; }
    setErr(null); setPlanBusy(true);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/creative-plan`, {
        idea: i,
        language: storyLang,
        duration: storyDuration,
        scene_count: sceneCount,
      }, { timeout: 60000 });
      const p = r.data as CreativePlan;
      if (!p?.creative_plan_id) throw new Error('LLM returned no plan — try again.');
      setPlan(p);
      setStep('plan');
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to generate creative plan.');
    } finally { setPlanBusy(false); }
  }, [idea]);

  /* ------- Sprint 30: build reel from a Creative Plan ------- */
  const startReelFromPlan = useCallback(async (cp: CreativePlan) => {
    setErr(null); setBusy(true);
    try {
      const body: any = {
        idea,
        title: cp.hook?.slice(0, 60) || idea.slice(0, 60),
        // script is just a placeholder — backend re-derives from the plan
        script: cp.hook || cp.script?.[0] || idea,
        // use first scene_keyword as a fallback for image_query/single-clip path
        image_query: cp.scene_keywords?.[0] || idea,
        mode: reelMode,
        total_duration: storyDuration,
        voice_id: voiceId,
        voice_style: 'story',          // backend will override from plan.voice_style
        music_mood: 'cinematic_epic',  // backend will override from plan.bgm_style
        motion: 'auto',
        aspect_ratio: '9:16',
        duration_per_shot: 2.5,
        creative_plan_id: cp.creative_plan_id,
        // Sprint 36 — ModelPicker selections
        model_id: modelId,
        resolution,
        user_tier: user?.subscription_tier || 'free',
        lang: storyLang,
      };
      const r = await axios.post(`${BACKEND_URL}/api/wizard/create-reel`, body, { timeout: 30000 });
      const jid = r.data?.job_id as string;
      setJob({ job_id: jid, status: 'queued' });
      setStep('progress');
      startPolling(jid);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to create reel.');
    } finally { setBusy(false); }
  }, [idea, voiceId, reelMode]);

  /* ------- Step 2: pick one → start job ------- */
  const startReel = useCallback(async (opt: Option, overrides?: Partial<Option> & { script?: string; bgm_url?: string; voice_id?: string; images?: string[] }) => {
    setErr(null); setBusy(true);
    try {
      const scriptText = (overrides?.script ?? opt.script) || '';
      const body: any = {
        idea,
        title: opt.title,
        script: scriptText,
        image_query: opt.image_query || idea,
        mode: reelMode,                                  // 'video' | 'images'
        total_duration: 10,
        voice_id: overrides?.voice_id || voiceId,
        voice_style: opt.voice_style || 'story',
        music_mood: opt.music_mood || 'cinematic_epic',
        bgm_url: overrides?.bgm_url ?? bgmUrl,
        motion: opt.motion || 'auto',
        aspect_ratio: '9:16',
        duration_per_shot: 2.5,
        user_tier: user?.subscription_tier || 'free',
        lang: storyLang,
      };
      // Image overrides only apply to image-mode (video mode uses Pixabay video stream)
      if (reelMode === 'images') {
        if (overrides?.images && overrides.images.length >= 2) {
          body.images = overrides.images;
        } else if (pickedImages.length >= 2) {
          body.images = pickedImages;
        }
      }
      const r = await axios.post(`${BACKEND_URL}/api/wizard/create-reel`, body, { timeout: 30000 });
      const jid = r.data?.job_id as string;
      setJob({ job_id: jid, status: 'queued' });
      setStep('progress');
      startPolling(jid);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to create reel.');
    } finally { setBusy(false); }
  }, [idea, voiceId, bgmUrl, pickedImages, reelMode]);

  const startPolling = useCallback((jid: string) => {
    if (pollTimer.current) clearInterval(pollTimer.current);
    pollTimer.current = setInterval(async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/wizard/job/${jid}`, { timeout: 10000 });
        const j = r.data as JobState;
        setJob(j);
        if (j.status === 'completed' || j.status === 'failed') {
          if (pollTimer.current) { clearInterval(pollTimer.current); pollTimer.current = null; }
          if (j.status === 'completed') setStep('preview');
        }
      } catch {}
    }, 2000);
  }, []);

  const handleSelectOption = (opt: Option) => {
    setSelected(opt);
    setEditedScript(opt.script || '');
    // default BGM mood
    const mood = (opt.music_mood || 'cinematic_epic').toLowerCase();
    const matched = bgmList.find(b => (b.mood || '').includes(mood.split('_')[0]));
    setBgmUrl(matched?.url);
    // auto-start the reel using defaults
    startReel(opt);
  };

  /* ------- BGM chip preview ------- */
  const previewBGM = async (b: BGM) => {
    try {
      if (bgmSoundRef.current) {
        try { await bgmSoundRef.current.unloadAsync(); } catch {}
        bgmSoundRef.current = null;
      }
      if (bgmPlayingId === b.id) { setBgmPlayingId(null); return; }
      const s = new Audio.Sound();
      await s.loadAsync({ uri: `${BACKEND_URL}${b.url}` });
      await s.setVolumeAsync(0.9);
      bgmSoundRef.current = s;
      setBgmPlayingId(b.id);
      await s.playAsync();
      // stop after 5s
      setTimeout(async () => {
        try { await s.stopAsync(); await s.unloadAsync(); } catch {}
        setBgmPlayingId(null);
      }, 5000);
    } catch {}
  };

  /* ------- Step 4 regenerate ------- */
  const regenerateWithEdits = useCallback(() => {
    if (!selected) return;
    startReel(selected, { script: editedScript, bgm_url: bgmUrl, voice_id: voiceId, images: pickedImages.length >= 2 ? pickedImages : undefined });
  }, [selected, editedScript, bgmUrl, voiceId, pickedImages, startReel]);

  /* ------- Step 4 image swap ------- */
  const openImagePicker = useCallback(async () => {
    if (!selected) return;
    const q = imageSearch.trim() || selected.image_query || idea;
    setImagesModalOpen(true);
    setImageLoading(true);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/wizard/preview-images`, { image_query: q, count: 12 }, { timeout: 15000 });
      setImagePool(r.data?.images || []);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Could not load images');
    } finally { setImageLoading(false); }
  }, [selected, idea, imageSearch]);

  const togglePickedImage = (url: string) => {
    setPickedImages((prev) => {
      if (prev.includes(url)) return prev.filter(u => u !== url);
      if (prev.length >= 4) return prev; // cap at 4
      return [...prev, url];
    });
  };

  const confirmImageSwap = () => {
    if (pickedImages.length < 2) { Alert.alert('Pick at least 2 images', 'The reel needs 2 to 4 images.'); return; }
    setImagesModalOpen(false);
    if (selected) startReel(selected, { script: editedScript, bgm_url: bgmUrl, voice_id: voiceId, images: pickedImages });
  };

  /* ------- Step 5 upsell ------- */
  const [upsellBusy, setUpsellBusy] = useState(false);
  const tryCinematic = useCallback(async () => {
    if (!selected) return;
    setUpsellBusy(true);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/wizard/upsell-cinematic`, {
        script: editedScript || selected.script,
        voice_id: voiceId,
        motion: selected.motion || 'cinematic_zoom',
        duration: 5,
        aspect_ratio: '9:16',
      }, { timeout: 20000 });
      if (r.data?.ok === false) {
        Alert.alert('Daily AI budget reached', r.data?.reason || 'Try again later.');
      } else {
        Alert.alert('Cinematic ready to queue', `This will cost ~${r.data?.estimated_credits || 50} credits. Going to the AI Video screen now.`, [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Continue', onPress: () => router.push('/videogen' as any) },
        ]);
      }
    } catch (e: any) {
      Alert.alert('Upsell failed', e?.response?.data?.detail || e?.message || 'Try again.');
    } finally { setUpsellBusy(false); }
  }, [selected, editedScript, voiceId, router]);

  /* ------- Render helpers ------- */
  const Header = (
    <GlassHeader
      icon="sparkles"
      title="Creator Wizard"
      subtitle="Free · Instant Reel"
      onBack={() => {
        if (step === 'idea') router.back();
        else if (step === 'options') setStep('idea');
        else if (step === 'plan') setStep('idea');
        else if (step === 'preview') setStep('options');
        else if (step === 'upsell') setStep('preview');
        else router.back();
      }}
    />
  );

  const stepBadges = (
    <View style={s.stepBar}>
      {(['idea','options','progress','preview','upsell'] as Step[]).map((st, i) => (
        <View key={st} style={[s.stepDot, (step === st ? s.stepDotActive : ([ 'idea','options','progress','preview','upsell' ].indexOf(step) > i ? s.stepDotDone : null))]}>
          <Text style={[s.stepDotTxt, (step === st || [ 'idea','options','progress','preview','upsell' ].indexOf(step) > i) ? { color: '#0B1120' } : null ]}>{i + 1}</Text>
        </View>
      ))}
    </View>
  );

  return (
    <View style={{ flex: 1 }}>
    <SafeAreaView edges={['top']} style={s.safe}>
      <StatusBar barStyle="light-content" />
      {Header}
      {stepBadges}

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 110 }} keyboardShouldPersistTaps="handled">
          {err ? (
            <View style={s.errBanner}><Ionicons name="alert-circle" size={16} color="#F87171" /><Text style={s.errText}>{err}</Text></View>
          ) : null}

          {/* STEP 1: IDEA */}
          {step === 'idea' && (
            <View>
              <LinearGradient colors={['#312E81', '#1E1B4B']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.introCard}>
                <Text style={s.introTitle}>What do you want to create today?</Text>
                <Text style={s.introSub}>Describe your idea in a sentence. Our AI will craft 3 distinct concepts and build an instant reel for you.</Text>
              </LinearGradient>

              {/* Phase-1: Reel-mode toggle (Pixabay video vs AI image ken-burns)
                  Sprint 36-rev: per user request, reverted from the new
                  ModelPicker rollout — the Creator Wizard pipeline IS the
                  Pixabay path, so showing a premium MH catalog here is
                  misleading. Premium models live on the dedicated tool
                  screens (AI Video Gen, Motion Control, etc.) instead. */}
              <Text style={[s.label, { marginTop: 4 }]}>Reel style</Text>
              <View style={s.modeRow}>
                <TouchableOpacity
                  activeOpacity={0.85}
                  style={[s.modeCard, reelMode === 'video' && s.modeCardActive]}
                  onPress={() => setReelMode('video')}
                >
                  <View style={s.modeHeader}>
                    <Text style={s.modeIcon}>⚡</Text>
                    <Text style={s.modeBadge}>FREE · INSTANT</Text>
                  </View>
                  <Text style={s.modeTitle}>Stock Video</Text>
                  <Text style={s.modeDesc}>Real Pixabay clips · cinematic · always free</Text>
                  {reelMode === 'video' && <View style={s.modeCheck}><Ionicons name="checkmark" size={12} color="#0B1120" /></View>}
                </TouchableOpacity>
                <TouchableOpacity
                  activeOpacity={0.85}
                  style={[s.modeCard, reelMode === 'images' && s.modeCardActive]}
                  onPress={() => setReelMode('images')}
                >
                  <View style={s.modeHeader}>
                    <Text style={s.modeIcon}>🎨</Text>
                    <Text style={s.modeBadge}>FREE</Text>
                  </View>
                  <Text style={s.modeTitle}>AI Images</Text>
                  <Text style={s.modeDesc}>4 photos · ken-burns motion · stylised</Text>
                  {reelMode === 'images' && <View style={s.modeCheck}><Ionicons name="checkmark" size={12} color="#0B1120" /></View>}
                </TouchableOpacity>
              </View>

              {/* Story length selector (Multi-Scene Story Engine) */}
              <View style={s.storyLenRow}>
                <Text style={s.storyLenLabel}>Story length</Text>
                <View style={s.storyLenSeg}>
                  {([15, 20, 30] as const).map((d) => {
                    const active = storyDuration === d;
                    const scenes = d === 15 ? 4 : d === 20 ? 5 : 6;
                    return (
                      <TouchableOpacity
                        key={d}
                        onPress={() => setStoryDuration(d)}
                        style={[s.storyLenBtn, active && s.storyLenBtnActive]}
                        activeOpacity={0.85}
                      >
                        <Text style={[s.storyLenBtnTxt, active && s.storyLenBtnTxtActive]}>
                          {d}s
                        </Text>
                        <Text style={[s.storyLenBtnSub, active && { color: '#0B1120' }]}>{scenes} scenes</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
              <View style={s.upsellHint}>
                <Ionicons name="flash" size={11} color="#FBBF24" />
                <Text style={s.upsellHintTxt}>Want a fully AI-generated cinematic reel? You'll see the MagiCAi upgrade after preview.</Text>
              </View>

              <Text style={s.label}>Your idea</Text>
              <TextInput
                value={idea}
                onChangeText={setIdea}
                placeholder="e.g. A devotional reel about Lord Krishna's flute"
                placeholderTextColor="#64748B"
                style={s.ideaInput}
                multiline
                maxLength={400}
              />
              <Text style={s.hint}>{idea.length}/400</Text>

              <Text style={[s.label, { marginTop: 16 }]}>Quick ideas</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
                {[
                  'Morning meditation for busy professionals',
                  'Devotional reel — flute of Lord Krishna',
                  'Monday motivation in Hindi — hustle',
                  'Funny office life of Indian techies',
                  'Why Bollywood villains always monologue',
                ].map(q => (
                  <TouchableOpacity key={q} style={s.quickChip} onPress={() => setIdea(q)}>
                    <Text style={s.quickChipTxt}>{q}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity style={[s.primaryBtn, (busy || idea.trim().length < 5) ? s.btnDisabled : null]} onPress={fetchOptions} disabled={busy || idea.trim().length < 5}>
                {busy ? <ActivityIndicator color="#fff" /> : (
                  <>
                    <Ionicons name="sparkles" size={18} color="#fff" />
                    <Text style={s.primaryBtnTxt}>Generate 3 concepts</Text>
                  </>
                )}
              </TouchableOpacity>

              {/* Sprint 30 — Smart Plan (Creative Plan Engine) */}
              {/* Story duration is now driven by the ModelPicker above (the
                  cascading "Duration" segmented row), so we no longer render
                  a separate selector here. */}

              {/* Language selector — drives both LLM language AND auto Hindi-voice swap */}
              <View style={s.storyLenRow}>
                <Text style={s.storyLenLabel}>Voice / Script language</Text>
                <View style={s.storyLenSeg}>
                  {(['english', 'hindi', 'hinglish'] as const).map((lang) => {
                    const active = storyLang === lang;
                    const labels = { english: 'English', hindi: 'हिन्दी', hinglish: 'Hinglish' };
                    return (
                      <TouchableOpacity
                        key={lang}
                        onPress={() => setStoryLang(lang)}
                        style={[s.storyLenBtn, active && s.storyLenBtnActive]}
                        activeOpacity={0.85}
                      >
                        <Text style={[s.storyLenBtnTxt, { fontSize: 14 }, active && s.storyLenBtnTxtActive]}>
                          {labels[lang]}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>

              <TouchableOpacity
                style={[s.smartPlanBtn, (planBusy || idea.trim().length < 5) ? s.btnDisabled : null]}
                onPress={fetchCreativePlan}
                disabled={planBusy || idea.trim().length < 5}
                activeOpacity={0.85}
              >
                {planBusy ? <ActivityIndicator color="#FBBF24" /> : (
                  <>
                    <Ionicons name="rocket" size={16} color="#FBBF24" />
                    <Text style={s.smartPlanBtnTxt}>✨ Smart Plan · {storyDuration}s story</Text>
                    <View style={s.smartPlanBadge}><Text style={s.smartPlanBadgeTxt}>NEW</Text></View>
                  </>
                )}
              </TouchableOpacity>
              <Text style={s.smartPlanHint}>
                Multi-scene cinematic reel — {sceneCount} scene-matched clips, xfade transitions, emotion-tuned voice.
              </Text>
            </View>
          )}

          {/* STEP 1.5: SMART PLAN PREVIEW (Sprint 30) */}
          {step === 'plan' && plan && (
            <View>
              <LinearGradient colors={['#312E81', '#1E1B4B']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.introCard}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Ionicons name="rocket" size={18} color="#FBBF24" />
                  <Text style={[s.introTitle, { fontSize: 18 }]}>Your Creative Plan</Text>
                  <View style={s.planSourcePill}>
                    <Text style={s.planSourcePillTxt}>{plan.source === 'cache' ? 'Cached' : 'AI'}</Text>
                  </View>
                </View>
                <Text style={s.introSub}>One blueprint drives every step — visuals, voice, and music stay aligned.</Text>
              </LinearGradient>

              {/* Hook */}
              <View style={s.planSection}>
                <Text style={s.planLabel}>HOOK</Text>
                <Text style={s.planHook} numberOfLines={3}>{plan.hook}</Text>
              </View>

              {/* Script (one bullet per scene) */}
              <View style={s.planSection}>
                <Text style={s.planLabel}>SCRIPT · {plan.script?.length || 0} SCENES</Text>
                {plan.script?.map((line, i) => (
                  <View key={i} style={s.scriptRow}>
                    <View style={s.scriptIdx}><Text style={s.scriptIdxTxt}>{i + 1}</Text></View>
                    <Text style={s.scriptLine}>{line}</Text>
                  </View>
                ))}
              </View>

              {/* Scene keywords (Pixabay search queries) */}
              <View style={s.planSection}>
                <Text style={s.planLabel}>VISUAL SEARCH KEYWORDS</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {plan.scene_keywords?.map((kw, i) => (
                    <View key={i} style={s.keywordChip}>
                      <Ionicons name="search" size={10} color="#A78BFA" />
                      <Text style={s.keywordChipTxt}>{kw}</Text>
                    </View>
                  ))}
                </View>
              </View>

              {/* Voice + BGM + Mood metadata */}
              <View style={s.planMetaGrid}>
                <View style={s.planMetaCard}>
                  <Ionicons name="mic" size={14} color="#A78BFA" />
                  <Text style={s.planMetaLabel}>Voice</Text>
                  <Text style={s.planMetaValue} numberOfLines={2}>{plan.voice_style}</Text>
                </View>
                <View style={s.planMetaCard}>
                  <Ionicons name="musical-notes" size={14} color="#FBBF24" />
                  <Text style={s.planMetaLabel}>BGM</Text>
                  <Text style={s.planMetaValue} numberOfLines={2}>{plan.bgm_style}</Text>
                </View>
                <View style={s.planMetaCard}>
                  <Ionicons name="color-palette" size={14} color="#EC4899" />
                  <Text style={s.planMetaLabel}>Mood</Text>
                  <Text style={s.planMetaValue}>{plan.mood}</Text>
                </View>
              </View>

              {/* Action buttons */}
              <TouchableOpacity
                style={[s.primaryBtn, busy ? s.btnDisabled : null]}
                onPress={() => startReelFromPlan(plan)}
                disabled={busy}
              >
                {busy ? <ActivityIndicator color="#fff" /> : (
                  <>
                    <Ionicons name="film" size={18} color="#fff" />
                    <Text style={s.primaryBtnTxt}>Create my reel</Text>
                  </>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={s.ghostBtn}
                onPress={() => { setPlan(null); fetchCreativePlan(); }}
                disabled={planBusy}
              >
                {planBusy ? <ActivityIndicator color="#94A3B8" /> : (
                  <Text style={s.ghostBtnTxt}>🔄 Regenerate plan</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity style={[s.ghostBtn, { marginTop: 6 }]} onPress={() => setStep('idea')}>
                <Text style={s.ghostBtnTxt}>← Back to idea</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* STEP 2: OPTIONS */}
          {step === 'options' && (
            <View>
              <Text style={s.sectionTitle}>Choose your concept</Text>
              <Text style={s.sectionSub}>Each option has a different tone. Tap to start generating your reel.</Text>
              {options.map((opt, idx) => (
                <TouchableOpacity key={idx} style={s.optCard} activeOpacity={0.85} onPress={() => handleSelectOption(opt)}>
                  <LinearGradient
                    colors={[
                      ['#6366F1','#4338CA'],
                      ['#EC4899','#BE185D'],
                      ['#F59E0B','#B45309'],
                    ][idx % 3] as any}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 1 }}
                    style={s.optCardInner}
                  >
                    <View style={s.optHeaderRow}>
                      <View style={s.toneChip}><Text style={s.toneChipTxt}>{opt.tone}</Text></View>
                      <Text style={s.optIdx}>#{idx + 1}</Text>
                    </View>
                    <Text style={s.optTitle}>{opt.title}</Text>
                    <Text style={s.optScript} numberOfLines={4}>{opt.script}</Text>
                    <View style={s.optMeta}>
                      <View style={s.metaPill}><Ionicons name="musical-notes" size={11} color="#E2E8F0" /><Text style={s.metaTxt}> {opt.music_mood || 'cinematic'}</Text></View>
                      <View style={s.metaPill}><Ionicons name="image" size={11} color="#E2E8F0" /><Text style={s.metaTxt}> {opt.image_query?.slice(0,22)}</Text></View>
                      <View style={s.metaPill}><Ionicons name="film" size={11} color="#E2E8F0" /><Text style={s.metaTxt}> {opt.motion || 'ken_burns'}</Text></View>
                    </View>
                    <View style={s.optCTA}><Text style={s.optCTATxt}>Use this concept →</Text></View>
                  </LinearGradient>
                </TouchableOpacity>
              ))}
              <TouchableOpacity style={s.ghostBtn} onPress={() => setStep('idea')}>
                <Text style={s.ghostBtnTxt}>Try a different idea</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* STEP 3: PROGRESS */}
          {step === 'progress' && (
            <View style={{ alignItems: 'center', paddingVertical: 30 }}>
              {/* V2.0 — AI Prompt context card (only shown when arriving from
                   /ai-prompts; renders the hook, mood, hashtags so the user
                   has something beautiful to read while the job renders). */}
              {aiPromptMeta?.hook ? (
                <View style={aiMetaStyles.card}>
                  <View style={aiMetaStyles.badgeRow}>
                    <Text style={aiMetaStyles.badge}>✨ AI CRAFTED</Text>
                    {aiPromptMeta.style_tag ? (
                      <Text style={aiMetaStyles.styleTag}>{aiPromptMeta.style_tag}</Text>
                    ) : null}
                  </View>
                  <Text style={aiMetaStyles.hook} numberOfLines={4}>
                    “{aiPromptMeta.hook}”
                  </Text>
                  <View style={aiMetaStyles.chipsRow}>
                    {aiPromptMeta.detected_category ? (
                      <View style={aiMetaStyles.chip}>
                        <Text style={aiMetaStyles.chipTxt}>🏷️ {aiPromptMeta.detected_category}</Text>
                      </View>
                    ) : null}
                    {aiPromptMeta.mood ? (
                      <View style={aiMetaStyles.chip}>
                        <Text style={aiMetaStyles.chipTxt}>💫 {aiPromptMeta.mood}</Text>
                      </View>
                    ) : null}
                  </View>
                  {Array.isArray(aiPromptMeta.hashtags) && aiPromptMeta.hashtags.length > 0 ? (
                    <Text style={aiMetaStyles.hashtags} numberOfLines={1}>
                      {aiPromptMeta.hashtags.slice(0, 4).join('  ')}
                    </Text>
                  ) : null}
                </View>
              ) : null}

              <ActivityIndicator size="large" color="#8B5CF6" />
              <Text style={s.progressTitle}>
                {aiPromptMeta?.hook ? 'AI is crafting your video…' : 'Building your reel…'}
              </Text>
              <Text style={s.progressStage}>{job?.stage ? job.stage.replace(/_/g,' ') : 'queued'}</Text>
              <View style={s.barTrack}><View style={[s.barFill, { width: `${job?.progress || 5}%` }]} /></View>
              <Text style={s.progressPct}>{job?.progress || 0}%</Text>
              <Text style={s.progressHint}>Typically 10–30 seconds</Text>
              <View style={s.stagesList}>
                {(reelMode === 'video' ? [
                  ['fetch_video', 'Finding stock video', 'image'],
                  ['process_video', 'Processing video', 'film'],
                  ['tts', 'Generating voice', 'mic'],
                  ['mux', 'Mixing audio', 'musical-notes'],
                  ['done', 'Finalizing', 'checkmark-circle'],
                ] : [
                  ['fetch_images', 'Finding images', 'image'],
                  ['animate', 'Adding motion', 'film'],
                  ['concat', 'Editing clips', 'cut'],
                  ['tts', 'Generating voice', 'mic'],
                  ['mux', 'Mixing audio', 'musical-notes'],
                  ['done', 'Finalizing', 'checkmark-circle'],
                ]).map(([k, label, icon]) => {
                  const stages = reelMode === 'video'
                    ? ['queued','fetch_video','process_video','tts','mux','done']
                    : ['queued','fetch_images','animate','concat','tts','mux','done'];
                  const cur = stages.indexOf(job?.stage || 'queued');
                  const mine = stages.indexOf(k);
                  const active = mine <= cur && cur > 0;
                  return (
                    <View key={k} style={s.stageRow}>
                      <Ionicons name={active ? 'checkmark-circle' : 'ellipse-outline'} size={16} color={active ? '#10B981' : '#475569'} />
                      <Text style={[s.stageTxt, active ? { color: '#fff' } : null]}>{label}</Text>
                    </View>
                  );
                })}
              </View>
              {job?.status === 'failed' && (
                <View style={{ marginTop: 12, alignItems: 'center' }}>
                  <Text style={s.errText}>{job.error || 'Something went wrong'}</Text>
                  <TouchableOpacity style={s.primaryBtn} onPress={() => setStep('options')}>
                    <Text style={s.primaryBtnTxt}>Try again</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          )}

          {/* STEP 4: PREVIEW + LEAN EDITS */}
          {step === 'preview' && job?.result_url && (
            <View>
              <View style={s.previewBox}>
                <Video
                  source={{ uri: `${BACKEND_URL}${job.result_url}` }}
                  style={s.previewVideo}
                  useNativeControls
                  resizeMode={ResizeMode.CONTAIN}
                  isLooping
                  shouldPlay
                />
              </View>

              <View style={s.statsRow}>
                <View style={s.statPill}><Ionicons name="time" size={12} color="#A78BFA" /><Text style={s.statTxt}> {Math.round(job.duration || 10)}s</Text></View>
                <View style={s.statPill}><Ionicons name={job.has_voice ? 'mic' : 'mic-off'} size={12} color="#A78BFA" /><Text style={s.statTxt}> {job.has_voice ? 'Voice' : 'No voice'}</Text></View>
                <View style={s.statPill}><Ionicons name="musical-notes" size={12} color="#A78BFA" /><Text style={s.statTxt}> {job.has_bgm ? 'BGM' : 'Silent'}</Text></View>
                <View style={[s.statPill, { backgroundColor: 'rgba(16,185,129,0.15)', borderColor: 'rgba(16,185,129,0.4)' }]}>
                  <Text style={[s.statTxt, { color: '#10B981' }]}>Free</Text>
                </View>
              </View>

              <View style={s.actionRow}>
                <TouchableOpacity style={[s.actionBtn, { backgroundColor: '#10B981' }]} onPress={() => setStep('upsell')}>
                  <Ionicons name="flash" size={16} color="#fff" />
                  <Text style={s.actionBtnTxt}>Cinematic AI</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.actionBtn} onPress={async () => {
                  try { await Share.share({ url: `${BACKEND_URL}${job.result_url}`, message: selected?.title || 'My AI Reel' }); } catch {}
                }}>
                  <Ionicons name="share-social" size={16} color="#fff" />
                  <Text style={s.actionBtnTxt}>Share</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.actionBtn, !tier.canUseFeature('download_to_gallery') && { opacity: 0.65 }]}
                  onPress={async () => {
                    if (!job?.result_url) return;
                    if (!tier.requireFeature('download_to_gallery', 'Asset download to gallery')) return;
                    const url = `${BACKEND_URL}${job.result_url}`;
                    const fname = suggestFileName(url, 'video');
                    await saveAssetToDevice(url, fname, 'video');
                  }}
                >
                  <Ionicons
                    name={tier.canUseFeature('download_to_gallery') ? 'download' : 'lock-closed'}
                    size={16} color="#fff" />
                  <Text style={s.actionBtnTxt}>
                    {tier.canUseFeature('download_to_gallery') ? 'Download' : 'Download (Pro)'}
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.actionBtn} onPress={() => setStep('options')}>
                  <Ionicons name="refresh" size={16} color="#fff" />
                  <Text style={s.actionBtnTxt}>Retry</Text>
                </TouchableOpacity>
              </View>

              {/* Lean edit — script */}
              <Text style={s.editTitle}>Refine script</Text>
              <TextInput
                value={editedScript}
                onChangeText={setEditedScript}
                multiline
                style={s.editInput}
                placeholder="Tap to edit the spoken script"
                placeholderTextColor="#475569"
              />

              {/* Lean edit — voice */}
              <Text style={s.editTitle}>Voice</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {VOICE_PRESETS.map(v => (
                  <TouchableOpacity key={v.id} style={[s.chip, voiceId === v.id && s.chipActive]} onPress={() => setVoiceId(v.id)}>
                    <Text style={[s.chipTxt, voiceId === v.id && s.chipTxtActive]}>{v.name}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>

              {/* Lean edit — BGM */}
              <Text style={s.editTitle}>Background music</Text>
              {bgmList.length === 0 ? (
                <Text style={s.hint}>No BGM tracks available</Text>
              ) : (
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {bgmList.map(b => (
                    <View key={b.id} style={{ marginRight: 8 }}>
                      <TouchableOpacity
                        style={[s.chip, bgmUrl === b.url && s.chipActive]}
                        onPress={() => setBgmUrl(b.url)}
                      >
                        <Text style={[s.chipTxt, bgmUrl === b.url && s.chipTxtActive]}>{b.name}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={s.bgmPlay} onPress={() => previewBGM(b)}>
                        <Ionicons name={bgmPlayingId === b.id ? 'stop-circle' : 'play-circle'} size={22} color="#8B5CF6" />
                      </TouchableOpacity>
                    </View>
                  ))}
                </ScrollView>
              )}

              {/* Lean edit — Images */}
              <Text style={s.editTitle}>Images ({pickedImages.length > 0 ? `${pickedImages.length} picked` : 'auto from Pixabay'})</Text>
              <TouchableOpacity style={s.imagesEditBtn} onPress={openImagePicker} activeOpacity={0.85}>
                <Ionicons name="images" size={16} color="#A78BFA" />
                <Text style={s.imagesEditTxt}>Swap / reselect images from Pixabay</Text>
                <Ionicons name="chevron-forward" size={14} color="#A78BFA" />
              </TouchableOpacity>

              <TouchableOpacity style={[s.primaryBtn, { marginTop: 14 }]} onPress={regenerateWithEdits} disabled={busy}>
                {busy ? <ActivityIndicator color="#fff" /> : (
                  <>
                    <Ionicons name="sparkles" size={16} color="#fff" />
                    <Text style={s.primaryBtnTxt}>Regenerate (Free)</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          )}

          {/* STEP 5: UPSELL */}
          {step === 'upsell' && (
            <View>
              <LinearGradient colors={['#F59E0B', '#EC4899', '#8B5CF6']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.upsellCard}>
                <Text style={s.upsellPill}>PREMIUM ✨</Text>
                <Text style={s.upsellTitle}>Upgrade to Cinematic AI</Text>
                <Text style={s.upsellSub}>Full MagiCAi AI video — fluid camera, realistic motion, voice-matched mouth movement. Typically 50–200 credits.</Text>

                <View style={{ marginTop: 14 }}>
                  {[
                    ['Real AI video (not stills + motion)', 'videocam'],
                    ['Native voice-to-image lip sync', 'mic-circle'],
                    ['Cinematic camera & lighting', 'film'],
                    ['Export in HD 1080p', 'sparkles'],
                  ].map(([t, ic]) => (
                    <View key={t} style={s.upsellRow}>
                      <Ionicons name={ic as any} size={16} color="#FEF08A" />
                      <Text style={s.upsellRowTxt}>{t}</Text>
                    </View>
                  ))}
                </View>

                <TouchableOpacity style={[s.primaryBtn, { marginTop: 18, backgroundColor: '#0B1120' }]} onPress={tryCinematic} disabled={upsellBusy}>
                  {upsellBusy ? <ActivityIndicator color="#fff" /> : (
                    <>
                      <Ionicons name="flash" size={16} color="#fff" />
                      <Text style={s.primaryBtnTxt}>Generate cinematic (~50 cr)</Text>
                    </>
                  )}
                </TouchableOpacity>
              </LinearGradient>

              <TouchableOpacity style={[s.ghostBtn, { marginTop: 16 }]} onPress={() => setStep('preview')}>
                <Text style={s.ghostBtnTxt}>Back to preview</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>

      {/* ===== Image Picker Modal (step 4 lean edit) ===== */}
      <Modal visible={imagesModalOpen} animationType="slide" onRequestClose={() => setImagesModalOpen(false)} transparent>
        <View style={s.modalBackdrop}>
          <View style={s.modalSheet}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>Swap images</Text>
              <TouchableOpacity onPress={() => setImagesModalOpen(false)}>
                <Ionicons name="close" size={24} color="#94A3B8" />
              </TouchableOpacity>
            </View>
            <Text style={s.modalSub}>Pick 2–4 images. Current: {pickedImages.length} selected</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 10, marginBottom: 6 }}>
              <TextInput
                value={imageSearch}
                onChangeText={setImageSearch}
                placeholder={selected?.image_query || 'Search keywords'}
                placeholderTextColor="#64748B"
                style={s.modalSearch}
                onSubmitEditing={openImagePicker}
              />
              <TouchableOpacity onPress={openImagePicker} style={s.searchBtn}>
                <Ionicons name="search" size={16} color="#fff" />
              </TouchableOpacity>
            </View>
            {imageLoading ? (
              <View style={{ paddingVertical: 40, alignItems: 'center' }}><ActivityIndicator color="#8B5CF6" /></View>
            ) : (
              <ScrollView contentContainerStyle={s.gridScroll}>
                <View style={s.grid}>
                  {imagePool.map((img) => {
                    const sel = pickedImages.includes(img.url);
                    const idx = pickedImages.indexOf(img.url);
                    return (
                      <TouchableOpacity key={img.url} onPress={() => togglePickedImage(img.url)} activeOpacity={0.8} style={[s.gridItem, sel && s.gridItemSel]}>
                        <Image source={{ uri: img.preview || img.url }} style={s.gridImg} />
                        {sel && (
                          <View style={s.selBadge}>
                            <Text style={s.selBadgeTxt}>{idx + 1}</Text>
                          </View>
                        )}
                      </TouchableOpacity>
                    );
                  })}
                  {imagePool.length === 0 && !imageLoading && (
                    <Text style={{ color: '#64748B', textAlign: 'center', paddingVertical: 30, width: '100%' }}>No images found. Try another keyword.</Text>
                  )}
                </View>
              </ScrollView>
            )}
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
              <TouchableOpacity style={[s.ghostBtnFlat, { flex: 1 }]} onPress={() => { setPickedImages([]); setImagesModalOpen(false); }}>
                <Text style={s.ghostBtnTxt}>Clear & auto-pick</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.primaryBtn, { flex: 1, marginTop: 0, opacity: pickedImages.length < 2 ? 0.5 : 1 }]} onPress={confirmImageSwap} disabled={pickedImages.length < 2}>
                <Ionicons name="sparkles" size={14} color="#fff" />
                <Text style={s.primaryBtnTxt}>Use {pickedImages.length} image{pickedImages.length === 1 ? '' : 's'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
    <BottomTabBar active="create" />
    <AuthGateModal
      visible={authGateOpen}
      onClose={() => setAuthGateOpen(false)}
      reason={gateReason}
      nextRoute="/create-wizard"
    />
    </View>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0B1120' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#1E293B' },
  headerBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  headerSub: { color: '#10B981', fontSize: 11, fontWeight: '700', marginTop: 2 },
  stepBar: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', paddingVertical: 10, gap: 6 },
  stepDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' },
  stepDotActive: { backgroundColor: '#8B5CF6' },
  stepDotDone: { backgroundColor: '#10B981' },
  stepDotTxt: { color: '#64748B', fontSize: 12, fontWeight: '700' },

  errBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(248,113,113,0.1)', borderColor: 'rgba(248,113,113,0.3)', borderWidth: 1, padding: 10, borderRadius: 10, marginBottom: 10, gap: 6 },
  errText: { color: '#F87171', fontSize: 13, flex: 1 },

  introCard: { borderRadius: 16, padding: 16, marginBottom: 16 },
  introTitle: { color: '#fff', fontSize: 18, fontWeight: '800', marginBottom: 6 },
  introSub: { color: 'rgba(255,255,255,0.85)', fontSize: 13, lineHeight: 19 },

  /* Phase-1 Reel-mode toggle */
  modeRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  modeCard: {
    flex: 1, backgroundColor: '#1E293B', borderRadius: 14, padding: 12,
    borderWidth: 1.5, borderColor: '#334155', position: 'relative',
  },
  modeCardActive: { borderColor: '#10B981', backgroundColor: 'rgba(16,185,129,0.12)' },
  modeHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  modeIcon: { fontSize: 22 },
  modeBadge: { color: '#10B981', fontSize: 9, fontWeight: '800', letterSpacing: 0.4 },
  modeTitle: { color: '#fff', fontSize: 14, fontWeight: '800', marginBottom: 2 },
  modeDesc: { color: '#94A3B8', fontSize: 11, lineHeight: 14 },
  modeCheck: {
    position: 'absolute', top: 8, right: 8,
    width: 18, height: 18, borderRadius: 9, backgroundColor: '#10B981',
    alignItems: 'center', justifyContent: 'center',
  },
  upsellHint: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: 'rgba(251,191,36,0.08)', borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 8, marginBottom: 16,
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.2)',
  },
  upsellHintTxt: { color: '#FBBF24', fontSize: 11, flex: 1, lineHeight: 14 },

  label: { color: '#CBD5E1', fontSize: 13, fontWeight: '700', marginBottom: 6 },
  ideaInput: { backgroundColor: '#1E293B', color: '#fff', borderRadius: 12, padding: 14, fontSize: 15, minHeight: 100, textAlignVertical: 'top', borderWidth: 1, borderColor: '#334155' },
  hint: { color: '#64748B', fontSize: 12, marginTop: 4 },
  quickChip: { backgroundColor: '#1E293B', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 8, marginRight: 8, marginBottom: 8, borderWidth: 1, borderColor: '#334155' },
  quickChipTxt: { color: '#E2E8F0', fontSize: 12 },

  primaryBtn: { marginTop: 20, backgroundColor: '#8B5CF6', borderRadius: 14, paddingVertical: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  primaryBtnTxt: { color: '#fff', fontWeight: '800', fontSize: 15 },
  btnDisabled: { opacity: 0.5 },
  ghostBtn: { marginTop: 12, paddingVertical: 12, alignItems: 'center' },
  ghostBtnTxt: { color: '#94A3B8', fontSize: 13 },

  sectionTitle: { color: '#fff', fontSize: 17, fontWeight: '800', marginBottom: 4 },
  sectionSub: { color: '#94A3B8', fontSize: 13, marginBottom: 14 },
  optCard: { borderRadius: 16, marginBottom: 12, overflow: 'hidden' },
  optCardInner: { padding: 16 },
  optHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  toneChip: { backgroundColor: 'rgba(255,255,255,0.22)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  toneChipTxt: { color: '#fff', fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  optIdx: { color: 'rgba(255,255,255,0.7)', fontSize: 12, fontWeight: '700' },
  optTitle: { color: '#fff', fontSize: 17, fontWeight: '800', marginBottom: 6 },
  optScript: { color: 'rgba(255,255,255,0.9)', fontSize: 13, lineHeight: 18 },
  optMeta: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 10 },
  metaPill: { backgroundColor: 'rgba(0,0,0,0.25)', flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, marginRight: 6, marginTop: 4 },
  metaTxt: { color: '#E2E8F0', fontSize: 10, fontWeight: '600' },
  optCTA: { marginTop: 12, alignItems: 'flex-end' },
  optCTATxt: { color: '#FEF08A', fontSize: 13, fontWeight: '800' },

  progressTitle: { color: '#fff', fontSize: 17, fontWeight: '700', marginTop: 14 },
  progressStage: { color: '#A78BFA', fontSize: 13, marginTop: 4, textTransform: 'capitalize' },
  barTrack: { width: '80%', height: 6, backgroundColor: '#1E293B', borderRadius: 3, overflow: 'hidden', marginTop: 12 },
  barFill: { height: '100%', backgroundColor: '#8B5CF6', borderRadius: 3 },
  progressPct: { color: '#fff', fontSize: 20, fontWeight: '800', marginTop: 8 },
  progressHint: { color: '#64748B', fontSize: 12, marginTop: 4 },
  stagesList: { marginTop: 22, alignSelf: 'stretch', paddingHorizontal: 20 },
  stageRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 7, gap: 8 },
  stageTxt: { color: '#64748B', fontSize: 13 },

  previewBox: { aspectRatio: 9 / 16, backgroundColor: '#000', borderRadius: 14, overflow: 'hidden', alignSelf: 'center', width: W * 0.72 },
  previewVideo: { width: '100%', height: '100%' },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', marginTop: 12, gap: 6 },
  statPill: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(139,92,246,0.15)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.35)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, marginHorizontal: 3, marginVertical: 3 },
  statTxt: { color: '#E9D5FF', fontSize: 11, fontWeight: '700' },
  actionRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 14, gap: 8 },
  actionBtn: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, paddingVertical: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4 },
  actionBtnTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },

  editTitle: { color: '#CBD5E1', fontSize: 13, fontWeight: '700', marginTop: 14, marginBottom: 6 },
  editInput: { backgroundColor: '#1E293B', color: '#fff', borderRadius: 10, padding: 12, minHeight: 80, textAlignVertical: 'top', borderWidth: 1, borderColor: '#334155' },
  chip: { backgroundColor: '#1E293B', borderRadius: 14, paddingHorizontal: 12, paddingVertical: 7, marginRight: 6, borderWidth: 1, borderColor: '#334155' },
  chipActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  chipTxt: { color: '#CBD5E1', fontSize: 12 },
  chipTxtActive: { color: '#fff', fontWeight: '800' },
  bgmPlay: { position: 'absolute', right: 10, top: 4 },

  upsellCard: { borderRadius: 20, padding: 20 },
  upsellPill: { color: '#0B1120', backgroundColor: '#FEF08A', alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  upsellTitle: { color: '#fff', fontSize: 22, fontWeight: '800', marginTop: 10, marginBottom: 6 },
  upsellSub: { color: 'rgba(255,255,255,0.92)', fontSize: 13, lineHeight: 19 },
  upsellRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, gap: 8 },
  upsellRowTxt: { color: '#fff', fontSize: 13, flex: 1 },

  // Image picker modal
  imagesEditBtn: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.35)', borderRadius: 10, paddingVertical: 12, paddingHorizontal: 14, gap: 10 },
  imagesEditTxt: { color: '#E9D5FF', fontSize: 13, fontWeight: '600', flex: 1 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  modalSheet: { backgroundColor: '#0B1120', borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 24, maxHeight: '85%', borderTopWidth: 1, borderColor: '#1E293B' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  modalTitle: { color: '#fff', fontSize: 18, fontWeight: '800' },
  modalSub: { color: '#94A3B8', fontSize: 13, marginTop: 4 },
  modalSearch: { flex: 1, backgroundColor: '#1E293B', color: '#fff', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: '#334155', fontSize: 13 },
  searchBtn: { marginLeft: 8, width: 42, height: 42, borderRadius: 10, backgroundColor: '#8B5CF6', alignItems: 'center', justifyContent: 'center' },
  gridScroll: { paddingVertical: 8 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  gridItem: { width: '31%', aspectRatio: 9 / 16, marginBottom: 8, borderRadius: 10, overflow: 'hidden', borderWidth: 2, borderColor: 'transparent', backgroundColor: '#1E293B' },
  gridItemSel: { borderColor: '#8B5CF6' },
  gridImg: { width: '100%', height: '100%' },
  selBadge: { position: 'absolute', top: 6, left: 6, width: 22, height: 22, borderRadius: 11, backgroundColor: '#8B5CF6', alignItems: 'center', justifyContent: 'center' },
  selBadgeTxt: { color: '#fff', fontSize: 11, fontWeight: '800' },
  ghostBtnFlat: { paddingVertical: 14, borderRadius: 14, backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#334155' },

  // Sprint 30 — Smart Plan (Creative Plan Engine) UI
  smartPlanBtn: {
    marginTop: 12, backgroundColor: 'rgba(251,191,36,0.10)',
    borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)',
    borderRadius: 14, paddingVertical: 13,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
  },
  smartPlanBtnTxt: { color: '#FBBF24', fontWeight: '800', fontSize: 14, letterSpacing: 0.3 },
  smartPlanBadge: {
    backgroundColor: '#FBBF24', paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: 6, marginLeft: 4,
  },
  smartPlanBadgeTxt: { color: '#0B1120', fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  smartPlanHint: { color: '#94A3B8', fontSize: 11, textAlign: 'center', marginTop: 6, lineHeight: 16, paddingHorizontal: 12 },

  // Multi-Scene Story Engine — duration selector (15s / 20s / 30s)
  storyLenRow: { marginTop: 14 },
  storyLenLabel: {
    color: '#94A3B8', fontSize: 10, fontWeight: '900',
    letterSpacing: 1, marginBottom: 8, paddingHorizontal: 4,
  },
  storyLenSeg: {
    flexDirection: 'row', gap: 8,
  },
  storyLenBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)',
    borderRadius: 14,
  },
  storyLenBtnActive: {
    backgroundColor: '#FBBF24',
    borderColor: '#FBBF24',
    shadowColor: '#FBBF24',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5, shadowRadius: 12, elevation: 8,
  },
  storyLenBtnTxt: { color: '#FFFFFF', fontWeight: '900', fontSize: 18 },
  storyLenBtnTxtActive: { color: '#0B1120' },
  storyLenBtnSub: { color: '#94A3B8', fontSize: 10, fontWeight: '700', marginTop: 2 },

  // Plan preview card sections
  planSection: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    borderRadius: 14, padding: 14, marginTop: 12,
  },
  planLabel: { color: '#94A3B8', fontSize: 10, fontWeight: '900', letterSpacing: 1, marginBottom: 8 },
  planHook: { color: '#fff', fontSize: 16, fontWeight: '700', lineHeight: 22 },
  scriptRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 8 },
  scriptIdx: {
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: 'rgba(139,92,246,0.25)',
    borderWidth: 1, borderColor: 'rgba(139,92,246,0.5)',
    alignItems: 'center', justifyContent: 'center', marginTop: 1,
  },
  scriptIdxTxt: { color: '#C4B5FD', fontSize: 11, fontWeight: '800' },
  scriptLine: { flex: 1, color: '#E2E8F0', fontSize: 13, lineHeight: 18 },
  keywordChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(167,139,250,0.12)',
    borderWidth: 1, borderColor: 'rgba(167,139,250,0.35)',
    paddingHorizontal: 8, paddingVertical: 5, borderRadius: 10,
  },
  keywordChipTxt: { color: '#C4B5FD', fontSize: 11, fontWeight: '700' },
  planMetaGrid: { flexDirection: 'row', gap: 8, marginTop: 12 },
  planMetaCard: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    borderRadius: 12, padding: 10, gap: 4,
  },
  planMetaLabel: { color: '#94A3B8', fontSize: 9, fontWeight: '900', letterSpacing: 0.6 },
  planMetaValue: { color: '#fff', fontSize: 12, fontWeight: '700', lineHeight: 16 },
  planSourcePill: {
    marginLeft: 'auto',
    backgroundColor: 'rgba(16,185,129,0.18)',
    borderWidth: 1, borderColor: 'rgba(16,185,129,0.40)',
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8,
  },
  planSourcePillTxt: { color: '#34D399', fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
});

// V2.0 — Styles for the AI Prompt context card on the progress screen
const aiMetaStyles = StyleSheet.create({
  card: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(236,72,153,0.45)',
    padding: 16,
    marginBottom: 20,
    shadowColor: '#EC4899',
    shadowOpacity: 0.35,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 6 },
  },
  badgeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  badge: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1.5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: 'rgba(236,72,153,0.28)',
    borderWidth: 1,
    borderColor: 'rgba(236,72,153,0.6)',
    borderRadius: 999,
  },
  styleTag: {
    color: '#FBBF24',
    fontSize: 11,
    fontWeight: '800',
    textTransform: 'capitalize',
    letterSpacing: 0.5,
  },
  hook: {
    color: '#F8FAFC',
    fontSize: 16,
    fontStyle: 'italic',
    lineHeight: 22,
    fontWeight: '600',
    marginBottom: 12,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
  },
  chip: {
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  chipTxt: { color: '#E2E8F0', fontSize: 11, fontWeight: '700', textTransform: 'capitalize' },
  hashtags: {
    color: '#60A5FA',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.3,
    marginTop: 2,
  },
});
