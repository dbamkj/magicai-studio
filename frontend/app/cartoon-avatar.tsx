/* Phase-4A — Cartoon Avatar Generator screen
 *
 * Flow: pick style → pick emotion → upload photo OR enter prompt → tap Generate
 *       → poll job → preview cartoon avatar → download / share / use-in-reel
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  Image, StatusBar, Pressable, TextInput, Alert, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import FreeVsProToggle from '../src/components/FreeVsProToggle';
import { useAuth } from '../src/AuthContext';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { useTierGuard } from '../src/useTierGuard';
import { saveAssetToDevice, suggestFileName } from '../src/downloadHelper';

const API = (process.env.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_BACKEND_URL || '') + '/api';

type Style = { id: string; label: string; icon: string; tagline: string; premium: boolean };
const EMOTIONS = [
  { id: 'happy',       emoji: '😊', label: 'Happy' },
  { id: 'excited',     emoji: '🤩', label: 'Excited' },
  { id: 'confident',   emoji: '😎', label: 'Confident' },
  { id: 'playful',     emoji: '😜', label: 'Playful' },
  { id: 'mysterious',  emoji: '😏', label: 'Mysterious' },
  { id: 'peaceful',    emoji: '😌', label: 'Peaceful' },
  { id: 'devotional',  emoji: '🙏', label: 'Devotional' },
  { id: 'fierce',      emoji: '😤', label: 'Fierce' },
  { id: 'angry',       emoji: '😠', label: 'Angry' },
  { id: 'sad',         emoji: '😢', label: 'Sad' },
  { id: 'surprised',   emoji: '😲', label: 'Surprised' },
  { id: 'neutral',     emoji: '😐', label: 'Neutral' },
];


export default function CartoonAvatarScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const tier = useTierGuard();
  const userIsPro = !!user && user.subscription_tier !== 'free';

  const [styles, setStyles] = useState<Style[]>([]);
  const [styleId, setStyleId] = useState<string>('pixar');
  const [emotion, setEmotion] = useState<string>('happy');
  const [prompt, setPrompt] = useState<string>('');
  const [imageB64, setImageB64] = useState<string | null>(null);
  const [imagePreviewUri, setImagePreviewUri] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<any>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const pollTimer = useRef<any>(null);

  // ---------- load styles ----------
  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API}/avatar/styles`, { timeout: 12000 });
        setStyles(r.data?.styles || []);
      } catch (e) { console.warn('avatar styles load fail', e); }
    })();
    return () => { if (pollTimer.current) clearInterval(pollTimer.current); };
  }, []);

  // ---------- pick image from gallery ----------
  const pickImage = useCallback(async () => {
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted && Platform.OS !== 'web') {
        Alert.alert('Permission needed', 'Please allow photo access to upload an image.');
        return;
      }
      const r = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [9, 16],
        quality: 0.85,
        base64: true,
      });
      if (r.canceled) return;
      const a = r.assets?.[0];
      if (!a) return;
      setImagePreviewUri(a.uri);
      setImageB64(a.base64 || null);
    } catch (e: any) {
      Alert.alert('Image picker failed', e?.message || 'Try again.');
    }
  }, []);

  const clearImage = () => { setImageB64(null); setImagePreviewUri(null); };

  // ---------- generate ----------
  const generate = useCallback(async () => {
    if (busy) return;
    if (!imageB64 && !prompt.trim()) {
      Alert.alert('Need a source', 'Upload a photo or describe yourself in the prompt.');
      return;
    }
    setBusy(true);
    setResultUrl(null);
    setJob(null);
    try {
      const body: any = { style: styleId, emotion };
      if (imageB64) body.image_b64 = imageB64;
      if (prompt.trim()) body.prompt = prompt.trim();
      const r = await axios.post(`${API}/avatar/cartoonize`, body, { timeout: 30000 });
      const jid = r.data?.job_id;
      if (!jid) throw new Error('No job id');
      setJob({ id: jid, status: 'queued' });
      // poll
      pollTimer.current = setInterval(async () => {
        try {
          const j = await axios.get(`${API}/avatar/jobs/${jid}`, { timeout: 8000 });
          setJob(j.data);
          if (j.data?.status === 'completed') {
            clearInterval(pollTimer.current);
            const url = (process.env.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_BACKEND_URL || '') + j.data.image_url;
            setResultUrl(url);
            setBusy(false);
          } else if (j.data?.status === 'failed') {
            clearInterval(pollTimer.current);
            Alert.alert('Generation failed', j.data?.error || 'Please try again.');
            setBusy(false);
          }
        } catch (e) { /* keep polling */ }
      }, 2500);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (typeof detail === 'object' && detail?.premium_required) {
        Alert.alert('Premium style', detail.reason, [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Upgrade', onPress: () => router.push('/buy?tab=tier' as any) },
        ]);
      } else if (typeof detail === 'object' && detail?.moderation_blocked) {
        Alert.alert('Content blocked', detail.reason || 'Please rephrase your prompt.');
      } else {
        Alert.alert('Could not generate', e?.message || 'Try again');
      }
      setBusy(false);
    }
  }, [busy, styleId, emotion, prompt, imageB64, router]);

  // ---------- result actions ----------
  const reset = () => {
    setResultUrl(null); setJob(null);
    if (pollTimer.current) clearInterval(pollTimer.current);
  };

  const sActive = styles.find(x => x.id === styleId);

  return (
    <AuroraBackground>
    <SafeAreaView style={s.root} edges={['top']}>
      <StatusBar barStyle="light-content" />

      <GlassHeader
        icon="color-palette"
        title="Cartoon Avatar"
        subtitle="AI-stylised portrait · Free + Premium styles"
        onBack={() => router.back()}
        gradient={['#A78BFA', '#06B6D4', '#10B981']}
      />

      {resultUrl ? (
        // ---------- RESULT VIEW (Free vs Pro toggle) ----------
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
          <FreeVsProToggle
            mediaUrl={resultUrl}
            mediaType="image"
            userIsPro={userIsPro}
            metaLabel={`${sActive?.icon ?? ''}  ${sActive?.label ?? ''}  ·  ${EMOTIONS.find(e => e.id === emotion)?.label ?? ''}`}
            onUpgrade={() => router.push('/buy?tab=tier' as any)}
            onDownload={async () => {
              if (!resultUrl) return;
              const fname = suggestFileName(resultUrl, 'image');
              await saveAssetToDevice(resultUrl, fname, 'image');
            }}
          />

          {/* ---------- Phase 4E: Animate to talking video CTA ---------- */}
          <TouchableOpacity
            onPress={() => {
              // 🔒 Tier gate — Talking Avatar lip-sync requires Creator+
              if (!tier.requireFeature('talking_avatar_lipsync', 'Talking Avatar (lip-sync)')) {
                return;
              }
              router.push({
                pathname: '/lipsync',
                params: { prefill_image: resultUrl, prefill_meta: `Cartoon · ${sActive?.label ?? ''}` },
              } as any);
            }}
            style={[s.actionBtn, { backgroundColor: '#7B5CFF', marginTop: 12 }]}
            activeOpacity={0.85}
          >
            <Ionicons name={tier.canUseFeature('talking_avatar_lipsync') ? 'videocam' : 'lock-closed'} size={14} color="#fff" />
            <Text style={s.actionBtnTxt}>
              {tier.canUseFeature('talking_avatar_lipsync')
                ? 'Animate to Talking Video →'
                : 'Animate to Talking Video (Creator+)'}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity onPress={reset} style={[s.actionBtn, { backgroundColor: '#1E293B', marginTop: 8 }]}>
            <Ionicons name="refresh" size={14} color="#fff" />
            <Text style={s.actionBtnTxt}>Generate Again</Text>
          </TouchableOpacity>
        </ScrollView>
      ) : (
        // ---------- INPUT VIEW ----------
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
          {/* Style picker */}
          <Text style={s.label}>1. Pick a style</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingVertical: 4 }}>
            {styles.map(st => {
              const active = styleId === st.id;
              return (
                <Pressable key={st.id} onPress={() => setStyleId(st.id)}
                  style={[s.styleCard, active && s.styleCardActive]}>
                  <Text style={{ fontSize: 28 }}>{st.icon}</Text>
                  <Text style={[s.styleLabel, active && { color: '#fff' }]}>{st.label}</Text>
                  <Text style={s.styleTag} numberOfLines={2}>{st.tagline}</Text>
                  {st.premium && <View style={s.premiumPill}><Text style={s.premiumPillTxt}>PRO</Text></View>}
                </Pressable>
              );
            })}
          </ScrollView>

          {/* Emotion picker */}
          <Text style={[s.label, { marginTop: 18 }]}>2. Pick an emotion</Text>
          <View style={s.emoRow}>
            {EMOTIONS.map(e => {
              const active = emotion === e.id;
              return (
                <Pressable key={e.id} onPress={() => setEmotion(e.id)}
                  style={[s.emoChip, active && s.emoChipActive]}>
                  <Text style={{ fontSize: 18 }}>{e.emoji}</Text>
                  <Text style={[s.emoTxt, active && { color: '#fff' }]}>{e.label}</Text>
                </Pressable>
              );
            })}
          </View>

          {/* Source picker */}
          <Text style={[s.label, { marginTop: 18 }]}>3. Provide a source</Text>
          <View style={s.sourceRow}>
            <TouchableOpacity activeOpacity={0.85} onPress={pickImage}
              style={[s.uploadCard, imagePreviewUri && { borderColor: '#10B981' }]}>
              {imagePreviewUri ? (
                <>
                  <Image source={{ uri: imagePreviewUri }} resizeMode="cover" style={{ width: '100%', height: '100%' }} />
                  <Pressable onPress={clearImage} style={s.imgClose}>
                    <Ionicons name="close" size={14} color="#fff" />
                  </Pressable>
                </>
              ) : (
                <>
                  <Ionicons name="cloud-upload-outline" size={28} color="#8B5CF6" />
                  <Text style={s.uploadHint}>Upload selfie</Text>
                  <Text style={s.uploadHintSub}>9:16 best</Text>
                </>
              )}
            </TouchableOpacity>
            <View style={s.orWrap}><Text style={s.orTxt}>OR</Text></View>
            <View style={[s.promptCard, prompt.length > 0 && { borderColor: '#8B5CF6' }]}>
              <Text style={s.promptLabel}>Describe yourself</Text>
              <TextInput
                value={prompt}
                onChangeText={setPrompt}
                placeholder="e.g. young Indian woman with long dark hair, glasses"
                placeholderTextColor="#475569"
                multiline
                style={s.promptInput}
                maxLength={250}
              />
              <Text style={s.promptCount}>{prompt.length}/250</Text>
            </View>
          </View>

          {/* CTA */}
          <TouchableOpacity activeOpacity={0.85} onPress={generate} disabled={busy}
            style={{ marginTop: 22, borderRadius: 14, overflow: 'hidden', opacity: busy ? 0.6 : 1 }}>
            <LinearGradient colors={['#8B5CF6', '#EC4899']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={s.cta}>
              {busy ? (
                <>
                  <ActivityIndicator size="small" color="#fff" />
                  <Text style={s.ctaTxt}>{job?.stage ? `${job.stage}…` : 'Generating…'}</Text>
                </>
              ) : (
                <>
                  <Ionicons name="sparkles" size={16} color="#fff" />
                  <Text style={s.ctaTxt}>Generate Cartoon Avatar</Text>
                </>
              )}
            </LinearGradient>
          </TouchableOpacity>

          <Text style={s.foot}>
            <Ionicons name="shield-checkmark-outline" size={11} color="#94A3B8" />
            {' '}Free · Watermarked · ~10 sec · Powered by MagiCAi Studio
          </Text>
        </ScrollView>
      )}
    </SafeAreaView>
    </AuroraBackground>
  );
}


/* ============ styles ============ */
const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: 'transparent' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '800' },
  headerSub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },

  label: { color: '#fff', fontSize: 13, fontWeight: '800', marginBottom: 8, letterSpacing: 0.2 },

  styleCard: {
    width: 110, padding: 12, alignItems: 'center', borderRadius: 14,
    backgroundColor: '#1E293B', borderWidth: 1.5, borderColor: '#334155',
    position: 'relative',
  },
  styleCardActive: { borderColor: '#8B5CF6', backgroundColor: 'rgba(139,92,246,0.18)' },
  styleLabel: { color: '#94A3B8', fontSize: 12, fontWeight: '800', marginTop: 6 },
  styleTag: { color: '#64748B', fontSize: 9, textAlign: 'center', marginTop: 3, lineHeight: 12 },
  premiumPill: {
    position: 'absolute', top: 6, right: 6,
    paddingHorizontal: 5, paddingVertical: 1, borderRadius: 5,
    backgroundColor: '#FBBF24',
  },
  premiumPillTxt: { color: '#0B1120', fontSize: 8, fontWeight: '900' },

  emoRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  emoChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 14,
    backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155',
  },
  emoChipActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  emoTxt: { color: '#94A3B8', fontWeight: '700', fontSize: 12 },

  sourceRow: { flexDirection: 'row', gap: 10, alignItems: 'stretch' },
  uploadCard: {
    width: 130, height: 170, borderRadius: 14, backgroundColor: '#1E293B',
    borderWidth: 2, borderStyle: 'dashed', borderColor: '#334155',
    alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
  },
  uploadHint: { color: '#94A3B8', fontSize: 12, fontWeight: '700', marginTop: 6 },
  uploadHintSub: { color: '#64748B', fontSize: 10, marginTop: 2 },
  imgClose: { position: 'absolute', top: 6, right: 6, width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(0,0,0,0.6)', alignItems: 'center', justifyContent: 'center' },

  orWrap: { width: 24, alignItems: 'center', justifyContent: 'center' },
  orTxt: { color: '#475569', fontSize: 10, fontWeight: '800', letterSpacing: 1 },

  promptCard: {
    flex: 1, padding: 12, borderRadius: 14, backgroundColor: '#1E293B',
    borderWidth: 1.5, borderColor: '#334155',
  },
  promptLabel: { color: '#94A3B8', fontSize: 10, fontWeight: '700', marginBottom: 4 },
  promptInput: { color: '#fff', fontSize: 12, minHeight: 80, padding: 0, textAlignVertical: 'top' },
  promptCount: { color: '#64748B', fontSize: 9, textAlign: 'right', marginTop: 4 },

  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14 },
  ctaTxt: { color: '#fff', fontWeight: '800', fontSize: 14, letterSpacing: 0.2 },
  foot: { color: '#94A3B8', fontSize: 11, textAlign: 'center', marginTop: 12 },

  resultWrap: {
    backgroundColor: '#000', borderRadius: 16, overflow: 'hidden',
    aspectRatio: 9 / 16, alignItems: 'center', justifyContent: 'center',
  },
  resultImg: { width: '100%', height: '100%' },
  resultMeta: { marginTop: 12, alignItems: 'center', gap: 6 },
  resultMetaTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },
  wmBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(251,191,36,0.12)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 },
  wmTxt: { color: '#FBBF24', fontSize: 10, fontWeight: '700' },

  actionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 12, borderRadius: 11 },
  actionBtnTxt: { color: '#fff', fontWeight: '800', fontSize: 12 },
});
