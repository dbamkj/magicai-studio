import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import CosmicBackground from '../src/CosmicBackground';
import AuroraBackground from '../src/AuroraBackground';

const TOOLS = [
  { route: '/avatar-studio', title: 'AI Avatar Studio', desc: '6-step talking avatar wizard (NEW)', icon: 'sparkles', color: '#EC4899' },
  { route: '/trending', title: 'Trending Templates', desc: 'Ready-made recipes (NEW)', icon: 'flame', color: '#EF4444' },
  { route: '/avatar', title: 'Talking Avatar', desc: 'Photo → Talking character', icon: 'happy', color: '#A855F7' },
  { route: '/cartoon-avatar', title: 'Cartoon Avatar', desc: 'Cartoonize a portrait', icon: 'color-palette', color: '#7B5CFF' },
  { route: '/videogen', title: 'AI Video Gen', desc: 'Text/Image/Video → Video', icon: 'film', color: '#F97316' },
  { route: '/motion-control', title: 'Motion Control', desc: 'Photo → video · Free', icon: 'move', color: '#10B981' },
  { route: '/imagegen', title: 'AI Image Gen', desc: 'Generate from prompt', icon: 'sparkles', color: '#EC4899' },
  { route: '/lipsync', title: 'Lip Sync', desc: 'Multi-char dialogue sync', icon: 'mic', color: '#8B5CF6' },
  { route: '/ai-bg-lipsync', title: 'AI Bg Lip Sync', desc: 'Character in new AI scene', icon: 'color-wand', color: '#EC4899' },
  { route: '/redub', title: 'Video Re-dub', desc: 'Single or multi speaker', icon: 'sync', color: '#06B6D4' },
  { route: '/faceswap', title: 'Face Swap', desc: 'Swap faces in videos', icon: 'people', color: '#EC4899' },
  { route: '/headswap', title: 'Head & Body', desc: 'Swap heads or outfits', icon: 'body', color: '#F97316' },
  { route: '/multiswap', title: 'Multi Swap', desc: 'Batch swap multi chars', icon: 'layers', color: '#F59E0B' },
  { route: '/projects', title: 'My Projects', desc: 'View all creations', icon: 'folder', color: '#10B981' },
];

export default function ExploreToolsScreen() {
  const router = useRouter();
  return (
    <CosmicBackground>
    <AuroraBackground>
    <SafeAreaView style={s.container}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={24} color="#fff" /></TouchableOpacity>
        <Text style={s.title}>All Tools</Text>
        <View style={{ width: 44 }} />
      </View>
      <ScrollView contentContainerStyle={s.scroll}>
        <View style={s.grid}>
          {TOOLS.map(t => (
            <TouchableOpacity key={t.route} style={s.card} activeOpacity={0.85} onPress={() => router.push(t.route as any)}>
              <View style={[s.iconBadge, { backgroundColor: t.color }]}><Ionicons name={t.icon as any} size={22} color="#fff" /></View>
              <Text style={s.cardTitle}>{t.title}</Text>
              <Text style={s.cardDesc}>{t.desc}</Text>
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
  title: { fontSize: 22, fontWeight: 'bold', color: '#fff' },
  scroll: { padding: 16, paddingBottom: 60 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'space-between' },
  card: { width: '48%', backgroundColor: '#1E293B', borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: '#334155' },
  iconBadge: { width: 44, height: 44, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  cardTitle: { color: '#fff', fontSize: 15, fontWeight: '700' },
  cardDesc: { color: '#94A3B8', fontSize: 12, marginTop: 4 },
});
