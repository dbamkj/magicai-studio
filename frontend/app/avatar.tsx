import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  Image, ActivityIndicator, Alert, TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { Video, ResizeMode } from 'expo-av';
import { uploadImageFile } from '../src/uploadHelper';
import VoicePicker from '../src/VoicePicker';
import { findVoice } from '../src/voices';
import VoiceStylePicker from '../src/VoiceStylePicker';
import MotionPicker from '../src/MotionPicker';
import ResolutionPicker from '../src/ResolutionPicker';
import PauseChips from '../src/PauseChips';
import { useMhCapabilities } from '../src/useMhCapabilities';
import FreeVsProToggle from '../src/components/FreeVsProToggle';
import { useAuth } from '../src/AuthContext';
import { useTheme } from '../src/ThemeContext';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { useTierGuard } from '../src/useTierGuard';
import { saveAssetToDevice, suggestFileName } from '../src/downloadHelper';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export default function TalkingAvatarScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prefill?: string; edit_of?: string }>();
  const { user } = useAuth();
  const { isDark } = useTheme();
  const tier = useTierGuard();
  const titleColor = isDark ? '#FFFFFF' : '#0F0C29';
  const userIsPro = !!user && user.subscription_tier !== 'free';
  const [editingOf, setEditingOf] = useState<string | null>(null);

  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);

  const [script, setScript] = useState('');
  const [voiceId, setVoiceId] = useState('hi-IN-SwaraNeural');
  const [voiceStyle, setVoiceStyle] = useState<string | null>(null);
  const [voiceRate, setVoiceRate] = useState<string | null>(null);
  const [voicePitch, setVoicePitch] = useState<string | null>(null);
  const [motion, setMotion] = useState<string | null>(null);
  const [aspectRatio, setAspectRatio] = useState<'9:16' | '16:9' | '1:1'>('9:16');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  // MH talking_avatar capability — drives the price-info bar below resolution.
  const mhCap = useMhCapabilities('talking_avatar');

  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [projectStatus, setProjectStatus] = useState('');
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultError, setResultError] = useState('');
  const pollRef = useRef<any>(null);

  // Prefill from Library → Edit
  useEffect(() => {
    if (!params.prefill) return;
    try {
      const p = JSON.parse(String(params.prefill));
      if (params.edit_of) setEditingOf(String(params.edit_of));
      if (p.image_path) { setImagePath(p.image_path); setImageUri(`${BACKEND_URL}${p.image_path}`); }
      if (p.script) setScript(p.script);
      if (p.voice_id) setVoiceId(p.voice_id);
      if (p.voice_style) setVoiceStyle(p.voice_style);
      if (p.voice_rate) setVoiceRate(p.voice_rate);
      if (p.voice_pitch) setVoicePitch(p.voice_pitch);
      if (p.motion) setMotion(p.motion);
      if (p.aspect_ratio) setAspectRatio(p.aspect_ratio);
      if (p.resolution) setResolution(p.resolution);
    } catch (e) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll result
  useEffect(() => {
    if (!projectId || !processing) return;
    pollRef.current = setInterval(async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`, { timeout: 15000 });
        const prog = r.data?.progress || 0;
        const st = r.data?.status || '';
        setProgress(prog); setProjectStatus(st);
        if (st === 'completed') {
          setResultUrl(r.data.result_url ? `${BACKEND_URL}${r.data.result_url}` : null);
          setProcessing(false);
          if (pollRef.current) clearInterval(pollRef.current);
        } else if (st === 'failed') {
          setResultError(r.data.error || 'Render failed');
          setProcessing(false);
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch (e) {}
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  const pickImage = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.85 });
    if (res.canceled || !res.assets?.[0]) return;
    const asset = res.assets[0];
    setImageUri(asset.uri);
    setImageUploading(true);
    try {
      const up = await uploadImageFile(asset.uri, '/api/upload-image');
      setImagePath(up.file_path);
    } catch (e) {
      Alert.alert('Upload failed', 'Could not upload image.');
      setImageUri(null);
    }
    setImageUploading(false);
  };

  const canGenerate = !!imagePath && !imageUploading && script.trim().length > 0 && !processing;

  const generate = async () => {
    if (!canGenerate) { Alert.alert('Missing fields', 'Please upload an image and type a script.'); return; }
    // 🔒 Tier gate: Talking Avatar lip-sync requires Creator+
    if (!tier.requireFeature('talking_avatar_lipsync', 'Talking Avatar lip-sync')) {
      return;
    }
    try {
      setProcessing(true); setProgress(0); setResultUrl(null); setResultError('');
      const body = {
        image_path: imagePath,
        script: script.trim(),
        voice_id: voiceId,
        voice_style: voiceStyle || undefined,
        voice_rate: voiceRate || undefined,
        voice_pitch: voicePitch || undefined,
        motion: motion || undefined,
        aspect_ratio: aspectRatio,
        resolution,
        parent_id: editingOf || undefined,
      };
      const r = await axios.post(`${BACKEND_URL}/api/create-talking-avatar`, body, { timeout: 30000 });
      setProjectId(r.data.project_id);
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed to start';
      Alert.alert('Error', String(msg));
      setProcessing(false);
    }
  };

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          {/* Premium glass header */}
          <GlassHeader
            icon="happy"
            title="Talking Avatar"
            subtitle="Turn any photo into a talking character"
            onBack={() => router.back()}
            style={{ marginBottom: 12, paddingHorizontal: 0 }}
          />
          {editingOf && (
            <View style={s.editBanner}>
              <Ionicons name="git-branch" size={16} color="#A78BFA" />
              <Text style={s.editText}>Editing previous version — inputs carried over</Text>
            </View>
          )}

          {/* 🔒 Tier-required banner (Free + Starter) */}
          {!tier.canUseFeature('talking_avatar_lipsync') && (
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => router.push('/subscription' as any)}
              style={s.gateBanner}
            >
              <Ionicons name="lock-closed" size={16} color="#FBBF24" />
              <Text style={s.gateBannerText}>
                Talking Avatar requires the Creator plan or higher.
              </Text>
              <Text style={s.gateBannerCta}>Upgrade →</Text>
            </TouchableOpacity>
          )}

          {/* Step 1: Image */}
          <View style={s.section}>
            <Text style={s.stepTitle}>1. Upload character photo</Text>
            <TouchableOpacity onPress={pickImage} style={s.imagePicker} activeOpacity={0.85}>
              {imageUri ? (
                <Image source={{ uri: imageUri }} style={s.imagePreview} />
              ) : (
                <View style={s.imagePlaceholder}>
                  <Ionicons name="image-outline" size={40} color="#64748B" />
                  <Text style={s.imagePlaceholderText}>Tap to pick image</Text>
                </View>
              )}
              {imageUploading && (
                <View style={s.uploadingOverlay}><ActivityIndicator color="#fff" /></View>
              )}
            </TouchableOpacity>
          </View>

          {/* Step 2: Script */}
          <View style={s.section}>
            <Text style={s.stepTitle}>2. Script (what should the avatar say?)</Text>
            <TextInput
              style={s.scriptInput}
              value={script}
              onChangeText={setScript}
              placeholder="Type the dialogue… Add [pause:1.5] for pauses."
              placeholderTextColor="#64748B"
              multiline
              textAlignVertical="top"
            />
            <PauseChips onInsert={(tag) => setScript((prev) => (prev || '') + (prev && !prev.endsWith(' ') ? ' ' : '') + tag)} />
          </View>

          {/* Step 3: Voice */}
          <View style={s.section}>
            <Text style={s.stepTitle}>3. Voice</Text>
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
          </View>

          {/* Step 4: Camera motion */}
          <View style={s.section}>
            <Text style={s.stepTitle}>4. Camera motion (optional)</Text>
            <MotionPicker
              selectedId={motion}
              onSelect={setMotion}
              label="Add camera movement"
            />
          </View>

          {/* Step 5: Format */}
          <View style={s.section}>
            <Text style={s.stepTitle}>5. Format</Text>
            <Text style={s.label}>Aspect ratio</Text>
            <View style={s.row}>
              {(['9:16', '16:9', '1:1'] as const).map(ar => (
                <TouchableOpacity key={ar} onPress={() => setAspectRatio(ar)} style={[s.pill, aspectRatio === ar && s.pillActive]}>
                  <Text style={[s.pillText, aspectRatio === ar && s.pillTextActive]}>{ar}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.label}>Resolution</Text>
            <ResolutionPicker selected={resolution} onSelect={setResolution} />
            {mhCap.costPerSec != null && (
              <View style={s.mhInfoBar}>
                <Ionicons name="information-circle" size={14} color="#A78BFA" />
                <Text style={s.mhInfoText}>
                  Pricing: 🪙 {mhCap.costPerSec}¢/sec · min billed {mhCap.minBilled}s ({mhCap.minCost} credits)
                </Text>
              </View>
            )}
          </View>

          {/* Progress / Result */}
          {processing && (
            <View style={s.resultCard}>
              <ActivityIndicator color="#A78BFA" />
              <Text style={s.resultText}>Rendering avatar… {progress}% ({projectStatus})</Text>
            </View>
          )}
          {resultError && (
            <View style={[s.resultCard, { borderColor: '#EF4444' }]}>
              <Ionicons name="alert-circle" size={22} color="#EF4444" />
              <Text style={[s.resultText, { color: '#FCA5A5' }]}>{resultError}</Text>
            </View>
          )}
          {resultUrl && (
            <View style={s.resultCard}>
              <Text style={[s.stepTitle, { marginBottom: 8 }]}>✨ Your talking avatar</Text>
              <FreeVsProToggle
                mediaUrl={resultUrl}
                mediaType="video"
                userIsPro={userIsPro}
                aspectRatio={9 / 16}
                freeTagline="Watermark · 480p · 15s · Standard render"
                proTagline="Clean · 1080p HD · 60s · Faster render"
                onUpgrade={() => router.push('/buy?tab=tier' as any)}
                onDownload={async () => {
                  if (!resultUrl) return;
                  if (!tier.requireFeature('download_to_gallery', 'Avatar download to gallery')) return;
                  const fname = suggestFileName(resultUrl, 'video');
                  await saveAssetToDevice(resultUrl, fname, 'video');
                }}
              />
              <TouchableOpacity style={[s.libBtn, { marginTop: 12 }]} onPress={() => router.push('/projects')} activeOpacity={0.8}>
                <Ionicons name="folder-open" size={16} color="#fff" />
                <Text style={s.libBtnText}>Open in Library</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Generate button */}
          <TouchableOpacity
            style={[s.cta, !canGenerate && s.ctaDisabled]}
            onPress={generate}
            disabled={!canGenerate}
            activeOpacity={0.85}
          >
            {processing ? <ActivityIndicator color="#fff" /> : (
              <>
                <Ionicons name="play-circle" size={22} color="#fff" />
                <Text style={s.ctaText}>Create Talking Avatar</Text>
              </>
            )}
          </TouchableOpacity>
          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  scroll: { padding: 16, paddingBottom: 40 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 12 },
  back: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.06)' },
  title: { fontSize: 22, fontWeight: '800', color: '#fff' },
  subtitle: { fontSize: 13, color: '#94A3B8', marginTop: 2 },
  editBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.4)', padding: 10, borderRadius: 10, marginBottom: 12 },
  editText: { color: '#A78BFA', fontSize: 13, flex: 1 },
  gateBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(251,191,36,0.10)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)', paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12, marginBottom: 12 },
  gateBannerText: { color: '#FCD34D', fontSize: 12.5, flex: 1, lineHeight: 17 },
  gateBannerCta: { color: '#FBBF24', fontSize: 12, fontWeight: '900', letterSpacing: 0.4 },
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
  },
  stepTitle: { fontSize: 15, fontWeight: '700', color: '#fff', marginBottom: 10 },
  label: { color: '#9CA3AF', fontSize: 13, marginBottom: 6, marginTop: 4 },
  mhInfoBar: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, paddingVertical: 8, paddingHorizontal: 10, backgroundColor: 'rgba(167,139,250,0.08)', borderWidth: 1, borderColor: 'rgba(167,139,250,0.3)', borderRadius: 10 },
  mhInfoText: { color: '#C4B5FD', fontSize: 12, fontWeight: '600', flex: 1 },
  hint: { color: '#6B7280', fontSize: 12, marginTop: 4 },
  imagePicker: { height: 220, borderRadius: 12, overflow: 'hidden', backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)', alignItems: 'center', justifyContent: 'center' },
  imagePlaceholder: { alignItems: 'center', gap: 8 },
  imagePlaceholderText: { color: '#64748B', fontSize: 14 },
  imagePreview: { width: '100%', height: '100%', resizeMode: 'cover' },
  uploadingOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.6)', alignItems: 'center', justifyContent: 'center' },
  scriptInput: { backgroundColor: 'rgba(255,255,255,0.04)', color: '#fff', borderRadius: 10, padding: 12, fontSize: 15, minHeight: 100, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  row: { flexDirection: 'row', gap: 8, marginBottom: 8, flexWrap: 'wrap' },
  pill: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)' },
  pillActive: { backgroundColor: 'rgba(139,92,246,0.22)', borderColor: 'rgba(167,139,250,0.65)' },
  pillText: { color: '#9CA3AF', fontSize: 13, fontWeight: '500' },
  pillTextActive: { color: '#E0D4FF', fontWeight: '700' },
  resultCard: { backgroundColor: 'rgba(139,92,246,0.08)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.35)', borderRadius: 12, padding: 12, marginBottom: 14, gap: 8, alignItems: 'center' },
  resultText: { color: '#E5E7EB', fontSize: 14, textAlign: 'center' },
  resultVideo: { width: '100%', height: 300, borderRadius: 10, backgroundColor: '#000' },
  libBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 9, backgroundColor: '#7C3AED', borderRadius: 999, marginTop: 8 },
  libBtnText: { color: '#fff', fontSize: 13, fontWeight: '700' },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#8B5CF6', borderRadius: 14, paddingVertical: 16, marginTop: 8 },
  ctaDisabled: { opacity: 0.5 },
  ctaText: { color: '#fff', fontSize: 16, fontWeight: '800' },
});
