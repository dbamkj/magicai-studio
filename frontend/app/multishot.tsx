import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput, ActivityIndicator, Alert,
  KeyboardAvoidingView, Platform, Image, LayoutAnimation, UIManager,
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
import { uploadImageFile } from '../src/uploadHelper';
import QualityPicker from '../src/QualityPicker';
import ResolutionPicker from '../src/ResolutionPicker';
import PauseChips from '../src/PauseChips';
import { useMhCapabilities } from '../src/useMhCapabilities';
import VoiceStylePicker from '../src/VoiceStylePicker';
import MotionPicker from '../src/MotionPicker';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const MAX_SHOTS = 6;
// MH min-billed 5s → only expose values ≥5s.
const DURATIONS = [5, 10, 15];

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

type Shot = {
  id: string;
  prompt: string;
  duration: number;
  start_image_uri?: string | null;
  start_image_path?: string | null;
  image_uploading?: boolean;
  dialogue?: string;
  dialogue_audio_uri?: string | null;
  dialogue_audio_path?: string | null;
  dialogue_uploading?: boolean;
  voice_id?: string;
  sound_effect?: string;
  quality_mode?: 'quick' | 'studio';
  transition_out?: 'cut' | 'fade' | 'crossfade';
  motion?: string | null;  // Sprint 3 Phase A: ffmpeg motion preset (bypasses MH when set + start_image)
  expanded?: boolean;
};

const newShot = (expanded = true): Shot => ({
  id: `shot_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
  prompt: '',
  duration: 5,
  voice_id: 'hi-IN-SwaraNeural',
  sound_effect: 'none',
  quality_mode: 'studio',
  transition_out: 'cut',
  expanded,
});

export default function MultiShotScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prefill?: string; edit_of?: string }>();
  const [editingOf, setEditingOf] = useState<string | null>(null);
  const [shots, setShots] = useState<Shot[]>([newShot(true)]);
  // MH image_to_video capability — shots default to image-to-video under the hood.
  const mhCap = useMhCapabilities('image_to_video');
  const [aspectRatio, setAspectRatio] = useState<'9:16' | '16:9' | '1:1'>('9:16');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  const [voiceStyle, setVoiceStyle] = useState<string | null>(null); // Sprint 2 — timeline-wide
  const [voiceRate, setVoiceRate] = useState<string | null>(null); // Sprint 2 Phase B
  const [voicePitch, setVoicePitch] = useState<string | null>(null); // Sprint 2 Phase B
  const [sfxList, setSfxList] = useState<any[]>([{ id: 'none', name: 'None', icon: 'volume-mute' }]);

  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultError, setResultError] = useState('');
  const pollRef = useRef<any>(null);

  // --- recording state (shared per active shot) ---
  const [recordingShotId, setRecordingShotId] = useState<string | null>(null);
  const [recordDuration, setRecordDuration] = useState(0);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const recordTimerRef = useRef<any>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/sound-effects`);
        if (r.data?.effects) setSfxList(r.data.effects);
      } catch (e) {}
    })();
  }, []);

  // Sprint 1 — prefill from /projects → doEdit (replaces default shots)
  useEffect(() => {
    if (!params.prefill) return;
    try {
      const p = JSON.parse(String(params.prefill));
      if (params.edit_of) setEditingOf(String(params.edit_of));
      if (p.aspect_ratio) setAspectRatio(p.aspect_ratio);
      if (p.resolution) setResolution(p.resolution);
      if (p.voice_style) setVoiceStyle(p.voice_style);
      if (Array.isArray(p.shots) && p.shots.length > 0) {
        const prefilled: Shot[] = p.shots.map((s: any, idx: number) => ({
          id: `prefill_shot_${idx}_${Date.now()}`,
          prompt: s.prompt || '',
          duration: s.duration || 5,
          start_image_path: s.start_image_path || null,
          start_image_uri: s.start_image_path ? `${BACKEND_URL}${s.start_image_path}` : null,
          dialogue: s.dialogue || '',
          dialogue_audio_path: s.dialogue_audio_path || null,
          voice_id: s.voice_id || 'hi-IN-SwaraNeural',
          sound_effect: s.sound_effect || 'none',
          quality_mode: s.quality_mode || 'studio',
          transition_out: s.transition_out || 'cut',
          motion: s.motion || null,
          expanded: idx === 0,
        }));
        setShots(prefilled);
      }
    } catch (e) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (projectId && processing) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
          setProgress(r.data.progress || 0);
          if (r.data.status === 'completed') {
            clearInterval(pollRef.current); setProcessing(false);
            setResultStatus('completed'); setResultUrl(r.data.result_url);
          } else if (r.data.status === 'failed') {
            clearInterval(pollRef.current); setProcessing(false);
            setResultStatus('failed'); setResultError(r.data.error_message || 'Failed');
          }
        } catch (e) {}
      }, 4000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  const updateShot = (id: string, patch: Partial<Shot>) => {
    setShots(ss => ss.map(s => (s.id === id ? { ...s, ...patch } : s)));
  };

  const toggleExpand = (id: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setShots(ss => ss.map(s => (s.id === id ? { ...s, expanded: !s.expanded } : s)));
  };

  const addShot = () => {
    if (shots.length >= MAX_SHOTS) {
      Alert.alert('Max shots', `Maximum ${MAX_SHOTS} shots per timeline.`);
      return;
    }
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setShots(ss => [...ss.map(s => ({ ...s, expanded: false })), newShot(true)]);
  };

  const removeShot = (id: string) => {
    if (shots.length <= 1) { Alert.alert('At least 1 shot required'); return; }
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setShots(ss => ss.filter(s => s.id !== id));
  };

  const pickStartImage = async (shotId: string) => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission needed'); return; }
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (r.canceled || !r.assets?.[0]) return;
    const uri = r.assets[0].uri;
    updateShot(shotId, { start_image_uri: uri, image_uploading: true });
    try {
      const data = await uploadImageFile(uri, '/api/upload-face-image');
      updateShot(shotId, { start_image_path: data.file_path, image_uploading: false });
    } catch (e) {
      Alert.alert('Upload failed'); updateShot(shotId, { start_image_uri: null, image_uploading: false });
    }
  };

  const clearStartImage = (shotId: string) => {
    updateShot(shotId, { start_image_uri: null, start_image_path: null });
  };

  const pickDialogueAudio = async (shotId: string) => {
    const r = await DocumentPicker.getDocumentAsync({ type: 'audio/*', copyToCacheDirectory: true });
    if (r.canceled || !r.assets?.[0]) return;
    const a = r.assets[0];
    updateShot(shotId, { dialogue_audio_uri: a.uri, dialogue_uploading: true });
    try {
      const fd = new FormData();
      if (Platform.OS === 'web') {
        const resp = await fetch(a.uri); const blob = await resp.blob();
        fd.append('file', new File([blob], a.name || 'audio.mp3', { type: blob.type || 'audio/mpeg' }));
      } else {
        fd.append('file', { uri: a.uri, name: a.name || 'audio.mp3', type: a.mimeType || 'audio/mpeg' } as any);
      }
      const up = await axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
      updateShot(shotId, { dialogue_audio_path: up.data.file_path, dialogue_uploading: false });
    } catch (e) {
      Alert.alert('Upload failed'); updateShot(shotId, { dialogue_audio_uri: null, dialogue_uploading: false });
    }
  };

  const startRecordingForShot = async (shotId: string) => {
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (perm.status !== 'granted') { Alert.alert('Microphone permission required'); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const rec = new Audio.Recording();
      await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await rec.startAsync();
      recordingRef.current = rec;
      setRecordingShotId(shotId); setRecordDuration(0);
      recordTimerRef.current = setInterval(() => setRecordDuration(d => d + 1), 1000);
    } catch (e: any) { Alert.alert('Recording error', e?.message || ''); setRecordingShotId(null); }
  };

  const stopRecordingForShot = async () => {
    try {
      if (recordTimerRef.current) { clearInterval(recordTimerRef.current); recordTimerRef.current = null; }
      const rec = recordingRef.current;
      const shotId = recordingShotId;
      if (!rec || !shotId) { setRecordingShotId(null); return; }
      await rec.stopAndUnloadAsync();
      const uri = rec.getURI(); recordingRef.current = null;
      const dur = recordDuration;
      setRecordingShotId(null); setRecordDuration(0);
      if (!uri || dur < 1) { Alert.alert('Too short', 'Please record at least 1 second.'); return; }
      updateShot(shotId, { dialogue_audio_uri: uri, dialogue_uploading: true });
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
        updateShot(shotId, { dialogue_audio_path: up.data.file_path, dialogue_uploading: false });
      } catch (e) { Alert.alert('Upload failed'); updateShot(shotId, { dialogue_audio_uri: null, dialogue_uploading: false }); }
    } catch (e) { setRecordingShotId(null); }
  };

  const clearDialogueAudio = (shotId: string) => {
    updateShot(shotId, { dialogue_audio_uri: null, dialogue_audio_path: null });
  };

  const totalDuration = shots.reduce((acc, s) => acc + (s.duration || 5), 0);
  const canGenerate = !processing && shots.every(s => s.prompt.trim().length > 0);

  const generate = async () => {
    if (!canGenerate) { Alert.alert('All shots need a prompt'); return; }
    try {
      setProcessing(true); setProgress(0); setResultStatus('none'); setResultUrl(null); setResultError('');
      const payloadShots = shots.map((s, idx) => ({
        prompt: s.prompt.trim(),
        duration: s.duration,
        start_image_path: s.start_image_path || undefined,
        dialogue: s.dialogue?.trim() || undefined,
        dialogue_audio_path: s.dialogue_audio_path || undefined,
        voice_id: s.voice_id,
        sound_effect: s.sound_effect !== 'none' ? s.sound_effect : undefined,
        quality_mode: s.quality_mode,
        // transition only matters for non-last shots; defaults to 'cut'
        transition_out: idx < shots.length - 1 ? (s.transition_out || 'cut') : 'cut',
        motion: s.motion || undefined,  // Sprint 3: ffmpeg motion preset — bypasses MH when set + start_image
      }));
      const r = await axios.post(`${BACKEND_URL}/api/create-multishot`, {
        shots: payloadShots, aspect_ratio: aspectRatio, resolution,
        voice_style: voiceStyle || undefined,
        voice_rate: voiceRate || undefined,
        voice_pitch: voicePitch || undefined,
        parent_id: editingOf || undefined,
      });
      setProjectId(r.data.project_id);
    } catch (e: any) {
      setProcessing(false);
      Alert.alert('Error', e.response?.data?.detail || 'Failed');
    }
  };

  const resetAll = () => {
    Alert.alert('Clear timeline?', 'This will remove all shots.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear', style: 'destructive', onPress: () => {
        setShots([newShot(true)]); setAspectRatio('9:16'); setResolution('720p');
        setProjectId(null); setProcessing(false); setProgress(0); setResultStatus('none'); setResultUrl(null); setResultError('');
      }},
    ]);
  };

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          {/* Header */}
          <View style={s.header}>
            <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
            <Text style={s.title}>Multi-shot Studio</Text>
            <TouchableOpacity onPress={resetAll} style={s.backBtn}><Ionicons name="refresh" size={22} color="#EF4444" /></TouchableOpacity>
          </View>

          <Text style={s.subtitle}>Stitch up to {MAX_SHOTS} AI-generated shots into a seamless story. Each shot gets its own prompt, audio & SFX.</Text>

          {editingOf && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.4)', padding: 10, borderRadius: 10, marginBottom: 12 }}>
              <Ionicons name="git-branch" size={16} color="#A78BFA" />
              <Text style={{ color: '#A78BFA', fontSize: 13, flex: 1 }}>Editing previous version — all shots carried over. Tweak and re-run.</Text>
            </View>
          )}

          {/* Sprint 2 — Timeline-wide Voice Style (applied to all shots without their own preset) */}
          <View style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)', marginBottom: 12 }}>
            <VoiceStylePicker
              selectedId={voiceStyle}
              onSelect={setVoiceStyle}
              label="Timeline Voice Style"
              customRate={voiceRate}
              customPitch={voicePitch}
              onCustomRate={setVoiceRate}
              onCustomPitch={setVoicePitch}
            />
            <PauseChips
              label="Tap to append pause to the last shot's dialogue"
              onInsert={(tag) => setShots(ss => {
                if (ss.length === 0) return ss;
                const last = ss[ss.length - 1];
                const sep = last.dialogue && !last.dialogue.endsWith(' ') ? ' ' : '';
                return ss.map((s, i) => i === ss.length - 1 ? { ...s, dialogue: (s.dialogue || '') + sep + tag } : s);
              })}
            />
          </View>

          {/* Progress card */}
          {processing && (
            <View style={s.progCard}>
              <Ionicons name="hourglass" size={18} color="#F97316" />
              <View style={{ flex: 1 }}>
                <Text style={s.progLabel}>Generating {shots.length} shot{shots.length > 1 ? 's' : ''}… {progress}%</Text>
                <View style={s.progBar}><View style={[s.progFill, { width: `${progress}%` }]} /></View>
              </View>
            </View>
          )}

          {resultStatus === 'completed' && resultUrl && (
            <View style={s.successBanner}>
              <Ionicons name="checkmark-circle" size={22} color="#10B981" />
              <Text style={s.successT}>Timeline ready ✓</Text>
              <TouchableOpacity style={s.viewBtn} onPress={() => router.push({ pathname: '/project/[id]', params: { id: projectId! } } as any)}>
                <Text style={s.viewBtnT}>View</Text>
              </TouchableOpacity>
            </View>
          )}
          {resultStatus === 'failed' && (
            <View style={s.errBanner}>
              <Ionicons name="alert-circle" size={18} color="#EF4444" />
              <Text style={s.errT} numberOfLines={3}>{resultError}</Text>
            </View>
          )}

          {/* Shot cards */}
          {shots.map((shot, idx) => (
            <View key={shot.id} style={s.shotCard}>
              <TouchableOpacity style={s.shotHeader} onPress={() => toggleExpand(shot.id)} activeOpacity={0.8}>
                <View style={s.shotHeaderLeft}>
                  <View style={s.shotBadge}><Text style={s.shotBadgeText}>{idx + 1}</Text></View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.shotTitle}>Shot {idx + 1}{shot.prompt ? ` · ${shot.prompt.slice(0, 30)}${shot.prompt.length > 30 ? '…' : ''}` : ''}</Text>
                    <Text style={s.shotMeta}>{shot.duration}s · {shot.start_image_path ? 'image→video' : 'text→video'}{shot.dialogue_audio_path ? ' · 🎙' : shot.dialogue ? ' · 🗣' : ''}{shot.sound_effect && shot.sound_effect !== 'none' ? ' · 🔊' : ''}</Text>
                  </View>
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  {shots.length > 1 && (
                    <TouchableOpacity onPress={() => removeShot(shot.id)} style={s.iconBtn} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                      <Ionicons name="trash-outline" size={18} color="#EF4444" />
                    </TouchableOpacity>
                  )}
                  <Ionicons name={shot.expanded ? 'chevron-up' : 'chevron-down'} size={22} color="#94A3B8" />
                </View>
              </TouchableOpacity>

              {shot.expanded && (
                <View style={s.shotBody}>
                  {/* Prompt */}
                  <Text style={s.label}>Prompt *</Text>
                  <TextInput
                    style={s.input}
                    placeholder="Describe this shot..."
                    placeholderTextColor="#64748B"
                    value={shot.prompt}
                    onChangeText={t => updateShot(shot.id, { prompt: t })}
                    multiline
                  />

                  {/* Start frame */}
                  <Text style={[s.label, { marginTop: 12 }]}>Start Frame (optional)</Text>
                  {shot.start_image_uri ? (
                    <View style={s.imgPreview}>
                      <Image source={{ uri: shot.start_image_uri }} style={s.imgThumb} />
                      <View style={{ flex: 1 }}>
                        <Text style={s.imgText}>{shot.image_uploading ? 'Uploading…' : 'Image ready'}</Text>
                        <TouchableOpacity onPress={() => clearStartImage(shot.id)} style={s.clearLink}>
                          <Text style={s.clearLinkT}>Remove</Text>
                        </TouchableOpacity>
                      </View>
                    </View>
                  ) : (
                    <TouchableOpacity style={s.uploadBtn} onPress={() => pickStartImage(shot.id)}>
                      <Ionicons name="image-outline" size={18} color="#A78BFA" />
                      <Text style={s.uploadBtnT}>Upload start frame (or use text→video)</Text>
                    </TouchableOpacity>
                  )}

                  {/* Duration */}
                  <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 12 }}>
                    <Text style={s.label}>Duration</Text>
                    {mhCap.costPerSec != null && (
                      <Text style={{ color: '#94A3B8', fontSize: 11 }}>
                        · {mhCap.costPerSec}¢/sec
                      </Text>
                    )}
                  </View>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    {(mhCap.durationOptions || DURATIONS).map(d => {
                      const cost = mhCap.costPerSec ? Math.max(mhCap.costPerSec * d, mhCap.minCost || 0) : null;
                      return (
                        <TouchableOpacity key={d} style={[s.durChip, shot.duration === d && s.durChipActive]} onPress={() => updateShot(shot.id, { duration: d })}>
                          <Text style={[s.durChipT, shot.duration === d && { color: '#fff' }]}>{d}s</Text>
                          {cost != null && (
                            <Text style={{ color: shot.duration === d ? '#FDE68A' : '#64748B', fontSize: 9, marginTop: 1 }}>🪙 {cost}</Text>
                          )}
                        </TouchableOpacity>
                      );
                    })}
                  </View>

                  {/* Quality tier */}
                  <Text style={[s.label, { marginTop: 12 }]}>Quality / Model</Text>
                  <QualityPicker
                    feature={shot.start_image_path ? 'image_to_video' : 'text_to_video'}
                    selectedId={shot.quality_mode || 'studio'}
                    onSelect={(id) => updateShot(shot.id, { quality_mode: id as any })}
                  />

                  {/* Sprint 3 Phase A — Motion preset (bypasses MH when set + start_image) */}
                  {shot.start_image_path && (
                    <View style={{ marginTop: 12 }}>
                      <MotionPicker
                        selectedId={shot.motion || null}
                        onSelect={(id) => updateShot(shot.id, { motion: id })}
                        label="Motion (instead of AI video)"
                        showSavingsHint
                      />
                    </View>
                  )}

                  {/* Dialogue */}
                  <Text style={[s.label, { marginTop: 12 }]}>Dialogue (optional)</Text>
                  <TextInput
                    style={[s.input, { minHeight: 50 }]}
                    placeholder={shot.dialogue_audio_path ? 'Using uploaded audio (TTS disabled)' : 'What should the character say?'}
                    placeholderTextColor="#64748B"
                    value={shot.dialogue || ''}
                    onChangeText={t => updateShot(shot.id, { dialogue: t })}
                    multiline
                    editable={!shot.dialogue_audio_path}
                  />

                  {/* Voice */}
                  <VoicePicker selectedId={shot.voice_id || 'hi-IN-SwaraNeural'} onSelect={(v) => updateShot(shot.id, { voice_id: v })} />
                  <Text style={s.hint}>Voice: <Text style={{ color: '#A78BFA', fontWeight: '700' }}>{findVoice(shot.voice_id || '')?.name || 'Swara'}</Text></Text>

                  {/* Audio upload / record */}
                  <Text style={[s.label, { marginTop: 10 }]}>Or use your own audio</Text>
                  {shot.dialogue_audio_uri ? (
                    <View style={s.audioCard}>
                      <Ionicons name="musical-note" size={18} color="#10B981" />
                      <Text style={s.audioText}>{shot.dialogue_uploading ? 'Uploading…' : 'Audio ready ✓'}</Text>
                      <TouchableOpacity onPress={() => clearDialogueAudio(shot.id)}>
                        <Ionicons name="close-circle" size={20} color="#EF4444" />
                      </TouchableOpacity>
                    </View>
                  ) : (
                    <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
                      <TouchableOpacity style={s.audioBtn} onPress={() => pickDialogueAudio(shot.id)} disabled={recordingShotId === shot.id}>
                        <Ionicons name="cloud-upload-outline" size={16} color="#A78BFA" />
                        <Text style={s.audioBtnT}>Upload</Text>
                      </TouchableOpacity>
                      {recordingShotId === shot.id ? (
                        <TouchableOpacity style={[s.audioBtn, { borderColor: '#EF4444', backgroundColor: '#EF444420' }]} onPress={stopRecordingForShot}>
                          <Ionicons name="stop-circle" size={16} color="#EF4444" />
                          <Text style={[s.audioBtnT, { color: '#EF4444' }]}>Stop ({recordDuration}s)</Text>
                        </TouchableOpacity>
                      ) : (
                        <TouchableOpacity style={s.audioBtn} onPress={() => startRecordingForShot(shot.id)}>
                          <Ionicons name="mic" size={16} color="#F97316" />
                          <Text style={[s.audioBtnT, { color: '#F97316' }]}>Record</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  )}

                  {/* SFX */}
                  <Text style={[s.label, { marginTop: 12 }]}>Sound Effect</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                    {sfxList.map((sfx: any) => (
                      <TouchableOpacity key={sfx.id} style={[s.sfxChip, shot.sound_effect === sfx.id && s.sfxChipActive]} onPress={() => updateShot(shot.id, { sound_effect: sfx.id })}>
                        <Ionicons name={sfx.icon as any} size={12} color={shot.sound_effect === sfx.id ? '#fff' : '#A78BFA'} />
                        <Text style={[s.sfxChipText, shot.sound_effect === sfx.id && { color: '#fff' }]}>{sfx.name}</Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>

                  {/* Transition → next shot (only if not last) */}
                  {idx < shots.length - 1 && (
                    <>
                      <Text style={[s.label, { marginTop: 12 }]}>Transition → next shot</Text>
                      <View style={{ flexDirection: 'row', gap: 6 }}>
                        {[
                          { id: 'cut', label: 'Cut', icon: 'remove' },
                          { id: 'fade', label: 'Fade', icon: 'sunny-outline' },
                          { id: 'crossfade', label: 'Crossfade', icon: 'swap-horizontal' },
                        ].map(t => (
                          <TouchableOpacity
                            key={t.id}
                            style={[s.transChip, shot.transition_out === t.id && s.transChipActive]}
                            onPress={() => updateShot(shot.id, { transition_out: t.id as any })}
                          >
                            <Ionicons name={t.icon as any} size={12} color={shot.transition_out === t.id ? '#fff' : '#A78BFA'} />
                            <Text style={[s.transChipT, shot.transition_out === t.id && { color: '#fff' }]}>{t.label}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </>
                  )}
                </View>
              )}
              {/* Transition indicator between collapsed shots */}
              {idx < shots.length - 1 && (
                <View style={s.transitionInline}>
                  <View style={s.transitionLine} />
                  <View style={s.transitionPill}>
                    <Ionicons
                      name={shot.transition_out === 'crossfade' ? 'swap-horizontal' : shot.transition_out === 'fade' ? 'sunny-outline' : 'remove'}
                      size={11}
                      color="#A78BFA"
                    />
                    <Text style={s.transitionPillT}>
                      {shot.transition_out === 'crossfade' ? 'Crossfade' : shot.transition_out === 'fade' ? 'Fade' : 'Cut'}
                    </Text>
                  </View>
                  <View style={s.transitionLine} />
                </View>
              )}
            </View>
          ))}

          {/* Add shot */}
          {shots.length < MAX_SHOTS && (
            <TouchableOpacity style={s.addShotBtn} onPress={addShot}>
              <Ionicons name="add-circle" size={22} color="#F97316" />
              <Text style={s.addShotT}>Add another shot ({shots.length}/{MAX_SHOTS})</Text>
            </TouchableOpacity>
          )}

          {/* Global options */}
          <View style={s.section}>
            <Text style={s.sTitle}>Aspect Ratio</Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              {(['9:16', '16:9', '1:1'] as const).map(ar => (
                <TouchableOpacity key={ar} style={[s.aspectChip, aspectRatio === ar && s.aspectChipActive]} onPress={() => setAspectRatio(ar)}>
                  <Text style={[s.aspectChipText, aspectRatio === ar && { color: '#fff' }]}>{ar}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <View style={s.section}>
            <Text style={s.sTitle}>Resolution</Text>
            <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
          </View>

          <View style={s.totalCard}>
            <Text style={s.totalT}>Total Duration: {totalDuration}s · {shots.length} shot{shots.length > 1 ? 's' : ''}</Text>
          </View>

          {/* Generate */}
          <TouchableOpacity style={[s.genBtn, !canGenerate && { backgroundColor: '#334155' }]} onPress={generate} disabled={!canGenerate}>
            {processing ? (
              <View style={s.genBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={s.genBtnT}>Stitching… {progress}%</Text></View>
            ) : (
              <View style={s.genBtnI}><Ionicons name="sparkles" size={22} color="#fff" /><Text style={s.genBtnT}>Generate Timeline ({totalDuration}s)</Text></View>
            )}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  scroll: { padding: 16, paddingBottom: 80 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  subtitle: { color: '#94A3B8', fontSize: 12, marginBottom: 16, lineHeight: 17 },

  // Shot card
  shotCard: { backgroundColor: '#1E293B', borderRadius: 12, marginBottom: 12, borderWidth: 1, borderColor: '#334155', overflow: 'hidden' },
  shotHeader: { flexDirection: 'row', alignItems: 'center', padding: 12 },
  shotHeaderLeft: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 },
  shotBadge: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#F97316', alignItems: 'center', justifyContent: 'center' },
  shotBadgeText: { color: '#fff', fontWeight: 'bold', fontSize: 13 },
  shotTitle: { color: '#fff', fontWeight: '700', fontSize: 14 },
  shotMeta: { color: '#94A3B8', fontSize: 11, marginTop: 2 },
  shotBody: { paddingHorizontal: 12, paddingBottom: 12, borderTopWidth: 1, borderTopColor: '#334155' },
  iconBtn: { padding: 6 },

  label: { color: '#E2E8F0', fontSize: 12, fontWeight: '700', marginTop: 10, marginBottom: 6 },
  input: { backgroundColor: '#0F172A', borderRadius: 8, padding: 10, color: '#fff', fontSize: 13, borderWidth: 1, borderColor: '#334155', minHeight: 70, textAlignVertical: 'top' },

  imgPreview: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#0F172A', borderRadius: 8, padding: 8, borderWidth: 1, borderColor: '#334155' },
  imgThumb: { width: 60, height: 60, borderRadius: 6, backgroundColor: '#334155' },
  imgText: { color: '#E2E8F0', fontSize: 12, fontWeight: '600' },
  clearLink: { marginTop: 4 }, clearLinkT: { color: '#EF4444', fontSize: 12 },
  uploadBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#0F172A', borderRadius: 8, padding: 12, borderWidth: 1, borderColor: '#A78BFA60', borderStyle: 'dashed' },
  uploadBtnT: { color: '#A78BFA', fontSize: 12, fontWeight: '600' },

  durChip: { backgroundColor: '#0F172A', borderRadius: 6, paddingHorizontal: 12, paddingVertical: 7, borderWidth: 1, borderColor: '#334155' },
  durChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  durChipT: { color: '#94A3B8', fontSize: 12, fontWeight: '700' },

  hint: { color: '#94A3B8', fontSize: 11, marginTop: 6 },

  audioBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#0F172A', borderRadius: 8, paddingVertical: 10, borderWidth: 1, borderColor: '#A78BFA60', borderStyle: 'dashed' },
  audioBtnT: { color: '#A78BFA', fontSize: 12, fontWeight: '700' },
  audioCard: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#10B98110', borderRadius: 8, padding: 10, marginTop: 6, borderWidth: 1, borderColor: '#10B98140' },
  audioText: { flex: 1, color: '#E2E8F0', fontSize: 12, fontWeight: '600' },

  sfxChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#0F172A', borderRadius: 14, paddingHorizontal: 10, paddingVertical: 6, marginRight: 6, borderWidth: 1, borderColor: '#A78BFA40' },
  sfxChipActive: { backgroundColor: '#A78BFA', borderColor: '#A78BFA' },
  sfxChipText: { color: '#A78BFA', fontSize: 11, fontWeight: '700' },
  // Transition picker
  transChip: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, backgroundColor: '#0F172A', borderRadius: 8, paddingVertical: 8, borderWidth: 1, borderColor: '#A78BFA40' },
  transChipActive: { backgroundColor: '#A78BFA', borderColor: '#A78BFA' },
  transChipT: { color: '#A78BFA', fontSize: 12, fontWeight: '700' },
  transitionInline: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, paddingHorizontal: 12 },
  transitionLine: { flex: 1, height: 1, backgroundColor: '#334155' },
  transitionPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, backgroundColor: '#0F172A', borderWidth: 1, borderColor: '#A78BFA40' },
  transitionPillT: { color: '#A78BFA', fontSize: 10, fontWeight: '700' },

  addShotBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#F9731620', borderRadius: 10, paddingVertical: 14, marginVertical: 8, borderWidth: 1, borderColor: '#F9731660', borderStyle: 'dashed' },
  addShotT: { color: '#F97316', fontSize: 14, fontWeight: '700' },

  section: { marginVertical: 10 },
  sTitle: { fontSize: 14, fontWeight: '700', color: '#E2E8F0', marginBottom: 8 },

  aspectChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: '#334155' },
  aspectChipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  aspectChipText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },

  totalCard: { backgroundColor: '#0EA5E920', borderRadius: 10, padding: 12, marginVertical: 12, borderWidth: 1, borderColor: '#0EA5E940' },
  totalT: { color: '#67E8F9', fontSize: 13, fontWeight: '700', textAlign: 'center' },

  genBtn: { backgroundColor: '#F97316', borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 6 },
  genBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  genBtnT: { color: '#fff', fontSize: 16, fontWeight: 'bold' },

  progCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#1E293B', padding: 12, borderRadius: 10, marginBottom: 12, borderWidth: 1, borderColor: '#F9731640' },
  progLabel: { color: '#fff', fontSize: 13, fontWeight: '600' },
  progBar: { height: 6, backgroundColor: '#334155', borderRadius: 3, overflow: 'hidden', marginTop: 6 },
  progFill: { height: 6, backgroundColor: '#F97316' },
  successBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#10B98110', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#10B98140', marginBottom: 12 },
  successT: { flex: 1, color: '#10B981', fontWeight: '700' },
  viewBtn: { backgroundColor: '#10B981', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6 },
  viewBtnT: { color: '#fff', fontSize: 12, fontWeight: '700' },
  errBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444410', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#EF444440', marginBottom: 12 },
  errT: { flex: 1, color: '#EF4444', fontSize: 12 },
});
