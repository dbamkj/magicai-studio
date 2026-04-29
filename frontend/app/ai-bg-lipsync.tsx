import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput, ActivityIndicator, Alert,
  KeyboardAvoidingView, Platform, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import VoicePicker from '../src/VoicePicker';
import { findVoice } from '../src/voices';
import { uploadImageFile } from '../src/uploadHelper';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type SceneMode = 'custom' | 'suggested';

interface Suggestion { title: string; prompt: string; }

const DURATIONS = [
  { label: '5s', v: 5 }, { label: '10s', v: 10 }, { label: '15s', v: 15 },
  { label: '30s', v: 30 }, { label: '1 min', v: 60 }, { label: '2 min', v: 120 },
];

export default function AiBgLipSyncScreen() {
  const router = useRouter();
  const [charUri, setCharUri] = useState<string | null>(null);
  const [charPath, setCharPath] = useState<string | null>(null);
  const [charUploading, setCharUploading] = useState(false);
  const [sceneMode, setSceneMode] = useState<SceneMode>('suggested');
  const [userHint, setUserHint] = useState('');
  const [customPrompt, setCustomPrompt] = useState('');
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState('');
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [dialogue, setDialogue] = useState('');
  const [voiceId, setVoiceId] = useState('hi-IN-SwaraNeural');
  const [duration, setDuration] = useState(10);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<'idle' | 'scene' | 'lipsync'>('idle');
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultError, setResultError] = useState('');
  const pollRef = useRef<any>(null);

  useEffect(() => {
    if (projectId && processing) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
          const p = r.data.progress || 0;
          setProgress(p);
          // Stage 1: scene generation (5-65%), Stage 2: lip sync (65-100%)
          setStage(p < 65 ? 'scene' : 'lipsync');
          if (r.data.status === 'completed' || r.data.status === 'failed') {
            clearInterval(pollRef.current); setProcessing(false);
            setResultStatus(r.data.status === 'completed' ? 'completed' : 'failed');
            if (r.data.status === 'failed') setResultError(r.data.error_message || 'Failed');
          }
        } catch (e) {}
      }, 3500);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  const resetAll = () => {
    Alert.alert('Clear & Reset', 'Clear everything?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear All', style: 'destructive', onPress: () => {
        setCharUri(null); setCharPath(null); setCharUploading(false);
        setSceneMode('suggested'); setUserHint(''); setCustomPrompt('');
        setSuggestions([]); setSelectedPrompt('');
        setDialogue(''); setVoiceId('hi-IN-SwaraNeural'); setDuration(10); setAspectRatio('9:16');
        setProjectId(null); setProcessing(false); setProgress(0); setStage('idle'); setResultStatus('none'); setResultError('');
      }},
    ]);
  };

  const pickChar = async (fromCamera = false) => {
    const { status } = fromCamera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = fromCamera ? await ImagePicker.launchCameraAsync({ quality: 0.8 }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!r.canceled && r.assets[0]) {
      const uri = r.assets[0].uri;
      setCharUri(uri); setCharUploading(true);
      try {
        const data = await uploadImageFile(uri, '/api/upload-face-image');
        setCharPath(data.file_path);
      } catch (e) { Alert.alert('Upload failed'); setCharUri(null); }
      finally { setCharUploading(false); }
    }
  };

  const fetchSuggestions = async () => {
    try {
      setLoadingSuggestions(true);
      const r = await axios.post(`${BACKEND_URL}/api/suggest-scenes`, { user_hint: userHint || undefined, count: 4 });
      setSuggestions(r.data.suggestions || []);
    } catch (e: any) { Alert.alert('Failed to fetch suggestions'); }
    finally { setLoadingSuggestions(false); }
  };

  const generate = async () => {
    if (!charPath) { Alert.alert('Upload character image first'); return; }
    const scenePrompt = sceneMode === 'custom' ? customPrompt.trim() : selectedPrompt.trim();
    if (!scenePrompt) { Alert.alert('Pick or write a scene prompt'); return; }
    if (!dialogue.trim()) { Alert.alert('Enter character dialogue'); return; }
    try {
      setProcessing(true); setProgress(0); setStage('scene'); setResultStatus('none');
      const r = await axios.post(`${BACKEND_URL}/api/create-ai-bg-lipsync`, {
        character_image_path: charPath,
        scene_prompt: scenePrompt,
        dialogue_text: dialogue,
        voice_id: voiceId,
        duration,
        aspect_ratio: aspectRatio,
      });
      setProjectId(r.data.project_id);
    } catch (e: any) {
      Alert.alert('Error', e.response?.data?.detail || 'Failed');
      setProcessing(false); setStage('idle');
    }
  };

  const canGenerate = !processing && !!charPath && (sceneMode === 'custom' ? customPrompt.trim() : selectedPrompt.trim()) && dialogue.trim();

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          <View style={s.header}>
            <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
            <Text style={s.title}>AI Background Lip Sync</Text>
            <TouchableOpacity onPress={resetAll} style={s.backBtn}><Ionicons name="refresh" size={22} color="#EF4444" /></TouchableOpacity>
          </View>
          <View style={s.tipCard}>
            <Ionicons name="sparkles" size={18} color="#EC4899" />
            <Text style={s.tipText}>Place your character in a brand-new AI-generated scene with new background, surroundings, and sound — not the original. Pick a scene or write your own.</Text>
          </View>

          {resultStatus === 'completed' && (
            <View style={s.successBanner}>
              <Ionicons name="checkmark-circle" size={22} color="#10B981" />
              <Text style={s.successText}>AI scene + lip sync ready!</Text>
              <TouchableOpacity style={s.viewBtn} onPress={() => router.push('/projects')}><Text style={s.viewBtnT}>View</Text></TouchableOpacity>
            </View>
          )}
          {resultStatus === 'failed' && <View style={s.errBanner}><Ionicons name="close-circle" size={22} color="#EF4444" /><Text style={s.errText}>{resultError}</Text></View>}
          {processing && (
            <View style={s.progressCard}>
              <View style={s.progressHeader}>
                <ActivityIndicator size="small" color="#EC4899" />
                <Text style={s.progressTitle}>
                  {stage === 'scene' ? 'Stage 1/2: Generating AI scene...' : 'Stage 2/2: Lip-syncing dialogue...'}
                </Text>
              </View>
              <View style={s.progressBarWrap}><View style={s.progressBarBg}><View style={[s.progressBarFill, { width: `${progress}%` }]} /></View><Text style={s.progressPct}>{progress}%</Text></View>
            </View>
          )}

          {/* Step 1: Character Image */}
          <View style={s.section}>
            <Text style={s.sTitle}>1. Character Image</Text>
            <Text style={s.hint}>Upload a photo of your character. They'll be placed into the new scene and lip-synced.</Text>
            {charUri ? (
              <View style={s.previewCard}>
                <Image source={{ uri: charUri }} style={s.previewImg} />
                {charUploading && <ActivityIndicator size="small" color="#EC4899" style={{ marginTop: 6 }} />}
                <TouchableOpacity style={s.changeBtn} onPress={() => pickChar(false)}><Text style={s.changeBtnT}>Change</Text></TouchableOpacity>
              </View>
            ) : (
              <View style={s.uploadRow}>
                <TouchableOpacity style={s.uploadBtn} onPress={() => pickChar(false)}><Ionicons name="images" size={22} color="#EC4899" /><Text style={s.uploadBtnT}>Gallery</Text></TouchableOpacity>
                <TouchableOpacity style={s.uploadBtn} onPress={() => pickChar(true)}><Ionicons name="camera" size={22} color="#EC4899" /><Text style={s.uploadBtnT}>Camera</Text></TouchableOpacity>
              </View>
            )}
          </View>

          {/* Step 2: Scene Source */}
          <View style={s.section}>
            <Text style={s.sTitle}>2. Choose Scene</Text>
            <View style={s.modeRow}>
              <TouchableOpacity style={[s.modeChip, sceneMode === 'suggested' && s.modeChipActive]} onPress={() => setSceneMode('suggested')}>
                <Ionicons name="sparkles" size={14} color={sceneMode === 'suggested' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, sceneMode === 'suggested' && { color: '#fff' }]}>AI Suggestions</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.modeChip, sceneMode === 'custom' && s.modeChipActive]} onPress={() => setSceneMode('custom')}>
                <Ionicons name="create" size={14} color={sceneMode === 'custom' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, sceneMode === 'custom' && { color: '#fff' }]}>Write My Own</Text>
              </TouchableOpacity>
            </View>

            {sceneMode === 'suggested' && (
              <View style={{ marginTop: 6 }}>
                <TextInput style={s.hintInput} value={userHint} onChangeText={setUserHint} placeholder="Optional topic hint (e.g., Krishna devotional, sci-fi hero, romantic)..." placeholderTextColor="#64748B" />
                <TouchableOpacity style={s.suggestBtn} onPress={fetchSuggestions} disabled={loadingSuggestions}>
                  {loadingSuggestions ? <ActivityIndicator size="small" color="#fff" /> : (
                    <><Ionicons name="sparkles" size={16} color="#fff" /><Text style={s.suggestBtnT}>Get AI Scene Ideas</Text></>
                  )}
                </TouchableOpacity>
                {suggestions.length > 0 && (
                  <View style={{ marginTop: 10 }}>
                    {suggestions.map((sg, i) => (
                      <TouchableOpacity key={i} style={[s.suggCard, selectedPrompt === sg.prompt && s.suggCardActive]} onPress={() => setSelectedPrompt(sg.prompt)}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                          <Ionicons name={selectedPrompt === sg.prompt ? 'radio-button-on' : 'radio-button-off'} size={18} color={selectedPrompt === sg.prompt ? '#EC4899' : '#94A3B8'} />
                          <Text style={s.suggTitle}>{sg.title}</Text>
                        </View>
                        <Text style={s.suggPrompt}>{sg.prompt}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              </View>
            )}

            {sceneMode === 'custom' && (
              <TextInput
                style={[s.hintInput, { minHeight: 100, textAlignVertical: 'top', marginTop: 8 }]}
                value={customPrompt}
                onChangeText={setCustomPrompt}
                placeholder="Describe the scene: e.g., 'Lord Krishna playing flute in Vrindavan garden at sunset, peacock feather, cinematic slow motion'"
                placeholderTextColor="#64748B"
                multiline
              />
            )}
          </View>

          {/* Step 3: Dialogue */}
          <View style={s.section}>
            <Text style={s.sTitle}>3. Character Dialogue</Text>
            <TextInput
              style={[s.hintInput, { minHeight: 80, textAlignVertical: 'top' }]}
              value={dialogue}
              onChangeText={setDialogue}
              placeholder="What should the character say? (Hindi or English)..."
              placeholderTextColor="#64748B"
              multiline
            />
          </View>

          {/* Step 4: Voice */}
          <View style={s.section}>
            <Text style={s.sTitle}>4. Voice</Text>
            <VoicePicker selectedId={voiceId} onSelect={setVoiceId} />
            <Text style={[s.hint, { marginTop: 6 }]}>Selected: <Text style={{ color: '#A78BFA', fontWeight: '700' }}>{findVoice(voiceId)?.name || 'Swara'}</Text></Text>
          </View>

          {/* Duration + Aspect */}
          <View style={s.section}>
            <Text style={s.sTitle}>5. Duration</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 6 }}>
              {DURATIONS.map((d, i) => (
                <TouchableOpacity key={i} style={[s.durChip, duration === d.v && s.durChipActive]} onPress={() => setDuration(d.v)}>
                  <Text style={[s.durChipText, duration === d.v && { color: '#fff' }]}>{d.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <Text style={[s.sTitle, { marginTop: 14 }]}>Aspect Ratio</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
              {['9:16', '16:9', '1:1'].map(ar => (
                <TouchableOpacity key={ar} style={[s.aspectChip, aspectRatio === ar && s.aspectChipActive]} onPress={() => setAspectRatio(ar)}>
                  <Text style={[s.aspectChipText, aspectRatio === ar && { color: '#fff' }]}>{ar}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <TouchableOpacity style={[s.genBtn, !canGenerate && { backgroundColor: '#334155' }]} onPress={generate} disabled={!canGenerate}>
            {processing ? (
              <View style={s.genBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={s.genBtnT}>Processing... {progress}%</Text></View>
            ) : (
              <View style={s.genBtnI}><Ionicons name="sparkles" size={22} color="#fff" /><Text style={s.genBtnT}>Generate AI Scene + Lip Sync</Text></View>
            )}
          </TouchableOpacity>
          <Text style={[s.hint, { textAlign: 'center', marginTop: 10 }]}>⚡ Uses ~{Math.round(duration * 17)} credits (image→video + lip-sync)</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 80 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  tipCard: { flexDirection: 'row', gap: 8, backgroundColor: '#EC489920', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#EC489940', marginBottom: 16 },
  tipText: { flex: 1, color: '#FBCFE8', fontSize: 12, lineHeight: 17 },
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
  modeRow: { flexDirection: 'row', gap: 8 },
  modeChip: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#1E293B', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#334155' },
  modeChipActive: { backgroundColor: '#EC4899', borderColor: '#EC4899' },
  modeText: { color: '#94A3B8', fontSize: 12, fontWeight: '700' },
  uploadRow: { flexDirection: 'row', gap: 10 },
  uploadBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1E293B', borderRadius: 10, padding: 18, borderWidth: 1, borderColor: '#EC4899', borderStyle: 'dashed' },
  uploadBtnT: { color: '#E2E8F0', fontSize: 14, fontWeight: '600' },
  previewCard: { backgroundColor: '#1E293B', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#334155' },
  previewImg: { width: '100%', height: 220, borderRadius: 8, backgroundColor: '#334155' },
  changeBtn: { marginTop: 8, padding: 8, backgroundColor: '#334155', borderRadius: 8, alignItems: 'center' }, changeBtnT: { color: '#E2E8F0', fontSize: 13, fontWeight: '600' },
  hintInput: { backgroundColor: '#1E293B', borderRadius: 10, padding: 12, color: '#fff', fontSize: 14, borderWidth: 1, borderColor: '#334155' },
  suggestBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#EC4899', borderRadius: 10, padding: 12, marginTop: 8 },
  suggestBtnT: { color: '#fff', fontSize: 14, fontWeight: '700' },
  suggCard: { backgroundColor: '#1E293B', borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#334155' },
  suggCardActive: { borderColor: '#EC4899', backgroundColor: '#EC489910' },
  suggTitle: { color: '#F9A8D4', fontSize: 14, fontWeight: '700' },
  suggPrompt: { color: '#CBD5E1', fontSize: 12, marginTop: 6, lineHeight: 17 },
  durChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 9, marginRight: 8, borderWidth: 1, borderColor: '#334155' },
  durChipActive: { backgroundColor: '#EC4899', borderColor: '#EC4899' },
  durChipText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  aspectChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: '#334155' },
  aspectChipActive: { backgroundColor: '#EC4899', borderColor: '#EC4899' },
  aspectChipText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#EC489940' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  progressTitle: { color: '#fff', fontSize: 13, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, backgroundColor: '#EC4899', borderRadius: 4 },
  progressPct: { color: '#EC4899', fontSize: 13, fontWeight: 'bold' },
  successBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#10B98110', padding: 14, borderRadius: 10, borderWidth: 1, borderColor: '#10B98140', marginBottom: 16 },
  successText: { flex: 1, color: '#10B981', fontSize: 15, fontWeight: '700' },
  viewBtn: { backgroundColor: '#10B981', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  viewBtnT: { color: '#fff', fontSize: 13, fontWeight: '700' },
  errBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444410', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#EF444440', marginBottom: 16 },
  errText: { flex: 1, color: '#EF4444', fontSize: 13 },
  genBtn: { backgroundColor: '#EC4899', borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 10 },
  genBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  genBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
});
