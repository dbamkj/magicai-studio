import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { TEMPLATES, findTemplate, Template } from '../src/templates';
import * as Clipboard from 'expo-clipboard';
import CosmicBackground from '../src/CosmicBackground';
import AuroraBackground from '../src/AuroraBackground';

export default function TemplatesScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string }>();
  const selected = params.id ? findTemplate(params.id) : null;

  const useTemplate = (t: Template, promptIndex: number = 0) => {
    const prompt = t.prompts[promptIndex] || t.prompts[0];
    // Pre-fill prompt into the target tool via URL param.
    router.push({
      pathname: t.route as any,
      params: {
        prompt,
        duration: t.settings?.duration?.toString(),
        aspectRatio: t.settings?.aspectRatio,
        voiceId: t.settings?.voiceId,
      },
    } as any);
  };

  const copyPrompt = async (p: string) => {
    try { await Clipboard.setStringAsync(p); Alert.alert('Copied!', 'Prompt copied to clipboard'); } catch {}
  };

  if (selected) {
    return (
      <CosmicBackground>
      <AuroraBackground>
      <SafeAreaView style={s.container}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
          <Text style={s.title}>{selected.title}</Text>
          <View style={{ width: 44 }} />
        </View>
        <ScrollView contentContainerStyle={s.scroll}>
          <Image source={{ uri: selected.img }} style={s.cover} />
          <View style={[s.labelBadge, { backgroundColor: selected.color }]}>
            <Text style={s.labelBadgeText}>{selected.label}</Text>
          </View>
          <Text style={s.description}>{selected.description}</Text>

          <Text style={s.sTitle}>Sample Prompts</Text>
          <Text style={s.hint}>Tap a prompt to pre-fill and open the tool, or copy it to customise.</Text>
          {selected.prompts.map((p, i) => (
            <View key={i} style={s.promptCard}>
              <Text style={s.promptText}>{p}</Text>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                <TouchableOpacity style={[s.actionBtn, { backgroundColor: selected.color }]} onPress={() => useTemplate(selected, i)}>
                  <Ionicons name="sparkles" size={14} color="#fff" />
                  <Text style={s.actionBtnText}>Use This</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.actionBtn, { backgroundColor: '#334155' }]} onPress={() => copyPrompt(p)}>
                  <Ionicons name="copy" size={14} color="#fff" />
                  <Text style={s.actionBtnText}>Copy</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}

          <TouchableOpacity style={[s.bigBtn, { backgroundColor: selected.color }]} onPress={() => useTemplate(selected, 0)}>
            <Ionicons name="rocket" size={22} color="#fff" />
            <Text style={s.bigBtnText}>Open Tool with This Template</Text>
          </TouchableOpacity>

          <TouchableOpacity style={s.customBtn} onPress={() => router.push(selected.route as any)}>
            <Text style={s.customBtnText}>Or start with my own prompt →</Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
      </AuroraBackground>
      </CosmicBackground>
    );
  }

  // Gallery view (no id)
  return (
    <CosmicBackground>
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
        <Text style={s.title}>Templates</Text>
        <View style={{ width: 44 }} />
      </View>
      <ScrollView contentContainerStyle={s.scroll}>
        <Text style={s.intro}>Tap any template to see sample prompts and create your own.</Text>
        <View style={s.grid}>
          {TEMPLATES.map(t => (
            <TouchableOpacity key={t.id} style={s.gridCard} activeOpacity={0.85} onPress={() => router.push({ pathname: '/templates', params: { id: t.id } } as any)}>
              <Image source={{ uri: t.img }} style={s.gridImg} />
              <View style={s.gridOverlay}>
                <View style={[s.labelBadge, { backgroundColor: t.color }]}>
                  <Text style={s.labelBadgeText}>{t.label}</Text>
                </View>
                <Text style={s.gridTitle}>{t.title}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
    </AuroraBackground>
    </CosmicBackground>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14 },
  backBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: 'bold', color: '#fff' },
  scroll: { padding: 16, paddingBottom: 60 },
  intro: { color: '#94A3B8', fontSize: 13, marginBottom: 14, textAlign: 'center' },
  cover: { width: '100%', height: 240, borderRadius: 16, backgroundColor: '#1E293B' },
  labelBadge: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, marginTop: 10 },
  labelBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800' },
  description: { color: '#CBD5E1', fontSize: 14, marginTop: 8, lineHeight: 20 },
  sTitle: { color: '#F1F5F9', fontSize: 17, fontWeight: '800', marginTop: 20, marginBottom: 6 },
  hint: { color: '#94A3B8', fontSize: 12, marginBottom: 10 },
  promptCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#334155' },
  promptText: { color: '#E2E8F0', fontSize: 13, lineHeight: 19 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 9, borderRadius: 8 },
  actionBtnText: { color: '#fff', fontSize: 13, fontWeight: '700' },
  bigBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, borderRadius: 14, padding: 18, marginTop: 16 },
  bigBtnText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  customBtn: { paddingVertical: 14, alignItems: 'center' },
  customBtnText: { color: '#8B5CF6', fontSize: 14, fontWeight: '700' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  gridCard: { width: '48%', height: 200, borderRadius: 14, overflow: 'hidden', marginBottom: 12, backgroundColor: '#1E293B' },
  gridImg: { width: '100%', height: '100%', position: 'absolute' },
  gridOverlay: { flex: 1, justifyContent: 'space-between', padding: 10, backgroundColor: 'rgba(0,0,0,0.28)' },
  gridTitle: { color: '#fff', fontSize: 14, fontWeight: '800' },
});
