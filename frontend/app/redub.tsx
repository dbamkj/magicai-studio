import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput, ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { Audio } from 'expo-av';
import axios from 'axios';
import { uploadVideoFile } from '../src/uploadHelper';
import ResolutionPicker from '../src/ResolutionPicker';
import { useMhCapabilities } from '../src/useMhCapabilities';
import VoicePicker from '../src/VoicePicker';
import { findVoice } from '../src/voices';
import AuroraBackground from '../src/AuroraBackground';
import AuthGateModal from '../src/components/AuthGateModal';
import { useAuth } from '../src/AuthContext';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export default function RedubScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const [showAuthGate, setShowAuthGate] = useState(false);
  const requireLogin = (): boolean => {
    if (!user) { setShowAuthGate(true); return false; }
    return true;
  };
  const [videoUri, setVideoUri] = useState<string | null>(null);
  const [videoPath, setVideoPath] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  // Script mode
  const [scriptMode, setScriptMode] = useState<'text' | 'audio'>('text');
  const [script, setScript] = useState('');
  const [voiceId, setVoiceId] = useState('hi-IN-SwaraNeural');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  // MH lip_sync capability — re-dub uses MH lipsync under the hood.
  const mhCap = useMhCapabilities('lip_sync');
  const [charType, setCharType] = useState<'male' | 'female'>('female');
  // Audio upload
  const [audioUri, setAudioUri] = useState<string | null>(null);
  const [audioPath, setAudioPath] = useState<string | null>(null);
  const [audioUploading, setAudioUploading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordDuration, setRecordDuration] = useState(0);
  const recordingRef = useRef<any>(null);
  const recordTimerRef = useRef<any>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [transcribedText, setTranscribedText] = useState('');
  // Processing
  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultError, setResultError] = useState('');
  const [showReview, setShowReview] = useState(false);
  const [targetDuration, setTargetDuration] = useState<number | null>(null);
  const pollRef = useRef<any>(null);

  // Reset all state
  const resetAll = () => {
    Alert.alert('Clear & Reset', 'This will clear the uploaded video, audio, script, and any result. Continue?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear All', style: 'destructive', onPress: () => {
        setVideoUri(null); setVideoPath(null); setUploadProgress(0); setUploading(false);
        setScriptMode('text'); setScript(''); setVoiceId('hi-IN-SwaraNeural'); setCharType('female');
        setAudioUri(null); setAudioPath(null); setAudioUploading(false);
        setIsRecording(false); setRecordDuration(0); setTranscribing(false); setTranscribedText('');
        setTargetDuration(null);
        setProjectId(null); setProcessing(false); setProgress(0); setResultStatus('none'); setResultError('');
        setShowReview(false);
      }},
    ]);
  };

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

  // Auto-select voice based on character type
  useEffect(() => {
    if (charType === 'male') setVoiceId('hi-IN-MadhurNeural');
    else setVoiceId('hi-IN-SwaraNeural');
  }, [charType]);

  const pickVideo = async () => {
    if (!requireLogin()) return;
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') { Alert.alert('Permission needed'); return; }
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['videos'], quality: 0.8 });
      if (!r.canceled && r.assets[0]) {
        setVideoUri(r.assets[0].uri); setUploading(true); setUploadProgress(0);
        try {
          const data = await uploadVideoFile(r.assets[0].uri);
          setVideoPath(data.file_path); setUploadProgress(100);
        } catch (e) { Alert.alert('Upload Error'); setVideoUri(null); }
        finally { setUploading(false); }
      }
    } catch (e) { Alert.alert('Error'); }
  };

  const startRecording = async () => {
    if (!requireLogin()) return;
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
      setAudioUri(uri); setAudioUploading(true); setTranscribing(true);
      try {
        const fd = new FormData();
        const fileName = `record_${Date.now()}.m4a`;
        if (Platform.OS === 'web') {
          const resp = await fetch(uri); const blob = await resp.blob();
          fd.append('file', new File([blob], fileName, { type: blob.type || 'audio/webm' }));
        } else {
          fd.append('file', { uri, name: fileName, type: 'audio/m4a' } as any);
        }
        const [upRes, transRes] = await Promise.all([
          axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 }),
          (async () => {
            const fd2 = new FormData();
            if (Platform.OS === 'web') {
              const resp2 = await fetch(uri); const blob2 = await resp2.blob();
              fd2.append('file', new File([blob2], fileName, { type: blob2.type || 'audio/webm' }));
            } else {
              fd2.append('file', { uri, name: fileName, type: 'audio/m4a' } as any);
            }
            return axios.post(`${BACKEND_URL}/api/transcribe-audio`, fd2, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
          })(),
        ]);
        setAudioPath(upRes.data.file_path);
        if (transRes.data.text) setTranscribedText(transRes.data.text);
      } catch (e) { Alert.alert('Upload Error'); setAudioUri(null); }
      finally { setAudioUploading(false); setTranscribing(false); }
    } catch (e: any) { Alert.alert('Error', e?.message || 'Failed to save recording'); setIsRecording(false); }
  };

  const pickAudio = async () => {
    if (!requireLogin()) return;
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: 'audio/*' });
      if (!result.canceled && result.assets && result.assets[0]) {
        setAudioUri(result.assets[0].uri); setAudioUploading(true);
        const fd = new FormData();
        if (Platform.OS === 'web') {
          const resp = await fetch(result.assets[0].uri);
          const blob = await resp.blob();
          fd.append('file', new File([blob], result.assets[0].name || 'audio.mp3', { type: result.assets[0].mimeType || 'audio/mp3' }));
        } else {
          fd.append('file', { uri: result.assets[0].uri, name: result.assets[0].name || 'audio.mp3', type: result.assets[0].mimeType || 'audio/mp3' } as any);
        }
        // Upload and transcribe simultaneously
        const [uploadRes] = await Promise.all([
          axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 }),
        ]);
        setAudioPath(uploadRes.data.file_path);
        setAudioUploading(false);
        // Transcribe
        setTranscribing(true);
        const fd2 = new FormData();
        if (Platform.OS === 'web') {
          const resp2 = await fetch(result.assets[0].uri);
          const blob2 = await resp2.blob();
          fd2.append('file', new File([blob2], result.assets[0].name || 'audio.mp3', { type: result.assets[0].mimeType || 'audio/mp3' }));
        } else {
          fd2.append('file', { uri: result.assets[0].uri, name: result.assets[0].name || 'audio.mp3', type: result.assets[0].mimeType || 'audio/mp3' } as any);
        }
        try {
          const transRes = await axios.post(`${BACKEND_URL}/api/transcribe-audio`, fd2, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
          if (transRes.data.transcript) {
            setTranscribedText(transRes.data.transcript);
            setScript(transRes.data.transcript);
          }
        } catch (e) {}
        setTranscribing(false);
      }
    } catch (e) { Alert.alert('Error'); setAudioUploading(false); setTranscribing(false); }
  };

  const startRedub = async () => {
    if (!requireLogin()) return;
    if (!videoPath) { Alert.alert('Upload video first'); return; }
    if (scriptMode === 'text' && !script.trim()) { Alert.alert('Enter script'); return; }
    if (scriptMode === 'audio' && !audioPath) { Alert.alert('Upload audio'); return; }
    try {
      setProcessing(true); setProgress(0); setResultStatus('none');
      const payload: any = { video_url: videoPath, script_text: script || transcribedText, voice_id: voiceId, resolution };
      if (scriptMode === 'audio' && audioPath) payload.audio_url = audioPath;
      if (targetDuration) payload.target_duration = targetDuration;
      const r = await axios.post(`${BACKEND_URL}/api/video-redub`, payload);
      setProjectId(r.data.project_id);
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || 'Failed'); setProcessing(false); }
  };

  const canStart = !!videoPath && (scriptMode === 'text' ? script.trim().length > 0 : !!audioPath) && !processing;

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          <View style={s.header}>
            <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
            <Text style={s.title}>Video Re-dub</Text>
            <TouchableOpacity onPress={resetAll} style={s.backBtn} accessibilityLabel="Clear & Reset">
              <Ionicons name="refresh" size={22} color="#EF4444" />
            </TouchableOpacity>
          </View>
          {/* Mode Tabs: Single vs Multi Character */}
          <View style={{ marginBottom: 20 }}>
            <Text style={s.sTitle}>Mode</Text>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <View style={[{ flex: 1, backgroundColor: '#06B6D4', borderRadius: 10, padding: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 }]}>
                <Ionicons name="person" size={18} color="#fff" />
                <Text style={{ color: '#fff', fontWeight: '700', fontSize: 14 }}>Single Character</Text>
              </View>
              <TouchableOpacity style={{ flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderWidth: 1, borderColor: '#334155' }} onPress={() => router.push('/redub-multi')}>
                <Ionicons name="people" size={18} color="#94A3B8" />
                <Text style={{ color: '#94A3B8', fontWeight: '700', fontSize: 14 }}>Multi Character</Text>
              </TouchableOpacity>
            </View>
            <Text style={[s.hint, { marginTop: 6 }]}>Single: one voice for whole video. Multi: auto-detect speakers and assign a unique voice to each.</Text>
          </View>

          {resultStatus === 'completed' && (
            <View style={s.successBanner}>
              <Ionicons name="checkmark-circle" size={24} color="#10B981" />
              <View style={{ flex: 1 }}><Text style={s.successTitle}>Re-dubbed video ready!</Text></View>
              <TouchableOpacity style={s.viewBtn} onPress={() => router.push('/projects')}><Text style={s.viewBtnT}>View</Text></TouchableOpacity>
            </View>
          )}
          {resultStatus === 'failed' && (
            <View style={s.errBanner}><Ionicons name="close-circle" size={22} color="#EF4444" /><Text style={s.errText}>{resultError}</Text></View>
          )}

          {processing && (
            <View style={s.progressCard}>
              <View style={s.progressHeader}><ActivityIndicator size="small" color="#06B6D4" /><Text style={s.progressTitle}>Re-dubbing video...</Text></View>
              <View style={s.progressBarWrap}><View style={s.progressBarBg}><View style={[s.progressBarFill, { width: `${progress}%` }]} /></View><Text style={s.progressPct}>{progress}%</Text></View>
            </View>
          )}

          {/* Step 1: Upload Video */}
          <View style={s.section}>
            <Text style={s.sTitle}>1. Upload Existing Video</Text>
            {videoUri ? (
              <View style={s.videoCard}>
                <Ionicons name="videocam" size={22} color="#06B6D4" />
                <Text style={s.videoName} numberOfLines={1}>{videoUri.split('/').pop()}</Text>
                {uploading ? (
                  <View style={{ flex: 0, alignItems: 'center' }}><ActivityIndicator size="small" color="#06B6D4" /><Text style={s.uploadPct}>{uploadProgress}%</Text></View>
                ) : <Ionicons name="checkmark-circle" size={20} color="#10B981" />}
                <TouchableOpacity onPress={() => { setVideoUri(null); setVideoPath(null); }}><Ionicons name="close-circle" size={22} color="#EF4444" /></TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={s.uploadBtn} onPress={pickVideo}>
                <Ionicons name="cloud-upload" size={28} color="#06B6D4" /><Text style={s.uploadText}>Choose Video</Text>
              </TouchableOpacity>
            )}
          </View>

          {/* Step 2: Script Mode */}
          <View style={s.section}>
            <Text style={s.sTitle}>2. New Script Source</Text>
            <View style={s.modeRow}>
              <TouchableOpacity style={[s.modeChip, scriptMode === 'text' && s.modeActive]} onPress={() => setScriptMode('text')}>
                <Ionicons name="text" size={18} color={scriptMode === 'text' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, scriptMode === 'text' && { color: '#fff' }]}>Type Script</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.modeChip, scriptMode === 'audio' && s.modeActive]} onPress={() => setScriptMode('audio')}>
                <Ionicons name="musical-note" size={18} color={scriptMode === 'audio' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, scriptMode === 'audio' && { color: '#fff' }]}>Upload Audio</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Step 3: Character Type */}
          <View style={s.section}>
            <Text style={s.sTitle}>3. Character Voice</Text>
            <View style={s.modeRow}>
              <TouchableOpacity style={[s.charChip, charType === 'female' && { backgroundColor: '#EC4899', borderColor: '#EC4899' }]} onPress={() => setCharType('female')}>
                <Ionicons name="woman" size={20} color={charType === 'female' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, charType === 'female' && { color: '#fff' }]}>Female</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.charChip, charType === 'male' && { backgroundColor: '#3B82F6', borderColor: '#3B82F6' }]} onPress={() => setCharType('male')}>
                <Ionicons name="man" size={20} color={charType === 'male' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, charType === 'male' && { color: '#fff' }]}>Male</Text>
              </TouchableOpacity>
            </View>
            <Text style={[s.hint, { marginTop: 8 }]}>Tap the play icon on any voice to preview.</Text>
            <View style={{ marginTop: 10 }}>
              <VoicePicker selectedId={voiceId} onSelect={setVoiceId} />
            </View>
          </View>

          {/* Script Input or Audio Upload */}
          {scriptMode === 'text' ? (
            <View style={s.section}>
              <Text style={s.sTitle}>4. New Dialogue</Text>
              <TextInput style={s.scriptInput} placeholder="Type the new dialogue..." placeholderTextColor="#64748B" value={script} onChangeText={setScript} multiline maxLength={2000} />
            </View>
          ) : (
            <View style={s.section}>
              <Text style={s.sTitle}>4. Upload Audio File</Text>
              <Text style={s.hint}>AI will transcribe and show the script for review.</Text>
              {audioUri ? (
                <View style={s.audioCard}>
                  <Ionicons name="musical-notes" size={22} color="#06B6D4" />
                  <Text style={s.audioName} numberOfLines={1}>{audioUri.split('/').pop()}</Text>
                  {audioUploading && <ActivityIndicator size="small" color="#06B6D4" />}
                  {!audioUploading && audioPath && <Ionicons name="checkmark-circle" size={18} color="#10B981" />}
                  <TouchableOpacity onPress={() => { setAudioUri(null); setAudioPath(null); setTranscribedText(''); }}><Ionicons name="close-circle" size={22} color="#EF4444" /></TouchableOpacity>
                </View>
              ) : isRecording ? (
                <View style={[s.audioCard, { borderColor: '#EF4444' }]}>
                  <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: '#EF4444' }} />
                  <Text style={{ color: '#EF4444', fontSize: 13, fontWeight: '700', flex: 1 }}>REC {Math.floor(recordDuration/60)}:{(recordDuration%60).toString().padStart(2,'0')}</Text>
                  <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#EF4444', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6 }} onPress={stopRecording}>
                    <Ionicons name="stop" size={14} color="#fff" />
                    <Text style={{ color: '#fff', fontSize: 12, fontWeight: '700', marginLeft: 4 }}>Stop</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <View style={{ gap: 8 }}>
                  <TouchableOpacity style={s.uploadBtn} onPress={pickAudio}>
                    <Ionicons name="cloud-upload" size={24} color="#06B6D4" /><Text style={s.uploadText}>Choose Audio File</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[s.uploadBtn, { backgroundColor: '#EF444415', borderColor: '#EF4444' }]} onPress={startRecording}>
                    <Ionicons name="mic" size={24} color="#EF4444" /><Text style={[s.uploadText, { color: '#EF4444' }]}>Record Audio</Text>
                  </TouchableOpacity>
                </View>
              )}
              {transcribing && (
                <View style={s.transcribeCard}><ActivityIndicator size="small" color="#F59E0B" /><Text style={s.transcribeText}>AI is transcribing audio...</Text></View>
              )}
              {transcribedText.length > 0 && (
                <View style={s.transcriptBox}>
                  <Text style={s.transcriptLabel}>Transcribed Script (editable):</Text>
                  <TextInput style={s.scriptInput} value={script || transcribedText} onChangeText={setScript} multiline maxLength={2000} />
                </View>
              )}
            </View>
          )}

          {/* Duration Selector */}
          <View style={s.section}>
            <Text style={s.sTitle}>Output Duration (optional)</Text>
            <Text style={s.hint}>Pick a target length, or leave default to match the video length.</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
              {[
                { label: 'Auto', v: null },
                { label: '2s', v: 2 }, { label: '5s', v: 5 }, { label: '10s', v: 10 },
                { label: '15s', v: 15 }, { label: '30s', v: 30 }, { label: '1 min', v: 60 }, { label: '2 min', v: 120 },
              ].map((d, i) => (
                <TouchableOpacity key={i} style={[{ backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, marginRight: 8, borderWidth: 1, borderColor: '#334155' }, targetDuration === d.v && { backgroundColor: '#06B6D4', borderColor: '#06B6D4' }]} onPress={() => setTargetDuration(d.v)}>
                  <Text style={[{ color: '#94A3B8', fontSize: 13, fontWeight: '600' }, targetDuration === d.v && { color: '#fff' }]}>{d.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Review & Create */}
          {/* Resolution + MH cost info */}
          <View style={{ marginBottom: 16 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: '#E2E8F0', marginBottom: 8 }}>Resolution</Text>
            <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
            {mhCap.costPerSec != null && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, paddingVertical: 8, paddingHorizontal: 10, backgroundColor: 'rgba(6,182,212,0.08)', borderWidth: 1, borderColor: 'rgba(6,182,212,0.3)', borderRadius: 10 }}>
                <Ionicons name="information-circle" size={14} color="#06B6D4" />
                <Text style={{ color: '#A5F3FC', fontSize: 12, fontWeight: '600', flex: 1 }}>
                  Re-dub pricing: 🪙 {mhCap.costPerSec}¢/sec · min billed {mhCap.minBilled}s ({mhCap.minCost} credits)
                </Text>
              </View>
            )}
          </View>

          <TouchableOpacity style={[s.startBtn, !canStart && { backgroundColor: '#334155' }]} onPress={() => setShowReview(true)} disabled={!canStart}>
            {processing ? <View style={s.startBtnI}><ActivityIndicator size="small" color="#fff" /><Text style={s.startBtnT}>Processing... {progress}%</Text></View>
            : <View style={s.startBtnI}><Ionicons name="eye" size={22} color="#fff" /><Text style={s.startBtnT}>Review & Re-dub</Text></View>}
          </TouchableOpacity>

          <View style={s.infoBox}>
            <Ionicons name="information-circle" size={18} color="#06B6D4" />
            <Text style={s.infoText}>AI extracts the face from your video and generates a new lip-synced version with your script or audio.</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Review Modal */}
      <Modal visible={showReview} animationType="slide" transparent onRequestClose={() => setShowReview(false)}>
        <View style={s.reviewOverlay}><View style={s.reviewSheet}>
          <View style={s.reviewHandle} />
          <Text style={s.reviewTitle}>Review Before Re-dubbing</Text>
          <ScrollView style={s.reviewBody}>
            <View style={s.reviewRow}><Text style={s.reviewLabel}>Video</Text><Text style={s.reviewValue}>{videoUri?.split('/').pop()}</Text></View>
            <View style={s.reviewRow}><Text style={s.reviewLabel}>Script Mode</Text><Text style={s.reviewValue}>{scriptMode === 'text' ? 'Typed Script' : 'Audio Upload'}</Text></View>
            <View style={s.reviewRow}><Text style={s.reviewLabel}>Character</Text><Text style={s.reviewValue}>{charType === 'male' ? 'Male' : 'Female'}</Text></View>
            <View style={s.reviewRow}><Text style={s.reviewLabel}>Voice</Text><Text style={s.reviewValue}>{findVoice(voiceId)?.name || voiceId}</Text></View>
            <View style={s.reviewScript}><Text style={s.reviewScriptLabel}>Script:</Text><Text style={s.reviewScriptText}>{script || transcribedText || '(audio file)'}</Text></View>
          </ScrollView>
          <View style={s.reviewActions}>
            <TouchableOpacity style={s.reviewEditBtn} onPress={() => setShowReview(false)}><Ionicons name="create" size={18} color="#06B6D4" /><Text style={s.reviewEditBtnT}>Edit</Text></TouchableOpacity>
            <TouchableOpacity style={s.reviewConfirmBtn} onPress={() => { setShowReview(false); startRedub(); }}><Ionicons name="checkmark-circle" size={18} color="#fff" /><Text style={s.reviewConfirmBtnT}>Confirm & Start</Text></TouchableOpacity>
          </View>
        </View></View>
      </Modal>
      <AuthGateModal
        visible={showAuthGate}
        onClose={() => setShowAuthGate(false)}
        reason="Video Re-dub"
        nextRoute="/redub"
      />
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' }, scroll: { padding: 20, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 16, gap: 8 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }, title: { fontSize: 22, fontWeight: 'bold', color: '#fff', flex: 1 },
  newBadge: { backgroundColor: '#06B6D4', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 }, newBadgeT: { color: '#fff', fontSize: 10, fontWeight: '900' },
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
  }, sTitle: { fontSize: 15, fontWeight: '600', color: '#E2E8F0', marginBottom: 6 },
  hint: { fontSize: 12, color: '#94A3B8', marginBottom: 8 },
  videoCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, borderWidth: 1, borderColor: '#06B6D440' },
  videoName: { flex: 1, color: '#E2E8F0', fontSize: 13 }, uploadPct: { color: '#06B6D4', fontSize: 10, marginTop: 2 },
  uploadBtn: { backgroundColor: '#1E293B', borderRadius: 12, padding: 20, alignItems: 'center', borderWidth: 1, borderColor: '#334155', borderStyle: 'dashed', gap: 8 },
  uploadText: { color: '#E2E8F0', fontSize: 14 },
  modeRow: { flexDirection: 'row', gap: 10 },
  modeChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  modeActive: { backgroundColor: '#06B6D4', borderColor: '#06B6D4' },
  modeText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  charChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  voiceChip: { backgroundColor: '#1E293B', borderRadius: 8, paddingVertical: 8, paddingHorizontal: 12, marginRight: 8, borderWidth: 1, borderColor: '#334155', alignItems: 'center' },
  voiceActive: { backgroundColor: '#06B6D4', borderColor: '#06B6D4' },
  voiceName: { color: '#E2E8F0', fontSize: 12, fontWeight: '600' }, voiceSub: { color: '#94A3B8', fontSize: 10 },
  scriptInput: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, color: '#fff', fontSize: 14, minHeight: 80, textAlignVertical: 'top', borderWidth: 1, borderColor: '#334155' },
  audioCard: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#1E293B', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#06B6D440' },
  audioName: { flex: 1, color: '#E2E8F0', fontSize: 13 },
  transcribeCard: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F59E0B10', borderRadius: 8, padding: 10, marginTop: 10, borderWidth: 1, borderColor: '#F59E0B30' },
  transcribeText: { color: '#F59E0B', fontSize: 13, fontWeight: '600' },
  transcriptBox: { marginTop: 12 },
  transcriptLabel: { color: '#10B981', fontSize: 13, fontWeight: '600', marginBottom: 6 },
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#06B6D440' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  progressTitle: { color: '#fff', fontSize: 14, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, borderRadius: 4, backgroundColor: '#06B6D4' }, progressPct: { fontSize: 13, fontWeight: 'bold', color: '#06B6D4', width: 36 },
  successBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#10B98110', borderRadius: 12, padding: 12, marginBottom: 14, borderWidth: 1, borderColor: '#10B98140', gap: 10 },
  successTitle: { color: '#10B981', fontSize: 15, fontWeight: '700' },
  viewBtn: { backgroundColor: '#10B981', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 6 }, viewBtnT: { color: '#fff', fontSize: 13, fontWeight: '700' },
  errBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444410', borderRadius: 10, padding: 12, marginBottom: 14 },
  errText: { color: '#EF4444', fontSize: 13, flex: 1 },
  startBtn: { backgroundColor: '#06B6D4', borderRadius: 14, padding: 18, alignItems: 'center', marginBottom: 14 },
  startBtnI: { flexDirection: 'row', alignItems: 'center', gap: 10 }, startBtnT: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
  infoBox: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: '#06B6D410', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#06B6D430' },
  infoText: { color: '#94A3B8', fontSize: 12, flex: 1, lineHeight: 18 },
  // Review Modal
  reviewOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  reviewSheet: { backgroundColor: '#1E293B', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '70%', paddingBottom: 30 },
  reviewHandle: { width: 40, height: 4, backgroundColor: '#475569', borderRadius: 2, alignSelf: 'center', marginTop: 12, marginBottom: 8 },
  reviewTitle: { fontSize: 18, fontWeight: 'bold', color: '#fff', textAlign: 'center', marginBottom: 12 },
  reviewBody: { paddingHorizontal: 20 },
  reviewRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#33415530' },
  reviewLabel: { color: '#94A3B8', fontSize: 13 }, reviewValue: { color: '#E2E8F0', fontSize: 13, fontWeight: '600', maxWidth: '60%', textAlign: 'right' },
  reviewScript: { backgroundColor: '#0F172A', borderRadius: 8, padding: 10, marginTop: 10 },
  reviewScriptLabel: { color: '#06B6D4', fontSize: 12, fontWeight: '700', marginBottom: 4 },
  reviewScriptText: { color: '#E2E8F0', fontSize: 13 },
  reviewActions: { flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingTop: 16 },
  reviewEditBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#334155', borderRadius: 12, padding: 14 },
  reviewEditBtnT: { color: '#06B6D4', fontSize: 15, fontWeight: '700' },
  reviewConfirmBtn: { flex: 2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#06B6D4', borderRadius: 12, padding: 14 },
  reviewConfirmBtnT: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
