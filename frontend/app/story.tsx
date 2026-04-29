import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator,
  Alert, TextInput, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import axios from 'axios';
import CosmicBackground from '../src/CosmicBackground';
import { useAuth } from '../src/AuthContext';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Scene = { title: string; prompt: string; dialogue?: string; motion?: string; duration?: number };
type Variable = { key: string; label: string; placeholder: string };
type Template = {
  id: string; label: string; emoji: string; desc: string;
  variables: Variable[]; scenes: Scene[];
  suggested_voice_style?: string;
  suggested_transition?: string;
};

export default function StoryScreen() {
  const router = useRouter();
  const { user, token, refresh } = useAuth();

  const [templates, setTemplates] = useState<Template[]>([]);
  const [cost, setCost] = useState(80);
  const [loading, setLoading] = useState(true);

  const [selected, setSelected] = useState<Template | null>(null);
  const [vars, setVars] = useState<Record<string, string>>({});
  const [aspect, setAspect] = useState('9:16');

  const [submitting, setSubmitting] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/story/templates`);
        setTemplates(r.data.templates || []);
        setCost(r.data.cost || 80);
      } catch {
        Alert.alert('Error', 'Could not load story templates');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    const iv = setInterval(async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/project/${projectId}`);
        setProgress(r.data?.progress || 0);
        if (r.data?.status === 'completed' && r.data?.result_url) {
          setResultUrl(`${BACKEND_URL}${r.data.result_url}`);
          clearInterval(iv); refresh();
        } else if (r.data?.status === 'failed') {
          setErrorMsg(r.data?.error_message || 'Generation failed');
          clearInterval(iv);
        }
      } catch {}
    }, 3500);
    return () => clearInterval(iv);
  }, [projectId]);

  const filledPreview = useMemo(() => {
    if (!selected) return [] as Scene[];
    const fill = (s: string) =>
      (s || '').replace(/\{(\w+)\}/g, (_, k) => (vars[k] || `{${k}}`));
    return selected.scenes.map(sc => ({
      ...sc,
      prompt: fill(sc.prompt),
      dialogue: sc.dialogue ? fill(sc.dialogue) : sc.dialogue,
    }));
  }, [selected, vars]);

  const allVarsFilled = selected ? selected.variables.every(v => (vars[v.key] || '').trim().length > 0) : false;

  const submit = async () => {
    if (!selected || !allVarsFilled) {
      Alert.alert('Fill all fields', 'Please fill in the template variables.');
      return;
    }
    setSubmitting(true); setErrorMsg(null); setProgress(0); setResultUrl(null);
    try {
      const r = await axios.post(
        `${BACKEND_URL}/api/story/create`,
        {
          template_id: selected.id,
          variables: vars,
          aspect_ratio: aspect,
        },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      setProjectId(r.data.project_id);
      refresh();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed';
      setErrorMsg(msg); Alert.alert('Error', msg);
    } finally {
      setSubmitting(false);
    }
  };

  const startAnother = () => {
    setProjectId(null); setResultUrl(null); setProgress(0); setErrorMsg(null); setSelected(null); setVars({});
  };

  if (loading) {
    return (
      <CosmicBackground>
        <AuroraBackground>
        <SafeAreaView style={s.container}>
          <View style={s.centerWrap}>
            <ActivityIndicator color="#A78BFA" size="large" />
            <Text style={s.loadText}>Loading story templates…</Text>
          </View>
        </SafeAreaView>
        </AuroraBackground>
      </CosmicBackground>
    );
  }

  // ======== Result / progress view ========
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
            <Text style={s.title}>📖 Story Mode</Text>
          </View>
          <View style={s.progressWrap}>
            {!done && (
              <>
                <ActivityIndicator color="#FBBF24" size="large" />
                <Text style={s.progressText}>{progress}% · Weaving your story…</Text>
                <Text style={s.progressHint}>3 cinematic scenes · stitched with voice, motion & transitions</Text>
                <View style={s.progressBar}>
                  <View style={[s.progressFill, { width: `${progress}%` }]} />
                </View>
              </>
            )}
            {errorMsg && (
              <>
                <Ionicons name="alert-circle" size={60} color="#EF4444" />
                <Text style={[s.progressText, { color: '#EF4444' }]}>Story build failed</Text>
                <Text style={s.progressHint}>{errorMsg}</Text>
                <TouchableOpacity onPress={startAnother} style={s.primaryBtn}>
                  <Text style={s.primaryBtnText}>Try again</Text>
                </TouchableOpacity>
              </>
            )}
            {resultUrl && (
              <>
                <Ionicons name="checkmark-circle" size={56} color="#10B981" />
                <Text style={s.progressText}>✨ Your story is ready</Text>
                <View style={s.resultBox}>
                  {Platform.OS === 'web' ? (
                    // @ts-ignore
                    <video src={resultUrl} controls autoPlay loop style={{ width: '100%', borderRadius: 12, maxHeight: 500 }} />
                  ) : (
                    <Text style={{ color: '#94A3B8' }}>Open in Projects to preview.</Text>
                  )}
                </View>
                <View style={{ flexDirection: 'row', gap: 10, marginTop: 18 }}>
                  <TouchableOpacity onPress={startAnother} style={s.secondaryBtn}>
                    <Text style={s.secondaryBtnText}>New story</Text>
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

  // ======== Template picker ========
  if (!selected) {
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
                <Text style={s.title}>📖 Story Mode</Text>
                <Text style={s.subtitle}>3 scenes, 1 tap — guided cinematic reels</Text>
              </View>
              <View style={s.costPill}>
                <Ionicons name="diamond" size={12} color="#FBBF24" />
                <Text style={s.costPillText}>{cost}¢</Text>
              </View>
            </View>
            <View style={s.instantReelBanner}>
              <Ionicons name="flash" size={14} color="#10B981" />
              <Text style={s.instantReelBannerText}>
                Flat <Text style={{ fontWeight: '900' }}>{cost} credits</Text> for 3 stitched scenes — cheaper than 3 separate AI Video jobs.
              </Text>
            </View>
            <Text style={s.sectionTitle}>Pick a template</Text>
            <View style={{ gap: 12, marginTop: 12 }}>
              {templates.map(t => (
                <TouchableOpacity
                  key={t.id}
                  onPress={() => { setSelected(t); setVars({}); }}
                  activeOpacity={0.85}
                  style={s.tplCard}
                >
                  <View style={s.tplEmojiWrap}>
                    <Text style={s.tplEmoji}>{t.emoji}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.tplLabel}>{t.label}</Text>
                    <Text style={s.tplDesc} numberOfLines={2}>{t.desc}</Text>
                    <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                      {t.scenes.map((_, i) => (
                        <View key={i} style={s.sceneDot}>
                          <Text style={s.sceneDotText}>{i + 1}</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color="#64748B" />
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.footNote}>
              Balance: 🪙 {user?.credits_balance ?? 0} · Tier: {user?.subscription_tier?.toUpperCase() || 'FREE'}
            </Text>
          </ScrollView>
        </SafeAreaView>
        </AuroraBackground>
      </CosmicBackground>
    );
  }

  // ======== Variable entry + scene preview ========
  return (
    <CosmicBackground>
      <AuroraBackground>
      <SafeAreaView style={s.container}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={{ flex: 1 }}
        >
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
            <View style={s.header}>
              <TouchableOpacity onPress={() => setSelected(null)} style={s.back}>
                <Ionicons name="arrow-back" size={22} color="#fff" />
              </TouchableOpacity>
              <View style={{ flex: 1 }}>
                <Text style={s.title}>{selected.emoji} {selected.label}</Text>
                <Text style={s.subtitle}>{selected.desc}</Text>
              </View>
              <View style={s.costPill}>
                <Ionicons name="diamond" size={12} color="#FBBF24" />
                <Text style={s.costPillText}>{cost}¢</Text>
              </View>
            </View>

            <Text style={s.sectionTitle}>Customise</Text>
            <View style={{ gap: 10, marginTop: 10 }}>
              {selected.variables.map(v => (
                <View key={v.key}>
                  <Text style={s.varLabel}>{v.label}</Text>
                  <TextInput
                    style={s.varInput}
                    value={vars[v.key] || ''}
                    onChangeText={tx => setVars({ ...vars, [v.key]: tx })}
                    placeholder={v.placeholder}
                    placeholderTextColor="#64748B"
                  />
                </View>
              ))}
            </View>

            <Text style={[s.sectionTitle, { marginTop: 20 }]}>Format</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
              {[
                { id: '9:16', label: 'Reel', emoji: '📱' },
                { id: '1:1', label: 'Square', emoji: '⬜' },
                { id: '16:9', label: 'Wide', emoji: '🖥️' },
              ].map(a => {
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
                  </TouchableOpacity>
                );
              })}
            </View>

            <Text style={[s.sectionTitle, { marginTop: 20 }]}>Preview</Text>
            <View style={{ gap: 10, marginTop: 10 }}>
              {filledPreview.map((sc, i) => (
                <View key={i} style={s.sceneCard}>
                  <View style={s.sceneHeader}>
                    <View style={s.sceneBadge}><Text style={s.sceneBadgeText}>{i + 1}</Text></View>
                    <Text style={s.sceneTitle}>{sc.title}</Text>
                    <View style={s.sceneMeta}>
                      {!!sc.motion && <Text style={s.sceneMetaText}>🎬 {sc.motion}</Text>}
                      {!!sc.duration && <Text style={s.sceneMetaText}>⏱ {sc.duration}s</Text>}
                    </View>
                  </View>
                  <Text style={s.scenePrompt} numberOfLines={3}>{sc.prompt}</Text>
                  {!!sc.dialogue && (
                    <View style={s.dialogBox}>
                      <Ionicons name="chatbubble-ellipses-outline" size={13} color="#A78BFA" />
                      <Text style={s.dialogText} numberOfLines={2}>{sc.dialogue}</Text>
                    </View>
                  )}
                </View>
              ))}
            </View>

            <TouchableOpacity
              onPress={submit}
              disabled={submitting || !allVarsFilled}
              activeOpacity={0.85}
              style={{ marginTop: 22, opacity: (submitting || !allVarsFilled) ? 0.5 : 1 }}
            >
              <LinearGradient
                colors={['#A78BFA', '#EC4899', '#FBBF24']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                style={s.cta}
              >
                {submitting ? <ActivityIndicator color="#fff" /> : (
                  <>
                    <Ionicons name="film" size={18} color="#fff" />
                    <Text style={s.ctaText}>Create Story · {cost} credits</Text>
                  </>
                )}
              </LinearGradient>
            </TouchableOpacity>

            <Text style={s.footNote}>
              Balance: 🪙 {user?.credits_balance ?? 0}
            </Text>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
      </AuroraBackground>
    </CosmicBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 6 },
  back: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)' },
  title: { fontSize: 19, fontWeight: '800', color: '#fff' },
  subtitle: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  costPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, backgroundColor: 'rgba(251,191,36,0.15)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)' },
  instantReelPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, backgroundColor: 'rgba(16,185,129,0.15)', borderWidth: 1, borderColor: 'rgba(16,185,129,0.5)' },
  instantReelPillText: { color: '#6EE7B7', fontSize: 10, fontWeight: '800', letterSpacing: 0.3 },
  instantReelBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(16,185,129,0.08)', borderWidth: 1, borderColor: 'rgba(16,185,129,0.3)', borderRadius: 10, padding: 10, marginTop: 10 },
  instantReelBannerText: { flex: 1, color: '#A7F3D0', fontSize: 12, lineHeight: 16, fontWeight: '600' },
  costPillText: { color: '#FBBF24', fontSize: 11, fontWeight: '800' },

  centerWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  loadText: { color: '#94A3B8' },

  sectionTitle: { color: '#fff', fontSize: 14, fontWeight: '800', marginTop: 18, letterSpacing: 0.3 },

  // Template cards
  tplCard: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  tplEmojiWrap: { width: 56, height: 56, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(167,139,250,0.15)' },
  tplEmoji: { fontSize: 32 },
  tplLabel: { color: '#fff', fontSize: 15, fontWeight: '800' },
  tplDesc: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  sceneDot: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(251,191,36,0.18)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.45)' },
  sceneDotText: { color: '#FBBF24', fontSize: 10, fontWeight: '900' },

  // Variable inputs
  varLabel: { color: '#CBD5E1', fontSize: 12, fontWeight: '700', marginBottom: 6 },
  varInput: { backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, color: '#fff', fontSize: 14 },

  aspChip: { flex: 1, paddingVertical: 12, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', alignItems: 'center', gap: 4 },
  aspChipActive: { backgroundColor: 'rgba(251,191,36,0.18)', borderColor: 'rgba(251,191,36,0.6)' },
  chipText: { color: '#CBD5E1', fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: '#FBBF24', fontWeight: '800' },

  // Scene preview cards
  sceneCard: { padding: 14, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  sceneHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  sceneBadge: { width: 24, height: 24, borderRadius: 12, backgroundColor: 'rgba(167,139,250,0.25)', alignItems: 'center', justifyContent: 'center' },
  sceneBadgeText: { color: '#A78BFA', fontSize: 11, fontWeight: '900' },
  sceneTitle: { color: '#fff', fontSize: 14, fontWeight: '700', flex: 1 },
  sceneMeta: { flexDirection: 'row', gap: 8 },
  sceneMetaText: { color: '#64748B', fontSize: 10 },
  scenePrompt: { color: '#CBD5E1', fontSize: 12, lineHeight: 17, fontStyle: 'italic' },
  dialogBox: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: 'rgba(167,139,250,0.08)', borderRadius: 8 },
  dialogText: { color: '#A78BFA', fontSize: 11, fontWeight: '600', flex: 1 },

  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 14 },
  ctaText: { color: '#fff', fontSize: 16, fontWeight: '900', letterSpacing: 0.5 },
  footNote: { color: '#64748B', fontSize: 11, textAlign: 'center', marginTop: 14 },

  // Result
  progressWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 12 },
  progressText: { color: '#fff', fontSize: 16, fontWeight: '700', marginTop: 10 },
  progressHint: { color: '#94A3B8', fontSize: 13, textAlign: 'center', maxWidth: 320 },
  progressBar: { width: '80%', height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.08)', overflow: 'hidden', marginTop: 16 },
  progressFill: { height: '100%', backgroundColor: '#A78BFA' },
  resultBox: { width: '100%', maxWidth: 420, marginTop: 16 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 18, paddingVertical: 12, borderRadius: 12, backgroundColor: '#A78BFA' },
  primaryBtnText: { color: '#fff', fontSize: 13, fontWeight: '800' },
  secondaryBtn: { paddingHorizontal: 16, paddingVertical: 12, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.08)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)' },
  secondaryBtnText: { color: '#CBD5E1', fontSize: 13, fontWeight: '700' },
});
