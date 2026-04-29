import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput,
  Image, ActivityIndicator, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import VoicePicker from '../src/VoicePicker';
import { findVoice } from '../src/voices';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

interface SpeakerLine { id: string; speakerIdx: number; text: string; }

export default function RedubMultiScreen() {
  const router = useRouter();
  const [videoUri, setVideoUri] = useState<string | null>(null);
  const [videoPath, setVideoPath] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [extractedFrames, setExtractedFrames] = useState<any[]>([]);
  const [transcript, setTranscript] = useState('');
  const [diarizedSegs, setDiarizedSegs] = useState<any[]>([]);
  const [detectedSpeakers, setDetectedSpeakers] = useState<number[]>([]);
  const [voiceIds, setVoiceIds] = useState<Record<number, string>>({});
  const [activeSpeaker, setActiveSpeaker] = useState(0);
  const [lines, setLines] = useState<SpeakerLine[]>([]);
  const [targetDuration, setTargetDuration] = useState<number | null>(null);
  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultError, setResultError] = useState('');
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
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  const resetAll = () => {
    Alert.alert('Clear & Reset', 'This will clear the uploaded video, speakers, and dialogue. Continue?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear All', style: 'destructive', onPress: () => {
        setVideoUri(null); setVideoPath(null); setUploading(false);
        setExtractedFrames([]); setTranscript(''); setDiarizedSegs([]); setDetectedSpeakers([]);
        setVoiceIds({}); setActiveSpeaker(0); setLines([]);
        setTargetDuration(null);
        setProjectId(null); setProcessing(false); setProgress(0); setResultStatus('none'); setResultError('');
      }},
    ]);
  };

  const pickRefVideo = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['videos'], quality: 0.5 });
    if (!r.canceled && r.assets[0]) {
      setVideoUri(r.assets[0].uri); setUploading(true);
      try {
        const fd = new FormData();
        if (Platform.OS === 'web') {
          const fr = await fetch(r.assets[0].uri); const blob = await fr.blob();
          fd.append('file', blob, 'ref.mp4');
        } else {
          fd.append('file', { uri: r.assets[0].uri, type: 'video/mp4', name: 'ref.mp4' } as any);
        }
        const res = await axios.post(`${BACKEND_URL}/api/extract-frames`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 180000 });
        setVideoPath(res.data.video_path);
        setExtractedFrames(res.data.frames || []);
        setTranscript(res.data.transcript || '');
        setDiarizedSegs(res.data.diarized_segments || []);
        // Identify distinct speakers (capped at 4)
        const speakerSet = new Set<number>();
        (res.data.diarized_segments || []).forEach((s: any) => speakerSet.add(s.speaker || 1));
        const speakers = Array.from(speakerSet).slice(0, 4).sort((a,b) => a-b);
        setDetectedSpeakers(speakers.length > 0 ? speakers : [1]);
        // Pre-fill lines from diarization (group by speaker)
        const newLines: SpeakerLine[] = (res.data.diarized_segments || []).map((s: any, i: number) => ({
          id: `seg_${i}`,
          speakerIdx: speakers.indexOf(s.speaker || 1),
          text: s.text || '',
        })).filter((l: SpeakerLine) => l.speakerIdx >= 0);
        if (newLines.length === 0 && res.data.transcript) {
          newLines.push({ id: 'manual_1', speakerIdx: 0, text: res.data.transcript });
        }
        setLines(newLines);
      } catch (e: any) { Alert.alert('Extract failed', e.message || 'Failed'); setVideoUri(null); }
      finally { setUploading(false); }
    }
  };

  const startMultiRedub = async () => {
    if (!videoPath) { Alert.alert('Upload video first'); return; }
    const nonEmpty = lines.filter(l => l.text.trim().length > 0);
    if (nonEmpty.length === 0) { Alert.alert('Add dialogue lines first'); return; }
    try {
      setProcessing(true); setProgress(0); setResultStatus('none');
      const dialogue_lines = nonEmpty.map(l => ({
        character_index: l.speakerIdx,
        text: l.text,
        voice_id: voiceIds[l.speakerIdx] || 'hi-IN-SwaraNeural',
      }));
      const payload = {
        image_urls: [],
        dialogue_lines,
        voice_ids: voiceIds,
        mode: 'ref_video_only',
        ref_video_path: videoPath,
        ...(targetDuration ? { target_duration: targetDuration } : {}),
      };
      const r = await axios.post(`${BACKEND_URL}/api/create-lipsync`, payload);
      setProjectId(r.data.project_id);
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || 'Failed'); setProcessing(false); }
  };

  const addLine = () => setLines(prev => [...prev, { id: Date.now().toString(), speakerIdx: activeSpeaker, text: '' }]);
  const updateLine = (id: string, text: string) => setLines(prev => prev.map(l => l.id === id ? { ...l, text } : l));
  const removeLine = (id: string) => setLines(prev => prev.filter(l => l.id !== id));

  const canStart = !!videoPath && lines.some(l => l.text.trim()) && !processing;
  const activeLines = lines.filter(l => l.speakerIdx === activeSpeaker);

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          <View style={s.header}>
            <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
            <Text style={s.title}>Multi-Character Re-dub</Text>
            <TouchableOpacity onPress={resetAll} style={s.backBtn}><Ionicons name="refresh" size={22} color="#EF4444" /></TouchableOpacity>
          </View>

          <View style={s.tipCard}>
            <Ionicons name="information-circle" size={18} color="#06B6D4" />
            <Text style={s.tipText}>Upload a video with multiple speakers. We'll auto-detect each speaker and let you assign a unique AI voice to each.</Text>
          </View>

          {resultStatus === 'completed' && (
            <View style={s.successBanner}><Ionicons name="checkmark-circle" size={22} color="#10B981" /><Text style={s.successText}>Multi-character re-dub complete!</Text>
              <TouchableOpacity style={s.viewBtn} onPress={() => router.push('/projects')}><Text style={s.viewBtnT}>View</Text></TouchableOpacity>
            </View>
          )}
          {resultStatus === 'failed' && <View style={s.errBanner}><Ionicons name="close-circle" size={22} color="#EF4444" /><Text style={s.errText}>{resultError}</Text></View>}
          {processing && (
            <View style={s.progressCard}>
              <View style={s.progressHeader}><ActivityIndicator size="small" color="#06B6D4" /><Text style={s.progressTitle}>Re-dubbing with {detectedSpeakers.length} voices...</Text></View>
              <View style={s.progressBarWrap}><View style={s.progressBarBg}><View style={[s.progressBarFill, { width: `${progress}%` }]} /></View><Text style={s.progressPct}>{progress}%</Text></View>
            </View>
          )}

          {/* Step 1: Upload video */}
          <View style={s.section}>
            <Text style={s.sTitle}>1. Upload Source Video</Text>
            {videoUri ? (
              <View style={s.videoCard}>
                <Ionicons name="videocam" size={20} color="#06B6D4" />
                <Text style={s.videoText}>{uploading ? 'Processing...' : 'Video ready'}</Text>
                {uploading && <ActivityIndicator size="small" color="#06B6D4" />}
                <TouchableOpacity onPress={pickRefVideo} style={s.changeBtn}><Text style={s.changeBtnT}>Change</Text></TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={s.uploadBtn} onPress={pickRefVideo}>
                <Ionicons name="cloud-upload" size={30} color="#06B6D4" />
                <Text style={s.uploadText}>Choose Video</Text>
              </TouchableOpacity>
            )}
          </View>

          {/* Step 2: Detected speakers */}
          {detectedSpeakers.length > 0 && (
            <>
              <View style={s.section}>
                <Text style={s.sTitle}>2. Detected Speakers ({detectedSpeakers.length})</Text>
                <Text style={s.hint}>We detected {detectedSpeakers.length} distinct voice{detectedSpeakers.length>1?'s':''} in the video. Assign a new AI voice to each.</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
                  {detectedSpeakers.map((_, idx) => (
                    <TouchableOpacity key={idx} style={[s.spTab, activeSpeaker === idx && s.spTabActive]} onPress={() => setActiveSpeaker(idx)}>
                      <Text style={[s.spTabText, activeSpeaker === idx && { color: '#fff' }]}>Speaker {idx+1}{voiceIds[idx] ? ' ✓' : ''}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>

              {/* Voice picker for active speaker */}
              <View style={s.section}>
                <Text style={s.sTitle}>3. Voice for Speaker {activeSpeaker + 1}</Text>
                <VoicePicker
                  selectedId={voiceIds[activeSpeaker]}
                  onSelect={(id) => setVoiceIds(prev => ({ ...prev, [activeSpeaker]: id }))}
                />
                <Text style={[s.hint, { marginTop: 6 }]}>Selected: <Text style={{ color: '#A78BFA', fontWeight: '700' }}>{findVoice(voiceIds[activeSpeaker])?.name || 'Default'}</Text></Text>
              </View>

              {/* Dialogue editor for active speaker */}
              <View style={s.section}>
                <Text style={s.sTitle}>4. Dialogue for Speaker {activeSpeaker + 1}</Text>
                {activeLines.length === 0 && <Text style={s.hint}>No lines yet. Tap "Add Line" below or edit the auto-detected transcript.</Text>}
                {activeLines.map(line => (
                  <View key={line.id} style={s.lineRow}>
                    <TextInput
                      style={s.lineInput}
                      value={line.text}
                      placeholder={`Type Speaker ${activeSpeaker+1}'s line...`}
                      placeholderTextColor="#64748B"
                      onChangeText={(t) => updateLine(line.id, t)}
                      multiline
                    />
                    <TouchableOpacity onPress={() => removeLine(line.id)} style={{ padding: 6 }}>
                      <Ionicons name="close-circle" size={22} color="#EF4444" />
                    </TouchableOpacity>
                  </View>
                ))}
                <TouchableOpacity onPress={addLine} style={s.addLineBtn}>
                  <Ionicons name="add-circle" size={20} color="#06B6D4" />
                  <Text style={s.addLineText}>Add Line</Text>
                </TouchableOpacity>
              </View>
            </>
          )}

          {detectedSpeakers.length > 0 && (
            <View style={s.section}>
              <Text style={s.sTitle}>5. Output Duration (optional)</Text>
              <Text style={s.hint}>Pick a target length or leave Auto (match source).</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
                {[
                  { label: 'Auto', v: null }, { label: '2s', v: 2 }, { label: '5s', v: 5 }, { label: '10s', v: 10 },
                  { label: '15s', v: 15 }, { label: '30s', v: 30 }, { label: '1 min', v: 60 }, { label: '2 min', v: 120 },
                ].map((d, i) => (
                  <TouchableOpacity key={i} style={[{ backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, marginRight: 8, borderWidth: 1, borderColor: '#334155' }, targetDuration === d.v && { backgroundColor: '#06B6D4', borderColor: '#06B6D4' }]} onPress={() => setTargetDuration(d.v)}>
                    <Text style={[{ color: '#94A3B8', fontSize: 13, fontWeight: '600' }, targetDuration === d.v && { color: '#fff' }]}>{d.label}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}

          <TouchableOpacity style={[s.cBtn, { backgroundColor: canStart ? '#06B6D4' : '#334155' }]} onPress={startMultiRedub} disabled={!canStart}>
            {processing ? (
              <View style={s.cBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={s.cBtnT}>Re-dubbing... {progress}%</Text></View>
            ) : (
              <View style={s.cBtnI}><Ionicons name="film" size={22} color="#fff" /><Text style={s.cBtnT}>Start Multi-Character Re-dub</Text></View>
            )}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 80 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: 'bold', color: '#fff' },
  section: { marginBottom: 20 }, sTitle: { fontSize: 16, fontWeight: '600', color: '#E2E8F0', marginBottom: 8 },
  hint: { color: '#94A3B8', fontSize: 13, lineHeight: 19 },
  tipCard: { flexDirection: 'row', gap: 8, backgroundColor: '#06B6D420', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#06B6D440', marginBottom: 16 },
  tipText: { flex: 1, color: '#A5F3FC', fontSize: 12, lineHeight: 17 },
  // Video upload
  uploadBtn: { backgroundColor: '#1E293B', borderRadius: 12, padding: 30, alignItems: 'center', borderWidth: 2, borderColor: '#06B6D4', borderStyle: 'dashed', gap: 8 },
  uploadText: { color: '#E2E8F0', fontSize: 15, fontWeight: '600' },
  videoCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#1E293B', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#06B6D440' },
  videoText: { flex: 1, color: '#E2E8F0', fontSize: 14 },
  changeBtn: { backgroundColor: '#334155', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6 },
  changeBtnT: { color: '#E2E8F0', fontSize: 12, fontWeight: '600' },
  // Speaker tabs
  spTab: { backgroundColor: '#1E293B', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8, marginRight: 8, borderWidth: 1, borderColor: '#334155' },
  spTabActive: { backgroundColor: '#06B6D4', borderColor: '#06B6D4' },
  spTabText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  // Dialogue editor
  lineRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginBottom: 8 },
  lineInput: { flex: 1, backgroundColor: '#1E293B', borderRadius: 8, padding: 10, color: '#fff', fontSize: 14, borderWidth: 1, borderColor: '#334155', minHeight: 44 },
  addLineBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#1E293B', padding: 10, borderRadius: 8, borderWidth: 1, borderColor: '#06B6D440', alignSelf: 'flex-start' },
  addLineText: { color: '#06B6D4', fontSize: 13, fontWeight: '700' },
  // Progress
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: '#06B6D440' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  progressTitle: { color: '#fff', fontSize: 14, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, backgroundColor: '#06B6D4', borderRadius: 4 },
  progressPct: { color: '#06B6D4', fontSize: 13, fontWeight: 'bold' },
  successBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#10B98110', padding: 14, borderRadius: 10, borderWidth: 1, borderColor: '#10B98140', marginBottom: 16 },
  successText: { flex: 1, color: '#10B981', fontSize: 15, fontWeight: '700' },
  viewBtn: { backgroundColor: '#10B981', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  viewBtnT: { color: '#fff', fontSize: 13, fontWeight: '700' },
  errBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444410', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#EF444440', marginBottom: 16 },
  errText: { flex: 1, color: '#EF4444', fontSize: 13 },
  cBtn: { borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 6 },
  cBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  cBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
});
