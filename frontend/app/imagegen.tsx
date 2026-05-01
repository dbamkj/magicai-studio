import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput, ActivityIndicator, Alert, Image, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { uploadImageFile } from '../src/uploadHelper';
import QualityPicker from '../src/QualityPicker';
import ResolutionPicker from '../src/ResolutionPicker';
import AuroraBackground from '../src/AuroraBackground';
import ModelPickerBlock from '../src/components/ModelPickerBlock';
import AuthGateModal from '../src/components/AuthGateModal';
import { useAuth } from '../src/AuthContext';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const SAMPLE_PROMPTS = [
  { label: 'Indian Man', prompt: 'Professional portrait of a handsome Indian man wearing traditional kurta, warm lighting, photorealistic, 4K quality' },
  { label: 'Indian Woman', prompt: 'Beautiful Indian woman in elegant saree, traditional jewelry, natural makeup, studio lighting, photorealistic' },
  { label: 'Indian Couple', prompt: 'Indian couple in traditional wedding attire, bride in red lehenga, groom in sherwani, grand background, 4K' },
  { label: 'Business Pro', prompt: 'Confident Indian businessman in formal suit, modern office background, professional headshot, natural lighting' },
  { label: 'Festival', prompt: 'Indian woman celebrating Diwali with diyas and rangoli, colorful traditional dress, warm festive lighting' },
];

const DEITY_PROMPTS = [
  { label: 'Lord Krishna', prompt: 'Lord Krishna playing divine flute in Vrindavan garden, peacock feather crown, blue skin, golden ornaments, lotus flowers, ethereal glow, divine Hindu art, 4K photorealistic' },
  { label: 'Lord Shiva', prompt: 'Lord Shiva meditating on Mount Kailash, third eye, crescent moon, snake around neck, Ganga flowing from hair, trishul, divine cosmic energy, 4K' },
  { label: 'Goddess Durga', prompt: 'Goddess Durga Maa riding lion, ten arms with divine weapons, red saree, golden crown, fierce yet compassionate, cosmic background, 4K Hindu art' },
  { label: 'Lord Ganesha', prompt: 'Lord Ganesha seated on lotus throne, modak in hand, golden ornaments, elephant head, blessing pose, warm divine light, 4K' },
  { label: 'Lord Ram', prompt: 'Lord Ram in royal Ayodhya court, bow and arrow, blue skin, golden crown, divine aura, epic Indian mythological art, 4K' },
  { label: 'Lord Hanuman', prompt: 'Lord Hanuman in heroic flying pose carrying Sanjeevani mountain, powerful muscular form, devotional expression, sunrise sky, 4K' },
  { label: 'Goddess Lakshmi', prompt: 'Goddess Lakshmi showering gold coins, seated on lotus in divine ocean, four arms, red saree, golden crown, prosperity aura, 4K' },
  { label: 'Goddess Saraswati', prompt: 'Goddess Saraswati playing veena, white saree, swan beside her, books and lotus, peaceful scholarly divine light, 4K' },
  { label: 'Radha Krishna', prompt: 'Radha and Krishna divine love in Vrindavan, flute music, peacock feather, lotus garden, moonlit night, ethereal Hindu art, 4K' },
  { label: 'Lord Vishnu', prompt: 'Lord Vishnu reclining on Shesha Naga in cosmic ocean, four arms holding conch chakra mace lotus, Goddess Lakshmi at feet, 4K' },
];

const STYLES = [
  { id: 'natural', label: 'Natural' },
  { id: 'cinematic', label: 'Cinematic' },
  { id: 'portrait', label: 'Portrait' },
  { id: 'artistic', label: 'Artistic' },
  { id: 'vibrant', label: 'Vibrant' },
];

export default function ImageGenScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prompt?: string; aspectRatio?: string; prefill?: string; edit_of?: string }>();
  const [prompt, setPrompt] = useState('');
  useEffect(() => {
    if (params.prompt) setPrompt(String(params.prompt));
    // Sprint 1 — Edit pre-fill from /projects
    if (params.prefill) {
      try {
        const p = JSON.parse(String(params.prefill));
        if (p.prompt) setPrompt(p.prompt);
        if (p.aspect_ratio) setAspectRatio(p.aspect_ratio);
        if (p.style) setStyle(p.style);
        if (p.quality_mode) setQualityMode(p.quality_mode);
        if (p.resolution) setResolution(p.resolution);
      } catch (e) {}
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [style, setStyle] = useState('natural');
  const [qualityMode, setQualityMode] = useState<'quick' | 'studio' | 'cinematic'>('studio');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultError, setResultError] = useState('');
  const [refImage, setRefImage] = useState<string | null>(null);
  const [refVideoUri, setRefVideoUri] = useState<string | null>(null);
  const [refFrames, setRefFrames] = useState<any[]>([]);
  const [refUploading, setRefUploading] = useState(false);
  const pollRef = useRef<any>(null);

  // Auth gate for guest users — replaces the ugly white "Authentication required"
  // alert with the same modal shown elsewhere in the app.
  const { user } = useAuth();
  const [showAuthGate, setShowAuthGate] = useState(false);

  useEffect(() => {
    if (projectId && processing) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
          setProgress(r.data.progress || 0);
          if (r.data.status === 'completed' || r.data.status === 'failed') {
            clearInterval(pollRef.current);
            setProcessing(false);
            if (r.data.status === 'completed') {
              setResultStatus('completed');
              setResultUrl(r.data.result_url?.startsWith('/api') ? `${BACKEND_URL}${r.data.result_url}` : r.data.result_url);
            } else {
              setResultStatus('failed'); setResultError(r.data.error_message || 'Failed');
            }
          }
        } catch (e) {}
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  const generate = async () => {
    if (!user) { setShowAuthGate(true); return; }
    if (!prompt.trim()) { Alert.alert('Enter a prompt'); return; }
    try {
      setProcessing(true); setProgress(0); setResultStatus('none'); setResultUrl(null);
      const r = await axios.post(`${BACKEND_URL}/api/generate-image`, { prompt, aspect_ratio: aspectRatio, style, quality_mode: qualityMode, resolution, parent_id: params.edit_of ? String(params.edit_of) : undefined });
      setProjectId(r.data.project_id);
    } catch (e: any) {
      const status = e?.response?.status;
      if (status === 401 || status === 403) { setShowAuthGate(true); setProcessing(false); return; }
      Alert.alert('Error', e.response?.data?.detail || 'Failed');
      setProcessing(false);
    }
  };

  const pickRefImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!r.canceled && r.assets[0]) {
      setRefImage(r.assets[0].uri);
      setPrompt(prev => prev ? prev + ', similar to reference image' : 'Generate image similar to reference');
    }
  };

  const pickRefVideo = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['videos'], quality: 0.5 });
    if (!r.canceled && r.assets[0]) {
      setRefVideoUri(r.assets[0].uri); setRefUploading(true);
      try {
        const fd = new FormData();
        if (Platform.OS === 'web') {
          const resp = await fetch(r.assets[0].uri);
          const blob = await resp.blob();
          fd.append('file', new File([blob], 'ref.mp4', { type: 'video/mp4' }));
        } else {
          fd.append('file', { uri: r.assets[0].uri, name: 'ref.mp4', type: 'video/mp4' } as any);
        }
        const res = await axios.post(`${BACKEND_URL}/api/extract-frames`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
        setRefFrames(res.data.frames || []);
        // Auto-suggest prompt based on the video
        if (!prompt) setPrompt('Generate a high-quality 4K image inspired by this video scene, capturing the characters, setting, mood and atmosphere');
      } catch (e) { Alert.alert('Error', 'Could not process video'); }
      finally { setRefUploading(false); }
    }
  };

  const useSample = (p: string) => setPrompt(p);

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          <View style={s.header}>
            <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
            <Text style={s.title}>AI Image Gen</Text>
            <TouchableOpacity onPress={() => {
              Alert.alert('Clear & Reset', 'Clear prompt, reference, and any result?', [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Clear All', style: 'destructive', onPress: () => {
                  setPrompt(''); setAspectRatio('16:9'); setStyle('natural');
                  setRefImage(null); setRefVideoUri(null); setRefFrames([]); setRefUploading(false);
                  setProjectId(null); setProcessing(false); setProgress(0); setResultStatus('none'); setResultError(''); setResultUrl(null);
                }},
              ]);
            }} style={s.backBtn}><Ionicons name="refresh" size={22} color="#EF4444" /></TouchableOpacity>
          </View>
          {/* Result */}
          {resultStatus === 'completed' && resultUrl && (
            <View style={s.resultCard}>
              <Image source={{ uri: resultUrl }} style={s.resultImg} resizeMode="contain" />
              <View style={s.resultActions}>
                <TouchableOpacity style={s.resultBtn} onPress={() => router.push('/projects')}><Ionicons name="folder" size={18} color="#fff" /><Text style={s.resultBtnT}>Projects</Text></TouchableOpacity>
              </View>
            </View>
          )}
          {resultStatus === 'failed' && (
            <View style={s.errBanner}><Ionicons name="close-circle" size={22} color="#EF4444" /><Text style={s.errText}>{resultError}</Text></View>
          )}

          {processing && (
            <View style={s.progressCard}>
              <View style={s.progressHeader}><ActivityIndicator size="small" color="#EC4899" /><Text style={s.progressTitle}>Generating image...</Text></View>
              <View style={s.progressBarWrap}><View style={s.progressBarBg}><View style={[s.progressBarFill, { width: `${progress}%` }]} /></View><Text style={s.progressPct}>{progress}%</Text></View>
            </View>
          )}

          {/* Prompt */}
          <View style={s.section}>
            <Text style={s.sTitle}>1. Describe Your Image</Text>
            <TextInput style={s.promptInput} placeholder="Describe the image you want to generate..." placeholderTextColor="#64748B" value={prompt} onChangeText={setPrompt} multiline maxLength={2000} />
          </View>

          {/* Reference Video (NEW) */}
          <View style={s.section}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <Text style={s.sTitle}>Reference Video</Text>
              <View style={{ backgroundColor: '#EF4444', borderRadius: 4, paddingHorizontal: 6, paddingVertical: 1 }}><Text style={{ color: '#fff', fontSize: 9, fontWeight: '900' }}>NEW</Text></View>
            </View>
            <Text style={{ color: '#94A3B8', fontSize: 12, marginBottom: 8 }}>Upload a video and AI will extract key frames to suggest prompts.</Text>
            {refVideoUri ? (
              <View style={{ backgroundColor: '#1E293B', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#EC489940' }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Ionicons name="videocam" size={20} color="#EC4899" />
                  <Text style={{ color: '#E2E8F0', flex: 1, fontSize: 13 }}>Video uploaded</Text>
                  {refUploading && <ActivityIndicator size="small" color="#EC4899" />}
                  {!refUploading && <Ionicons name="checkmark-circle" size={18} color="#10B981" />}
                  <TouchableOpacity onPress={() => { setRefVideoUri(null); setRefFrames([]); }}><Ionicons name="close-circle" size={20} color="#EF4444" /></TouchableOpacity>
                </View>
                {refFrames.length > 0 && (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                    {refFrames.map((f: any, i: number) => (
                      <Image key={i} source={{ uri: `${BACKEND_URL}${f.url}` }} style={{ width: 80, height: 80, borderRadius: 8, marginRight: 8, backgroundColor: '#334155' }} />
                    ))}
                  </ScrollView>
                )}
              </View>
            ) : (
              <TouchableOpacity style={s.sampleChip} onPress={pickRefVideo}>
                <Text style={s.sampleLabel}>Upload Reference Video</Text>
              </TouchableOpacity>
            )}
          </View>

          {/* Reference Image (optional) */}
          <View style={s.section}>
            <Text style={s.sTitle}>Reference Image (Optional)</Text>
            {refImage ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#1E293B', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#EC489940' }}>
                <Image source={{ uri: refImage }} style={{ width: 60, height: 60, borderRadius: 8 }} />
                <Text style={{ color: '#E2E8F0', flex: 1, fontSize: 13 }}>Reference uploaded</Text>
                <TouchableOpacity onPress={() => setRefImage(null)}><Ionicons name="close-circle" size={22} color="#EF4444" /></TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={s.sampleChip} onPress={pickRefImage}>
                <Text style={s.sampleLabel}>Upload Reference Image</Text>
              </TouchableOpacity>
            )}
          </View>

          {/* Sample Prompts */}
          <View style={s.section}>
            <Text style={s.sTitle}>Sample Prompts</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {SAMPLE_PROMPTS.map((sp, i) => (
                <TouchableOpacity key={i} style={s.sampleChip} onPress={() => useSample(sp.prompt)}>
                  <Text style={s.sampleLabel}>{sp.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Gods & Goddess Prompts */}
          <View style={s.section}>
            <Text style={s.sTitle}>Indian Gods & Goddess</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {DEITY_PROMPTS.map((sp, i) => (
                <TouchableOpacity key={`deity-${i}`} style={[s.sampleChip, { borderColor: '#F59E0B40' }]} onPress={() => useSample(sp.prompt)}>
                  <Text style={[s.sampleLabel, { color: '#F59E0B' }]}>{sp.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Style */}
          <View style={s.section}>
            <Text style={s.sTitle}>2. Style</Text>
            <View style={s.styleRow}>
              {STYLES.map(st => (
                <TouchableOpacity key={st.id} style={[s.styleChip, style === st.id && s.styleActive]} onPress={() => setStyle(st.id)}>
                  <Text style={[s.styleText, style === st.id && { color: '#fff' }]}>{st.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Aspect Ratio */}
          <View style={s.section}>
            <Text style={s.sTitle}>3. Aspect Ratio</Text>
            <View style={s.ratioRow}>
              {[{ v: '16:9', l: 'Landscape' }, { v: '9:16', l: 'Portrait' }].map(ar => (
                <TouchableOpacity key={ar.v} style={[s.ratioChip, aspectRatio === ar.v && s.ratioActive]} onPress={() => setAspectRatio(ar.v)}>
                  <Text style={[s.ratioLabel, aspectRatio === ar.v && { color: '#fff' }]}>{ar.v}</Text>
                  <Text style={[s.ratioDesc, aspectRatio === ar.v && { color: '#E2E8F0' }]}>{ar.l}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* AI Image Model selector — Magic Hour catalog (replaces legacy QualityPicker per Apr-29 spec) */}
          <View style={s.section}>
            <ModelPickerBlock kind="image" />
          </View>

          {/* Output Quality (resolution + tier gate) */}
          <View style={s.section}>
            <Text style={s.sTitle}>4. Output Quality</Text>
            <Text style={{ color: '#94A3B8', fontSize: 11, marginBottom: 10, marginTop: -4 }}>
              Final image size you'll download. Higher = sharper, more credits.
            </Text>
            <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
          </View>

          <TouchableOpacity style={[s.genBtn, (!prompt.trim() || processing) && { backgroundColor: '#334155' }]} onPress={generate} disabled={!prompt.trim() || processing}>
            {processing ? <View style={s.genBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={s.genBtnT}>Generating... {progress}%</Text></View>
            : <View style={s.genBtnI}><Ionicons name="sparkles" size={22} color="#fff" /><Text style={s.genBtnT}>Generate Image</Text></View>}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
      <AuthGateModal
        visible={showAuthGate}
        onClose={() => setShowAuthGate(false)}
        reason="Image generation"
        nextRoute="/imagegen"
      />
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 16, gap: 8 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }, title: { fontSize: 22, fontWeight: 'bold', color: '#fff', flex: 1 },
  newBadge: { backgroundColor: '#EC4899', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 }, newBadgeT: { color: '#fff', fontSize: 10, fontWeight: '900' },
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
  }, sTitle: { fontSize: 15, fontWeight: '600', color: '#E2E8F0', marginBottom: 8 },
  promptInput: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, color: '#fff', fontSize: 15, minHeight: 80, textAlignVertical: 'top', borderWidth: 1, borderColor: '#334155' },
  sampleChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, marginRight: 8, borderWidth: 1, borderColor: '#334155' },
  sampleLabel: { color: '#EC4899', fontSize: 13, fontWeight: '600' },
  styleRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  styleChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: '#334155' },
  styleActive: { backgroundColor: '#EC4899', borderColor: '#EC4899' },
  styleText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  ratioRow: { flexDirection: 'row', gap: 12 },
  ratioChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  ratioActive: { backgroundColor: '#EC4899', borderColor: '#EC4899' },
  ratioLabel: { color: '#E2E8F0', fontSize: 18, fontWeight: 'bold' }, ratioDesc: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#EC489940' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  progressTitle: { color: '#fff', fontSize: 14, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, borderRadius: 4, backgroundColor: '#EC4899' }, progressPct: { fontSize: 13, fontWeight: 'bold', color: '#EC4899', width: 36 },
  resultCard: { backgroundColor: '#1E293B', borderRadius: 12, overflow: 'hidden', marginBottom: 16, borderWidth: 1, borderColor: '#10B98140' },
  resultImg: { width: '100%', height: 250 },
  resultActions: { flexDirection: 'row', padding: 12, gap: 8 },
  resultBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#10B981', borderRadius: 8, padding: 12 },
  resultBtnT: { color: '#fff', fontSize: 14, fontWeight: '700' },
  errBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444410', borderRadius: 10, padding: 12, marginBottom: 14 },
  errText: { color: '#EF4444', fontSize: 13, flex: 1 },
  genBtn: { backgroundColor: '#EC4899', borderRadius: 14, padding: 18, alignItems: 'center' },
  genBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 }, genBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
});
