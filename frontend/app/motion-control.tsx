import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator,
  Alert, Image, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { Video, ResizeMode } from 'expo-av';
import CosmicBackground from '../src/CosmicBackground';
import ResolutionPicker from '../src/ResolutionPicker';
import axios from 'axios';
import AuroraBackground from '../src/AuroraBackground';
import useTierGuard from '../src/useTierGuard';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type MotionPreset = {
  id: string;
  label: string;
  description?: string;
  icon?: string;
};

/** Motion Control — lightweight image → video tool that uses only FFmpeg on
 *  the backend (zoompan filter) to apply a ken-burns / zoom / pan preset.
 *  Zero Magic-Hour credits. */
export default function MotionControlScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prefill?: string; from_template?: string }>();
  const tier = useTierGuard();

  const [presets, setPresets] = useState<MotionPreset[]>([]);
  const [motion, setMotion] = useState<string>('ken_burns');
  const [duration, setDuration] = useState<number>(5);
  const [aspect, setAspect] = useState<'9:16' | '16:9' | '1:1'>('9:16');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [sourceLabel, setSourceLabel] = useState<string | null>(null);

  // Prefill motion / aspect / thumbnail from template
  useEffect(() => {
    if (params.prefill) {
      try {
        const p = JSON.parse(String(params.prefill));
        if (p.motion) setMotion(p.motion);
        if (p.aspect_ratio) setAspect(p.aspect_ratio);
        if (p.duration) setDuration(p.duration);
        if (p.thumbnail_url) {
          const full = String(p.thumbnail_url).startsWith('http') ? p.thumbnail_url : `${BACKEND_URL}${p.thumbnail_url}`;
          setImageUri(full);
          setSourceLabel(p.source_label || 'Template cover');
          // Use backend /api/upload-from-url to avoid browser CORS on 3rd-party CDNs.
          (async () => {
            setUploading(true);
            try {
              const token = (typeof window !== 'undefined' && window.localStorage)
                ? window.localStorage.getItem('magicai_jwt_v1') : null;
              const r = await axios.post(
                `${BACKEND_URL}/api/upload-from-url`,
                { url: full, filename: 'template_cover.jpg' },
                { timeout: 45000, headers: token ? { Authorization: `Bearer ${token}` } : {} },
              );
              const path = r.data?.file_path || r.data?.path;
              if (path) setImagePath(path);
              else Alert.alert('Could not load template cover', 'Please pick an image from your gallery.');
            } catch (e: any) {
              Alert.alert('Could not load template cover', e.response?.data?.detail || 'Pick an image from your gallery to continue.');
            } finally {
              setUploading(false);
            }
          })();
        }
      } catch {}
    }
  }, []);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/motion-presets`).then(r => {
      setPresets(r.data?.presets || []);
    }).catch(() => {});
  }, []);

  const pick = async (fromCamera: boolean) => {
    const perm = fromCamera
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) { Alert.alert('Permission needed'); return; }
    const r = fromCamera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.9 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.9 });
    if (r.canceled || !r.assets?.[0]) return;
    const asset = r.assets[0];
    setImageUri(asset.uri);
    setSourceLabel(null);
    setUploading(true);
    try {
      const token = (typeof window !== 'undefined' && window.localStorage)
        ? window.localStorage.getItem('magicai_jwt_v1') : null;
      const blob = await (await fetch(asset.uri)).blob();
      const fd = new FormData();
      fd.append('file', blob as any, asset.fileName || 'motion_src.jpg');
      const up = await axios.post(`${BACKEND_URL}/api/upload-image`, fd as any, {
        timeout: 60000,
        headers: { 'Content-Type': 'multipart/form-data', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      setImagePath(up.data?.file_path || up.data?.path || up.data?.image_path);
    } catch (e: any) {
      Alert.alert('Upload failed', e.response?.data?.detail || 'Could not upload the image.');
      setImageUri(null);
    } finally {
      setUploading(false);
    }
  };

  const render = async () => {
    if (!imagePath) { Alert.alert('Upload an image first'); return; }
    // 🔒 Tier gate — Motion Control is now a Creator+/Pro feature.
    if (!tier.requireFeature('motion_control', 'Motion Control')) return;
    setProcessing(true);
    setResultUrl(null);
    setProgress(5);
    try {
      const token = (typeof window !== 'undefined' && window.localStorage)
        ? window.localStorage.getItem('magicai_jwt_v1') : null;
      const r = await axios.post(`${BACKEND_URL}/api/animate-image`, {
        image_path: imagePath, motion, duration, resolution,
      }, { timeout: 30000, headers: token ? { Authorization: `Bearer ${token}` } : {} });
      const pid = r.data?.project_id;
      setProjectId(pid);
      // Poll project status
      const poll = async () => {
        try {
          const pr = await axios.get(`${BACKEND_URL}/api/project/${pid}`, { timeout: 15000 });
          const st = pr.data?.project;
          if (!st) return;
          setProgress(st.progress || 10);
          if (st.status === 'completed' && st.result_url) {
            setResultUrl(st.result_url);
            setProcessing(false);
            return;
          }
          if (st.status === 'failed') {
            Alert.alert('Render failed', st.error || 'Unknown error');
            setProcessing(false);
            return;
          }
          setTimeout(poll, 1500);
        } catch {
          setTimeout(poll, 2000);
        }
      };
      setTimeout(poll, 800);
    } catch (e: any) {
      setProcessing(false);
      Alert.alert('Error', e.response?.data?.detail || 'Failed to start render.');
    }
  };

  const resultFull = resultUrl
    ? (resultUrl.startsWith('http') ? resultUrl : `${BACKEND_URL}${resultUrl}`)
    : null;

  return (
    <CosmicBackground>
      <AuroraBackground>
      <SafeAreaView style={s.container}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }} keyboardShouldPersistTaps="handled">
            {/* Header */}
            <View style={s.header}>
              <TouchableOpacity onPress={() => router.back()} style={s.back}>
                <Ionicons name="arrow-back" size={22} color="#fff" />
              </TouchableOpacity>
              <View style={{ flex: 1 }}>
                <Text style={s.title}>🎥 Motion Control</Text>
                <Text style={s.subtitle}>Photo → video · ken-burns / zoom / pan</Text>
              </View>

              {/* Creator+ pill — replaces the previous "Free" label so the
                  tier requirement is obvious in the page header itself. */}
              <View style={[s.instantPill, { borderColor: 'rgba(251,191,36,0.45)', backgroundColor: 'rgba(251,191,36,0.14)' }]}>
                <Ionicons name="lock-closed" size={11} color="#FBBF24" />
                <Text style={[s.instantPillText, { color: '#FBBF24' }]}>Creator+</Text>
              </View>
            </View>

            {/* Banner clarifying this is a paid-plan feature */}
            <View style={[s.instantBanner, { borderColor: 'rgba(251,191,36,0.35)', backgroundColor: 'rgba(251,191,36,0.10)' }]}>
              <Ionicons name="diamond" size={14} color="#FBBF24" />
              <Text style={[s.instantBannerText, { color: '#FBBF24' }]}>
                Motion Control is part of the Creator & Pro plans.
              </Text>
            </View>

            {/* Step 1: Source image */}
            <Text style={s.stepTitle}>1. Source photo</Text>
            {imageUri ? (
              <View style={s.imagePreviewWrap}>
                <Image source={{ uri: imageUri }} style={s.imagePreview} resizeMode="cover" />
                {uploading && (
                  <View style={s.uploadOverlay}>
                    <ActivityIndicator size="small" color="#FBBF24" />
                    <Text style={s.uploadOverlayText}>Uploading…</Text>
                  </View>
                )}
                {!!sourceLabel && <Text style={s.sourceLabel}>From: {sourceLabel}</Text>}
                <TouchableOpacity style={s.changeBtn} onPress={() => { setImageUri(null); setImagePath(null); setSourceLabel(null); }}>
                  <Text style={s.changeBtnText}>Change</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <View style={s.uploadRow}>
                <TouchableOpacity style={s.uploadBtn} onPress={() => pick(false)} activeOpacity={0.82}>
                  <Ionicons name="images" size={22} color="#FBBF24" />
                  <Text style={s.uploadBtnT}>Gallery</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.uploadBtn} onPress={() => pick(true)} activeOpacity={0.82}>
                  <Ionicons name="camera" size={22} color="#FBBF24" />
                  <Text style={s.uploadBtnT}>Camera</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Step 2: Motion preset */}
            <Text style={s.stepTitle}>2. Motion preset</Text>
            <View style={s.motionGrid}>
              {presets.map(p => {
                const active = motion === p.id;
                return (
                  <TouchableOpacity
                    key={p.id}
                    style={[s.motionChip, active && s.motionChipActive]}
                    onPress={() => setMotion(p.id)}
                    activeOpacity={0.82}
                  >
                    <Text style={[s.motionChipText, active && { color: '#fff' }]}>{p.label || p.id}</Text>
                    {!!p.description && (
                      <Text style={[s.motionChipDesc, active && { color: '#FDE68A' }]} numberOfLines={1}>{p.description}</Text>
                    )}
                  </TouchableOpacity>
                );
              })}
              {presets.length === 0 && (
                <Text style={{ color: '#94A3B8', fontSize: 12 }}>Loading presets…</Text>
              )}
            </View>

            {/* Step 3: Duration + Aspect + Resolution */}
            <Text style={s.stepTitle}>3. Output</Text>
            <Text style={s.label}>Duration</Text>
            <View style={s.row}>
              {[3, 5, 8, 10, 15].map(d => (
                <TouchableOpacity key={d} style={[s.pill, duration === d && s.pillActive]} onPress={() => setDuration(d)}>
                  <Text style={[s.pillText, duration === d && s.pillTextActive]}>{d}s</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.label}>Aspect ratio</Text>
            <View style={s.row}>
              {(['9:16', '16:9', '1:1'] as const).map(a => (
                <TouchableOpacity key={a} style={[s.pill, aspect === a && s.pillActive]} onPress={() => setAspect(a)}>
                  <Text style={[s.pillText, aspect === a && s.pillTextActive]}>{a}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.label}>Resolution</Text>
            <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />

            {/* Render button + status */}
            {processing && (
              <View style={s.resultCard}>
                <ActivityIndicator color="#FBBF24" />
                <Text style={s.resultText}>Rendering motion… {progress}%</Text>
              </View>
            )}
            {resultFull && (
              <View style={s.resultCard}>
                <Video
                  source={{ uri: resultFull }}
                  style={s.resultVideo}
                  useNativeControls
                  resizeMode={ResizeMode.COVER}
                  shouldPlay={false}
                  isLooping
                />
                <Text style={[s.resultText, { color: '#A7F3D0' }]}>Motion applied ✓</Text>
              </View>
            )}

            <TouchableOpacity
              style={[s.cta, (!imagePath || processing) && s.ctaDisabled]}
              disabled={!imagePath || processing}
              onPress={render}
              activeOpacity={0.85}
            >
              <Ionicons
                name={tier.canUseFeature('motion_control') ? 'sparkles' : 'lock-closed'}
                size={20}
                color={!imagePath || processing ? '#64748B' : '#1F1029'}
              />
              <Text style={[s.ctaText, (!imagePath || processing) && { color: '#64748B' }]}>
                {processing
                  ? 'Rendering…'
                  : tier.canUseFeature('motion_control')
                    ? 'Apply motion'
                    : 'Apply motion (Creator+)'}
              </Text>
            </TouchableOpacity>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
      </AuroraBackground>
    </CosmicBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 10 },
  back: { padding: 8 },
  title: { color: '#F1F5F9', fontSize: 20, fontWeight: '800' },
  subtitle: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  instantPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, backgroundColor: 'rgba(16,185,129,0.15)', borderWidth: 1, borderColor: 'rgba(16,185,129,0.5)' },
  instantPillText: { color: '#6EE7B7', fontSize: 10, fontWeight: '800' },
  instantBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(16,185,129,0.08)', borderWidth: 1, borderColor: 'rgba(16,185,129,0.3)', borderRadius: 10, padding: 10, marginBottom: 14 },
  instantBannerText: { flex: 1, color: '#A7F3D0', fontSize: 12, fontWeight: '600' },
  stepTitle: { color: '#F1F5F9', fontSize: 15, fontWeight: '800', marginTop: 12, marginBottom: 10 },
  label: { color: '#94A3B8', fontSize: 12, fontWeight: '600', marginTop: 12, marginBottom: 6 },
  uploadRow: { flexDirection: 'row', gap: 10 },
  uploadBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, backgroundColor: '#1E293B', borderRadius: 12, borderWidth: 1, borderColor: '#334155' },
  uploadBtnT: { color: '#F1F5F9', fontSize: 14, fontWeight: '700' },
  imagePreviewWrap: { position: 'relative', marginTop: 2, borderRadius: 14, overflow: 'hidden' },
  imagePreview: { width: '100%', height: 240, backgroundColor: '#0B1120' },
  uploadOverlay: { position: 'absolute', inset: 0, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(11,17,32,0.7)', gap: 8 },
  uploadOverlayText: { color: '#FBBF24', fontSize: 13, fontWeight: '700' },
  sourceLabel: { position: 'absolute', top: 8, left: 8, color: '#F1F5F9', fontSize: 11, fontWeight: '700', backgroundColor: 'rgba(15,23,42,0.78)', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 999 },
  changeBtn: { position: 'absolute', top: 8, right: 8, backgroundColor: 'rgba(15,23,42,0.9)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: 'rgba(167,139,250,0.5)' },
  changeBtnText: { color: '#A78BFA', fontSize: 11, fontWeight: '800' },
  motionGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  motionChip: { paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12, backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155', minWidth: 100 },
  motionChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  motionChipText: { color: '#E2E8F0', fontSize: 13, fontWeight: '800' },
  motionChipDesc: { color: '#94A3B8', fontSize: 10, marginTop: 2 },
  row: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  pill: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: 999, backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155' },
  pillActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  pillText: { color: '#E2E8F0', fontSize: 13, fontWeight: '700' },
  pillTextActive: { color: '#fff' },
  resultCard: { marginTop: 14, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(251,191,36,0.35)', backgroundColor: 'rgba(251,191,36,0.05)', alignItems: 'center', gap: 8 },
  resultText: { color: '#FDE68A', fontSize: 13, fontWeight: '700' },
  resultVideo: { width: '100%', height: 300, borderRadius: 10, backgroundColor: '#0B1120' },
  cta: { marginTop: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#FBBF24', paddingVertical: 15, borderRadius: 14 },
  ctaDisabled: { backgroundColor: '#1E293B' },
  ctaText: { color: '#1F1029', fontSize: 15, fontWeight: '900', letterSpacing: 0.3 },
});
