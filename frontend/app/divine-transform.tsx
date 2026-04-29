import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator,
  Alert, Image, Platform, Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';
import CosmicBackground from '../src/CosmicBackground';
import { useAuth } from '../src/AuthContext';
import AuroraBackground from '../src/AuroraBackground';
import ModelPickerBlock from '../src/components/ModelPickerBlock';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const { width: SCREEN_W } = Dimensions.get('window');

type Deity = {
  id: string; label: string; emoji: string;
  gradient: [string, string]; festival_pack?: string | null;
  prompt: string; suggested_transition: string; suggested_sfx: string;
};

type Transition = { id: string; label: string; emoji: string; desc: string };
type Sfx = { id: string; name: string; icon: string; category: string };

const ASPECTS = [
  { id: '9:16', label: 'Reel', emoji: '📱' },
  { id: '1:1', label: 'Square', emoji: '⬜' },
  { id: '16:9', label: 'Wide', emoji: '🖥️' },
];

export default function DivineTransformScreen() {
  const router = useRouter();
  const { user, token, refresh } = useAuth();

  // Metadata
  const [deities, setDeities] = useState<Deity[]>([]);
  const [transitions, setTransitions] = useState<Transition[]>([]);
  const [sfxList, setSfxList] = useState<Sfx[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);

  // User selections
  const [selectedDeity, setSelectedDeity] = useState<Deity | null>(null);
  const [humanImage, setHumanImage] = useState<{ uri: string; path: string } | null>(null);
  const [divineImage, setDivineImage] = useState<{ uri: string; path: string } | null>(null);
  const [transition, setTransition] = useState<string>('divine_reveal');
  const [sfx, setSfx] = useState<string>('om_chant');
  const [aspect, setAspect] = useState<string>('9:16');
  const [duration, setDuration] = useState<number>(5);

  // Submission
  const [submitting, setSubmitting] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load metadata
  useEffect(() => {
    (async () => {
      try {
        const [dr, tr, sr] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/divine/deities`),
          axios.get(`${BACKEND_URL}/api/divine/transitions`),
          axios.get(`${BACKEND_URL}/api/divine/sfx`),
        ]);
        setDeities(dr.data.deities || []);
        setTransitions(tr.data.transitions || []);
        setSfxList(sr.data.sfx || []);
      } catch (e: any) {
        Alert.alert('Error', 'Could not load divine metadata.');
      } finally {
        setLoadingMeta(false);
      }
    })();
  }, []);

  // Poll project status
  useEffect(() => {
    if (!projectId) return;
    const iv = setInterval(async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
        setProgress(r.data?.progress || 0);
        if (r.data?.status === 'completed' && r.data?.result_url) {
          setResultUrl(`${BACKEND_URL}${r.data.result_url}`);
          clearInterval(iv);
          refresh(); // credits balance updated
        } else if (r.data?.status === 'failed') {
          setErrorMsg(r.data?.error_message || 'Generation failed');
          clearInterval(iv);
        }
      } catch {}
    }, 3000);
    return () => clearInterval(iv);
  }, [projectId]);

  const onPickDeity = (d: Deity) => {
    setSelectedDeity(d);
    setTransition(d.suggested_transition);
    setSfx(d.suggested_sfx);
  };

  const pickImage = async (kind: 'human' | 'divine') => {
    const r = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.85,
      base64: true,
    });
    if (r.canceled || !r.assets?.[0]) return;
    const asset = r.assets[0];
    if (!asset.base64) { Alert.alert('Error', 'Could not read image'); return; }
    try {
      const up = await axios.post(`${BACKEND_URL}/api/upload-base64`, {
        base64: asset.base64,
        filename: asset.fileName || `${kind}_${Date.now()}.jpg`,
      });
      const path = up.data?.file_path;
      if (!path) throw new Error('upload failed');
      if (kind === 'human') setHumanImage({ uri: asset.uri, path });
      else setDivineImage({ uri: asset.uri, path });
    } catch (e: any) {
      Alert.alert('Upload failed', e.response?.data?.detail || e.message);
    }
  };

  const submit = async () => {
    if (!humanImage) { Alert.alert('Required', 'Upload your portrait first.'); return; }
    if (!selectedDeity && !divineImage) {
      Alert.alert('Required', 'Pick a deity OR upload a custom divine reference.'); return;
    }
    setSubmitting(true); setErrorMsg(null); setProgress(0); setResultUrl(null);
    try {
      const payload: any = {
        human_image_path: humanImage.path,
        transition, sfx, duration,
        aspect_ratio: aspect,
      };
      if (divineImage?.path) payload.divine_image_path = divineImage.path;
      if (selectedDeity) {
        payload.deity_id = selectedDeity.id;
        if (selectedDeity.festival_pack) payload.festival_pack = selectedDeity.festival_pack;
      }
      const r = await axios.post(`${BACKEND_URL}/api/divine-transform`, payload, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setProjectId(r.data.project_id);
      refresh();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed';
      setErrorMsg(msg);
      Alert.alert('Error', msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Reset for another run
  const startAnother = () => {
    setProjectId(null); setResultUrl(null); setProgress(0); setErrorMsg(null);
    setHumanImage(null);
  };

  if (loadingMeta) {
    return (
      <CosmicBackground>
        <AuroraBackground>
        <SafeAreaView style={s.container}>
          <View style={s.centerWrap}>
            <ActivityIndicator color="#A78BFA" size="large" />
            <Text style={s.loadText}>Loading divine assets…</Text>
          </View>
        </SafeAreaView>
        </AuroraBackground>
      </CosmicBackground>
    );
  }

  // ========= Result view =========
  if (projectId) {
    const done = !!resultUrl || !!errorMsg;
    return (
      <CosmicBackground>
        <AuroraBackground>
        <SafeAreaView style={s.container}>
          <View style={s.header}>
            <TouchableOpacity onPress={() => router.back()} style={s.back}>
              <Ionicons name="arrow-back" size={22} color="#fff" />
            </TouchableOpacity>
            <Text style={s.title}>🕉️ Divine Transformation</Text>
          </View>
          <View style={{ paddingHorizontal: 16 }}>
            <ModelPickerBlock kind="image" />
          </View>

          <View style={s.progressWrap}>
            {!done && (
              <>
                <ActivityIndicator color="#FBBF24" size="large" />
                <Text style={s.progressText}>{progress}% · Manifesting the divine…</Text>
                <Text style={s.progressHint}>
                  Face-swap → motion render → cinematic transition → SFX mix
                </Text>
                <View style={s.progressBar}>
                  <View style={[s.progressFill, { width: `${progress}%` }]} />
                </View>
              </>
            )}
            {errorMsg && (
              <>
                <Ionicons name="alert-circle" size={60} color="#EF4444" />
                <Text style={[s.progressText, { color: '#EF4444' }]}>Transformation failed</Text>
                <Text style={s.progressHint}>{errorMsg}</Text>
                <TouchableOpacity onPress={startAnother} style={s.primaryBtn}>
                  <Text style={s.primaryBtnText}>Try again</Text>
                </TouchableOpacity>
              </>
            )}
            {resultUrl && (
              <>
                <Ionicons name="checkmark-circle" size={56} color="#10B981" />
                <Text style={s.progressText}>✨ Divine transformation complete</Text>
                <View style={s.resultBox}>
                  {Platform.OS === 'web' ? (
                    // @ts-ignore — video tag works on web
                    <video src={resultUrl} controls autoPlay loop style={{ width: '100%', borderRadius: 12, maxHeight: 500 }} />
                  ) : (
                    <Text style={{ color: '#94A3B8' }}>Open in Projects to preview.</Text>
                  )}
                </View>
                <View style={{ flexDirection: 'row', gap: 10, marginTop: 18 }}>
                  <TouchableOpacity onPress={startAnother} style={s.secondaryBtn}>
                    <Text style={s.secondaryBtnText}>Another transform</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => router.push('/projects')} style={s.primaryBtn}>
                    <Ionicons name="folder" size={16} color="#fff" />
                    <Text style={s.primaryBtnText}>My Projects</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </SafeAreaView>
        </AuroraBackground>
      </CosmicBackground>
    );
  }

  // ========= Wizard view =========
  return (
    <CosmicBackground>
      <AuroraBackground>
      <SafeAreaView style={s.container}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          <View style={s.header}>
            <TouchableOpacity onPress={() => router.back()} style={s.back}>
              <Ionicons name="arrow-back" size={22} color="#fff" />
            </TouchableOpacity>
            <View style={{ flex: 1 }}>
              <Text style={s.title}>🕉️ Divine Transformation</Text>
              <Text style={s.subtitle}>Turn your portrait into a cinematic divine reel</Text>
            </View>
            <View style={s.costPill}>
              <Ionicons name="diamond" size={12} color="#FBBF24" />
              <Text style={s.costPillText}>120¢</Text>
            </View>
          </View>

          {/* STEP 1: Pick deity */}
          <SectionHead step={1} title="Choose deity" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingRight: 10 }}>
            {deities.map(d => {
              const active = selectedDeity?.id === d.id;
              return (
                <TouchableOpacity
                  key={d.id}
                  onPress={() => onPickDeity(d)}
                  activeOpacity={0.85}
                  style={[s.deityTile, active && { borderColor: d.gradient[0], borderWidth: 2.5 }]}
                >
                  <LinearGradient
                    colors={[d.gradient[0] + '66', d.gradient[1] + '33']}
                    style={s.deityGrad}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                  >
                    <Text style={s.deityEmoji}>{d.emoji}</Text>
                    <Text style={s.deityLabel}>{d.label}</Text>
                    {d.festival_pack && (
                      <View style={s.fpBadge}>
                        <Text style={s.fpBadgeText}>{d.festival_pack}</Text>
                      </View>
                    )}
                    {active && (
                      <View style={s.deityCheck}>
                        <Ionicons name="checkmark-circle" size={20} color={d.gradient[0]} />
                      </View>
                    )}
                  </LinearGradient>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {/* STEP 2: Upload divine reference (optional if deity chosen) */}
          <SectionHead
            step={2}
            title="Divine reference photo"
            subtitle={selectedDeity ? 'Optional — upload a custom deity photo to override' : 'Required — upload a divine reference'}
          />
          <TouchableOpacity style={s.uploadBox} activeOpacity={0.85} onPress={() => pickImage('divine')}>
            {divineImage ? (
              <Image source={{ uri: divineImage.uri }} style={s.uploadPreview} />
            ) : (
              <>
                <Ionicons name="cloud-upload-outline" size={32} color="#A78BFA" />
                <Text style={s.uploadText}>Upload deity / divine image</Text>
                <Text style={s.uploadHint}>Or just pick a deity above</Text>
              </>
            )}
          </TouchableOpacity>

          {/* STEP 3: User portrait */}
          <SectionHead step={3} title="Your portrait" subtitle="Clear front-facing photo for best results" />
          <TouchableOpacity style={s.uploadBox} activeOpacity={0.85} onPress={() => pickImage('human')}>
            {humanImage ? (
              <Image source={{ uri: humanImage.uri }} style={s.uploadPreview} />
            ) : (
              <>
                <Ionicons name="person-circle-outline" size={38} color="#FBBF24" />
                <Text style={s.uploadText}>Upload your portrait</Text>
                <Text style={s.uploadHint}>JPG / PNG · well-lit face</Text>
              </>
            )}
          </TouchableOpacity>

          {/* STEP 4: Cinematic transition */}
          <SectionHead step={4} title="Cinematic transition" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingRight: 10 }}>
            {transitions.map(t => {
              const active = transition === t.id;
              return (
                <TouchableOpacity
                  key={t.id}
                  onPress={() => setTransition(t.id)}
                  style={[s.chip, active && s.chipActive]}
                  activeOpacity={0.85}
                >
                  <Text style={{ fontSize: 15 }}>{t.emoji}</Text>
                  <Text style={[s.chipText, active && s.chipTextActive]}>{t.label}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
          <Text style={s.metaHint}>
            {transitions.find(t => t.id === transition)?.desc}
          </Text>

          {/* STEP 5: Divine SFX */}
          <SectionHead step={5} title="Divine sound" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingRight: 10 }}>
            {sfxList.map(sx => {
              const active = sfx === sx.id;
              return (
                <TouchableOpacity
                  key={sx.id}
                  onPress={() => setSfx(sx.id)}
                  style={[s.chip, active && s.chipActive]}
                  activeOpacity={0.85}
                >
                  <Ionicons name={sx.icon as any} size={14} color={active ? '#FBBF24' : '#94A3B8'} />
                  <Text style={[s.chipText, active && s.chipTextActive]}>{sx.name}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {/* STEP 6: Aspect + Duration */}
          <SectionHead step={6} title="Format" />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {ASPECTS.map(a => {
              const active = aspect === a.id;
              return (
                <TouchableOpacity
                  key={a.id}
                  onPress={() => setAspect(a.id)}
                  style={[s.aspChip, active && s.aspChipActive]}
                  activeOpacity={0.85}
                >
                  <Text style={{ fontSize: 18 }}>{a.emoji}</Text>
                  <Text style={[s.chipText, active && s.chipTextActive]}>{a.label}</Text>
                  <Text style={{ color: active ? '#FBBF24' : '#94A3B8', fontSize: 10 }}>{a.id}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
            {[3, 5, 7, 10].map(d => {
              const active = duration === d;
              return (
                <TouchableOpacity
                  key={d}
                  onPress={() => setDuration(d)}
                  style={[s.durChip, active && s.durChipActive]}
                  activeOpacity={0.85}
                >
                  <Text style={[s.chipText, active && s.chipTextActive]}>{d}s</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* CTA */}
          <TouchableOpacity
            onPress={submit}
            disabled={submitting || !humanImage}
            activeOpacity={0.85}
            style={{ marginTop: 24, opacity: (submitting || !humanImage) ? 0.5 : 1 }}
          >
            <LinearGradient
              colors={['#FBBF24', '#F97316', '#EC4899']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
              style={s.cta}
            >
              {submitting ? <ActivityIndicator color="#fff" /> : (
                <>
                  <Ionicons name="sparkles" size={18} color="#fff" />
                  <Text style={s.ctaText}>Transform · 120 credits</Text>
                </>
              )}
            </LinearGradient>
          </TouchableOpacity>

          <Text style={s.footNote}>
            Balance: 🪙 {user?.credits_balance ?? 0} · Tier: {user?.subscription_tier?.toUpperCase() || 'FREE'}
          </Text>
        </ScrollView>
      </SafeAreaView>
      </AuroraBackground>
    </CosmicBackground>
  );
}

function SectionHead({ step, title, subtitle }: { step: number; title: string; subtitle?: string }) {
  return (
    <View style={{ marginTop: 20, marginBottom: 10 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View style={s.stepDot}><Text style={s.stepDotText}>{step}</Text></View>
        <Text style={s.sectionTitle}>{title}</Text>
      </View>
      {!!subtitle && <Text style={s.sectionSub}>{subtitle}</Text>}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 6 },
  back: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)' },
  title: { fontSize: 19, fontWeight: '800', color: '#fff' },
  subtitle: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  costPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, backgroundColor: 'rgba(251,191,36,0.15)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)' },
  costPillText: { color: '#FBBF24', fontSize: 11, fontWeight: '800' },

  centerWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  loadText: { color: '#94A3B8' },

  stepDot: { width: 24, height: 24, borderRadius: 12, backgroundColor: 'rgba(251,191,36,0.2)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.6)', alignItems: 'center', justifyContent: 'center' },
  stepDotText: { color: '#FBBF24', fontSize: 11, fontWeight: '900' },
  sectionTitle: { color: '#fff', fontSize: 15, fontWeight: '800' },
  sectionSub: { color: '#94A3B8', fontSize: 12, marginTop: 4, marginLeft: 32 },

  deityTile: { width: 140, height: 160, borderRadius: 16, overflow: 'hidden', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  deityGrad: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 10, gap: 6 },
  deityEmoji: { fontSize: 56 },
  deityLabel: { color: '#fff', fontSize: 13, fontWeight: '700', textAlign: 'center' },
  fpBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: 'rgba(0,0,0,0.4)' },
  fpBadgeText: { color: '#FBBF24', fontSize: 9, fontWeight: '800', textTransform: 'uppercase' },
  deityCheck: { position: 'absolute', top: 8, right: 8 },

  uploadBox: { minHeight: 140, borderWidth: 1.5, borderStyle: 'dashed', borderColor: 'rgba(167,139,250,0.4)', borderRadius: 16, backgroundColor: 'rgba(167,139,250,0.05)', alignItems: 'center', justifyContent: 'center', padding: 20, gap: 6 },
  uploadText: { color: '#fff', fontSize: 14, fontWeight: '700' },
  uploadHint: { color: '#94A3B8', fontSize: 11 },
  uploadPreview: { width: '100%', height: 200, borderRadius: 12 },

  chip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  chipActive: { backgroundColor: 'rgba(251,191,36,0.18)', borderColor: 'rgba(251,191,36,0.6)' },
  chipText: { color: '#CBD5E1', fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: '#FBBF24', fontWeight: '800' },
  metaHint: { color: '#94A3B8', fontSize: 12, marginTop: 8, fontStyle: 'italic' },

  aspChip: { flex: 1, paddingVertical: 12, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', alignItems: 'center', gap: 4 },
  aspChipActive: { backgroundColor: 'rgba(251,191,36,0.18)', borderColor: 'rgba(251,191,36,0.6)' },

  durChip: { flex: 1, paddingVertical: 10, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', alignItems: 'center' },
  durChipActive: { backgroundColor: 'rgba(167,139,250,0.2)', borderColor: 'rgba(167,139,250,0.6)' },

  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 14 },
  ctaText: { color: '#fff', fontSize: 16, fontWeight: '900', letterSpacing: 0.5 },
  footNote: { color: '#64748B', fontSize: 11, textAlign: 'center', marginTop: 12 },

  // Result view
  progressWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 12 },
  progressText: { color: '#fff', fontSize: 16, fontWeight: '700', marginTop: 10 },
  progressHint: { color: '#94A3B8', fontSize: 13, textAlign: 'center', maxWidth: 320 },
  progressBar: { width: '80%', height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.08)', overflow: 'hidden', marginTop: 16 },
  progressFill: { height: '100%', backgroundColor: '#FBBF24' },
  resultBox: { width: '100%', maxWidth: 420, marginTop: 16 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 18, paddingVertical: 12, borderRadius: 12, backgroundColor: '#A78BFA' },
  primaryBtnText: { color: '#fff', fontSize: 13, fontWeight: '800' },
  secondaryBtn: { paddingHorizontal: 16, paddingVertical: 12, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.08)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)' },
  secondaryBtnText: { color: '#CBD5E1', fontSize: 13, fontWeight: '700' },
});
