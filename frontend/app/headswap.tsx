import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image, ActivityIndicator, Alert, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { uploadImageFile } from '../src/uploadHelper';
import ResolutionPicker from '../src/ResolutionPicker';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const MODES = [
  { id: 'headswap', label: 'Head Swap', desc: 'Replace head on body', icon: 'person' as const, color: '#F97316', hint: 'Upload a head/face and a target body. Best for: placing your face on another body photo.' },
  { id: 'bodyswap', label: 'Body/Outfit Swap', desc: 'Change outfit/body', icon: 'shirt' as const, color: '#06B6D4', hint: 'Upload a person photo and a garment/outfit image. The AI will dress the person in the new outfit.' },
];

const GARMENT_TYPES = [
  { id: 'entire_outfit', label: 'Full Outfit' },
  { id: 'upper_body', label: 'Upper Body' },
  { id: 'lower_body', label: 'Lower Body' },
  { id: 'dresses', label: 'Dresses' },
];

const BODY_IDEAS = [
  { emoji: '🕴️', label: 'Business Suit' },
  { emoji: '👰', label: 'Wedding Lehenga' },
  { emoji: '🥻', label: 'Silk Saree' },
  { emoji: '👔', label: 'Kurta Pajama' },
  { emoji: '🎽', label: 'Sports Jersey' },
  { emoji: '🦸', label: 'Superhero Suit' },
  { emoji: '👑', label: 'Royal Attire' },
  { emoji: '🏖️', label: 'Beach Wear' },
];

const HEAD_IDEAS = [
  { emoji: '🎬', label: 'Bollywood Hero' },
  { emoji: '👸', label: 'Movie Star' },
  { emoji: '🧙', label: 'Historical Figure' },
  { emoji: '👨‍👩‍👧', label: 'Family Face' },
  { emoji: '🎤', label: 'Music Star' },
  { emoji: '🏏', label: 'Cricket Hero' },
  { emoji: '🤴', label: 'Royal / King' },
  // Indian Gods & Goddesses
  { emoji: '🪈', label: 'Lord Krishna' },
  { emoji: '🕉️', label: 'Lord Shiva' },
  { emoji: '🐘', label: 'Lord Ganesha' },
  { emoji: '🏹', label: 'Lord Ram' },
  { emoji: '🐒', label: 'Lord Hanuman' },
  { emoji: '🗡️', label: 'Goddess Durga' },
  { emoji: '🪷', label: 'Goddess Lakshmi' },
  { emoji: '🎵', label: 'Goddess Saraswati' },
  { emoji: '⚔️', label: 'Goddess Kali' },
  { emoji: '💐', label: 'Goddess Parvati' },
  { emoji: '🐚', label: 'Lord Vishnu' },
  { emoji: '📿', label: 'Lord Brahma' },
];

const SWAP_TIPS = {
  headswap: [
    'Use front-facing photos for best results',
    'Similar lighting in both images works best',
    'Avoid images with hands covering the face',
  ],
  bodyswap: [
    'Full body shots work best for outfit changes',
    'Use garment images with plain backgrounds',
    'Front-facing poses give the best results',
  ],
};

export default function HeadSwapScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prefill?: string; edit_of?: string }>();
  const [editingOf, setEditingOf] = useState<string | null>(null);
  const [mode, setMode] = useState('headswap');
  const [image1, setImage1] = useState<string | null>(null);
  const [image1Path, setImage1Path] = useState<string | null>(null);
  const [image1Uploading, setImage1Uploading] = useState(false);
  const [image1Uploaded, setImage1Uploaded] = useState(false);
  const [image2, setImage2] = useState<string | null>(null);
  const [image2Path, setImage2Path] = useState<string | null>(null);
  const [image2Uploading, setImage2Uploading] = useState(false);
  const [image2Uploaded, setImage2Uploaded] = useState(false);
  const [garmentType, setGarmentType] = useState('entire_outfit');
  const [ideaGenerating, setIdeaGenerating] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultError, setResultError] = useState('');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  const pollRef = useRef<any>(null);

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
            } else {
              setResultStatus('failed');
              setResultError(r.data.error_message || 'Processing failed');
            }
          }
        } catch (e) {}
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  // Sprint 1 — prefill from /projects → doEdit
  useEffect(() => {
    if (!params.prefill) return;
    try {
      const p = JSON.parse(String(params.prefill));
      if (params.edit_of) setEditingOf(String(params.edit_of));
      if (p.resolution) setResolution(p.resolution);
      // Detect mode from endpoint-derived payload shape
      if (p.person_image_path || p.garment_image_path) {
        setMode('bodyswap');
        if (p.garment_type) setGarmentType(p.garment_type);
        if (p.person_image_path) {
          setImage1(`${BACKEND_URL}${p.person_image_path}`);
          setImage1Path(p.person_image_path);
          setImage1Uploaded(true);
        }
        if (p.garment_image_path) {
          setImage2(`${BACKEND_URL}${p.garment_image_path}`);
          setImage2Path(p.garment_image_path);
          setImage2Uploaded(true);
        }
      } else {
        setMode('headswap');
        if (p.head_image_path) {
          setImage1(`${BACKEND_URL}${p.head_image_path}`);
          setImage1Path(p.head_image_path);
          setImage1Uploaded(true);
        }
        if (p.body_image_path) {
          setImage2(`${BACKEND_URL}${p.body_image_path}`);
          setImage2Path(p.body_image_path);
          setImage2Uploaded(true);
        }
      }
    } catch (e) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reset all state (Clear & Reset)
  const resetAll = () => {
    Alert.alert('Clear & Reset', 'This will clear both images and any generated ideas. Continue?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear All', style: 'destructive', onPress: () => {
        setImage1(null); setImage1Path(null); setImage1Uploaded(false); setImage1Uploading(false);
        setImage2(null); setImage2Path(null); setImage2Uploaded(false); setImage2Uploading(false);
        setGarmentType('entire_outfit');
        setIdeaGenerating(null);
        setProjectId(null); setProcessing(false); setProgress(0); setResultStatus('none'); setResultError('');
      }},
    ]);
  };

  const dismissResult = () => { setResultStatus('none'); setResultError(''); };
  const viewProjects = () => { setResultStatus('none'); router.push('/projects'); };

  const pickImg = async (target: 1 | 2, fromCamera: boolean) => {
    const { status } = fromCamera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission needed'); return; }
    const r = fromCamera ? await ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.8 }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.8 });
    if (!r.canceled && r.assets[0]) {
      const uri = r.assets[0].uri;
      if (target === 1) { setImage1(uri); setImage1Uploaded(false); await uploadImg(uri, 1); }
      else { setImage2(uri); setImage2Uploaded(false); await uploadImg(uri, 2); }
    }
  };

  const uploadImg = async (uri: string, target: 1 | 2) => {
    const setUl = target === 1 ? setImage1Uploading : setImage2Uploading;
    const setUd = target === 1 ? setImage1Uploaded : setImage2Uploaded;
    const setP = target === 1 ? setImage1Path : setImage2Path;
    try {
      setUl(true);
      const data = await uploadImageFile(uri, '/api/upload-face-image');
      setP(data.file_path); setUd(true);
    } catch (e) {
      Alert.alert('Upload Error', 'Failed to upload image. Please try again.');
      if (target === 1) setImage1(null); else setImage2(null);
    } finally { setUl(false); }
  };

  // Generate outfit/head idea via AI → auto-fills image2 slot
  const generateIdea = async (label: string) => {
    try {
      setIdeaGenerating(label);
      const idea_type = mode === 'bodyswap' ? 'outfit' : 'head';
      const ar = mode === 'bodyswap' ? '9:16' : '1:1';
      const r = await axios.post(`${BACKEND_URL}/api/generate-idea-image`, { label, idea_type, aspect_ratio: ar }, { timeout: 180000 });
      const img_url = r.data.image_url;
      const file_path = r.data.file_path;
      if (!img_url || !file_path) throw new Error('Generation failed');
      // The served URL (relative) — render via full backend URL
      const fullUri = img_url.startsWith('http') ? img_url : `${BACKEND_URL}${img_url}`;
      setImage2(fullUri);
      setImage2Path(file_path);
      setImage2Uploaded(true);
      setImage2Uploading(false);
    } catch (e: any) {
      Alert.alert('Idea Generation Failed', e.response?.data?.detail || e.message || 'Failed to generate idea');
    } finally {
      setIdeaGenerating(null);
    }
  };

  const create = async () => {
    if (!image1Path || !image2Path) { Alert.alert('Upload both images'); return; }
    try {
      setProcessing(true); setProgress(0);
      let r;
      if (mode === 'headswap') {
        r = await axios.post(`${BACKEND_URL}/api/create-headswap`, { head_image_path: image1Path, body_image_path: image2Path, resolution, parent_id: editingOf || undefined });
      } else {
        r = await axios.post(`${BACKEND_URL}/api/create-bodyswap`, { person_image_path: image1Path, garment_image_path: image2Path, garment_type: garmentType, resolution, parent_id: editingOf || undefined });
      }
      setProjectId(r.data.project_id);
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || 'Failed'); setProcessing(false); }
  };

  const canCreate = image1Uploaded && image2Uploaded && !processing;
  const cur = MODES.find(m => m.id === mode)!;
  const label1 = mode === 'headswap' ? 'Head / Face Image' : 'Person Photo';
  const label2 = mode === 'headswap' ? 'Target Body Image' : 'Garment / Outfit Image';

  const ideas = mode === 'bodyswap' ? BODY_IDEAS : HEAD_IDEAS;

  const renderImgSection = (num: 1 | 2, label: string, image: string | null, uploading: boolean, uploaded: boolean) => (
    <View style={st.section}>
      <Text style={st.sTitle}>{num === 1 ? '2' : '3'}. {label}</Text>
      {image ? (
        <View style={st.preview}>
          <Image source={{ uri: image }} style={st.previewImg} />
          {uploading && <View style={st.overlay}><ActivityIndicator size="small" color={cur.color} /></View>}
          {uploaded && <View style={st.ok}><Ionicons name="checkmark-circle" size={18} color="#10B981" /><Text style={st.okT}>Ready</Text></View>}
          <TouchableOpacity style={st.changeBtn} onPress={() => pickImg(num, false)}><Text style={st.changeBtnT}>Change</Text></TouchableOpacity>
        </View>
      ) : (
        <View style={st.addRow}>
          <TouchableOpacity testID={`img${num}-gallery`} style={st.addBtn} onPress={() => pickImg(num, false)}><Ionicons name="images" size={22} color={cur.color} /><Text style={st.addBtnT}>Gallery</Text></TouchableOpacity>
          <TouchableOpacity testID={`img${num}-camera`} style={st.addBtn} onPress={() => pickImg(num, true)}><Ionicons name="camera" size={22} color={cur.color} /><Text style={st.addBtnT}>Camera</Text></TouchableOpacity>
        </View>
      )}
    </View>
  );

  return (
    <AuroraBackground>
    <SafeAreaView style={st.container}>
      <ScrollView contentContainerStyle={st.scroll}>
        <View style={st.header}>
          <TouchableOpacity testID="hs-back" onPress={() => router.back()} style={st.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
          <Text style={st.title}>{mode === 'headswap' ? 'Head Swap' : 'Body Swap'}</Text>
          <TouchableOpacity onPress={resetAll} style={st.backBtn} accessibilityLabel="Clear & Reset">
            <Ionicons name="refresh" size={22} color="#EF4444" />
          </TouchableOpacity>
        </View>

        {editingOf && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.4)', padding: 10, borderRadius: 10, marginBottom: 12 }}>
            <Ionicons name="git-branch" size={16} color="#A78BFA" />
            <Text style={{ color: '#A78BFA', fontSize: 13, flex: 1 }}>Editing previous version — images carried over. Replace to change.</Text>
          </View>
        )}

        {/* Mode Selector */}
        <View style={st.section}>
          <Text style={st.sTitle}>1. Choose Mode</Text>
          <View style={st.modeRow}>
            {MODES.map(m => (
              <TouchableOpacity key={m.id} testID={`mode-${m.id}`} style={[st.modeChip, mode === m.id && { backgroundColor: m.color, borderColor: m.color }]} onPress={() => setMode(m.id)}>
                <Ionicons name={m.icon as any} size={18} color={mode === m.id ? '#fff' : '#94A3B8'} />
                <Text style={[st.modeText, mode === m.id && { color: '#fff' }]}>{m.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={st.hint}>{cur.hint}</Text>
          <View style={{ marginTop: 6, gap: 4 }}>
            {SWAP_TIPS[mode as keyof typeof SWAP_TIPS]?.map((tip, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Ionicons name="bulb-outline" size={14} color="#F59E0B" />
                <Text style={{ color: '#94A3B8', fontSize: 12 }}>{tip}</Text>
              </View>
            ))}
          </View>
        </View>

        {processing && (
          <View style={[st.progressCard, { borderColor: `${cur.color}40` }]}>
            <View style={st.progressHeader}><ActivityIndicator size="small" color={cur.color} /><Text style={st.progressTitle}>Processing with MagiCAi...</Text></View>
            <View style={st.progressBarWrap}><View style={st.progressBarBg}><View style={[st.progressBarFill, { width: `${progress}%`, backgroundColor: cur.color }]} /></View><Text style={[st.progressPct, { color: cur.color }]}>{progress}%</Text></View>
          </View>
        )}

        {resultStatus === 'completed' && (
          <View style={st.resultBanner}>
            <Ionicons name="checkmark-circle" size={24} color="#10B981" />
            <View style={st.resultTextWrap}>
              <Text style={st.resultTitle}>Complete!</Text>
              <Text style={st.resultDesc}>Result is ready in My Projects</Text>
            </View>
            <View style={st.resultBtns}>
              <TouchableOpacity style={st.resultViewBtn} onPress={viewProjects}><Text style={st.resultViewBtnT}>View</Text></TouchableOpacity>
              <TouchableOpacity style={st.resultDismissBtn} onPress={dismissResult}><Ionicons name="close" size={20} color="#94A3B8" /></TouchableOpacity>
            </View>
          </View>
        )}

        {resultStatus === 'failed' && (
          <View style={[st.resultBanner, { borderColor: '#EF444440', backgroundColor: '#EF444410' }]}>
            <Ionicons name="close-circle" size={24} color="#EF4444" />
            <View style={st.resultTextWrap}>
              <Text style={[st.resultTitle, { color: '#EF4444' }]}>Failed</Text>
              <Text style={st.resultDesc} numberOfLines={2}>{resultError}</Text>
            </View>
            <TouchableOpacity style={st.resultDismissBtn} onPress={dismissResult}><Ionicons name="close" size={20} color="#94A3B8" /></TouchableOpacity>
          </View>
        )}

        {renderImgSection(1, label1, image1, image1Uploading, image1Uploaded)}

        {/* Idea generation panel — appears just above image 2 slot */}
        <View style={st.section}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Ionicons name="sparkles" size={16} color="#8B5CF6" />
            <Text style={st.ideasTitle}>{mode === 'bodyswap' ? 'AI Outfit Ideas' : 'AI Head/Face Ideas'}</Text>
          </View>
          <Text style={[st.hint, { marginTop: 0, marginBottom: 8 }]}>
            Tap any idea to auto-generate the {mode === 'bodyswap' ? 'outfit' : 'head/face'} image via AI. Or upload your own image below.
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {ideas.map((idea, i) => {
              const loading = ideaGenerating === idea.label;
              return (
                <TouchableOpacity
                  key={i}
                  style={[st.ideaChip, loading && { backgroundColor: '#8B5CF630', borderColor: '#8B5CF6' }]}
                  onPress={() => !ideaGenerating && generateIdea(idea.label)}
                  disabled={!!ideaGenerating}
                >
                  <Text style={{ fontSize: 22 }}>{idea.emoji}</Text>
                  <Text style={st.ideaLabel}>{idea.label}</Text>
                  {loading ? (
                    <ActivityIndicator size="small" color="#8B5CF6" style={{ marginTop: 2 }} />
                  ) : (
                    <Text style={st.ideaTap}>Tap to generate</Text>
                  )}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {renderImgSection(2, label2, image2, image2Uploading, image2Uploaded)}

        {/* Garment Type for body swap */}
        {mode === 'bodyswap' && (
          <View style={st.section}>
            <Text style={st.sTitle}>4. Garment Type</Text>
            <View style={st.garmentRow}>
              {GARMENT_TYPES.map(g => (
                <TouchableOpacity key={g.id} testID={`garment-${g.id}`} style={[st.garmentChip, garmentType === g.id && { backgroundColor: '#06B6D4', borderColor: '#06B6D4' }]} onPress={() => setGarmentType(g.id)}>
                  <Text style={[st.garmentText, garmentType === g.id && { color: '#fff' }]}>{g.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {/* Resolution */}
        <View style={{ marginBottom: 16 }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#E2E8F0', marginBottom: 8 }}>Resolution</Text>
          <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
        </View>

        <TouchableOpacity testID="create-btn" style={[st.cBtn, { backgroundColor: canCreate ? cur.color : '#334155' }]} onPress={create} disabled={!canCreate}>
          {processing ? (
            <View style={st.cBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={st.cBtnT}>Processing... {progress}%</Text></View>
          ) : (
            <View style={st.cBtnI}><Ionicons name={cur.icon as any} size={22} color="#fff" /><Text style={st.cBtnT}>Start {cur.label}</Text></View>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }, title: { fontSize: 24, fontWeight: 'bold', color: '#fff' },
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
  }, sTitle: { fontSize: 16, fontWeight: '600', color: '#E2E8F0', marginBottom: 8 },
  hint: { color: '#94A3B8', fontSize: 13, lineHeight: 19, marginTop: 8 },
  modeRow: { flexDirection: 'row', gap: 10 },
  modeChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  modeText: { color: '#94A3B8', fontSize: 14, fontWeight: '600' },
  // Ideas
  ideasTitle: { color: '#C4B5FD', fontSize: 13, fontWeight: '700' },
  ideaChip: { backgroundColor: '#1E293B', borderRadius: 10, padding: 10, marginRight: 8, alignItems: 'center', minWidth: 100, borderWidth: 1, borderColor: '#334155' },
  ideaLabel: { color: '#E2E8F0', fontSize: 11, fontWeight: '600', marginTop: 4, textAlign: 'center' },
  ideaTap: { color: '#8B5CF6', fontSize: 9, fontWeight: '700', marginTop: 2 },
  // Progress
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 16, marginBottom: 16, borderWidth: 1 },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  progressTitle: { color: '#fff', fontSize: 15, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, borderRadius: 4 },
  progressPct: { fontSize: 14, fontWeight: 'bold', width: 40 },
  // Image upload
  addRow: { flexDirection: 'row', gap: 10 },
  addBtn: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 20, alignItems: 'center', borderWidth: 1, borderColor: '#334155', borderStyle: 'dashed', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  addBtnT: { color: '#E2E8F0', fontSize: 14 },
  preview: { backgroundColor: '#1E293B', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#334155' },
  previewImg: { width: '100%', height: 200, borderRadius: 8, backgroundColor: '#334155' },
  overlay: { position: 'absolute', top: 12, left: 12, right: 12, height: 200, borderRadius: 8, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center' },
  ok: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 }, okT: { color: '#10B981', fontSize: 13, fontWeight: '600' },
  changeBtn: { marginTop: 10, padding: 10, backgroundColor: '#334155', borderRadius: 8, alignItems: 'center' }, changeBtnT: { color: '#E2E8F0', fontSize: 14, fontWeight: '600' },
  garmentRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  garmentChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: '#334155' },
  garmentText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  cBtn: { borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 6 },
  cBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 }, cBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
  // Result banner
  resultBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#10B98110', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#10B98140', gap: 10 },
  resultTextWrap: { flex: 1 },
  resultTitle: { color: '#10B981', fontSize: 16, fontWeight: '700' },
  resultDesc: { color: '#94A3B8', fontSize: 13, marginTop: 2 },
  resultBtns: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  resultViewBtn: { backgroundColor: '#10B981', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 8 },
  resultViewBtnT: { color: '#fff', fontSize: 14, fontWeight: '700' },
  resultDismissBtn: { padding: 4 },
});
