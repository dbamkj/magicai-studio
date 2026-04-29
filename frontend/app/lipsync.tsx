import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  TextInput, Image, ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { Audio } from 'expo-av';
import axios from 'axios';
import { uploadImageFile } from '../src/uploadHelper';
import VoicePicker from '../src/VoicePicker';
import ResolutionPicker from '../src/ResolutionPicker';
import VoiceStylePicker from '../src/VoiceStylePicker';
import PauseChips from '../src/PauseChips';
import { useTierGuard } from '../src/useTierGuard';
import { useMhCapabilities } from '../src/useMhCapabilities';
import { VOICE_LIBRARY, findVoice } from '../src/voices';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const ALL_VOICES = VOICE_LIBRARY;

const ASPECT_RATIOS = [
  { value: '16:9', label: '16:9', desc: 'Landscape' },
  { value: '9:16', label: '9:16', desc: 'Portrait' },
];

interface CharacterImage {
  id: string; uri: string; didUrl: string | null; uploading: boolean; uploaded: boolean;
}
interface DialogueLine {
  id: string; characterIndex: number; text: string;
}

export default function LipSyncScreen() {
  const router = useRouter();
  const tier = useTierGuard();
  const params = useLocalSearchParams<{ prefill?: string; edit_of?: string; prefill_image?: string; prefill_meta?: string }>();
  const [editingOf, setEditingOf] = useState<string | null>(null);
  const [lipsyncMode, setLipsyncMode] = useState<'images_only' | 'ref_video_only' | 'ref_video_plus_images'>('images_only');
  const [targetDuration, setTargetDuration] = useState<number | null>(null);
  // MH capability: lip_sync feature. Duration is usually auto-derived from
  // audio/script length but we still show option chips with real MH pricing.
  const mhCap = useMhCapabilities('lip_sync');
  const [characters, setCharacters] = useState<CharacterImage[]>([]);
  const [dialogueLines, setDialogueLines] = useState<DialogueLine[]>([{ id: '1', characterIndex: 0, text: '' }]);
  const [voiceIds, setVoiceIds] = useState<Record<number, string>>({});
  const getVoiceForChar = (idx: number) => voiceIds[idx] || (idx % 2 === 0 ? 'hi-IN-SwaraNeural' : 'en-US-GuyNeural');
  const [audioMode, setAudioMode] = useState<'tts' | 'audio'>('tts');
  const [audioUri, setAudioUri] = useState<string | null>(null);
  const [audioPath, setAudioPath] = useState<string | null>(null);
  const [charAudios, setCharAudios] = useState<Record<number, { uri: string; path: string | null; uploading: boolean; source?: 'file' | 'record' }>>({});
  const [recordingCharIdx, setRecordingCharIdx] = useState<number | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const recordTimerRef = useRef<any>(null);
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [resolution, setResolution] = useState<'480p' | '720p' | '1080p'>('720p');
  const [voiceStyle, setVoiceStyle] = useState<string | null>(null); // Sprint 2
  const [voiceRate, setVoiceRate] = useState<string | null>(null); // Sprint 2 Phase B
  const [voicePitch, setVoicePitch] = useState<string | null>(null); // Sprint 2 Phase B
  const [activeCharTab, setActiveCharTab] = useState(0);
  const [showReview, setShowReview] = useState(false);
  // Reference video
  const [refVideoUri, setRefVideoUri] = useState<string | null>(null);
  const [refVideoPath, setRefVideoPath] = useState<string | null>(null);
  const [refFrames, setRefFrames] = useState<any[]>([]);
  const [refTranscript, setRefTranscript] = useState('');
  const [refUploading, setRefUploading] = useState(false);
  const [refDiarized, setRefDiarized] = useState<any[]>([]);
  // Processing state
  const [processing, setProcessing] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultStatus, setResultStatus] = useState<'none' | 'completed' | 'failed'>('none');
  const [resultError, setResultError] = useState('');
  const pollRef = useRef<any>(null);

  // Polling for progress
  useEffect(() => {
    if (projectId && processing) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
          setProgress(r.data.progress || 0);
          if (r.data.status === 'completed' || r.data.status === 'failed') {
            clearInterval(pollRef.current);
            setProcessing(false);
            setResultStatus(r.data.status === 'completed' ? 'completed' : 'failed');
            if (r.data.status === 'failed') setResultError(r.data.error_message || 'Processing failed');
          }
        } catch (e) {}
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId, processing]);

  // Sprint 1 — prefill from /projects → doEdit
  // Phase 4E — also handle prefill_image (from cartoon-avatar "Animate to Video" CTA)
  useEffect(() => {
    // Phase 4E: simple image-only prefill (from cartoon-avatar deep link)
    if (params.prefill_image) {
      try {
        const url = String(params.prefill_image);
        setLipsyncMode('images_only');
        setCharacters([{ id: 'prefill_cartoon', uri: url, didUrl: url, uploading: false, uploaded: true } as any]);
      } catch {}
    }
    if (!params.prefill) return;
    try {
      const p = JSON.parse(String(params.prefill));
      if (params.edit_of) setEditingOf(String(params.edit_of));
      if (p.mode) setLipsyncMode(p.mode);
      if (p.aspect_ratio) setAspectRatio(p.aspect_ratio);
      if (p.resolution) setResolution(p.resolution);
      if (p.voice_style) setVoiceStyle(p.voice_style);
      if (p.target_duration) setTargetDuration(p.target_duration);
      if (p.voice_ids) setVoiceIds(p.voice_ids);
      // Reuse character image_urls as already-uploaded (didUrl)
      if (Array.isArray(p.image_urls) && p.image_urls.length > 0) {
        const chars: CharacterImage[] = p.image_urls.map((url: string, i: number) => ({
          id: `prefill_char_${i}`, uri: url, didUrl: url, uploading: false, uploaded: true,
        }));
        setCharacters(chars);
      }
      // Reuse ref video path
      if (p.ref_video_path) {
        setRefVideoPath(p.ref_video_path);
        setRefVideoUri(`${BACKEND_URL}${p.ref_video_path}`);
      }
      // Reuse dialogue lines
      if (Array.isArray(p.dialogue_lines) && p.dialogue_lines.length > 0) {
        const lines: DialogueLine[] = p.dialogue_lines.map((dl: any, idx: number) => ({
          id: `dl_${idx}`, characterIndex: dl.character_index || 0, text: dl.text || '',
        }));
        setDialogueLines(lines.length > 0 ? lines : [{ id: '1', characterIndex: 0, text: '' }]);
      }
      // Reuse global audio
      if (p.audio_url) {
        setAudioPath(p.audio_url);
        setAudioMode('audio');
      }

      // Session 31 — Auto-import template media from Inspiration
      // If the user came from a template with a preview VIDEO, download it via
      // /api/upload-from-url and pre-set as the reference video + upload the
      // thumbnail as the first character image.
      const importTemplateMedia = async () => {
        const token = (typeof window !== 'undefined' && window.localStorage)
          ? window.localStorage.getItem('magicai_jwt_v1') : null;
        const hdr = token ? { Authorization: `Bearer ${token}` } : {};
        // 1) Reference video from preview_url
        if (p.template_preview_url) {
          try {
            const url = String(p.template_preview_url).startsWith('http')
              ? p.template_preview_url : `${BACKEND_URL}${p.template_preview_url}`;
            const r = await axios.post(`${BACKEND_URL}/api/upload-from-url`,
              { url, filename: 'tpl_ref.mp4' },
              { timeout: 45000, headers: hdr });
            const path = r.data?.file_path;
            const serve = r.data?.url;
            if (path) {
              setRefVideoPath(path);
              setRefVideoUri(serve?.startsWith('http') ? serve : `${BACKEND_URL}${serve}`);
            }
          } catch (e) {
            // fall through silently — user can manually upload
          }
        }
        // 2) Character image from thumbnail_url
        if (p.template_thumbnail_url) {
          try {
            const url = String(p.template_thumbnail_url).startsWith('http')
              ? p.template_thumbnail_url : `${BACKEND_URL}${p.template_thumbnail_url}`;
            const r = await axios.post(`${BACKEND_URL}/api/upload-from-url`,
              { url, filename: 'tpl_char.jpg' },
              { timeout: 45000, headers: hdr });
            const servePath = r.data?.url;
            if (servePath) {
              const newChar: CharacterImage = {
                id: `tpl_char_${Date.now()}`,
                uri: `${BACKEND_URL}${servePath}`,
                didUrl: servePath,
                uploading: false,
                uploaded: true,
              };
              setCharacters(prev => [...prev.filter(c => c.id.startsWith('prefill_') ? false : true), newChar]);
            }
          } catch (e) {}
        }
      };
      if (p.template_preview_url || p.template_thumbnail_url) {
        importTemplateMedia();
      }
    } catch (e) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ========= CHARACTER IMAGE FUNCTIONS =========
  const addCharacter = async (fromCamera: boolean) => {
    try {
      const { status } = fromCamera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') { Alert.alert('Permission Required'); return; }
      const result = fromCamera ? await ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.8 }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.8 });
      if (!result.canceled && result.assets[0]) {
        const nc: CharacterImage = { id: Date.now().toString(), uri: result.assets[0].uri, didUrl: null, uploading: true, uploaded: false };
        setCharacters(prev => [...prev, nc]);
        try {
          const data = await uploadImageFile(result.assets[0].uri, '/api/upload-image');
          setCharacters(prev => prev.map(c => c.id === nc.id ? { ...c, didUrl: data.url, uploading: false, uploaded: true } : c));
        } catch (e) {
          Alert.alert('Upload Error'); setCharacters(prev => prev.filter(c => c.id !== nc.id));
        }
      }
    } catch (e) { Alert.alert('Error', 'Failed to pick image'); }
  };

  const removeCharacter = (charId: string) => {
    const idx = characters.findIndex(c => c.id === charId);
    setCharacters(prev => prev.filter(c => c.id !== charId));
    setDialogueLines(prev => prev.map(line => {
      if (line.characterIndex === idx) return { ...line, characterIndex: 0 };
      if (line.characterIndex > idx) return { ...line, characterIndex: line.characterIndex - 1 };
      return line;
    }));
    if (activeCharTab >= characters.length - 1) setActiveCharTab(Math.max(0, characters.length - 2));
  };

  // ========= AUDIO UPLOAD =========
  const pickAudio = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: 'audio/*' });
      if (!result.canceled && result.assets && result.assets[0]) {
        setAudioUri(result.assets[0].uri);
        // Upload audio
        const fd = new FormData();
        if (Platform.OS === 'web') {
          const resp = await fetch(result.assets[0].uri);
          const blob = await resp.blob();
          fd.append('file', new File([blob], result.assets[0].name || 'audio.mp3', { type: result.assets[0].mimeType || 'audio/mp3' }));
        } else {
          fd.append('file', { uri: result.assets[0].uri, name: result.assets[0].name || 'audio.mp3', type: result.assets[0].mimeType || 'audio/mp3' } as any);
        }
        const r = await axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30000 });
        setAudioPath(r.data.file_path);
      }
    } catch (e) { Alert.alert('Error', 'Failed to pick audio file'); }
  };

  // ========= DIALOGUE =========
  const addDialogueLine = (charIdx?: number) => {
    setDialogueLines(prev => [...prev, { id: Date.now().toString(), characterIndex: charIdx ?? activeCharTab, text: '' }]);
  };
  const updateDialogueLine = (lineId: string, field: string, value: any) => {
    setDialogueLines(prev => prev.map(l => l.id === lineId ? { ...l, [field]: value } : l));
  };
  const removeDialogueLine = (lineId: string) => {
    if (dialogueLines.length <= 1) return;
    setDialogueLines(prev => prev.filter(l => l.id !== lineId));
  };

  // ========= CREATE =========
  const createLipSync = async () => {
    const uploadedChars = characters.filter(c => c.uploaded && c.didUrl);
    const hasCharAudios = Object.values(charAudios).some(a => a?.path);
    const filledLines = dialogueLines.filter(l => l.text.trim());

    // Build unified dialogue list - TTS lines + per-char audios merged in order
    const mergeDialogue = (): any[] => {
      const lines: any[] = [];
      // First: TTS text lines in their original order
      filledLines.forEach(l => {
        lines.push({
          character_index: Math.min(l.characterIndex, Math.max(uploadedChars.length - 1, 0)),
          text: l.text,
        });
      });
      // Then: per-character uploaded/recorded audios appended
      uploadedChars.forEach((_, idx) => {
        if (charAudios[idx]?.path) {
          lines.push({ character_index: idx, text: '', audio_url: charAudios[idx].path });
        }
      });
      return lines;
    };

    // Validation per mode
    if (lipsyncMode === 'images_only') {
      if (uploadedChars.length === 0) { Alert.alert('Missing Characters', 'Add at least one character image'); return; }
      const hasAnyAudioSource = filledLines.length > 0 || hasCharAudios || !!audioPath;
      if (!hasAnyAudioSource) { Alert.alert('Missing Audio', 'Add dialogue text, upload/record audio, or upload a global audio file'); return; }
    } else if (lipsyncMode === 'ref_video_only') {
      if (!refVideoPath) { Alert.alert('Missing Reference Video', 'Upload a reference video first'); return; }
      // Characters are optional; dialogues can be distributed across them (no image required)
      const hasAnyAudioSource = filledLines.length > 0 || hasCharAudios || !!audioPath || !!refTranscript.trim();
      if (!hasAnyAudioSource) { Alert.alert('Missing Audio', 'Add a dialogue, use the extracted transcript, or upload audio'); return; }
    } else { // ref_video_plus_images
      if (!refVideoPath) { Alert.alert('Missing Reference Video', 'Upload a reference video first'); return; }
      if (uploadedChars.length === 0) { Alert.alert('Missing Characters', 'Add character image(s) to use for lip sync'); return; }
      const hasAnyAudioSource = filledLines.length > 0 || hasCharAudios || !!audioPath;
      if (!hasAnyAudioSource) { Alert.alert('Missing Audio', 'Add dialogue text or record/upload audio'); return; }
    }

    try {
      // 🔒 Tier gate: Lip-sync requires Creator+
      if (!tier.requireFeature('talking_avatar_lipsync', 'Talking Avatar (lip-sync)')) {
        return;
      }
      setProcessing(true); setProgress(0); setResultStatus('none');
      const payload: any = {
        image_urls: lipsyncMode === 'ref_video_only' ? [] : uploadedChars.map(c => c.didUrl),
        voice_ids: voiceIds,
        aspect_ratio: aspectRatio,
        mode: lipsyncMode,
        resolution,
        voice_style: voiceStyle || undefined,
        voice_rate: voiceRate || undefined,
        voice_pitch: voicePitch || undefined,
        parent_id: editingOf || undefined,
      };
      if (lipsyncMode !== 'images_only' && refVideoPath) payload.ref_video_path = refVideoPath;
      if (targetDuration) payload.target_duration = targetDuration;

      // Unified dialogue: merge TTS + recorded/uploaded per-char audios + global
      if (lipsyncMode === 'ref_video_only') {
        // For ref_video_only, if TTS lines exist use them, else use transcript/global audio
        if (filledLines.length > 0) {
          payload.dialogue_lines = filledLines.map(l => ({ character_index: 0, text: l.text }));
        } else if (refTranscript.trim()) {
          payload.dialogue_lines = [{ character_index: 0, text: refTranscript.trim() }];
        } else if (audioPath) {
          payload.dialogue_lines = [{ character_index: 0, text: '', audio_url: audioPath }];
          payload.audio_url = audioPath;
        } else {
          payload.dialogue_lines = [];
        }
      } else {
        const merged = mergeDialogue();
        // If nothing in merged but global audioPath set, use it
        if (merged.length === 0 && audioPath) {
          merged.push({ character_index: 0, text: '', audio_url: audioPath });
          payload.audio_url = audioPath;
        }
        payload.dialogue_lines = merged;
      }
      const r = await axios.post(`${BACKEND_URL}/api/create-lipsync`, payload);
      setProjectId(r.data.project_id);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to create lip sync');
      setProcessing(false);
    }
  };

  // Reset all state (Clear Cache button)
  const resetAll = () => {
    Alert.alert('Clear & Reset', 'This will clear all uploaded characters, audio, and dialogue. Continue?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Clear All', style: 'destructive', onPress: () => {
        // Stop any recording
        if (recordingCharIdx !== null) cancelRecording();
        setCharacters([]);
        setDialogueLines([{ id: Date.now().toString(), characterIndex: 0, text: '' }]);
        setCharAudios({});
        setAudioUri(null); setAudioPath(null);
        setRefVideoUri(null); setRefVideoPath(null); setRefFrames([]); setRefTranscript('');
        setProjectId(null); setProcessing(false); setProgress(0); setResultStatus('none'); setResultError('');
        setActiveCharTab(0); setVoiceIds({}); setAudioMode('tts');
      }},
    ]);
  };

  const dismissResult = () => { setResultStatus('none'); setResultError(''); };
  const viewProjects = () => { setResultStatus('none'); router.push('/projects'); };

  const pickRefVideo = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['videos'], quality: 0.5 });
    if (!r.canceled && r.assets[0]) {
      setRefVideoUri(r.assets[0].uri); setRefUploading(true); setRefTranscript(''); setRefVideoPath(null);
      try {
        const fd = new FormData();
        if (Platform.OS === 'web') {
          const resp = await fetch(r.assets[0].uri);
          const blob = await resp.blob();
          fd.append('file', new File([blob], 'ref_video.mp4', { type: 'video/mp4' }));
        } else {
          fd.append('file', { uri: r.assets[0].uri, name: 'ref_video.mp4', type: 'video/mp4' } as any);
        }
        const res = await axios.post(`${BACKEND_URL}/api/extract-frames`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 180000 });
        setRefFrames(res.data.frames || []);
        if (res.data.video_path) setRefVideoPath(res.data.video_path);
        if (res.data.transcript) setRefTranscript(res.data.transcript);
        setRefDiarized(res.data.diarized_segments || []);
      } catch (e) { Alert.alert('Error', 'Could not process reference video'); }
      finally { setRefUploading(false); }
    }
  };

  // Auto-populate dialogue lines from the diarized transcript (per-speaker, per-timestamp)
  const applyTranscriptToDialogue = () => {
    const MAX_AUTO_SPEAKERS = 4;
    // In ref_video_plus_images: prefer the user's existing character count
    // In ref_video_only: use detected speakers (capped at MAX_AUTO_SPEAKERS)
    if (refDiarized && refDiarized.length > 0) {
      let speakerIds = Array.from(new Set(refDiarized.map((s: any) => s.speaker ?? 1))).sort((a: any, b: any) => a - b);
      const rawCount = speakerIds.length;
      // Cap speakers to MAX_AUTO_SPEAKERS (safety net for Gemini hallucinations)
      if (speakerIds.length > MAX_AUTO_SPEAKERS) {
        speakerIds = speakerIds.slice(0, MAX_AUTO_SPEAKERS);
      }
      // In ref_video_plus_images, target is user's existing char count; otherwise detected
      const userCharCount = characters.length;
      const targetCount = lipsyncMode === 'ref_video_plus_images' && userCharCount > 0
        ? userCharCount
        : speakerIds.length;
      // Auto-create character slots if we need more (ref_video_only case)
      if (characters.length < targetCount) {
        const toAdd = targetCount - characters.length;
        const newChars = Array.from({ length: toAdd }, (_, i) => ({
          id: `auto-${Date.now()}-${i}`,
          uri: '',
          didUrl: null,
          uploading: false,
          uploaded: false,
        }));
        setCharacters(prev => [...prev, ...newChars]);
      }
      // Map every diarized segment to a char index (complete dialogue coverage)
      const newLines = refDiarized.map((seg: any, i: number) => {
        const rawSpk = seg.speaker ?? 1;
        const idxInSpeakerIds = speakerIds.indexOf(rawSpk);
        // If detected speaker is valid, map it proportionally to target count
        // else use round-robin fallback so all segments get a character
        let charIdx: number;
        if (idxInSpeakerIds >= 0 && speakerIds.length > 0) {
          charIdx = idxInSpeakerIds % targetCount;
        } else {
          charIdx = i % targetCount;
        }
        return { id: (Date.now() + i).toString(), characterIndex: charIdx, text: String(seg.text || '').trim() };
      }).filter((l: any) => l.text);
      if (newLines.length > 0) {
        setDialogueLines(newLines);
        setActiveCharTab(0);
        setAudioMode('tts');
        const noteParts: string[] = [];
        if (rawCount > MAX_AUTO_SPEAKERS) noteParts.push(`auto-clustered from ${rawCount} detected voices`);
        if (lipsyncMode === 'ref_video_plus_images' && userCharCount > 0 && speakerIds.length !== userCharCount) {
          noteParts.push(`distributed across your ${userCharCount} characters`);
        }
        const note = noteParts.length ? ` (${noteParts.join(', ')})` : '';
        Alert.alert('Script Applied', `${newLines.length} dialogue line${newLines.length === 1 ? '' : 's'} across ${targetCount} speaker${targetCount === 1 ? '' : 's'}${note}.`);
        return;
      }
    }
    // Fallback: split plain transcript on punctuation (no diarization available)
    if (!refTranscript.trim()) return;
    const rawLines = refTranscript.split(/[.!?।\n]+/).map(s => s.trim()).filter(Boolean);
    if (rawLines.length === 0) return;
    const numChars = Math.max(characters.length, 1);
    const newLines = rawLines.map((text, i) => ({
      id: (Date.now() + i).toString(),
      characterIndex: i % numChars,
      text,
    }));
    setDialogueLines(newLines);
    setActiveCharTab(0);
    setAudioMode('tts');
    Alert.alert('Script Applied', `${newLines.length} dialogue line${newLines.length === 1 ? '' : 's'} loaded${numChars > 1 ? ` across ${numChars} speakers` : ''}. Edit below.`);
  };

  const pickCharAudio = async (charIdx: number) => {
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: 'audio/*' });
      if (!result.canceled && result.assets && result.assets[0]) {
        setCharAudios(prev => ({ ...prev, [charIdx]: { uri: result.assets[0].uri, path: null, uploading: true, source: 'file' } }));
        const fd = new FormData();
        if (Platform.OS === 'web') {
          const resp = await fetch(result.assets[0].uri);
          const blob = await resp.blob();
          fd.append('file', new File([blob], result.assets[0].name || 'audio.mp3', { type: result.assets[0].mimeType || 'audio/mp3' }));
        } else {
          fd.append('file', { uri: result.assets[0].uri, name: result.assets[0].name || 'audio.mp3', type: result.assets[0].mimeType || 'audio/mp3' } as any);
        }
        const r = await axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
        setCharAudios(prev => ({ ...prev, [charIdx]: { ...prev[charIdx], path: r.data.file_path, uploading: false } }));
      }
    } catch (e) { Alert.alert('Error', 'Failed to upload audio'); }
  };

  // ========= IN-APP AUDIO RECORDING =========
  const startRecording = async (charIdx: number) => {
    try {
      // Prevent starting another if one is in progress
      if (recordingCharIdx !== null) {
        Alert.alert('Recording in progress', 'Please stop the current recording first.');
        return;
      }
      const perm = await Audio.requestPermissionsAsync();
      if (perm.status !== 'granted') {
        Alert.alert('Microphone Permission', 'Please grant microphone access to record audio.');
        return;
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await recording.startAsync();
      recordingRef.current = recording;
      setRecordingCharIdx(charIdx);
      setRecordingDuration(0);
      // Start duration timer
      recordTimerRef.current = setInterval(() => {
        setRecordingDuration(d => d + 1);
      }, 1000);
    } catch (e: any) {
      console.error('Recording error:', e);
      Alert.alert('Recording Error', e?.message || 'Could not start recording.');
      setRecordingCharIdx(null);
    }
  };

  const stopRecording = async (charIdx: number) => {
    try {
      const rec = recordingRef.current;
      if (!rec) { setRecordingCharIdx(null); return; }
      if (recordTimerRef.current) { clearInterval(recordTimerRef.current); recordTimerRef.current = null; }
      await rec.stopAndUnloadAsync();
      const uri = rec.getURI();
      recordingRef.current = null;
      const finalDuration = recordingDuration;
      setRecordingCharIdx(null);
      setRecordingDuration(0);
      if (!uri) { Alert.alert('Error', 'No audio recorded.'); return; }
      if (finalDuration < 1) { Alert.alert('Too short', 'Please record at least 1 second of audio.'); return; }
      // Mark uploading
      setCharAudios(prev => ({ ...prev, [charIdx]: { uri, path: null, uploading: true, source: 'record' } }));
      // Upload
      const fd = new FormData();
      const fileName = `record_char${charIdx + 1}_${Date.now()}.m4a`;
      if (Platform.OS === 'web') {
        const resp = await fetch(uri);
        const blob = await resp.blob();
        fd.append('file', new File([blob], fileName, { type: blob.type || 'audio/webm' }));
      } else {
        fd.append('file', { uri, name: fileName, type: 'audio/m4a' } as any);
      }
      const r = await axios.post(`${BACKEND_URL}/api/upload-audio`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
      setCharAudios(prev => ({ ...prev, [charIdx]: { ...prev[charIdx], path: r.data.file_path, uploading: false } }));
    } catch (e: any) {
      console.error('Stop recording error:', e);
      Alert.alert('Upload Error', e?.message || 'Failed to save recording.');
      setCharAudios(prev => { const n = { ...prev }; delete n[charIdx]; return n; });
      setRecordingCharIdx(null);
    }
  };

  const cancelRecording = async () => {
    try {
      if (recordTimerRef.current) { clearInterval(recordTimerRef.current); recordTimerRef.current = null; }
      const rec = recordingRef.current;
      if (rec) {
        try { await rec.stopAndUnloadAsync(); } catch (_) {}
      }
      recordingRef.current = null;
      setRecordingCharIdx(null);
      setRecordingDuration(0);
    } catch (e) {}
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recordTimerRef.current) clearInterval(recordTimerRef.current);
      if (recordingRef.current) {
        recordingRef.current.stopAndUnloadAsync().catch(() => {});
      }
    };
  }, []);

  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const allCharsUploaded = characters.length > 0 && characters.every(c => c.uploaded);
  const hasCharAudios = Object.values(charAudios).some(a => a?.path);
  const hasDialogue = audioMode === 'audio' ? (!!audioPath || hasCharAudios) : (dialogueLines.some(l => l.text.trim()) || (lipsyncMode === 'ref_video_only' && !!refTranscript.trim()));
  const charReq = lipsyncMode === 'ref_video_only' ? true : allCharsUploaded;
  const refReq = lipsyncMode === 'images_only' ? true : !!refVideoPath;
  const canCreate = charReq && refReq && hasDialogue && !processing && recordingCharIdx === null;

  // Lines for active character tab
  const charLines = dialogueLines.filter(l => l.characterIndex === activeCharTab);

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
          <GlassHeader
            icon="mic"
            title="Lip Sync"
            subtitle="Animate any face with voice or audio"
            onBack={() => router.back()}
            right={
              <TouchableOpacity onPress={resetAll} accessibilityLabel="Clear & Reset" style={{ width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="refresh" size={20} color="#EF4444" />
              </TouchableOpacity>
            }
            style={{ marginBottom: 16, paddingHorizontal: 0 }}
          />

          {editingOf && (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(139,92,246,0.12)', borderWidth: 1, borderColor: 'rgba(139,92,246,0.4)', padding: 10, borderRadius: 10, marginBottom: 12 }}>
              <Ionicons name="git-branch" size={16} color="#A78BFA" />
              <Text style={{ color: '#A78BFA', fontSize: 13, flex: 1 }}>Editing previous version — inputs carried over. Tweak and re-run.</Text>
            </View>
          )}

          {/* Sprint 2 — Voice Style */}
          <View style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)', marginBottom: 12 }}>
            <VoiceStylePicker
              selectedId={voiceStyle}
              onSelect={setVoiceStyle}
              customRate={voiceRate}
              customPitch={voicePitch}
              onCustomRate={setVoiceRate}
              onCustomPitch={setVoicePitch}
            />
            <PauseChips
              label="Tap to append pause to the latest dialogue line"
              onInsert={(tag) => setDialogueLines(prev => {
                if (prev.length === 0) return [{ id: '1', characterIndex: 0, text: tag }];
                const out = [...prev];
                const last = out[out.length - 1];
                out[out.length - 1] = { ...last, text: (last.text || '') + (last.text && !last.text.endsWith(' ') ? ' ' : '') + tag };
                return out;
              })}
            />
          </View>

          {/* Result Banner */}
          {resultStatus === 'completed' && (
            <View style={s.resultBanner}>
              <Ionicons name="checkmark-circle" size={24} color="#10B981" />
              <View style={{ flex: 1 }}><Text style={s.resultTitle}>All segments ready!</Text><Text style={s.resultDesc}>View in My Projects</Text></View>
              <TouchableOpacity style={s.resultViewBtn} onPress={viewProjects}><Text style={s.resultViewBtnT}>View</Text></TouchableOpacity>
              <TouchableOpacity onPress={dismissResult}><Ionicons name="close" size={20} color="#94A3B8" /></TouchableOpacity>
            </View>
          )}
          {resultStatus === 'failed' && (
            <View style={[s.resultBanner, { borderColor: '#EF444440', backgroundColor: '#EF444410' }]}>
              <Ionicons name="close-circle" size={24} color="#EF4444" />
              <View style={{ flex: 1 }}><Text style={[s.resultTitle, { color: '#EF4444' }]}>Failed</Text><Text style={s.resultDesc} numberOfLines={2}>{resultError}</Text></View>
              <TouchableOpacity onPress={dismissResult}><Ionicons name="close" size={20} color="#94A3B8" /></TouchableOpacity>
            </View>
          )}

          {/* Progress Bar */}
          {processing && (
            <View style={s.progressCard}>
              <View style={s.progressHeader}><ActivityIndicator size="small" color="#8B5CF6" /><Text style={s.progressTitle}>Generating lip sync...</Text></View>
              <View style={s.progressBarWrap}><View style={s.progressBarBg}><View style={[s.progressBarFill, { width: `${progress}%` }]} /></View><Text style={s.progressPct}>{progress}%</Text></View>
            </View>
          )}

          {/* Mode Selector (NEW) */}
          <View style={s.section}>
            <Text style={s.sectionTitle}>Mode</Text>
            <Text style={s.hint}>Choose how you want to make your lip sync.</Text>
            <View style={{ gap: 8 }}>
              <TouchableOpacity style={[s.modeOption, lipsyncMode === 'images_only' && s.modeOptionActive]} onPress={() => setLipsyncMode('images_only')}>
                <Ionicons name="images" size={20} color={lipsyncMode === 'images_only' ? '#fff' : '#94A3B8'} />
                <View style={{ flex: 1 }}>
                  <Text style={[s.modeOptionTitle, lipsyncMode === 'images_only' && { color: '#fff' }]}>Images Only</Text>
                  <Text style={[s.modeOptionDesc, lipsyncMode === 'images_only' && { color: '#E2E8F0' }]}>Upload character images + dialogues/audio → merged video</Text>
                </View>
              </TouchableOpacity>
              <TouchableOpacity style={[s.modeOption, lipsyncMode === 'ref_video_plus_images' && s.modeOptionActive]} onPress={() => setLipsyncMode('ref_video_plus_images')}>
                <Ionicons name="git-merge" size={20} color={lipsyncMode === 'ref_video_plus_images' ? '#fff' : '#94A3B8'} />
                <View style={{ flex: 1 }}>
                  <Text style={[s.modeOptionTitle, lipsyncMode === 'ref_video_plus_images' && { color: '#fff' }]}>Ref Video + Images</Text>
                  <Text style={[s.modeOptionDesc, lipsyncMode === 'ref_video_plus_images' && { color: '#E2E8F0' }]}>Use ref video to auto-extract dialogues, then sync your character images</Text>
                </View>
              </TouchableOpacity>
              <View style={[s.modeOption, { borderStyle: 'dashed', opacity: 0.7 }]}>
                <Ionicons name="film" size={20} color="#94A3B8" />
                <View style={{ flex: 1 }}>
                  <Text style={[s.modeOptionTitle, { fontSize: 13 }]}>Re-dub a video? ➜ Use Video Re-dub</Text>
                  <Text style={s.modeOptionDesc}>The "Reference Video Only" flow has moved. Single or Multi-Character re-dubs are now in the Video Re-dub screen.</Text>
                </View>
                <TouchableOpacity style={{ backgroundColor: '#06B6D4', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6 }} onPress={() => router.push('/redub')}>
                  <Text style={{ color: '#fff', fontSize: 11, fontWeight: '700' }}>Open</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>

          {/* Reference Video (shown in ref_video_only and ref_video_plus_images modes) */}
          {lipsyncMode !== 'images_only' && (
          <View style={s.section}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <Text style={s.sectionTitle}>Reference Video</Text>
              <View style={{ backgroundColor: '#EF4444', borderRadius: 4, paddingHorizontal: 6, paddingVertical: 1 }}><Text style={{ color: '#fff', fontSize: 9, fontWeight: '900' }}>NEW</Text></View>
            </View>
            <Text style={s.hint}>Upload a reference video to auto-detect characters and suggest dialogues.</Text>
            {refVideoUri ? (
              <View style={{ backgroundColor: '#1E293B', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#8B5CF640' }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <Ionicons name="videocam" size={20} color="#8B5CF6" />
                  <Text style={{ color: '#E2E8F0', flex: 1, fontSize: 13 }}>{refVideoUri.split('/').pop()}</Text>
                  {refUploading && <ActivityIndicator size="small" color="#8B5CF6" />}
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
                {refTranscript.length > 0 && (
                  <View style={{ marginTop: 10, backgroundColor: '#0F172A', borderRadius: 8, padding: 10, borderWidth: 1, borderColor: '#10B98130' }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ color: '#10B981', fontSize: 12, fontWeight: '700' }}>Extracted Script/Lyrics:</Text>
                      <TouchableOpacity
                        onPress={async () => { await Clipboard.setStringAsync(refTranscript); Alert.alert('Copied', 'Transcript copied to clipboard.'); }}
                        style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#10B98120', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 }}>
                        <Ionicons name="copy-outline" size={14} color="#10B981" />
                        <Text style={{ color: '#10B981', fontSize: 11, fontWeight: '700' }}>Copy</Text>
                      </TouchableOpacity>
                    </View>
                    <Text style={{ color: '#E2E8F0', fontSize: 13, lineHeight: 20 }} selectable={true}>{refTranscript}</Text>
                    <TouchableOpacity
                      onPress={applyTranscriptToDialogue}
                      style={{ marginTop: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#10B981', borderRadius: 8, paddingVertical: 10 }}>
                      <Ionicons name="chatbubbles" size={16} color="#fff" />
                      <Text style={{ color: '#fff', fontSize: 13, fontWeight: '700' }}>
                        Use as Dialogue{characters.length > 1 ? ` (split across ${characters.length} chars)` : ''}
                      </Text>
                    </TouchableOpacity>
                    {characters.length === 0 && lipsyncMode !== 'ref_video_only' && (
                      <Text style={{ color: '#94A3B8', fontSize: 11, textAlign: 'center', marginTop: 6 }}>
                        💡 Add characters first, then tap above to auto-distribute lines.
                      </Text>
                    )}
                  </View>
                )}
                {refUploading && (
                  <View style={{ marginTop: 8, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <ActivityIndicator size="small" color="#8B5CF6" />
                    <Text style={{ color: '#94A3B8', fontSize: 12 }}>Extracting frames & transcribing audio...</Text>
                  </View>
                )}
              </View>
            ) : (
              <TouchableOpacity style={s.addBtn} onPress={pickRefVideo}>
                <Ionicons name="film" size={22} color="#8B5CF6" /><Text style={s.addBtnText}>Upload Reference Video</Text>
              </TouchableOpacity>
            )}
          </View>
          )}

          {/* Step 2: Characters (visible in ALL modes; images optional in ref_video_only) */}
          <View style={s.section}>
            <Text style={s.sectionTitle}>{lipsyncMode === 'ref_video_only' ? '1. Speakers / Characters' : '1. Character Images'}</Text>
            <Text style={s.hint}>
              {lipsyncMode === 'ref_video_only'
                ? 'Add a slot per speaker in your reference video (you can skip the image). Each speaker gets its own voice.'
                : 'Add one image per character.'}
            </Text>
            {characters.length > 0 && (
              <View style={s.charGrid}>
                {characters.map((char, idx) => (
                  <View key={char.id} style={s.charCard}>
                    {char.uri ? (
                      <Image source={{ uri: char.uri }} style={s.charImg} />
                    ) : (
                      <View style={[s.charImg, { backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' }]}>
                        <Ionicons name="person" size={36} color="#475569" />
                        <Text style={{ color: '#64748B', fontSize: 10, marginTop: 4 }}>Speaker {idx + 1}</Text>
                      </View>
                    )}
                    {char.uploading && <View style={s.charOverlay}><ActivityIndicator size="small" color="#8B5CF6" /></View>}
                    {char.uploaded && <View style={s.charCheck}><Ionicons name="checkmark-circle" size={18} color="#10B981" /></View>}
                    <View style={s.charLabel}><Text style={s.charLabelText}>Char {idx + 1}</Text></View>
                    <TouchableOpacity style={s.charRemove} onPress={() => removeCharacter(char.id)}><Ionicons name="close-circle" size={20} color="#EF4444" /></TouchableOpacity>
                  </View>
                ))}
              </View>
            )}
            <View style={s.addRow}>
              <TouchableOpacity style={s.addBtn} onPress={() => addCharacter(false)}><Ionicons name="images" size={22} color="#8B5CF6" /><Text style={s.addBtnText}>Gallery</Text></TouchableOpacity>
              <TouchableOpacity style={s.addBtn} onPress={() => addCharacter(true)}><Ionicons name="camera" size={22} color="#8B5CF6" /><Text style={s.addBtnText}>Camera</Text></TouchableOpacity>
              {lipsyncMode === 'ref_video_only' && (
                <TouchableOpacity style={s.addBtn} onPress={() => {
                  const newChar = { id: Date.now().toString(), uri: '', didUrl: null, uploading: false, uploaded: false };
                  setCharacters(prev => [...prev, newChar]);
                }}>
                  <Ionicons name="person-add" size={22} color="#8B5CF6" /><Text style={s.addBtnText}>No Image</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>

          {/* Step 2: Audio Mode */}
          <View style={s.section}>
            <Text style={s.sectionTitle}>2. Audio Source</Text>
            <View style={s.modeRow}>
              <TouchableOpacity style={[s.modeChip, audioMode === 'tts' && s.modeChipActive]} onPress={() => setAudioMode('tts')}>
                <Ionicons name="text" size={18} color={audioMode === 'tts' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, audioMode === 'tts' && { color: '#fff' }]}>Text-to-Speech</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.modeChip, audioMode === 'audio' && s.modeChipActive]} onPress={() => setAudioMode('audio')}>
                <Ionicons name="musical-note" size={18} color={audioMode === 'audio' ? '#fff' : '#94A3B8'} />
                <Text style={[s.modeText, audioMode === 'audio' && { color: '#fff' }]}>Custom Audio</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Step 3: Per-character Voice (always visible - applies to TTS lines) */}
          <View style={s.section}>
            <Text style={s.sectionTitle}>3. Voice per Character</Text>
            <Text style={s.hint}>{lipsyncMode === 'ref_video_only' ? 'Pick a voice for each speaker in your reference video.' : 'Applies to any character whose dialogue uses Text-to-Speech.'}</Text>
            {characters.length === 0 ? (
              <Text style={s.hint}>Add {lipsyncMode === 'ref_video_only' ? 'speakers' : 'characters'} first to assign voices.</Text>
            ) : (
              <>
                {/* Character voice tabs */}
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 10 }}>
                  {characters.map((_, idx) => (
                    <TouchableOpacity key={idx} style={[s.charVoiceTab, activeCharTab === idx && s.charVoiceTabActive]} onPress={() => setActiveCharTab(idx)}>
                      <Text style={[s.charVoiceTabText, activeCharTab === idx && { color: '#fff' }]}>Char {idx + 1}{voiceIds[idx] ? ' ✓' : ''}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
                <VoicePicker
                  selectedId={voiceIds[activeCharTab]}
                  onSelect={(id) => setVoiceIds(prev => ({ ...prev, [activeCharTab]: id }))}
                />
                <Text style={[s.hint, { marginTop: 6 }]}>
                  {lipsyncMode === 'ref_video_only' ? 'Voice' : `Voice for Char ${activeCharTab + 1}`}: <Text style={{ color: '#A78BFA', fontWeight: '700' }}>{findVoice(voiceIds[activeCharTab])?.name || 'Swara (default)'}</Text>
                </Text>
              </>
            )}
          </View>

          {/* TTS Mode: Per-character dialogue */}
          {audioMode === 'tts' && (
            <>

              {/* Step 4: Dialogue Script with Character Tabs */}
              <View style={s.section}>
                <Text style={s.sectionTitle}>4. Dialogue Script</Text>
                <Text style={s.hint}>Switch tabs to write each character's lines separately.</Text>
                {characters.length > 1 && (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 10 }}>
                    {characters.map((_, idx) => {
                      const lineCount = dialogueLines.filter(l => l.characterIndex === idx).length;
                      return (
                        <TouchableOpacity key={idx} style={[s.scriptTab, activeCharTab === idx && s.scriptTabActive]} onPress={() => setActiveCharTab(idx)}>
                          <Text style={[s.scriptTabText, activeCharTab === idx && { color: '#fff' }]}>Char {idx + 1} ({lineCount})</Text>
                        </TouchableOpacity>
                      );
                    })}
                    <TouchableOpacity style={[s.scriptTab, { borderColor: '#64748B' }]} onPress={() => setActiveCharTab(-1)}>
                      <Text style={s.scriptTabText}>All</Text>
                    </TouchableOpacity>
                  </ScrollView>
                )}

                {/* Show filtered or all lines */}
                {(activeCharTab === -1 ? dialogueLines : dialogueLines.filter(l => l.characterIndex === activeCharTab)).map((line, idx) => (
                  <View key={line.id} style={s.dialogueRow}>
                    <View style={s.dialogueHeader}>
                      <View style={[s.lineCharBadge, { backgroundColor: line.characterIndex === 0 ? '#8B5CF620' : '#EC489920' }]}>
                        <Text style={[s.lineCharText, { color: line.characterIndex === 0 ? '#8B5CF6' : '#EC4899' }]}>Char {line.characterIndex + 1}</Text>
                      </View>
                      {dialogueLines.length > 1 && (
                        <TouchableOpacity onPress={() => removeDialogueLine(line.id)} style={s.removeLineBtn}><Ionicons name="trash-outline" size={16} color="#EF4444" /></TouchableOpacity>
                      )}
                    </View>
                    <TextInput
                      style={s.dialogueInput}
                      placeholder={`Type Char ${line.characterIndex + 1}'s dialogue...`}
                      placeholderTextColor="#64748B"
                      value={line.text}
                      onChangeText={(t) => updateDialogueLine(line.id, 'text', t)}
                      multiline maxLength={1000}
                    />
                  </View>
                ))}
                <TouchableOpacity style={s.addLineBtn} onPress={() => addDialogueLine()}>
                  <Ionicons name="add-circle" size={20} color="#8B5CF6" />
                  <Text style={s.addLineBtnText}>Add Line for Char {activeCharTab >= 0 ? activeCharTab + 1 : 1}</Text>
                </TouchableOpacity>
              </View>
            </>
          )}

          {/* Custom Audio Mode */}
          {audioMode === 'audio' && (
            <View style={s.section}>
              <Text style={s.sectionTitle}>3. Upload Audio per Character</Text>
              <Text style={s.hint}>Upload a separate audio file for each character, or one audio for all.</Text>
              {/* Global audio */}
              <View style={{ marginBottom: 10 }}>
                <Text style={{ color: '#94A3B8', fontSize: 13, fontWeight: '600', marginBottom: 6 }}>All Characters (single audio):</Text>
                {audioUri ? (
                  <View style={s.audioCard}>
                    <Ionicons name="musical-notes" size={22} color="#8B5CF6" />
                    <Text style={s.audioName} numberOfLines={1}>{audioUri.split('/').pop()}</Text>
                    <TouchableOpacity onPress={() => { setAudioUri(null); setAudioPath(null); }}><Ionicons name="close-circle" size={22} color="#EF4444" /></TouchableOpacity>
                  </View>
                ) : (
                  <TouchableOpacity style={s.uploadAudioBtn} onPress={pickAudio}>
                    <Ionicons name="cloud-upload" size={22} color="#8B5CF6" /><Text style={s.uploadAudioText}>Choose Audio File</Text>
                  </TouchableOpacity>
                )}
              </View>
              {/* Per-character audio */}
              {characters.length > 0 && (
                <View>
                  <Text style={{ color: '#94A3B8', fontSize: 13, fontWeight: '600', marginBottom: 6 }}>Or per character (upload or record):</Text>
                  {characters.map((_, idx) => {
                    const isRecording = recordingCharIdx === idx;
                    const someoneElseRecording = recordingCharIdx !== null && recordingCharIdx !== idx;
                    const hasAudio = !!charAudios[idx]?.path;
                    const isUploading = charAudios[idx]?.uploading;
                    return (
                      <View key={`chaudio-${idx}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <View style={{ backgroundColor: '#8B5CF620', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4, minWidth: 54 }}>
                          <Text style={{ color: '#8B5CF6', fontSize: 12, fontWeight: '700' }}>Char {idx + 1}</Text>
                        </View>
                        {hasAudio ? (
                          <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#1E293B', borderRadius: 8, padding: 8, borderWidth: 1, borderColor: '#10B98140' }}>
                            <Ionicons name={charAudios[idx]?.source === 'record' ? 'mic' : 'musical-note'} size={16} color="#10B981" />
                            <Text style={{ color: '#E2E8F0', fontSize: 12, flex: 1 }} numberOfLines={1}>
                              {charAudios[idx]?.source === 'record' ? 'Recorded audio' : (charAudios[idx]?.uri?.split('/').pop() || 'audio file')}
                            </Text>
                            <TouchableOpacity onPress={() => setCharAudios(prev => { const n = { ...prev }; delete n[idx]; return n; })}><Ionicons name="close" size={16} color="#EF4444" /></TouchableOpacity>
                          </View>
                        ) : isUploading ? (
                          <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#1E293B', borderRadius: 8, padding: 8, borderWidth: 1, borderColor: '#334155' }}>
                            <ActivityIndicator size="small" color="#8B5CF6" />
                            <Text style={{ color: '#94A3B8', fontSize: 12 }}>Uploading...</Text>
                          </View>
                        ) : isRecording ? (
                          <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EF444415', borderRadius: 8, padding: 8, borderWidth: 1, borderColor: '#EF4444' }}>
                            <View style={s.recDot} />
                            <Text style={{ color: '#EF4444', fontSize: 13, fontWeight: '700' }}>REC {formatDuration(recordingDuration)}</Text>
                            <View style={{ flex: 1 }} />
                            <TouchableOpacity onPress={() => stopRecording(idx)} style={s.stopBtn}>
                              <Ionicons name="stop" size={14} color="#fff" />
                              <Text style={{ color: '#fff', fontSize: 12, fontWeight: '700', marginLeft: 4 }}>Stop</Text>
                            </TouchableOpacity>
                            <TouchableOpacity onPress={cancelRecording} style={{ paddingHorizontal: 6 }}>
                              <Ionicons name="close" size={18} color="#94A3B8" />
                            </TouchableOpacity>
                          </View>
                        ) : (
                          <View style={{ flex: 1, flexDirection: 'row', gap: 6 }}>
                            <TouchableOpacity
                              style={[s.charAudioAction, someoneElseRecording && { opacity: 0.5 }]}
                              disabled={someoneElseRecording}
                              onPress={() => pickCharAudio(idx)}>
                              <Ionicons name="cloud-upload" size={14} color="#8B5CF6" />
                              <Text style={s.charAudioActionT}>Upload</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                              style={[s.charAudioAction, { borderColor: '#EF444440' }, someoneElseRecording && { opacity: 0.5 }]}
                              disabled={someoneElseRecording}
                              onPress={() => startRecording(idx)}>
                              <Ionicons name="mic" size={14} color="#EF4444" />
                              <Text style={[s.charAudioActionT, { color: '#EF4444' }]}>Record</Text>
                            </TouchableOpacity>
                          </View>
                        )}
                      </View>
                    );
                  })}
                </View>
              )}
            </View>
          )}

          {/* Aspect Ratio */}
          <View style={s.section}>
            <Text style={s.sectionTitle}>{audioMode === 'tts' ? '5' : '4'}. Aspect Ratio</Text>
            <View style={s.ratioRow}>
              {ASPECT_RATIOS.map(ar => (
                <TouchableOpacity key={ar.value} style={[s.ratioChip, aspectRatio === ar.value && s.ratioActive]} onPress={() => setAspectRatio(ar.value)}>
                  <Text style={[s.ratioLabel, aspectRatio === ar.value && { color: '#fff' }]}>{ar.label}</Text>
                  <Text style={[s.ratioDesc, aspectRatio === ar.value && { color: '#E2E8F0' }]}>{ar.desc}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Output Duration — applies to all lip sync modes */}
          <View style={s.section}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8 }}>
              <Text style={s.sectionTitle}>Output Duration (optional)</Text>
              {mhCap.costPerSec != null && (
                <Text style={{ color: '#94A3B8', fontSize: 11 }}>
                  · {mhCap.costPerSec}¢/sec · min {mhCap.minBilled}s
                </Text>
              )}
            </View>
            <Text style={s.hint}>Auto matches the dialogue / ref-video length. Min billed 5s; &lt;5s still bills as 5s.</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
              {[{ label: 'Auto', v: null, cost: null }, ...(mhCap.durationOptions || [5, 10, 15]).map(v => ({
                label: `${v}s`, v, cost: mhCap.costPerSec ? Math.max(mhCap.costPerSec * v, mhCap.minCost || 0) : null,
              }))].map((d, i) => (
                <TouchableOpacity key={i} style={[{ backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10, marginRight: 8, borderWidth: 1, borderColor: '#334155' }, targetDuration === d.v && { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' }]} onPress={() => setTargetDuration(d.v)}>
                  <Text style={[{ color: '#94A3B8', fontSize: 13, fontWeight: '600' }, targetDuration === d.v && { color: '#fff' }]}>{d.label}</Text>
                  {d.cost != null && (
                    <Text style={{ color: targetDuration === d.v ? '#FDE68A' : '#64748B', fontSize: 10, marginTop: 2 }}>🪙 {d.cost}</Text>
                  )}
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Resolution */}
          <View style={{ marginBottom: 16 }}>
            <Text style={s.sectionTitle}>Resolution</Text>
            <ResolutionPicker selected={resolution} onSelect={(r) => setResolution(r as any)} />
          </View>

          {/* Create Button -> opens Review */}
          <TouchableOpacity style={[s.createBtn, !canCreate && s.createBtnDisabled]} onPress={() => setShowReview(true)} disabled={!canCreate}>
            {processing ? (
              <View style={s.createBtnInner}><ActivityIndicator size="small" color="#fff" /><Text style={s.createBtnText}>Processing... {progress}%</Text></View>
            ) : (
              <View style={s.createBtnInner}><Ionicons name="eye" size={22} color="#fff" /><Text style={s.createBtnText}>Review & Create</Text></View>
            )}
          </TouchableOpacity>

          {/* Review Modal */}
          <Modal visible={showReview} animationType="slide" transparent onRequestClose={() => setShowReview(false)}>
            <View style={s.reviewOverlay}>
              <View style={s.reviewSheet}>
                <View style={s.reviewHandle} />
                <Text style={s.reviewTitle}>Review Before Creating</Text>
                <ScrollView style={s.reviewBody}>
                  <View style={s.reviewRow}><Text style={s.reviewLabel}>Characters</Text><Text style={s.reviewValue}>{characters.filter(c => c.uploaded).length} uploaded</Text></View>
                  <View style={s.reviewRow}><Text style={s.reviewLabel}>Audio Mode</Text><Text style={s.reviewValue}>{audioMode === 'tts' ? 'Text-to-Speech' : 'Custom Audio'}</Text></View>
                  {audioMode === 'tts' && characters.map((_, idx) => (
                    <View key={idx} style={s.reviewRow}><Text style={s.reviewLabel}>Char {idx+1} Voice</Text><Text style={s.reviewValue}>{findVoice(voiceIds[idx])?.name || 'Default'}</Text></View>
                  ))}
                  <View style={s.reviewRow}><Text style={s.reviewLabel}>Dialogue Lines</Text><Text style={s.reviewValue}>{dialogueLines.filter(l => l.text.trim()).length} lines</Text></View>
                  <View style={s.reviewRow}><Text style={s.reviewLabel}>Aspect Ratio</Text><Text style={s.reviewValue}>{aspectRatio}</Text></View>
                  {dialogueLines.filter(l => l.text.trim()).map((l, i) => (
                    <View key={l.id} style={s.reviewScript}><Text style={s.reviewScriptChar}>Char {l.characterIndex + 1}:</Text><Text style={s.reviewScriptText}>{l.text}</Text></View>
                  ))}
                </ScrollView>
                <View style={s.reviewActions}>
                  <TouchableOpacity style={s.reviewEditBtn} onPress={() => setShowReview(false)}><Ionicons name="create" size={18} color="#8B5CF6" /><Text style={s.reviewEditBtnT}>Edit</Text></TouchableOpacity>
                  <TouchableOpacity style={s.reviewConfirmBtn} onPress={() => { setShowReview(false); createLipSync(); }}><Ionicons name="checkmark-circle" size={18} color="#fff" /><Text style={s.reviewConfirmBtnT}>Confirm & Create</Text></TouchableOpacity>
                </View>
              </View>
            </View>
          </Modal>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
    </AuroraBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  scroll: { padding: 20, paddingBottom: 60 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#fff' },
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
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#E2E8F0', marginBottom: 4 },
  hint: { fontSize: 13, color: '#94A3B8', marginBottom: 8 },
  modeOption: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#1E293B', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#334155' },
  modeOptionActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  modeOptionTitle: { color: '#E2E8F0', fontSize: 14, fontWeight: '700', marginBottom: 2 },
  modeOptionDesc: { color: '#94A3B8', fontSize: 11, lineHeight: 15 },
  // Result
  resultBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#10B98110', borderRadius: 12, padding: 12, marginBottom: 14, borderWidth: 1, borderColor: '#10B98140', gap: 10 },
  resultTitle: { color: '#10B981', fontSize: 15, fontWeight: '700' },
  resultDesc: { color: '#94A3B8', fontSize: 12 },
  resultViewBtn: { backgroundColor: '#10B981', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 6 },
  resultViewBtnT: { color: '#fff', fontSize: 13, fontWeight: '700' },
  // Progress
  progressCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#8B5CF640' },
  progressHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  progressTitle: { color: '#fff', fontSize: 14, fontWeight: '600', flex: 1 },
  progressBarWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  progressBarBg: { flex: 1, height: 8, backgroundColor: '#334155', borderRadius: 4, overflow: 'hidden' },
  progressBarFill: { height: 8, borderRadius: 4, backgroundColor: '#8B5CF6' },
  progressPct: { fontSize: 13, fontWeight: 'bold', color: '#8B5CF6', width: 36 },
  // Characters
  charGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 10 },
  charCard: { width: 90, height: 110, borderRadius: 10, overflow: 'hidden', backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155' },
  charImg: { width: '100%', height: 72, backgroundColor: '#334155' },
  charOverlay: { position: 'absolute', top: 0, left: 0, right: 0, height: 72, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center' },
  charCheck: { position: 'absolute', top: 3, right: 3 },
  charLabel: { paddingHorizontal: 6, paddingVertical: 3 },
  charLabelText: { color: '#E2E8F0', fontSize: 12, fontWeight: '600' },
  charRemove: { position: 'absolute', top: -2, left: -2 },
  addRow: { flexDirection: 'row', gap: 10 },
  addBtn: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', borderStyle: 'dashed', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  addBtnText: { color: '#E2E8F0', fontSize: 14 },
  // Audio mode
  modeRow: { flexDirection: 'row', gap: 10 },
  modeChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  modeChipActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  modeText: { color: '#94A3B8', fontSize: 14, fontWeight: '600' },
  // Voice tabs
  charVoiceTab: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 8, marginRight: 8, borderWidth: 1, borderColor: '#334155' },
  charVoiceTabActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  charVoiceTabText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  // Chips
  chip: { backgroundColor: '#1E293B', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12, marginRight: 8, borderWidth: 1, borderColor: '#334155', minWidth: 75, alignItems: 'center' },
  chipActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  chipName: { color: '#E2E8F0', fontSize: 13, fontWeight: '600' },
  chipNameActive: { color: '#fff' },
  chipSub: { color: '#94A3B8', fontSize: 10, marginTop: 1 },
  chipSubActive: { color: '#E2E8F0' },
  // Script tabs
  scriptTab: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 8, marginRight: 8, borderWidth: 1, borderColor: '#334155' },
  scriptTabActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  scriptTabText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  // Dialogue
  dialogueRow: { backgroundColor: '#1E293B', borderRadius: 10, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: '#334155' },
  dialogueHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  lineCharBadge: { borderRadius: 6, paddingHorizontal: 10, paddingVertical: 4 },
  lineCharText: { fontSize: 12, fontWeight: '700' },
  removeLineBtn: { marginLeft: 'auto', padding: 4 },
  dialogueInput: { backgroundColor: '#0F172A', borderRadius: 8, padding: 10, color: '#fff', fontSize: 14, minHeight: 44, textAlignVertical: 'top' },
  addLineBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 12, backgroundColor: '#1E293B', borderRadius: 10, borderWidth: 1, borderColor: '#8B5CF640', borderStyle: 'dashed' },
  addLineBtnText: { color: '#8B5CF6', fontSize: 14, fontWeight: '600' },
  // Audio upload
  audioCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, borderWidth: 1, borderColor: '#8B5CF640' },
  audioName: { flex: 1, color: '#E2E8F0', fontSize: 14 },
  uploadAudioBtn: { backgroundColor: '#1E293B', borderRadius: 10, padding: 20, alignItems: 'center', borderWidth: 1, borderColor: '#334155', borderStyle: 'dashed', gap: 8 },
  uploadAudioText: { color: '#E2E8F0', fontSize: 15 },
  // Per-character audio actions
  charAudioAction: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, backgroundColor: '#1E293B', borderRadius: 8, padding: 8, borderWidth: 1, borderColor: '#8B5CF640', borderStyle: 'dashed' },
  charAudioActionT: { color: '#8B5CF6', fontSize: 12, fontWeight: '600' },
  recDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#EF4444' },
  stopBtn: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#EF4444', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6 },
  // Ratio
  ratioRow: { flexDirection: 'row', gap: 12 },
  ratioChip: { flex: 1, backgroundColor: '#1E293B', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  ratioActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  ratioLabel: { color: '#E2E8F0', fontSize: 18, fontWeight: 'bold' },
  ratioDesc: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  // Create
  createBtn: { backgroundColor: '#8B5CF6', borderRadius: 14, padding: 18, alignItems: 'center', marginTop: 4 },
  createBtnDisabled: { backgroundColor: '#334155' },
  createBtnInner: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  createBtnText: { color: '#fff', fontSize: 17, fontWeight: 'bold' },
  // Review Modal
  reviewOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  reviewSheet: { backgroundColor: '#1E293B', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '75%', paddingBottom: 30 },
  reviewHandle: { width: 40, height: 4, backgroundColor: '#475569', borderRadius: 2, alignSelf: 'center', marginTop: 12, marginBottom: 8 },
  reviewTitle: { fontSize: 18, fontWeight: 'bold', color: '#fff', textAlign: 'center', marginBottom: 12 },
  reviewBody: { paddingHorizontal: 20, maxHeight: 300 },
  reviewRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#33415530' },
  reviewLabel: { color: '#94A3B8', fontSize: 13 },
  reviewValue: { color: '#E2E8F0', fontSize: 13, fontWeight: '600' },
  reviewScript: { backgroundColor: '#0F172A', borderRadius: 8, padding: 10, marginTop: 8 },
  reviewScriptChar: { color: '#8B5CF6', fontSize: 12, fontWeight: '700', marginBottom: 4 },
  reviewScriptText: { color: '#E2E8F0', fontSize: 13 },
  reviewActions: { flexDirection: 'row', gap: 10, paddingHorizontal: 20, paddingTop: 16 },
  reviewEditBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#334155', borderRadius: 12, padding: 14 },
  reviewEditBtnT: { color: '#8B5CF6', fontSize: 15, fontWeight: '700' },
  reviewConfirmBtn: { flex: 2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#8B5CF6', borderRadius: 12, padding: 14 },
  reviewConfirmBtnT: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
