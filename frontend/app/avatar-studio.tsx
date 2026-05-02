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
import { SafeAreaView } from 'react-native-safe-area-context';
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

// ────────────────────────── Screen ──────────────────────────
export default function AvatarStudioScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const userIsPro = !!user && (user.subscription_tier || 'free') !== 'free';

  const [showAuthGate, setShowAuthGate] = useState(false);
  const requireLogin = (): boolean => {
    if (!user) { setShowAuthGate(true); return false; }
    return true;
  };

  // ── Mode toggle (Cartoon vs Talking). Drives whether we cartoonize the
  // uploaded photo before lip-syncing, and which step machine renders.
  const [mode, setMode] = useState<'cartoon' | 'talking'>('cartoon');

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

  // ── step 4: voice + preview audio ──
  const [audioBusy, setAudioBusy] = useState(false);
  const audioRef = useRef<Audio.Sound | null>(null);

  // ── step 5: image + generate ──
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  // Manual script — used in Talking mode OR as an override in Cartoon mode.
  const [manualScript, setManualScript] = useState('');
  const [generating, setGenerating] = useState(false);
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

  // ────────────────────────── Fetch dialogues ──────────────────────────
  const fetchDialogues = useCallback(async () => {
    if (!styleId || !idea.trim()) return;
    setLoadingDialogues(true); setDialogueErr(null); setDialogueId(null);
    try {
      const r = await axios.post(`${API}/avatar/dialogues`, {
        style_id: styleId,
        idea: idea.trim(),
        language,
        count: 3,
      }, { timeout: 45000 });
      const dlg: Dialogue[] = r.data?.dialogues || [];
      setDialogues(dlg);
      if (dlg.length) setDialogueId(dlg[0].id);
    } catch (e: any) {
      setDialogueErr(e?.response?.data?.detail || e?.message || 'Could not generate dialogues.');
    } finally {
      setLoadingDialogues(false);
    }
  }, [styleId, idea, language]);

  // ────────────────────────── Audio preview ──────────────────────────
  const playAudioPreview = useCallback(async () => {
    if (!pickedDialogue || !activeStyle) return;
    try {
      setAudioBusy(true);
      // stop existing
      if (audioRef.current) {
        try { await audioRef.current.unloadAsync(); } catch {}
        audioRef.current = null;
      }
      // hit the TTS preview endpoint (Sarvam, already in the app)
      const r = await axios.post(
        `${API}/generate-prompts/preview-audio`,
        {
          text: pickedDialogue.text,
          voice_type: activeStyle.personality.voice_style,
          language,
          max_seconds: 3.5,
        },
        { responseType: 'arraybuffer', timeout: 30000 },
      );
      const b64 = arrayBufferToBase64(r.data);
      const uri = `data:audio/mpeg;base64,${b64}`;
      const sound = new Audio.Sound();
      await sound.loadAsync({ uri });
      audioRef.current = sound;
      await sound.playAsync();
    } catch (e: any) {
      Alert.alert('Voice preview unavailable', 'You can still generate the video in the next step.');
    } finally {
      setAudioBusy(false);
    }
  }, [pickedDialogue, activeStyle, language]);

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
      const persona = activeStyle.personality;
      let cartoonPath = imagePath;

      // ── CARTOON MODE: cartoonize the uploaded photo first ─────────
      if (mode === 'cartoon') {
        setGenStage(`Cartoonizing in ${activeStyle.label} style…`);
        setGenProgress(10);
        try {
          // Read the uploaded file back as base64 for the cartoonize API
          // (it needs image_b64). We already have imageUri from the picker.
          const b64 = await fileToBase64(imageUri || '');
          const cr = await axios.post(`${API}/avatar/cartoonize`, {
            image_b64: b64,
            style: activeStyle.id,
            emotion: 'happy',
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
      const body = {
        image_path: cartoonPath,
        script,
        voice_id: persona.voice_id,
        voice_style: persona.voice_style,
        motion: 'ken_burns',
        aspect_ratio: '9:16',
        resolution: userIsPro ? '720p' : '480p',
      };
      const r = await axios.post(`${API}/create-talking-avatar`, body, { timeout: 30000 });
      const pid = r.data?.project_id;
      if (!pid) throw new Error('No project id returned');

      // Poll /api/project/{pid}
      pollRef.current = setInterval(async () => {
        try {
          const j = await axios.get(`${API}/project/${pid}`, { timeout: 15000 });
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
        } catch { /* keep polling */ }
      }, 3000);
    } catch (e: any) {
      setResultError(e?.response?.data?.detail || e?.message || 'Generation failed');
      setGenerating(false);
    }
  }, [imagePath, imageUri, pickedDialogue, manualScript, activeStyle, userIsPro, user, mode]);

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
      // fire dialogue gen + advance
      fetchDialogues();
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

                <FieldLabel>Quick starts</FieldLabel>
                <View style={[s.catRow, { marginBottom: 8 }]}>
                  {(IDEA_SUGGESTIONS[categoryId] || []).map(sug => (
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

                <View style={{ height: 20 }} />

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

                {/* 1) Upload */}
                <FieldLabel>1 · Upload portrait</FieldLabel>
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

                {/* 3) Voice vibe picker — reuses the style personality mapping */}
                <FieldLabel>3 · Voice vibe</FieldLabel>
                <View style={s.catRow}>
                  {styles.slice(0, 8).map(st => (
                    <Chip
                      key={st.id}
                      label={`${st.icon} ${st.label}`}
                      active={st.id === styleId}
                      onPress={() => setStyleId(st.id)}
                      style={{ marginRight: 8, marginBottom: 8 }}
                    />
                  ))}
                </View>
                {activeStyle && (
                  <Text style={s.voiceMeta}>
                    ✨ Voice: {activeStyle.personality.voice_id} · {activeStyle.personality.tone}
                  </Text>
                )}

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
            <View style={s.bottomNav}>
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
});
