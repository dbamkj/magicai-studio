import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image, ActivityIndicator, Alert, Modal, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { uploadImageFile } from '../src/uploadHelper';
import ResolutionPicker from '../src/ResolutionPicker';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const GARMENT_TYPES = [
  { id: 'entire_outfit', label: 'Full Outfit' },
  { id: 'upper_body', label: 'Upper Body' },
  { id: 'lower_body', label: 'Lower Body' },
  { id: 'dresses', label: 'Dresses' },
];

const BODY_TIPS = [
  '📸 Upload ONE clear photo of the person (front-facing, full body ideal)',
  '👕 Then add ONE garment image per outfit you want to try',
  '✨ Works best with plain backgrounds and good lighting',
  '🎯 Match garment type (Full / Upper / Lower / Dress) for each swap',
];

const HEAD_TIPS = [
  '📸 Upload ONE body photo where the face/head will be replaced',
  '👤 Then add ONE clear head/face image per look you want',
  '✨ Similar lighting and angle on both photos gives best results',
  '🎭 Neutral expression on the head image works better than extreme poses',
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

interface BaseImage {
  id: string;
  uri: string | null;
  path: string | null;
  uploading: boolean;
  uploaded: boolean;
  label: string;
}

interface SwapItem {
  id: string;
  imageUri: string | null;
  imagePath: string | null;
  uploading: boolean;
  uploaded: boolean;
  label: string;
  garmentType: string;
  targetBaseId: string | null;
}

export default function MultiSwapScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prefill?: string; edit_of?: string }>();
  const [editingOf, setEditingOf] = useState<string | null>(null);
  const [swapType, setSwapType] = useState<'bodyswap' | 'headswap'>('bodyswap');
  // Multiple base images (each can have multiple swaps assigned)
  const [baseImages, setBaseImages] = useState<BaseImage[]>([]);
  // Multiple swap items
  const [swapItems, setSwapItems] = useState<SwapItem[]>([]);
  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultError, setResultError] = useState('');
  const [showReview, setShowReview] = useState(false);
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  const pollRef = useRef<any>(null);

  useEffect(() => {
    if (projectId && processing) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
          setProgress(r.data.progress || 0);
          if (r.data.status === 'completed' || r.data.status === 'failed') {
            clearInterval(pollRef.current); setProcessing(false);
            setResultStatus(r.data.status === 'completed' ? 'completed' : 'failed');
            if (r.data.status === 'failed') setResultError(r.data.error_message || 'Failed');
          }
        } catch (e) {}
      }, 4000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  // Sprint 1 — prefill from /projects → doEdit (lightweight: just type + res + banner)
  useEffect(() => {
    if (!params.prefill) return;
    try {
      const p = JSON.parse(String(params.prefill));
      if (params.edit_of) setEditingOf(String(params.edit_of));
      if (p.swap_type) setSwapType(p.swap_type);
      if (p.resolution) setResolution(p.resolution);
    } catch (e) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addBaseImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.8 });
    if (!r.canceled && r.assets[0]) {
      const id = Date.now().toString();
      const newBase: BaseImage = { id, uri: r.assets[0].uri, path: null, uploading: true, uploaded: false, label: `Image ${baseImages.length + 1}` };
      setBaseImages(prev => [...prev, newBase]);
      try {
        const data = await uploadImageFile(r.assets[0].uri, '/api/upload-face-image');
        setBaseImages(prev => prev.map(b => b.id === id ? { ...b, path: data.file_path, uploading: false, uploaded: true } : b));
      } catch (e) { Alert.alert('Upload Error'); setBaseImages(prev => prev.filter(b => b.id !== id)); }
    }
  };

  const removeBase = (id: string) => {
    setBaseImages(prev => prev.filter(b => b.id !== id));
    // Unassign any swap items that pointed to this base
    setSwapItems(prev => prev.map(s => s.targetBaseId === id ? { ...s, targetBaseId: null } : s));
  };

  // Reset all state (Clear & Reset)
  const resetAll = () => {
    Alert.alert('Clear & Reset', 'This will clear all base images and swap items. Continue?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear All', style: 'destructive', onPress: () => {
        setBaseImages([]); setSwapItems([]);
        setProjectId(null); setProcessing(false); setProgress(0); setResultStatus('none'); setResultError('');
        setShowReview(false);
      }},
    ]);
  };

  // Auto-generate swap image from a preset idea label (no upload prompt)
  const addIdeaSwap = async (presetLabel: string) => {
    // Auto-assign to first available base image if any
    const autoTarget = baseImages.find(b => b.uploaded)?.id || (baseImages[0]?.id || null);
    const id = Date.now().toString();
    const newItem: SwapItem = { id, imageUri: null, imagePath: null, uploading: true, uploaded: false, label: presetLabel, garmentType: 'entire_outfit', targetBaseId: autoTarget };
    setSwapItems(prev => [...prev, newItem]);
    try {
      const idea_type = swapType === 'bodyswap' ? 'outfit' : 'head';
      const ar = swapType === 'bodyswap' ? '9:16' : '1:1';
      const r = await axios.post(`${BACKEND_URL}/api/generate-idea-image`, { label: presetLabel, idea_type, aspect_ratio: ar }, { timeout: 180000 });
      const img_url = r.data.image_url;
      const file_path = r.data.file_path;
      if (!img_url || !file_path) throw new Error('Generation failed');
      const fullUri = img_url.startsWith('http') ? img_url : `${BACKEND_URL}${img_url}`;
      setSwapItems(prev => prev.map(s => s.id === id ? { ...s, imageUri: fullUri, imagePath: file_path, uploading: false, uploaded: true } : s));
    } catch (e: any) {
      setSwapItems(prev => prev.filter(s => s.id !== id));
      Alert.alert('Idea Generation Failed', e.response?.data?.detail || e.message || 'Failed to generate idea');
    }
  };

  const addSwapItem = async (presetLabel?: string) => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.8 });
    if (!r.canceled && r.assets[0]) {
      const id = Date.now().toString();
      const label = presetLabel || `Swap ${swapItems.length + 1}`;
      // Auto-assign to first available base image if any
      const autoTarget = baseImages.find(b => b.uploaded)?.id || (baseImages[0]?.id || null);
      const newItem: SwapItem = { id, imageUri: r.assets[0].uri, imagePath: null, uploading: true, uploaded: false, label, garmentType: 'entire_outfit', targetBaseId: autoTarget };
      setSwapItems(prev => [...prev, newItem]);
      try {
        const data = await uploadImageFile(r.assets[0].uri, '/api/upload-face-image');
        setSwapItems(prev => prev.map(s => s.id === id ? { ...s, imagePath: data.file_path, uploading: false, uploaded: true } : s));
      } catch (e) { Alert.alert('Upload Error'); setSwapItems(prev => prev.filter(s => s.id !== id)); }
    }
  };

  const removeItem = (id: string) => setSwapItems(prev => prev.filter(s => s.id !== id));

  const startMultiSwap = async () => {
    if (baseImages.filter(b => b.uploaded).length === 0) { Alert.alert('Upload at least one base image'); return; }
    const uploaded = swapItems.filter(s => s.uploaded && s.imagePath && s.targetBaseId);
    if (!uploaded.length) { Alert.alert('Add swap images', 'Add at least one garment/head image and assign it to a base image'); return; }
    try {
      setProcessing(true); setProgress(0); setResultStatus('none');
      const swaps = uploaded.map((s) => {
        const base = baseImages.find(b => b.id === s.targetBaseId);
        const basePath = base?.path;
        return swapType === 'bodyswap'
          ? { person_image_path: basePath, garment_image_path: s.imagePath, garment_type: s.garmentType, label: `${s.label} (${base?.label})` }
          : { head_image_path: s.imagePath, body_image_path: basePath, label: `${s.label} (${base?.label})` };
      });
      const r = await axios.post(`${BACKEND_URL}/api/create-multi-swap`, { swap_type: swapType, swaps, resolution, parent_id: editingOf || undefined });
      setProjectId(r.data.project_id);
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || 'Failed'); setProcessing(false); }
  };

  const readyBases = baseImages.filter(b => b.uploaded);
  const readySwaps = swapItems.filter(s => s.uploaded && s.targetBaseId);
  const canCreate = readyBases.length > 0 && readySwaps.length > 0 && !processing;

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <ScrollView contentContainerStyle={s.scroll}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
          <Text style={s.title}>Multi Swap</Text>
          <TouchableOpacity onPress={resetAll} style={s.backBtn} accessibilityLabel="Clear & Reset">
            <Ionicons name="refresh" size={22} color="#EF4444" />
          </TouchableOpacity>
        </View>
        {editingOf && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.4)', padding: 10, borderRadius: 10, marginBottom: 12 }}>
            <Ionicons name="git-branch" size={16} color="#A78BFA" />
            <Text style={{ color: '#A78BFA', fontSize: 13, flex: 1 }}>Editing previous version — re-add your base images and swaps to re-run.</Text>
          </View>
        )}

        {resultStatus === 'completed' && (
          <View style={s.successBanner}><Ionicons name="checkmark-circle" size={24} color="#10B981" /><View style={{ flex: 1 }}><Text style={s.successTitle}>All swaps complete!</Text></View>
            <TouchableOpacity style={s.viewBtn} onPress={() => router.push('/projects')}><Text style={s.viewBtnT}>View</Text></TouchableOpacity></View>
        )}
        {resultStatus === 'failed' && <View style={s.errBanner}><Ionicons name="close-circle" size={22} color="#EF4444" /><Text style={s.errText}>{resultError}</Text></View>}
        {processing && (
          <View style={s.progressCard}><View style={s.progressHeader}><ActivityIndicator size="small" color="#F97316" /><Text style={s.progressTitle}>Processing {swapItems.filter(s => s.uploaded).length} swaps...</Text></View>
            <View style={s.progressBarWrap}><View style={s.progressBarBg}><View style={[s.progressBarFill, { width: `${progress}%` }]} /></View><Text style={s.progressPct}>{progress}%</Text></View></View>
        )}

        {/* Swap Type */}
        <View style={s.section}>
          <Text style={s.sTitle}>1. Swap Type</Text>
          <View style={s.modeRow}>
            <TouchableOpacity style={[s.modeChip, swapType === 'bodyswap' && s.modeActive]} onPress={() => setSwapType('bodyswap')}>
              <Ionicons name="shirt" size={18} color={swapType === 'bodyswap' ? '#fff' : '#94A3B8'} /><Text style={[s.modeText, swapType === 'bodyswap' && { color: '#fff' }]}>Body/Outfit</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.modeChip, swapType === 'headswap' && s.modeActive]} onPress={() => setSwapType('headswap')}>
              <Ionicons name="person" size={18} color={swapType === 'headswap' ? '#fff' : '#94A3B8'} /><Text style={[s.modeText, swapType === 'headswap' && { color: '#fff' }]}>Head Swap</Text>
            </TouchableOpacity>
          </View>

          {/* Mode-specific tips */}
          <View style={s.tipsCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <Ionicons name="bulb" size={16} color="#F59E0B" />
              <Text style={s.tipsTitle}>{swapType === 'bodyswap' ? 'How Body/Outfit Swap works' : 'How Head Swap works'}</Text>
            </View>
            {(swapType === 'bodyswap' ? BODY_TIPS : HEAD_TIPS).map((t, i) => (
              <Text key={i} style={s.tipsLine}>{t}</Text>
            ))}
          </View>

          {/* Mode-specific idea suggestions */}
          <View style={{ marginTop: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <Ionicons name="sparkles" size={14} color="#8B5CF6" />
              <Text style={s.ideasTitle}>{swapType === 'bodyswap' ? 'Outfit ideas to try' : 'Face ideas to try'}</Text>
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {(swapType === 'bodyswap' ? BODY_IDEAS : HEAD_IDEAS).map((idea, i) => {
                const loading = swapItems.some(s => s.label === idea.label && s.uploading);
                return (
                  <TouchableOpacity
                    key={i}
                    style={[s.ideaChip, loading && { backgroundColor: '#8B5CF630', borderColor: '#8B5CF6' }]}
                    onPress={() => addIdeaSwap(idea.label)}
                    disabled={loading}
                  >
                    <Text style={{ fontSize: 20 }}>{idea.emoji}</Text>
                    <Text style={s.ideaLabel}>{idea.label}</Text>
                    {loading ? (
                      <ActivityIndicator size="small" color="#8B5CF6" style={{ marginTop: 2 }} />
                    ) : (
                      <Text style={s.ideaTap}>Tap to generate</Text>
                    )}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
            <Text style={s.ideaHint}>Tap any idea above to auto-generate an AI {swapType === 'bodyswap' ? 'outfit' : 'head/face'} image. Or manually upload your own via the "Add {swapType === 'bodyswap' ? 'Garment' : 'Head'} Image" button below.</Text>
          </View>
        </View>

        {/* Base Images (multiple allowed) */}
        <View style={s.section}>
          <Text style={s.sTitle}>2. {swapType === 'bodyswap' ? 'Person Photos' : 'Target Body Photos'} ({baseImages.length})</Text>
          <Text style={[s.ideaHint, { marginBottom: 8 }]}>Upload one or more photos. Each swap below can target a specific photo.</Text>
          {baseImages.map((b, idx) => (
            <View key={b.id} style={s.baseRow}>
              <Image source={{ uri: b.uri || '' }} style={s.baseThumb} />
              <View style={{ flex: 1 }}>
                <Text style={s.baseLabel}>{b.label}</Text>
                {b.uploading && <Text style={s.swapStatus}>Uploading...</Text>}
                {b.uploaded && <Text style={[s.swapStatus, { color: '#10B981' }]}>Ready</Text>}
              </View>
              <TouchableOpacity onPress={() => removeBase(b.id)}><Ionicons name="close-circle" size={22} color="#EF4444" /></TouchableOpacity>
            </View>
          ))}
          <TouchableOpacity style={s.addItemBtn} onPress={addBaseImage}>
            <Ionicons name="add-circle" size={22} color="#F97316" /><Text style={s.addItemText}>Add {swapType === 'bodyswap' ? 'Person' : 'Body'} Photo</Text>
          </TouchableOpacity>
        </View>

        {/* Swap Items */}
        <View style={s.section}>
          <Text style={s.sTitle}>3. {swapType === 'bodyswap' ? 'Garment / Outfit Images' : 'Head / Face Images'} ({swapItems.length})</Text>
          {baseImages.length === 0 && <Text style={s.ideaHint}>Add a base photo above first to assign swaps to it.</Text>}
          {swapItems.map((item, idx) => (
            <View key={item.id} style={s.swapRow}>
              <Image source={{ uri: item.imageUri || '' }} style={s.swapThumb} />
              <View style={{ flex: 1 }}>
                <Text style={s.swapLabel}>{item.label}</Text>
                {item.uploading && <Text style={s.swapStatus}>Uploading...</Text>}
                {item.uploaded && <Text style={[s.swapStatus, { color: '#10B981' }]}>Ready</Text>}
                {/* Base image selector */}
                {baseImages.length > 0 && (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
                    <Text style={{ color: '#94A3B8', fontSize: 10, marginRight: 6, alignSelf: 'center' }}>Apply to:</Text>
                    {baseImages.map(b => (
                      <TouchableOpacity key={b.id} style={[s.gtChip, item.targetBaseId === b.id && s.gtActive]} onPress={() => setSwapItems(prev => prev.map(sw => sw.id === item.id ? { ...sw, targetBaseId: b.id } : sw))}>
                        <Text style={[s.gtText, item.targetBaseId === b.id && { color: '#fff' }]}>{b.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                )}
                {swapType === 'bodyswap' && (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
                    {GARMENT_TYPES.map(g => (
                      <TouchableOpacity key={g.id} style={[s.gtChip, item.garmentType === g.id && s.gtActive]} onPress={() => setSwapItems(prev => prev.map(s => s.id === item.id ? { ...s, garmentType: g.id } : s))}>
                        <Text style={[s.gtText, item.garmentType === g.id && { color: '#fff' }]}>{g.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                )}
              </View>
              <TouchableOpacity onPress={() => removeItem(item.id)}><Ionicons name="close-circle" size={22} color="#EF4444" /></TouchableOpacity>
            </View>
          ))}
          <TouchableOpacity style={s.addItemBtn} onPress={() => addSwapItem()}>
            <Ionicons name="add-circle" size={22} color="#F97316" /><Text style={s.addItemText}>Add {swapType === 'bodyswap' ? 'Garment' : 'Head'} Image</Text>
          </TouchableOpacity>
        </View>

        <View style={{ marginBottom: 16 }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#E2E8F0', marginBottom: 8 }}>Resolution</Text>
          <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
        </View>

        <TouchableOpacity style={[s.createBtn, !canCreate && { backgroundColor: '#334155' }]} onPress={() => setShowReview(true)} disabled={!canCreate}>
          <View style={s.createBtnI}><Ionicons name="eye" size={22} color="#fff" /><Text style={s.createBtnT}>Review & Process All</Text></View>
        </TouchableOpacity>
      </ScrollView>

      {/* Review Modal */}
      <Modal visible={showReview} animationType="slide" transparent onRequestClose={() => setShowReview(false)}>
        <View style={s.reviewOverlay}><View style={s.reviewSheet}>
          <View style={s.reviewHandle} /><Text style={s.reviewTitle}>Review Multi Swap</Text>
          <ScrollView style={s.reviewBody}>
            <View style={s.reviewRow}><Text style={s.reviewLabel}>Type</Text><Text style={s.reviewValue}>{swapType === 'bodyswap' ? 'Body/Outfit Swap' : 'Head Swap'}</Text></View>
            <View style={s.reviewRow}><Text style={s.reviewLabel}>Base Images</Text><Text style={s.reviewValue}>{readyBases.length} photo{readyBases.length === 1 ? '' : 's'}</Text></View>
            <View style={s.reviewRow}><Text style={s.reviewLabel}>Swaps</Text><Text style={s.reviewValue}>{readySwaps.length} item{readySwaps.length === 1 ? '' : 's'}</Text></View>
          </ScrollView>
          <View style={s.reviewActions}>
            <TouchableOpacity style={s.reviewEditBtn} onPress={() => setShowReview(false)}><Text style={s.reviewEditBtnT}>Edit</Text></TouchableOpacity>
            <TouchableOpacity style={s.reviewConfirmBtn} onPress={() => { setShowReview(false); startMultiSwap(); }}><Text style={s.reviewConfirmBtnT}>Confirm & Start</Text></TouchableOpacity>
          </View>
        </View></View>
      </Modal>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 16, gap: 8 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }, title: { fontSize: 22, fontWeight: 'bold', color: '#fff', flex: 1 },
  newBadge: { backgroundColor: '#F97316', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 }, newBadgeT: { color: '#fff', fontSize: 10, fontWeight: '900' },
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
  modeRow: { flexDirection: 'row', gap: 10 },
  modeChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  modeActive: { backgroundColor: '#F97316', borderColor: '#F97316' }, modeText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  imgCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 10, borderWidth: 1, borderColor: '#334155' },
  imgPreview: { width: '100%', height: 180, borderRadius: 8 },
  imgOverlay: { position: 'absolute', top: 10, left: 10, right: 10, height: 180, borderRadius: 8, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center' },
  imgCheck: { position: 'absolute', top: 15, right: 15 },
  changeBtn: { marginTop: 8, padding: 10, backgroundColor: '#334155', borderRadius: 8, alignItems: 'center' }, changeBtnT: { color: '#E2E8F0', fontSize: 13, fontWeight: '600' },
  uploadBtn: { backgroundColor: '#1E293B', borderRadius: 12, padding: 20, alignItems: 'center', borderWidth: 1, borderColor: '#334155', borderStyle: 'dashed', gap: 8 },
  uploadText: { color: '#E2E8F0', fontSize: 14 },
  swapRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#1E293B', borderRadius: 10, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: '#334155' },
  swapThumb: { width: 56, height: 56, borderRadius: 8, backgroundColor: '#334155' },
  swapLabel: { color: '#E2E8F0', fontSize: 14, fontWeight: '600' }, swapStatus: { color: '#94A3B8', fontSize: 12 },
  gtChip: { backgroundColor: '#0F172A', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4, marginRight: 6, borderWidth: 1, borderColor: '#334155' },
  gtActive: { backgroundColor: '#F97316', borderColor: '#F97316' }, gtText: { color: '#94A3B8', fontSize: 10, fontWeight: '600' },
  // Tips + Ideas
  tipsCard: { marginTop: 10, backgroundColor: '#0F172A', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#F59E0B30' },
  tipsTitle: { color: '#F59E0B', fontSize: 12, fontWeight: '700' },
  tipsLine: { color: '#CBD5E1', fontSize: 12, lineHeight: 18, marginTop: 2 },
  ideasTitle: { color: '#C4B5FD', fontSize: 12, fontWeight: '700' },
  ideaChip: { backgroundColor: '#1E293B', borderRadius: 10, padding: 10, marginRight: 8, alignItems: 'center', minWidth: 84, borderWidth: 1, borderColor: '#334155' },
  ideaLabel: { color: '#E2E8F0', fontSize: 11, fontWeight: '600', marginTop: 4, textAlign: 'center' },
  ideaHint: { color: '#64748B', fontSize: 11, marginTop: 6, fontStyle: 'italic' },
  ideaTap: { color: '#8B5CF6', fontSize: 9, fontWeight: '700', marginTop: 2 },
  baseRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#1E293B', borderRadius: 10, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: '#F9731640' },
  baseThumb: { width: 60, height: 60, borderRadius: 8, backgroundColor: '#0F172A' },
  baseLabel: { color: '#F8FAFC', fontSize: 14, fontWeight: '600', marginBottom: 2 },
  addItemBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 14, backgroundColor: '#1E293B', borderRadius: 10, borderWidth: 1, borderColor: '#F9731640', borderStyle: 'dashed' },
  addItemText: { color: '#F97316', fontSize: 14, fontWeight: '600' },
  createBtn: { backgroundColor: '#F97316', borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 4 },
  createBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 }, createBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
  successBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#10B98110', borderRadius: 12, padding: 12, marginBottom: 14, borderWidth: 1, borderColor: '#10B98140', gap: 10 },
  successTitle: { color: '#10B981', fontSize: 15, fontWeight: '700' },
  viewBtn: { backgroundColor: '#10B981', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 6 }, viewBtnT: { color: '#fff', fontSize: 13, fontWeight: '700' },
  errBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444410', borderRadius: 10, padding: 12, marginBottom: 14 },
  errText: { color: '#EF4444', fontSize: 13, flex: 1 },
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#F9731640' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  progressTitle: { color: '#fff', fontSize: 13, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, borderRadius: 4, backgroundColor: '#F97316' }, progressPct: { fontSize: 13, fontWeight: 'bold', color: '#F97316', width: 36 },
  reviewOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  reviewSheet: { backgroundColor: '#1E293B', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '60%', paddingBottom: 30 },
  reviewHandle: { width: 40, height: 4, backgroundColor: '#475569', borderRadius: 2, alignSelf: 'center', marginTop: 12, marginBottom: 8 },
  reviewTitle: { fontSize: 18, fontWeight: 'bold', color: '#fff', textAlign: 'center', marginBottom: 12 },
  reviewBody: { paddingHorizontal: 20 },
  reviewRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#33415530' },
  reviewLabel: { color: '#94A3B8', fontSize: 13 }, reviewValue: { color: '#E2E8F0', fontSize: 13, fontWeight: '600' },
  reviewActions: { flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingTop: 16 },
  reviewEditBtn: { flex: 1, alignItems: 'center', backgroundColor: '#334155', borderRadius: 12, padding: 14 }, reviewEditBtnT: { color: '#F97316', fontSize: 15, fontWeight: '700' },
  reviewConfirmBtn: { flex: 2, alignItems: 'center', backgroundColor: '#F97316', borderRadius: 12, padding: 14 }, reviewConfirmBtnT: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
