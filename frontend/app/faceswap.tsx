import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image, ActivityIndicator, Alert, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import { uploadImageFile, uploadVideoFile } from '../src/uploadHelper';
import ResolutionPicker from '../src/ResolutionPicker';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import AuthGateModal from '../src/components/AuthGateModal';
import { useAuth } from '../src/AuthContext';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const ASPECT_RATIOS = [
  { value: '16:9', label: '16:9', desc: 'Landscape' },
  { value: '9:16', label: '9:16', desc: 'Portrait' },
];

const SWAP_TIPS = [
  'Front-facing clear face photos work best',
  'Similar lighting conditions improve quality',
  'Higher resolution images produce better results',
];

interface FaceEntry { id: string; uri: string; filePath: string | null; uploading: boolean; uploaded: boolean; }

export default function FaceSwapScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const [showAuthGate, setShowAuthGate] = useState(false);
  const requireLogin = (): boolean => {
    if (!user) { setShowAuthGate(true); return false; }
    return true;
  };
  const params = useLocalSearchParams<{ prefill?: string; edit_of?: string }>();
  const [targetMode, setTargetMode] = useState<'video' | 'image'>('video');
  const [faces, setFaces] = useState<FaceEntry[]>([]);
  const [videoUri, setVideoUri] = useState<string | null>(null);
  const [videoPath, setVideoPath] = useState<string | null>(null);
  // Target image for image mode
  const [targetImgUri, setTargetImgUri] = useState<string | null>(null);
  const [targetImgPath, setTargetImgPath] = useState<string | null>(null);
  const [targetImgUploading, setTargetImgUploading] = useState(false);
  const [targetImgUploaded, setTargetImgUploaded] = useState(false);
  const [videoDuration, setVideoDuration] = useState(0);
  const [videoSizeMb, setVideoSizeMb] = useState(0);
  const [videoUploading, setVideoUploading] = useState(false);
  const [videoUploaded, setVideoUploaded] = useState(false);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  const [processing, setProcessing] = useState(false);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [trimEnabled, setTrimEnabled] = useState(false);
  // Inline progress
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [projectStatus, setProjectStatus] = useState('');
  const pollRef = useRef<any>(null);
  // Sprint 1 — edit-of banner
  const [editingOf, setEditingOf] = useState<string | null>(null);

  // Sprint 1: parse prefill payload (from /projects → doEdit)
  useEffect(() => {
    if (!params.prefill) return;
    try {
      const p = JSON.parse(String(params.prefill));
      if (params.edit_of) setEditingOf(String(params.edit_of));
      if (p.target_type) setTargetMode(p.target_type);
      if (p.aspect_ratio) setAspectRatio(p.aspect_ratio);
      if (p.resolution) setResolution(p.resolution);
      // Reuse the already-uploaded source image paths (no re-upload needed)
      if (Array.isArray(p.source_image_paths)) {
        const entries: FaceEntry[] = p.source_image_paths.map((fp: string, idx: number) => ({
          id: `prefill_${idx}`, uri: `${BACKEND_URL}${fp}`, filePath: fp, uploading: false, uploaded: true,
        }));
        setFaces(entries);
      }
      if (p.target_type === 'image') {
        if (p.target_video_path) { setTargetImgPath(p.target_video_path); setTargetImgUri(`${BACKEND_URL}${p.target_video_path}`); setTargetImgUploaded(true); }
      } else {
        if (p.target_video_path) { setVideoPath(p.target_video_path); setVideoUri(`${BACKEND_URL}${p.target_video_path}`); setVideoUploaded(true); }
        if (p.video_duration) setVideoDuration(p.video_duration);
        if (typeof p.trim_start === 'number' || typeof p.trim_end === 'number') {
          setTrimEnabled(true);
          if (typeof p.trim_start === 'number') setTrimStart(p.trim_start);
          if (typeof p.trim_end === 'number') setTrimEnd(p.trim_end);
        }
      }
    } catch (e) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll project status
  useEffect(() => {
    if (projectId && processing) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
          setProgress(r.data.progress || 0);
          setProjectStatus(r.data.status);
          if (r.data.status === 'completed' || r.data.status === 'failed') {
            clearInterval(pollRef.current);
            setProcessing(false);
            if (r.data.status === 'completed') {
              Alert.alert('Face Swap Complete!', 'Your video is ready in My Projects.', [
                { text: 'View Projects', onPress: () => router.push('/projects') },
                { text: 'OK' },
              ]);
            } else {
              Alert.alert('Face Swap Failed', r.data.error_message || 'Unknown error');
            }
          }
        } catch (e) { /* ignore */ }
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  const addFace = async (fromCamera: boolean) => {
    if (!requireLogin()) return;
    try {
      const { status } = fromCamera
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') { Alert.alert('Permission Required'); return; }
      const result = fromCamera
        ? await ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.8 })
        : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.8 });
      if (!result.canceled && result.assets[0]) {
        const f: FaceEntry = { id: Date.now().toString(), uri: result.assets[0].uri, filePath: null, uploading: true, uploaded: false };
        setFaces(prev => [...prev, f]);
        await uploadFace(f.id, result.assets[0].uri);
      }
    } catch (e) { Alert.alert('Error', 'Failed'); }
  };

  const uploadFace = async (faceId: string, uri: string) => {
    try {
      const data = await uploadImageFile(uri, '/api/upload-face-image');
      setFaces(prev => prev.map(f => f.id === faceId ? { ...f, filePath: data.file_path, uploading: false, uploaded: true } : f));
    } catch (e) { Alert.alert('Upload Error'); setFaces(prev => prev.filter(f => f.id !== faceId)); }
  };

  const pickVideo = async (fromCamera: boolean) => {
    if (!requireLogin()) return;
    try {
      const { status } = fromCamera
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') { Alert.alert('Permission Required'); return; }
      const result = fromCamera
        ? await ImagePicker.launchCameraAsync({ mediaTypes: ['videos'], videoMaxDuration: 300, quality: 0.8 })
        : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['videos'], quality: 0.8 });
      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        setVideoUri(asset.uri);
        setVideoUploaded(false);
        setTrimEnabled(false);
        setTrimStart(0);
        // Use duration from picker if available
        const pickerDuration = asset.duration ? asset.duration / 1000 : 0;
        setVideoDuration(pickerDuration);
        setTrimEnd(pickerDuration);
        await uploadVideo(asset.uri, pickerDuration);
      }
    } catch (e) { Alert.alert('Error', 'Failed to pick video'); }
  };

  const uploadVideo = async (uri: string, pickerDuration: number) => {
    try {
      setVideoUploading(true);
      const data = await uploadVideoFile(uri);
      setVideoPath(data.file_path);
      setVideoUploaded(true);
      setVideoSizeMb(data.size_mb || 0);
      const serverDur = data.duration || 0;
      const finalDur = serverDur > 0 ? serverDur : pickerDuration;
      if (finalDur > 0) {
        setVideoDuration(finalDur);
        setTrimEnd(finalDur);
      }
    } catch (e: any) {
      Alert.alert('Upload Error', e.response?.data?.detail || 'Failed to upload video');
      setVideoUri(null);
    } finally { setVideoUploading(false); }
  };

  const adjustTrim = (which: 'start' | 'end', delta: number) => {
    if (which === 'start') {
      setTrimStart(prev => Math.max(0, Math.min(prev + delta, trimEnd - 1)));
    } else {
      setTrimEnd(prev => Math.max(trimStart + 1, Math.min(prev + delta, videoDuration)));
    }
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const pickTargetImage = async (fromCamera: boolean) => {
    if (!requireLogin()) return;
    const { status } = fromCamera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission needed'); return; }
    const r = fromCamera ? await ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.8 }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.8 });
    if (!r.canceled && r.assets[0]) {
      setTargetImgUri(r.assets[0].uri); setTargetImgUploading(true);
      try {
        const data = await uploadImageFile(r.assets[0].uri, '/api/upload-face-image');
        setTargetImgPath(data.file_path); setTargetImgUploaded(true);
      } catch (e) { Alert.alert('Upload Error'); setTargetImgUri(null); }
      finally { setTargetImgUploading(false); }
    }
  };

  const createFaceSwap = async () => {
    if (!requireLogin()) return;
    const up = faces.filter(f => f.uploaded && f.filePath);
    if (!up.length) { Alert.alert('Missing Faces'); return; }
    if (targetMode === 'video' && !videoPath) { Alert.alert('Missing Video'); return; }
    if (targetMode === 'image' && !targetImgPath) { Alert.alert('Missing Target Image'); return; }
    try {
      setProcessing(true); setProgress(0); setProjectStatus('processing');
      const r = await axios.post(`${BACKEND_URL}/api/create-faceswap`, {
        source_image_paths: up.map(f => f.filePath),
        target_video_path: targetMode === 'video' ? videoPath : targetImgPath,
        target_type: targetMode,
        face_indices: up.map((_, i) => i),
        aspect_ratio: aspectRatio,
        resolution,
        trim_start: trimEnabled && targetMode === 'video' ? trimStart : null,
        trim_end: trimEnabled && targetMode === 'video' ? trimEnd : null,
        video_duration: targetMode === 'video' && videoDuration > 0 ? videoDuration : null,
        parent_id: editingOf || undefined,
      });
      setProjectId(r.data.project_id);
    } catch (e: any) {
      Alert.alert('Error', e.response?.data?.detail || 'Failed');
      setProcessing(false);
    }
  };

  const canCreate = faces.length > 0 && faces.every(f => f.uploaded) && (targetMode === 'video' ? (videoUploaded && videoPath) : (targetImgUploaded && targetImgPath)) && !processing;

  return (
    <AuroraBackground>
    <SafeAreaView style={st.container}>
      <ScrollView contentContainerStyle={st.scroll} keyboardShouldPersistTaps="handled">
        <GlassHeader
          icon="swap-horizontal"
          title="Face Swap"
          subtitle="Swap face onto a video or image"
          onBack={() => router.back()}
          right={
            <TouchableOpacity onPress={() => {
              Alert.alert('Clear & Reset', 'This will clear all uploaded faces, video/image, and any result. Continue?', [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Clear All', style: 'destructive', onPress: () => {
                  setFaces([]); setVideoUri(null); setVideoPath(null);
                  setTargetImgUri(null); setTargetImgPath(null); setTargetImgUploading(false); setTargetImgUploaded(false);
                  setVideoDuration(0); setVideoSizeMb(0); setVideoUploading(false); setVideoUploaded(false);
                  setTrimStart(0); setTrimEnd(0); setTrimEnabled(false);
                  setProjectId(null); setProcessing(false); setProgress(0);
                }},
              ]);
            }} style={{ width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="refresh" size={20} color="#EF4444" />

            </TouchableOpacity>
          }
          gradient={['#EC4899', '#A78BFA', '#F59E0B']}
          style={{ marginBottom: 12, paddingHorizontal: 0 }}
        />

        <View style={st.info}><Ionicons name="information-circle" size={20} color="#EC4899" /><Text style={st.infoText}>Upload face(s) to swap onto a target video or image.</Text></View>

        {editingOf && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.4)', padding: 10, borderRadius: 10, marginBottom: 12 }}>
            <Ionicons name="git-branch" size={16} color="#A78BFA" />
            <Text style={{ color: '#A78BFA', fontSize: 13, flex: 1 }}>Editing previous version — media carried over. Replace to change.</Text>
          </View>
        )}

        {/* Mode Toggle */}
        <View style={st.section}>
          <Text style={st.sectionTitle}>1. Target Type</Text>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <TouchableOpacity style={[st.modeChip, targetMode === 'video' && st.modeActive]} onPress={() => setTargetMode('video')}>
              <Ionicons name="videocam" size={18} color={targetMode === 'video' ? '#fff' : '#94A3B8'} />
              <Text style={[st.modeText, targetMode === 'video' && { color: '#fff' }]}>Video</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[st.modeChip, targetMode === 'image' && st.modeActive]} onPress={() => setTargetMode('image')}>
              <Ionicons name="image" size={18} color={targetMode === 'image' ? '#fff' : '#94A3B8'} />
              <Text style={[st.modeText, targetMode === 'image' && { color: '#fff' }]}>Image</Text>
            </TouchableOpacity>
          </View>
          <View style={{ marginTop: 8, gap: 4 }}>
            {SWAP_TIPS.map((tip, i) => (
              <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Ionicons name="bulb-outline" size={14} color="#F59E0B" />
                <Text style={{ color: '#94A3B8', fontSize: 12 }}>{tip}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Inline Progress */}
        {processing && (
          <View style={st.progressCard}>
            <View style={st.progressHeader}>
              <ActivityIndicator size="small" color="#EC4899" />
              <Text style={st.progressTitle}>Processing Face Swap...</Text>
            </View>
            <View style={st.progressBarWrap}>
              <View style={st.progressBarBg}><View style={[st.progressBarFill, { width: `${progress}%` }]} /></View>
              <Text style={st.progressPct}>{progress}%</Text>
            </View>
            <Text style={st.progressHint}>This may take a few minutes for longer videos</Text>
          </View>
        )}

        {/* Step 1: Faces */}
        <View style={st.section}>
          <Text style={st.sTitle}>1. Face Image(s)</Text>
          {faces.length > 0 && (
            <View style={st.grid}>
              {faces.map((f, i) => (
                <View key={f.id} style={st.fCard}>
                  <Image source={{ uri: f.uri }} style={st.fImg} />
                  {f.uploading && <View style={st.fOvl}><ActivityIndicator size="small" color="#EC4899" /></View>}
                  {f.uploaded && <View style={st.fChk}><Ionicons name="checkmark-circle" size={18} color="#10B981" /></View>}
                  <View style={st.fLbl}><Text style={st.fLblT}>Face {i + 1}</Text></View>
                  <TouchableOpacity testID={`rm-face-${i}`} style={st.fRm} onPress={() => setFaces(prev => prev.filter(x => x.id !== f.id))}><Ionicons name="close-circle" size={20} color="#EF4444" /></TouchableOpacity>
                </View>
              ))}
            </View>
          )}
          <View style={st.addRow}>
            <TouchableOpacity testID="fs-add-gallery" style={st.addBtn} onPress={() => addFace(false)}><Ionicons name="images" size={22} color="#EC4899" /><Text style={st.addBtnT}>Gallery</Text></TouchableOpacity>
            <TouchableOpacity testID="fs-add-camera" style={st.addBtn} onPress={() => addFace(true)}><Ionicons name="camera" size={22} color="#EC4899" /><Text style={st.addBtnT}>Camera</Text></TouchableOpacity>
          </View>
        </View>

        {/* Step 2: Target (Video or Image based on mode) */}
        {targetMode === 'video' ? (
        <View style={st.section}>
          <Text style={st.sTitle}>2. Reference Video</Text>
          {videoUri ? (
            <View style={st.vPrev}>
              <View style={st.vThumb}>
                <Ionicons name="videocam" size={36} color="#EC4899" />
                <Text style={st.vThumbT}>
                  {videoUploaded
                    ? `Video Ready${videoDuration > 0 ? ` (${formatTime(videoDuration)})` : ''}${videoSizeMb > 0 ? ` · ${videoSizeMb}MB` : ''}`
                    : 'Uploading...'}
                </Text>
              </View>
              {videoUploading && <View style={st.vProg}><ActivityIndicator size="small" color="#EC4899" /><Text style={st.vProgT}>Uploading...</Text></View>}
              {videoUploaded && <View style={st.ok}><Ionicons name="checkmark-circle" size={18} color="#10B981" /><Text style={st.okT}>Uploaded</Text></View>}
              <TouchableOpacity style={st.changeBtn} onPress={() => pickVideo(false)}><Text style={st.changeBtnT}>Change Video</Text></TouchableOpacity>
            </View>
          ) : (
            <View style={st.addRow}>
              <TouchableOpacity testID="fs-vid-gallery" style={st.vidBtn} onPress={() => pickVideo(false)}><Ionicons name="folder-open" size={30} color="#EC4899" /><Text style={st.vidBtnT}>Gallery</Text></TouchableOpacity>
              <TouchableOpacity testID="fs-vid-record" style={st.vidBtn} onPress={() => pickVideo(true)}><Ionicons name="videocam" size={30} color="#EC4899" /><Text style={st.vidBtnT}>Record</Text></TouchableOpacity>
            </View>
          )}
        </View>
        ) : (
        <View style={st.section}>
          <Text style={st.sTitle}>2. Target Image</Text>
          {targetImgUri ? (
            <View style={st.vPrev}>
              <Image source={{ uri: targetImgUri }} style={{ width: '100%', height: 180, borderRadius: 8 }} />
              {targetImgUploading && <View style={st.vProg}><ActivityIndicator size="small" color="#EC4899" /><Text style={st.vProgT}>Uploading...</Text></View>}
              {targetImgUploaded && <View style={st.ok}><Ionicons name="checkmark-circle" size={18} color="#10B981" /><Text style={st.okT}>Uploaded</Text></View>}
              <TouchableOpacity style={st.changeBtn} onPress={() => pickTargetImage(false)}><Text style={st.changeBtnT}>Change Image</Text></TouchableOpacity>
            </View>
          ) : (
            <View style={st.addRow}>
              <TouchableOpacity style={st.vidBtn} onPress={() => pickTargetImage(false)}><Ionicons name="images" size={30} color="#EC4899" /><Text style={st.vidBtnT}>Gallery</Text></TouchableOpacity>
              <TouchableOpacity style={st.vidBtn} onPress={() => pickTargetImage(true)}><Ionicons name="camera" size={30} color="#EC4899" /><Text style={st.vidBtnT}>Camera</Text></TouchableOpacity>
            </View>
          )}
        </View>
        )}

        {/* Step 3: Trim (always show when video uploaded) */}
        {videoUploaded && (
          <View style={st.section}>
            <View style={st.trimHeader}>
              <Text style={st.sTitle}>3. Trim Video</Text>
              <TouchableOpacity testID="toggle-trim" style={[st.trimToggle, trimEnabled && st.trimToggleOn]} onPress={() => setTrimEnabled(!trimEnabled)}>
                <Text style={[st.trimToggleT, trimEnabled && { color: '#fff' }]}>{trimEnabled ? 'ON' : 'OFF'}</Text>
              </TouchableOpacity>
            </View>
            {!trimEnabled && (
              <Text style={st.trimOffHint}>Full video will be processed ({videoDuration > 0 ? formatTime(videoDuration) : 'unknown length'})</Text>
            )}
            {trimEnabled && (
              <View style={st.trimControls}>
                <View style={st.trimRow}>
                  <Text style={st.trimLabel}>Start: {formatTime(trimStart)}</Text>
                  <View style={st.trimBtns}>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('start', -5)}><Ionicons name="remove" size={18} color="#fff" /></TouchableOpacity>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('start', -1)}><Text style={st.trimBT}>-1s</Text></TouchableOpacity>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('start', 1)}><Text style={st.trimBT}>+1s</Text></TouchableOpacity>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('start', 5)}><Ionicons name="add" size={18} color="#fff" /></TouchableOpacity>
                  </View>
                </View>
                <View style={st.trimRow}>
                  <Text style={st.trimLabel}>End: {formatTime(trimEnd)}</Text>
                  <View style={st.trimBtns}>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('end', -5)}><Ionicons name="remove" size={18} color="#fff" /></TouchableOpacity>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('end', -1)}><Text style={st.trimBT}>-1s</Text></TouchableOpacity>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('end', 1)}><Text style={st.trimBT}>+1s</Text></TouchableOpacity>
                    <TouchableOpacity style={st.trimB} onPress={() => adjustTrim('end', 5)}><Ionicons name="add" size={18} color="#fff" /></TouchableOpacity>
                  </View>
                </View>
                {videoDuration > 0 && (
                  <View style={st.trimBarWrap}>
                    <View style={st.trimBar}><View style={[st.trimFill, { left: `${(trimStart / videoDuration) * 100}%`, right: `${100 - (trimEnd / videoDuration) * 100}%` }]} /></View>
                    <Text style={st.trimDur}>Selected: {formatTime(trimEnd - trimStart)}</Text>
                  </View>
                )}
              </View>
            )}
          </View>
        )}

        {/* Step 4: Ratio */}
        <View style={st.section}>
          <Text style={st.sTitle}>{videoUploaded ? '4' : '3'}. Aspect Ratio</Text>
          <View style={st.ratioRow}>
            {ASPECT_RATIOS.map(ar => (
              <TouchableOpacity key={ar.value} style={[st.ratioC, aspectRatio === ar.value && st.ratioCa]} onPress={() => setAspectRatio(ar.value)}>
                <Text style={[st.ratioL, aspectRatio === ar.value && { color: '#fff' }]}>{ar.label}</Text>
                <Text style={[st.ratioD, aspectRatio === ar.value && { color: '#E2E8F0' }]}>{ar.desc}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Resolution */}
        <View style={st.section}>
          <Text style={st.sTitle}>Resolution</Text>
          <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
        </View>

        <TouchableOpacity testID="create-faceswap-btn" style={[st.cBtn, !canCreate && st.cBtnD]} onPress={createFaceSwap} disabled={!canCreate}>
          {processing ? (
            <View style={st.cBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={st.cBtnT}>Processing... {progress}%</Text></View>
          ) : (
            <View style={st.cBtnI}><Ionicons name="swap-horizontal" size={22} color="#fff" /><Text style={st.cBtnT}>Start Face Swap ({faces.filter(f => f.uploaded).length} face{faces.filter(f => f.uploaded).length !== 1 ? 's' : ''})</Text></View>
          )}
        </TouchableOpacity>
      </ScrollView>
      <AuthGateModal
        visible={showAuthGate}
        onClose={() => setShowAuthGate(false)}
        reason="Face Swap"
        nextRoute="/faceswap"
      />
    </SafeAreaView>
    </AuroraBackground>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }, title: { fontSize: 24, fontWeight: 'bold', color: '#fff' },
  info: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#EC489915', borderRadius: 12, padding: 14, marginBottom: 20, gap: 8, borderWidth: 1, borderColor: '#EC489930' },
  infoText: { color: '#F1F5F9', fontSize: 13, flex: 1, lineHeight: 19 },
  // Progress
  progressCard: { backgroundColor: '#EC489920', borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: '#EC489940' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  progressTitle: { color: '#fff', fontSize: 16, fontWeight: '600' },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, backgroundColor: '#EC4899', borderRadius: 4 },
  progressPct: { color: '#EC4899', fontSize: 14, fontWeight: 'bold', width: 40 },
  progressHint: { color: '#94A3B8', fontSize: 12, marginTop: 8 },
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
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 10 },
  fCard: { width: 90, height: 110, borderRadius: 10, overflow: 'hidden', backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155' },
  fImg: { width: '100%', height: 72, backgroundColor: '#334155' },
  fOvl: { position: 'absolute', top: 0, left: 0, right: 0, height: 72, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center' },
  fChk: { position: 'absolute', top: 3, right: 3 }, fLbl: { paddingHorizontal: 6, paddingVertical: 3 }, fLblT: { color: '#E2E8F0', fontSize: 12, fontWeight: '600' },
  fRm: { position: 'absolute', top: -2, left: -2 },
  addRow: { flexDirection: 'row', gap: 10 },
  addBtn: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 16, alignItems: 'center', borderWidth: 1, borderColor: '#334155', borderStyle: 'dashed', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  addBtnT: { color: '#E2E8F0', fontSize: 14 },
  vidBtn: { flex: 1, backgroundColor: '#1E293B', borderRadius: 12, padding: 24, alignItems: 'center', borderWidth: 1, borderColor: '#334155' }, vidBtnT: { color: '#E2E8F0', marginTop: 8, fontSize: 15 },
  vPrev: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#334155' },
  vThumb: { alignItems: 'center', paddingVertical: 16, backgroundColor: '#0F172A', borderRadius: 8 }, vThumbT: { color: '#E2E8F0', marginTop: 6, fontSize: 14, fontWeight: '600' },
  vProg: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }, vProgT: { color: '#94A3B8', fontSize: 13 },
  ok: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 }, okT: { color: '#10B981', fontSize: 13, fontWeight: '600' },
  changeBtn: { marginTop: 10, padding: 10, backgroundColor: '#334155', borderRadius: 8, alignItems: 'center' }, changeBtnT: { color: '#E2E8F0', fontSize: 14, fontWeight: '600' },
  trimHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  trimToggle: { backgroundColor: '#334155', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 6 }, trimToggleOn: { backgroundColor: '#10B981' },
  trimToggleT: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  trimOffHint: { color: '#64748B', fontSize: 13, marginBottom: 4 },
  trimControls: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#334155' },
  trimRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  trimLabel: { color: '#E2E8F0', fontSize: 14, fontWeight: '600', width: 90 },
  trimBtns: { flexDirection: 'row', gap: 6 },
  trimB: { backgroundColor: '#334155', borderRadius: 6, width: 40, height: 32, alignItems: 'center', justifyContent: 'center' },
  trimBT: { color: '#E2E8F0', fontSize: 12, fontWeight: '600' },
  trimBarWrap: { marginTop: 4 },
  trimBar: { height: 8, backgroundColor: '#334155', borderRadius: 4, position: 'relative', overflow: 'hidden' },
  trimFill: { position: 'absolute', top: 0, bottom: 0, backgroundColor: '#EC4899', borderRadius: 4 },
  trimDur: { color: '#94A3B8', fontSize: 12, marginTop: 6, textAlign: 'center' },
  ratioRow: { flexDirection: 'row', gap: 12 },
  ratioC: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  ratioCa: { backgroundColor: '#EC4899', borderColor: '#EC4899' },
  ratioL: { color: '#E2E8F0', fontSize: 18, fontWeight: 'bold' }, ratioD: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  cBtn: { backgroundColor: '#EC4899', borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 6 }, cBtnD: { backgroundColor: '#334155' },
  cBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 }, cBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
  // Mode toggle
  modeChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  modeActive: { backgroundColor: '#EC4899', borderColor: '#EC4899' },
  modeText: { color: '#94A3B8', fontSize: 14, fontWeight: '600' },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#E2E8F0', marginBottom: 8 },
});
