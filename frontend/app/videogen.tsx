import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput, ActivityIndicator, Alert,
  KeyboardAvoidingView, Platform, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { Audio } from 'expo-av';
import axios from 'axios';
import VoicePicker from '../src/VoicePicker';
import { findVoice } from '../src/voices';
import { uploadImageFile, uploadVideoFile } from '../src/uploadHelper';
import QualityPicker from '../src/QualityPicker';
import ResolutionPicker from '../src/ResolutionPicker';
import PauseChips from '../src/PauseChips';
import { useMhCapabilities } from '../src/useMhCapabilities';
import VoiceStylePicker from '../src/VoiceStylePicker';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import ModelPickerBlock from '../src/components/ModelPickerBlock';
import AuthGateModal from '../src/components/AuthGateModal';
import { useAuth } from '../src/AuthContext';
import { useTheme } from '../src/ThemeContext';
import { useTierGuard } from '../src/useTierGuard';
import { saveAssetToDevice, suggestFileName } from '../src/downloadHelper';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type Mode = 'text' | 'image' | 'video';

const TEXT_SAMPLES = [
  { label: 'Krishna Bhajan', prompt: 'Lord Krishna playing flute in Vrindavan garden, divine glow, peacock feather, devotional atmosphere, cinematic slow motion' },
  { label: 'Ganesh Aarti', prompt: 'Lord Ganesha blessing devotees during aarti ceremony, golden temple background, warm candlelight, devotional close-up' },
  { label: 'Shiv Tandav', prompt: 'Lord Shiva performing cosmic dance Tandav, Mount Kailash, divine energy, dramatic blue and gold, cinematic wide shot' },
  { label: 'Ram Darbar', prompt: 'Lord Ram in royal Ayodhya palace court with Sita, Lakshman, Hanuman, ornate grandeur, warm golden lighting' },
  { label: 'Hanuman Ji', prompt: 'Lord Hanuman in heroic pose carrying Sanjeevani mountain, sunrise sky, dynamic aerial cinematic angle' },
  { label: 'Diwali Joy', prompt: 'Indian family celebrating Diwali, lighting diyas, fireworks in night sky, warm festive glow, close-up faces smiling' },
];

const IMG2VID_SAMPLES = [
  { label: 'Subtle Motion', prompt: 'Add gentle camera zoom and subtle lighting variations, cinematic mood' },
  { label: 'Divine Glow', prompt: 'Add divine glow pulsating around subject, subtle particles, warm golden aura' },
  { label: 'Wind & Fabric', prompt: 'Gentle wind flowing through fabric, hair moving naturally, soft cinematic motion' },
  { label: 'Zoom In Drama', prompt: 'Slow dramatic zoom in on subject, dust particles in air, cinematic tension' },
  { label: 'Slow Turn', prompt: 'Subject slowly turns and smiles, soft natural motion, warm ambient lighting' },
  { label: 'Rain & Mood', prompt: 'Cinematic rain falling, subject looks up, melancholic mood, wet reflections' },
];

const VID2VID_STYLES = [
  'No Art Style', 'Anime Warrior', 'Ghibli Anime', '3D Render', 'Cyberpunk', 'Oil Painting',
  'Watercolor', 'Comic', 'Pixar', 'Pixel', 'Van Gogh', 'Samurai', 'Dark Fantasy', 'Neon Dream',
];

const VID2VID_SAMPLES = [
  { label: 'Anime Style', prompt: 'Vibrant anime with expressive eyes and dynamic action lines', style: 'Anime Warrior' },
  { label: 'Ghibli Dream', prompt: 'Soft Studio Ghibli style, warm pastel colors, hand-drawn magical feel', style: 'Ghibli Anime' },
  { label: '3D Pixar', prompt: 'Pixar-style 3D render with warm cinematic lighting', style: 'Pixar' },
  { label: 'Van Gogh', prompt: 'Van Gogh starry night brushstrokes, swirling textures, expressive colors', style: 'Van Gogh' },
  { label: 'Cyberpunk', prompt: 'Cyberpunk neon city, rain-soaked streets, pink and teal glow', style: 'Cyberpunk' },
  { label: 'Watercolor', prompt: 'Soft watercolor painting with gentle brushstrokes and paper texture', style: 'Watercolor' },
];

// MH text/image/video-to-video minimum billed duration = 5s. Anything shorter is
// still charged for 5s, so we only expose ≥5s to avoid silently wasting credits.
const DURATIONS = [
  { label: '5s', v: 5 }, { label: '10s', v: 10 }, { label: '15s', v: 15 },
];

export default function VideoGenScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prompt?: string; duration?: string; aspectRatio?: string; voiceId?: string; prefill?: string; edit_of?: string }>();
  const { isDark } = useTheme();
  const { user } = useAuth();
  const tier = useTierGuard();
  // Guest gate: AI Video Gen always requires sign-in (it consumes credits
  // and tier-based features). The /explore-tools "All Tools" pill links
  // here directly so the gate is enforced at this entry point too.
  const [authGateOpen, setAuthGateOpen] = useState(false);
  useEffect(() => {
    if (!user) setAuthGateOpen(true);
  }, [user]);
  const titleColor = isDark ? '#FFFFFF' : '#0F0C29';
  const [mode, setMode] = useState<Mode>('text');
  const [prompt, setPrompt] = useState('');
  const [lyrics, setLyrics] = useState('');
  const [voiceId, setVoiceId] = useState('hi-IN-SwaraNeural');
  const [voiceStyle, setVoiceStyle] = useState<string | null>(null); // Sprint 2
  const [voiceRate, setVoiceRate] = useState<string | null>(null); // Sprint 2 Phase B
  const [voicePitch, setVoicePitch] = useState<string | null>(null); // Sprint 2 Phase B
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [duration, setDuration] = useState(5);
  const [shotCount, setShotCount] = useState(1);
  const [qualityMode, setQualityMode] = useState<'quick' | 'studio' | 'cinematic'>('studio');

  // MH capabilities — dynamically pulled from /api/mh-models. Each MH tool has
  // its own (duration_options, resolution_options, credits_per_sec, min_cost)
  // matrix and this hook keeps the picker in lock-step with the real billing.
  const _mhFeatureName = mode === 'text' ? 'text_to_video' : mode === 'image' ? 'image_to_video' : 'video_to_video';
  const mhCap = useMhCapabilities(_mhFeatureName, qualityMode);
  const mhFeature = mhCap.feature;
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p' | '4K'>('720p');
  // SFX catalog
  const [sfxList, setSfxList] = useState<any[]>([{ id: 'none', name: 'None', icon: 'volume-mute', category: 'None' }]);
  const [soundEffect, setSoundEffect] = useState<string>('none');
  // Dialogue audio (upload or record) — overrides TTS when set
  const [audioUri, setAudioUri] = useState<string | null>(null);
  const [audioPath, setAudioPath] = useState<string | null>(null);
  const [audioUploading, setAudioUploading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordDuration, setRecordDuration] = useState(0);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const recordTimerRef = useRef<any>(null);
  // Fetch SFX catalog once
  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/sound-effects`);
        if (r.data?.effects) setSfxList(r.data.effects);
      } catch (e) {}
    })();
  }, []);
  // Prefill from URL params (template) — once on mount
  useEffect(() => {
    if (params.prompt) setPrompt(String(params.prompt));
    if (params.duration) setDuration(parseInt(String(params.duration)) || 5);
    if (params.aspectRatio) setAspectRatio(String(params.aspectRatio));
    if (params.voiceId) setVoiceId(String(params.voiceId));
    // SessionStorage fallback for templates routed from /marketplace
    // (the rich payload that may exceed URL param length).
    try {
      if (typeof window !== 'undefined' && (window as any).sessionStorage) {
        const raw = (window as any).sessionStorage.getItem('videogen_template_prefill');
        if (raw) {
          const p = JSON.parse(raw);
          if (p.prompt) setPrompt(p.prompt);
          if (p.duration) setDuration(parseInt(String(p.duration)) || 5);
          if (p.aspectRatio) setAspectRatio(p.aspectRatio);
          if (p.voiceId) setVoiceId(p.voiceId);
          // Use mode hint to seed text/image/video toggle
          if (p.mode === 'images') setMode('image');
          // Clear after consume so subsequent visits don't re-fill
          (window as any).sessionStorage.removeItem('videogen_template_prefill');
        }
      }
    } catch {}
    // Sprint 1 — Edit pre-fill (JSON-encoded payload from /projects → doEdit)
    if (params.prefill) {
      try {
        const p = JSON.parse(String(params.prefill));
        if (p.prompt) setPrompt(p.prompt);
        if (p.duration) setDuration(parseInt(String(p.duration)) || 5);
        if (p.aspect_ratio) setAspectRatio(p.aspect_ratio);
        if (p.voice_id) setVoiceId(p.voice_id);
        if (p.lyrics) setLyrics(p.lyrics);
        if (p.sound_effect) setSoundEffect(p.sound_effect);
        if (p.quality_mode) setQualityMode(p.quality_mode);
        if (p.resolution) setResolution(p.resolution);
        if (p.voice_style) setVoiceStyle(p.voice_style);
      } catch (e) {}
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tier-aware default: Free users start at 480p, Pro users at 1080p, etc.
  // If user's current `resolution` value isn't allowed by their tier, snap
  // it down to their max permitted resolution.
  React.useEffect(() => {
    if (!tier.allowedResolutions.includes(resolution as any)) {
      // pick the highest one they're allowed to use
      const last = tier.allowedResolutions[tier.allowedResolutions.length - 1];
      if (last && last !== resolution) setResolution(last as any);
    }
  }, [tier.allowedResolutions, resolution]);
  // Image-to-video
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  // Video-to-video
  const [videoUri, setVideoUri] = useState<string | null>(null);
  const [videoPath, setVideoPath] = useState<string | null>(null);
  const [videoUploading, setVideoUploading] = useState(false);
  const [artStyle, setArtStyle] = useState('No Art Style');
  // Shared processing state
  const [processing, setProcessing] = useState(false);
  const [projectIds, setProjectIds] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultError, setResultError] = useState('');
  const pollRef = useRef<any>(null);

  useEffect(() => {
    if (projectIds.length > 0 && processing) {
      pollRef.current = setInterval(async () => {
        try {
          const results = await Promise.all(projectIds.map(id => axios.get(`${BACKEND_URL}/api/project/${id}`).then(r => r.data).catch(() => null)));
          const valid = results.filter(Boolean);
          if (valid.length === 0) return;
          const avgProgress = Math.round(valid.reduce((sum, r) => sum + (r.progress || 0), 0) / valid.length);
          setProgress(avgProgress);
          const allDone = valid.every(r => r.status === 'completed' || r.status === 'failed');
          if (allDone) {
            clearInterval(pollRef.current); setProcessing(false);
            const anyFailed = valid.some(r => r.status === 'failed');
            const allCompleted = valid.every(r => r.status === 'completed');
            if (allCompleted) setResultStatus('completed');
            else if (anyFailed) {
              setResultStatus('failed');
              setResultError(valid.find(r => r.status === 'failed')?.error_message || 'Failed');
            }
          }
        } catch (e) {}
      }, 3500);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectIds, processing]);

  const resetAll = () => {
    Alert.alert('Clear & Reset', 'Clear all inputs and any result?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear All', style: 'destructive', onPress: () => {
        setPrompt(''); setLyrics(''); setVoiceId('hi-IN-SwaraNeural');
        setAspectRatio('9:16'); setDuration(5); setShotCount(1);
        setImageUri(null); setImagePath(null); setImageUploading(false);
        setVideoUri(null); setVideoPath(null); setVideoUploading(false);
        setArtStyle('No Art Style');
        setSoundEffect('none'); setAudioUri(null); setAudioPath(null);
        setQualityMode('studio'); setResolution('720p');
        setProjectIds([]); setProcessing(false); setProgress(0); setResultStatus('none'); setResultError('');
      }},
    ]);
  };

  // --- Dialogue audio: upload from device ---
  const pickAudio = async () => {
    try {
      const r = await DocumentPicker.getDocumentAsync({ type: 'audio/*', copyToCacheDirectory: true });
      if (r.canceled || !r.assets?.[0]) return;
      const a = r.assets[0];
      setAudioUri(a.uri); setAudioUploading(true);
      try {
        const fd = new FormData();
        if (Platform.OS === 'web') {
          const resp = await fetch(a.uri); const blob = await resp.blob();
          fd.append('file', new File([blob], a.name || 'audio.mp3', { type: blob.type || 'audio/mpeg' }));
        } else {
          fd.append('file', { uri: a.uri, name: a.name || 'audio.mp3', type: a.mimeType || 'audio/mpeg' } as any);
        }
        const up = await axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
        setAudioPath(up.data.file_path);
      } catch (e: any) {
        Alert.alert('Upload failed', e?.message || 'Could not upload audio');
        setAudioUri(null);
      } finally { setAudioUploading(false); }
    } catch (e) {}
  };

  const startRecording = async () => {
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (perm.status !== 'granted') { Alert.alert('Microphone Permission', 'Please grant microphone access.'); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const rec = new Audio.Recording();
      await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await rec.startAsync();
      recordingRef.current = rec;
      setIsRecording(true); setRecordDuration(0);
      recordTimerRef.current = setInterval(() => setRecordDuration(d => d + 1), 1000);
    } catch (e: any) { Alert.alert('Recording Error', e?.message || 'Could not start recording'); setIsRecording(false); }
  };

  const stopRecording = async () => {
    try {
      if (recordTimerRef.current) { clearInterval(recordTimerRef.current); recordTimerRef.current = null; }
      const rec = recordingRef.current;
      if (!rec) { setIsRecording(false); return; }
      await rec.stopAndUnloadAsync();
      const uri = rec.getURI();
      recordingRef.current = null;
      const dur = recordDuration;
      setIsRecording(false); setRecordDuration(0);
      if (!uri) { Alert.alert('Error', 'No audio recorded.'); return; }
      if (dur < 1) { Alert.alert('Too short', 'Please record at least 1 second.'); return; }
      setAudioUri(uri); setAudioUploading(true);
      try {
        const fd = new FormData();
        const fileName = `record_${Date.now()}.m4a`;
        if (Platform.OS === 'web') {
          const resp = await fetch(uri); const blob = await resp.blob();
          fd.append('file', new File([blob], fileName, { type: blob.type || 'audio/webm' }));
        } else {
          fd.append('file', { uri, name: fileName, type: 'audio/m4a' } as any);
        }
        const up = await axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
        setAudioPath(up.data.file_path);
      } catch (e: any) {
        Alert.alert('Upload failed', e?.message || 'Could not upload recording');
        setAudioUri(null);
      } finally { setAudioUploading(false); }
    } catch (e) { setIsRecording(false); }
  };

  const clearAudio = () => { setAudioUri(null); setAudioPath(null); };

  const pickImage = async (fromCamera = false) => {
    const { status } = fromCamera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission needed'); return; }
    const r = fromCamera ? await ImagePicker.launchCameraAsync({ quality: 0.8 }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!r.canceled && r.assets[0]) {
      const uri = r.assets[0].uri;
      setImageUri(uri); setImageUploading(true);
      try {
        const data = await uploadImageFile(uri, '/api/upload-face-image');
        setImagePath(data.file_path);
      } catch (e) { Alert.alert('Upload failed'); setImageUri(null); }
      finally { setImageUploading(false); }
    }
  };

  const pickVideo = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['videos'], quality: 0.5 });
    if (!r.canceled && r.assets[0]) {
      const uri = r.assets[0].uri;
      setVideoUri(uri); setVideoUploading(true);
      try {
        const data = await uploadVideoFile(uri);
        setVideoPath(data.file_path);
      } catch (e) { Alert.alert('Upload failed'); setVideoUri(null); }
      finally { setVideoUploading(false); }
    }
  };

  const generate = async () => {
    // 🔒 Tier gate: AI Video Gen requires Starter+ (Free users blocked).
    if (!tier.requireFeature('ai_video_gen', 'AI Video Generation')) {
      return;
    }
    try {
      setProcessing(true); setProgress(0); setResultStatus('none'); setProjectIds([]);
      let r;
      if (mode === 'text') {
        if (!prompt.trim()) { Alert.alert('Enter a prompt'); setProcessing(false); return; }
        // For multi-shot text2video, call original endpoint multiple times
        const ids: string[] = [];
        for (let i = 0; i < shotCount; i++) {
          const resp = await axios.post(`${BACKEND_URL}/api/generate-video`, {
            prompt, aspect_ratio: aspectRatio, lyrics: lyrics || undefined,
            voice_id: voiceId, style: 'bhajan', duration,
            sound_effect: soundEffect !== 'none' ? soundEffect : undefined,
            audio_path: audioPath || undefined,
            quality_mode: qualityMode, resolution,
            voice_style: voiceStyle || undefined,
            voice_rate: voiceRate || undefined,
            voice_pitch: voicePitch || undefined,
            parent_id: params.edit_of ? String(params.edit_of) : undefined,
          });
          ids.push(resp.data.project_id);
        }
        setProjectIds(ids);
      } else if (mode === 'image') {
        if (!imagePath) { Alert.alert('Upload an image first'); setProcessing(false); return; }
        if (!prompt.trim()) { Alert.alert('Enter a prompt describing the motion'); setProcessing(false); return; }
        r = await axios.post(`${BACKEND_URL}/api/create-image-to-video`, {
          image_path: imagePath, prompt, duration, shot_count: shotCount, aspect_ratio: aspectRatio,
          quality_mode: qualityMode, resolution,
        });
        setProjectIds(r.data.project_ids || [r.data.project_id]);
      } else if (mode === 'video') {
        if (!videoPath) { Alert.alert('Upload a video first'); setProcessing(false); return; }
        if (!prompt.trim()) { Alert.alert('Enter a style prompt'); setProcessing(false); return; }
        r = await axios.post(`${BACKEND_URL}/api/create-video-to-video`, {
          video_path: videoPath, prompt, art_style: artStyle, duration, shot_count: shotCount, start_seconds: 0,
          quality_mode: qualityMode, resolution,
        });
        setProjectIds(r.data.project_ids || [r.data.project_id]);
      }
    } catch (e: any) {
      Alert.alert('Error', e.response?.data?.detail || 'Failed');
      setProcessing(false);
    }
  };

  const canGenerate = !processing && ((mode === 'text' && prompt.trim()) || (mode === 'image' && !!imagePath && prompt.trim()) || (mode === 'video' && !!videoPath && prompt.trim()));

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          <GlassHeader
            icon="film"
            title="AI Video Gen"
            subtitle="Cinematic AI · uses credits"
            onBack={() => router.back()}
            right={
              <TouchableOpacity onPress={resetAll} style={{ width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="refresh" size={20} color="#EF4444" />
              </TouchableOpacity>
            }
            gradient={['#F97316', '#EC4899', '#A78BFA']}
            style={{ marginBottom: 12, paddingHorizontal: 0 }}
          />

          {/* Pricing-model banner: Cinematic AI pricing & cheaper alternatives */}
          <View style={s.pricingBanner}>
            <View style={s.pricingBannerHead}>
              <Ionicons name="film" size={18} color="#F97316" />
              <Text style={s.pricingBannerTitle}>Cinematic AI Video</Text>
              <View style={s.pricingTag}><Text style={s.pricingTagText}>uses credits</Text></View>
            </View>
            <Text style={s.pricingBannerDesc}>
              MagiCAi powered · each generation consumes credits from your plan quota.
              Need a 3-scene narrative?{' '}
              <Text style={s.pricingBannerLink} onPress={() => router.push('/story' as any)}>Story Mode</Text>
              {' '}charges a flat 80 credits (cheaper than 3 separate jobs).
            </Text>
          </View>

          {/* 🔒 Tier-required banner — Free users blocked from AI Video Gen */}
          {!tier.canUseFeature('ai_video_gen') && (
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => router.push('/subscription' as any)}
              style={s.gateBanner}
            >
              <Ionicons name="lock-closed" size={16} color="#FBBF24" />
              <Text style={s.gateBannerText}>
                AI Video Generation requires the Starter plan or higher. Free users can create stock-clip Quick Reels from the home wizard.
              </Text>
              <Text style={s.gateBannerCta}>Upgrade →</Text>
            </TouchableOpacity>
          )}

          {resultStatus === 'completed' && (
            <View style={s.successBanner}>
              <Ionicons name="checkmark-circle" size={22} color="#10B981" />
              <Text style={s.successText}>{projectIds.length > 1 ? `${projectIds.length} shots ready!` : 'Video ready!'}</Text>
              <TouchableOpacity
                style={[s.viewBtn, { marginRight: 6 }]}
                onPress={async () => {
                  if (!tier.requireFeature('download_to_gallery', 'Asset download')) return;
                  const pid = projectIds[0];
                  if (!pid) return;
                  // Use projects list API to resolve the MP4 URL, then save.
                  try {
                    const token = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage.getItem('magicai_jwt_v1') : null;
                    const r = await axios.get(`${BACKEND_URL}/api/projects/${pid}`, { timeout: 10000, headers: token ? { Authorization: `Bearer ${token}` } : {} });
                    const url = r.data?.result_url || r.data?.output_url;
                    if (!url) { Alert.alert('Not ready', 'Video URL not available yet. Try again in a second.'); return; }
                    const abs = url.startsWith('http') ? url : `${BACKEND_URL}${url}`;
                    const fname = suggestFileName(abs, 'video');
                    await saveAssetToDevice(abs, fname, 'video');
                  } catch (e: any) {
                    Alert.alert('Download failed', e?.message || 'Could not fetch video URL.');
                  }
                }}
              >
                <Text style={s.viewBtnT}>
                  {tier.canUseFeature('download_to_gallery') ? '⬇ Save' : '🔒 Save'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.viewBtn} onPress={() => router.push('/projects')}><Text style={s.viewBtnT}>View</Text></TouchableOpacity>
            </View>
          )}
          {resultStatus === 'failed' && <View style={s.errBanner}><Ionicons name="close-circle" size={22} color="#EF4444" /><Text style={s.errText}>{resultError}</Text></View>}
          {processing && (
            <View style={s.progressCard}>
              <View style={s.progressHeader}><ActivityIndicator size="small" color="#F97316" /><Text style={s.progressTitle}>Generating {shotCount > 1 ? `${shotCount} shots` : 'video'}...</Text></View>
              <View style={s.progressBarWrap}><View style={s.progressBarBg}><View style={[s.progressBarFill, { width: `${progress}%` }]} /></View><Text style={s.progressPct}>{progress}%</Text></View>
            </View>
          )}

          {/* Mode Tabs */}
          <Text style={s.sTitle}>Generation Mode</Text>
          <View style={s.modeRow}>
            {[
              { id: 'text', label: 'Text → Video', icon: 'chatbubble-ellipses' },
              { id: 'image', label: 'Image → Video', icon: 'image' },
              { id: 'video', label: 'Video → Video', icon: 'film' },
            ].map(m => (
              <TouchableOpacity key={m.id} style={[s.modeChip, mode === m.id && s.modeChipActive]} onPress={() => setMode(m.id as Mode)}>
                <Ionicons name={m.icon as any} size={16} color={mode === m.id ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, mode === m.id && { color: '#fff' }]}>{m.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Image upload (image-to-video mode) */}
          {mode === 'image' && (
            <View style={s.section}>
              <Text style={s.sTitle}>1. Source Image</Text>
              {imageUri ? (
                <View style={s.previewCard}>
                  <Image source={{ uri: imageUri }} style={s.previewImg} />
                  {imageUploading && <ActivityIndicator size="small" color="#F97316" style={{ marginTop: 6 }} />}
                  <TouchableOpacity style={s.changeBtn} onPress={() => pickImage(false)}><Text style={s.changeBtnT}>Change</Text></TouchableOpacity>
                </View>
              ) : (
                <View style={s.uploadRow}>
                  <TouchableOpacity style={s.uploadBtn} onPress={() => pickImage(false)}><Ionicons name="images" size={24} color="#F97316" /><Text style={s.uploadBtnT}>Gallery</Text></TouchableOpacity>
                  <TouchableOpacity style={s.uploadBtn} onPress={() => pickImage(true)}><Ionicons name="camera" size={24} color="#F97316" /><Text style={s.uploadBtnT}>Camera</Text></TouchableOpacity>
                </View>
              )}
            </View>
          )}

          {/* Video upload (video-to-video mode) */}
          {mode === 'video' && (
            <View style={s.section}>
              <Text style={s.sTitle}>1. Source Video</Text>
              {videoUri ? (
                <View style={s.videoCard}>
                  <Ionicons name="videocam" size={20} color="#F97316" />
                  <Text style={s.videoText}>{videoUploading ? 'Uploading...' : 'Video ready'}</Text>
                  {videoUploading && <ActivityIndicator size="small" color="#F97316" />}
                  <TouchableOpacity style={s.changeBtn} onPress={pickVideo}><Text style={s.changeBtnT}>Change</Text></TouchableOpacity>
                </View>
              ) : (
                <TouchableOpacity style={s.uploadBtnBig} onPress={pickVideo}>
                  <Ionicons name="cloud-upload" size={30} color="#F97316" />
                  <Text style={s.uploadBtnT}>Choose Video</Text>
                </TouchableOpacity>
              )}

              <Text style={[s.sTitle, { marginTop: 14 }]}>Art Style</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {VID2VID_STYLES.map(st => (
                  <TouchableOpacity key={st} style={[s.styleChip, artStyle === st && s.styleChipActive]} onPress={() => setArtStyle(st)}>
                    <Text style={[s.styleChipText, artStyle === st && { color: '#fff' }]}>{st}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}

          {/* Prompt area + samples */}
          <View style={s.section}>
            <Text style={s.sTitle}>{mode === 'text' ? '1' : '2'}. Prompt</Text>
            <TextInput
              style={s.promptInput}
              placeholder={mode === 'text' ? 'Describe the video...' : mode === 'image' ? 'Describe how the image should animate...' : 'Describe the desired style/transformation...'}
              placeholderTextColor="#64748B"
              value={prompt}
              onChangeText={setPrompt}
              multiline
            />
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
              {(mode === 'text' ? TEXT_SAMPLES : mode === 'image' ? IMG2VID_SAMPLES : VID2VID_SAMPLES).map((sp: any, i) => (
                <TouchableOpacity key={i} style={s.sampleChip} onPress={() => {
                  setPrompt(sp.prompt);
                  if (mode === 'video' && sp.style) setArtStyle(sp.style);
                }}>
                  <Text style={s.sampleChipText}>{sp.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Voice + Dialogue (text-to-video only) */}
          {mode === 'text' && (
            <View style={s.section}>
              <Text style={s.sTitle}>3. Voice (optional, for voiceover)</Text>
              <VoicePicker selectedId={voiceId} onSelect={setVoiceId} />
              <Text style={[s.hint, { marginTop: 6 }]}>Selected: <Text style={{ color: '#A78BFA', fontWeight: '700' }}>{findVoice(voiceId)?.name || 'Swara'}</Text></Text>
              <VoiceStylePicker
                selectedId={voiceStyle}
                onSelect={setVoiceStyle}
                customRate={voiceRate}
                customPitch={voicePitch}
                onCustomRate={setVoiceRate}
                onCustomPitch={setVoicePitch}
              />
              <TextInput
                style={[s.promptInput, { minHeight: 60, marginTop: 10 }]}
                placeholder={audioPath ? 'Using your uploaded audio (TTS disabled)' : 'Optional lyrics/script...'}
                placeholderTextColor="#64748B"
                value={lyrics}
                onChangeText={setLyrics}
                multiline
                editable={!audioPath}
              />
              {!audioPath && (
                <PauseChips onInsert={(tag) => setLyrics((prev) => (prev || '') + (prev && !prev.endsWith(' ') ? ' ' : '') + tag)} />
              )}

              {/* Dialogue audio upload / record — overrides TTS when set */}
              <Text style={[s.sTitle, { marginTop: 14 }]}>Or use your own dialogue audio</Text>
              {audioUri ? (
                <View style={s.audioCard}>
                  <Ionicons name="musical-note" size={22} color="#10B981" />
                  <Text style={s.audioText} numberOfLines={1}>{audioUploading ? 'Uploading…' : 'Audio ready ✓'}</Text>
                  <TouchableOpacity onPress={clearAudio} style={s.audioClear}>
                    <Ionicons name="close-circle" size={22} color="#EF4444" />
                  </TouchableOpacity>
                </View>
              ) : (
                <View style={{ flexDirection: 'row', gap: 10, marginTop: 8 }}>
                  <TouchableOpacity style={s.audioBtn} onPress={pickAudio} disabled={audioUploading || isRecording}>
                    <Ionicons name="cloud-upload-outline" size={18} color="#A78BFA" />
                    <Text style={s.audioBtnT}>Upload</Text>
                  </TouchableOpacity>
                  {isRecording ? (
                    <TouchableOpacity style={[s.audioBtn, { borderColor: '#EF4444', backgroundColor: '#EF444420' }]} onPress={stopRecording}>
                      <Ionicons name="stop-circle" size={18} color="#EF4444" />
                      <Text style={[s.audioBtnT, { color: '#EF4444' }]}>Stop ({recordDuration}s)</Text>
                    </TouchableOpacity>
                  ) : (
                    <TouchableOpacity style={s.audioBtn} onPress={startRecording} disabled={audioUploading}>
                      <Ionicons name="mic" size={18} color="#F97316" />
                      <Text style={[s.audioBtnT, { color: '#F97316' }]}>Record</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}
              <Text style={s.hint}>If provided, this audio replaces the AI voiceover.</Text>
            </View>
          )}

          {/* Sound Effect picker (all modes) */}
          <View style={s.section}>
            <Text style={s.sTitle}>Sound Effect <Text style={{ color: '#64748B', fontWeight: '400', fontSize: 12 }}>(optional, layered in final mix)</Text></Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
              {sfxList.map((sfx: any) => (
                <TouchableOpacity
                  key={sfx.id}
                  style={[s.sfxChip, soundEffect === sfx.id && s.sfxChipActive]}
                  onPress={() => setSoundEffect(sfx.id)}
                >
                  <Ionicons name={sfx.icon as any} size={14} color={soundEffect === sfx.id ? '#fff' : '#A78BFA'} />
                  <Text style={[s.sfxChipText, soundEffect === sfx.id && { color: '#fff' }]}>{sfx.name}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            {soundEffect !== 'none' && (
              <Text style={s.hint}>Selected: <Text style={{ color: '#A78BFA', fontWeight: '700' }}>{sfxList.find(x => x.id === soundEffect)?.name}</Text> — will be softly blended under your video audio.</Text>
            )}
          </View>

          {/* Duration + Multi-shot */}
          <View style={s.section}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8 }}>
              <Text style={s.sTitle}>Output Duration</Text>
              {mhFeature && (
                <Text style={{ color: '#94A3B8', fontSize: 11 }}>
                  · min {mhCap.minBilled}s{mhCap.costPerSec ? ` · ${mhCap.costPerSec}¢/sec` : ''}
                </Text>
              )}
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
              {(mhCap.durationOptions || [5, 10, 15]).map((v) => {
                const cost = mhCap.costPerSec ? Math.max(mhCap.costPerSec * v, mhCap.minCost || 0) : null;
                const allowed = tier.allowedDurations.includes(v);
                return (
                  <TouchableOpacity
                    key={v}
                    style={[s.durChip, duration === v && s.durChipActive, !allowed && s.durChipLocked]}
                    onPress={() => {
                      if (!allowed) {
                        // Find which tier unlocks this duration and prompt upgrade
                        const minTier = v <= 15 ? 'free' : v <= 20 ? 'starter' : v <= 30 ? 'creator' : 'pro';
                        tier.requirePlan(minTier as any, `${v}s duration`);
                        return;
                      }
                      setDuration(v);
                    }}
                  >
                    <Text style={[s.durChipText, duration === v && { color: '#fff' }, !allowed && { color: '#94A3B8' }]}>{v}s</Text>
                    {!allowed ? (
                      <Ionicons name="lock-closed" size={9} color="#FBBF24" style={{ marginTop: 2 }} />
                    ) : (cost != null && (
                      <Text style={[{ color: duration === v ? '#FDE68A' : '#64748B', fontSize: 10, marginTop: 2 }]}>
                        🪙 {cost}
                      </Text>
                    ))}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            <Text style={[s.sTitle, { marginTop: 14 }]}>Multi-shot (generate variations)</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
              {[1, 2, 3, 4].map(n => (
                <TouchableOpacity key={n} style={[s.shotChip, shotCount === n && s.shotChipActive]} onPress={() => setShotCount(n)}>
                  <Ionicons name="copy" size={14} color={shotCount === n ? '#fff' : '#94A3B8'} />
                  <Text style={[s.shotChipText, shotCount === n && { color: '#fff' }]}>{n}×</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.hint}>Generate {shotCount} {shotCount === 1 ? 'video' : 'distinct video variations'} simultaneously. Each counts as a separate job.</Text>
          </View>

          {/* Aspect ratio (all modes) */}
          <View style={s.section}>
            <Text style={s.sTitle}>Aspect Ratio</Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {['9:16', '16:9', '1:1'].map(ar => (
                <TouchableOpacity key={ar} style={[s.aspectChip, aspectRatio === ar && s.aspectChipActive]} onPress={() => setAspectRatio(ar)}>
                  <Text style={[s.aspectChipText, aspectRatio === ar && { color: '#fff' }]}>{ar}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* AI Model selector — Magic Hour catalog (replaces legacy QualityPicker per Apr-29 spec) */}
          <View style={s.section}>
            <ModelPickerBlock kind="video" />
          </View>

          {/* Resolution selector */}
          <View style={s.section}>
            <Text style={s.sTitle}>Resolution</Text>
            <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
          </View>

          {/* Silent-video warning (only for text-mode + no voice/sfx/audio) */}
          {mode === 'text' && !audioPath && !lyrics.trim() && soundEffect === 'none' && (
            <View style={s.silentWarn}>
              <Ionicons name="volume-mute" size={18} color="#F59E0B" />
              <Text style={s.silentText} numberOfLines={3}>
                Heads up — MagiCAi's video model generates silent video. Add lyrics/dialogue, a dialogue audio, or a sound effect above, or your output will have no sound.
              </Text>
            </View>
          )}

          <TouchableOpacity style={[s.genBtn, !canGenerate && { backgroundColor: '#334155' }]} onPress={generate} disabled={!canGenerate}>
            {processing ? (
              <View style={s.genBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={s.genBtnT}>Processing... {progress}%</Text></View>
            ) : (
              <View style={s.genBtnI}><Ionicons name="sparkles" size={22} color="#fff" /><Text style={s.genBtnT}>Generate {shotCount > 1 ? `${shotCount} shots` : 'Video'}</Text></View>
            )}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
    <AuthGateModal
      visible={authGateOpen}
      reason="AI Video Generation"
      onCancel={() => { setAuthGateOpen(false); router.back(); }}
      onSignIn={() => { setAuthGateOpen(false); router.replace('/login' as any); }}
    />
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 80 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }, title: { fontSize: 22, fontWeight: 'bold', color: '#fff' },
  section: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1,
    borderColor: 'rgba(167,139,250,0.20)',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 14,
    marginBottom: 14,
    overflow: 'hidden',
    ...Platform.select({
      web: { boxShadow: '0 6px 22px rgba(15,12,41,0.25)' as any },
      default: { shadowColor: '#0F0C29', shadowOpacity: 0.35, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
    }),
  }, sTitle: { fontSize: 15, fontWeight: '700', color: '#E2E8F0', marginBottom: 8 },
  hint: { color: '#94A3B8', fontSize: 12, marginTop: 6, lineHeight: 17 },
  // Mode tabs
  modeRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  modeChip: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#1E293B', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#334155' },
  modeChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  modeText: { color: '#94A3B8', fontSize: 12, fontWeight: '700' },
  // Upload
  uploadRow: { flexDirection: 'row', gap: 10 },
  uploadBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1E293B', borderRadius: 10, padding: 18, borderWidth: 1, borderColor: '#F97316', borderStyle: 'dashed' },
  uploadBtnBig: { alignItems: 'center', gap: 8, backgroundColor: '#1E293B', borderRadius: 12, padding: 26, borderWidth: 2, borderColor: '#F97316', borderStyle: 'dashed' },
  uploadBtnT: { color: '#E2E8F0', fontSize: 14, fontWeight: '600' },
  previewCard: { backgroundColor: '#1E293B', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#334155' },
  previewImg: { width: '100%', height: 220, borderRadius: 8, backgroundColor: '#334155' },
  videoCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#1E293B', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#F9731640' },
  videoText: { flex: 1, color: '#E2E8F0', fontSize: 14 },
  changeBtn: { marginTop: 8, padding: 8, backgroundColor: '#334155', borderRadius: 8, alignItems: 'center' }, changeBtnT: { color: '#E2E8F0', fontSize: 13, fontWeight: '600' },
  // Prompt
  promptInput: { backgroundColor: '#1E293B', borderRadius: 10, padding: 12, color: '#fff', fontSize: 14, borderWidth: 1, borderColor: '#334155', minHeight: 90, textAlignVertical: 'top' },
  sampleChip: { backgroundColor: '#1E293B', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 7, marginRight: 8, borderWidth: 1, borderColor: '#F9731640' },
  sampleChipText: { color: '#FDBA74', fontSize: 12, fontWeight: '600' },
  // Art style
  styleChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, marginRight: 8, borderWidth: 1, borderColor: '#334155' },
  styleChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  styleChipText: { color: '#94A3B8', fontSize: 12, fontWeight: '600' },
  // Duration / multi-shot / aspect
  durChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 9, marginRight: 8, borderWidth: 1, borderColor: '#334155', alignItems: 'center' },
  durChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  durChipLocked: { borderStyle: 'dashed', backgroundColor: 'rgba(30,41,59,0.55)', borderColor: 'rgba(251,191,36,0.45)' },
  durChipText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  shotChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8, borderWidth: 1, borderColor: '#334155' },
  shotChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  shotChipText: { color: '#94A3B8', fontSize: 13, fontWeight: '700' },
  aspectChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: '#334155' },
  aspectChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  aspectChipText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  // SFX chips
  sfxChip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#1E293B', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 8, marginRight: 8, borderWidth: 1, borderColor: '#A78BFA40' },
  sfxChipActive: { backgroundColor: '#A78BFA', borderColor: '#A78BFA' },
  sfxChipText: { color: '#A78BFA', fontSize: 12, fontWeight: '700' },
  // Dialogue audio
  audioBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#1E293B', borderRadius: 10, paddingVertical: 12, borderWidth: 1, borderColor: '#A78BFA40', borderStyle: 'dashed' },
  audioBtnT: { color: '#A78BFA', fontSize: 13, fontWeight: '700' },
  audioCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#10B98110', borderRadius: 10, padding: 12, marginTop: 8, borderWidth: 1, borderColor: '#10B98140' },
  audioText: { flex: 1, color: '#E2E8F0', fontSize: 13, fontWeight: '600' },
  audioClear: { padding: 4 },
  // Silent video warning
  silentWarn: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: '#F59E0B15', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#F59E0B40', marginBottom: 16 },
  silentText: { flex: 1, color: '#FCD34D', fontSize: 12, lineHeight: 17 },

  // Pricing banner (Cinematic AI Video vs Instant Reel)
  pricingBanner: { backgroundColor: 'rgba(249,115,22,0.08)', borderWidth: 1, borderColor: 'rgba(249,115,22,0.35)', padding: 12, borderRadius: 12, marginBottom: 14 },
  pricingBannerHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  gateBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(251,191,36,0.10)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)', paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12, marginBottom: 14 },
  gateBannerText: { color: '#FCD34D', fontSize: 12.5, flex: 1, lineHeight: 17 },
  gateBannerCta: { color: '#FBBF24', fontSize: 12, fontWeight: '900', letterSpacing: 0.4 },
  pricingBannerTitle: { flex: 1, color: '#FDBA74', fontSize: 14, fontWeight: '800' },
  pricingTag: { backgroundColor: 'rgba(249,115,22,0.25)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999 },
  pricingTagText: { color: '#FED7AA', fontSize: 10, fontWeight: '800', letterSpacing: 0.3 },
  pricingBannerDesc: { color: '#CBD5E1', fontSize: 12, lineHeight: 17 },
  pricingBannerLink: { color: '#FBBF24', fontWeight: '700', textDecorationLine: 'underline' },
  // Progress / result
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#F9731640' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  progressTitle: { color: '#fff', fontSize: 14, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, backgroundColor: '#F97316', borderRadius: 4 },
  progressPct: { color: '#F97316', fontSize: 13, fontWeight: 'bold' },
  successBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#10B98110', padding: 14, borderRadius: 10, borderWidth: 1, borderColor: '#10B98140', marginBottom: 16 },
  successText: { flex: 1, color: '#10B981', fontSize: 15, fontWeight: '700' },
  viewBtn: { backgroundColor: '#10B981', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  viewBtnT: { color: '#fff', fontSize: 13, fontWeight: '700' },
  errBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444410', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#EF444440', marginBottom: 16 },
  errText: { flex: 1, color: '#EF4444', fontSize: 13 },
  // Button
  genBtn: { backgroundColor: '#F97316', borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 10 },
  genBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  genBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
});
