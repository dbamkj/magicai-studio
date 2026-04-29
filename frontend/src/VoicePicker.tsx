import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import { VOICE_LIBRARY, VOICE_CATEGORIES, Voice, findVoice } from './voices';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

interface VoicePickerProps {
  selectedId?: string;
  onSelect: (id: string) => void;
  // filter categories to show (default: all)
  categories?: Voice['category'][];
  // inline (scroll chips under categories) | compact (flat single row)
  mode?: 'inline' | 'compact';
}

export default function VoicePicker({ selectedId, onSelect, categories, mode = 'inline' }: VoicePickerProps) {
  const cats = (categories && categories.length > 0) ? categories : VOICE_CATEGORIES.map(c => c.id);
  const [provider, setProvider] = useState<'edge-tts' | 'sarvam'>('edge-tts');
  const [activeCat, setActiveCat] = useState<Voice['category']>(cats[0]);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      (async () => {
        try {
          if (soundRef.current) {
            await soundRef.current.unloadAsync();
            soundRef.current = null;
          }
        } catch {}
      })();
    };
  }, []);

  useEffect(() => {
    // If selected voice's category differs from active tab, switch
    if (selectedId) {
      const v = findVoice(selectedId);
      if (v && cats.includes(v.category) && v.category !== activeCat) {
        setActiveCat(v.category);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const playPreview = async (voiceId: string) => {
    try {
      // Stop any prior playback
      if (soundRef.current) {
        try {
          await soundRef.current.stopAsync();
          await soundRef.current.unloadAsync();
        } catch {}
        soundRef.current = null;
      }
      // If user tapped the already-playing voice -> just stop
      if (playingId === voiceId) {
        setPlayingId(null);
        return;
      }
      setLoadingId(voiceId);
      await Audio.setAudioModeAsync({ playsInSilentModeIOS: true, allowsRecordingIOS: false });
      const uri = `${BACKEND_URL}/api/preview-voice?voice_id=${encodeURIComponent(voiceId)}`;
      const { sound } = await Audio.Sound.createAsync(
        { uri },
        { shouldPlay: true, volume: 1.0 },
        (status: any) => {
          if (status.didJustFinish) {
            setPlayingId(null);
            (async () => {
              try { await sound.unloadAsync(); } catch {}
            })();
            if (soundRef.current === sound) soundRef.current = null;
          }
        }
      );
      soundRef.current = sound;
      setPlayingId(voiceId);
      setLoadingId(null);
    } catch (e) {
      console.warn('Voice preview failed:', e);
      setLoadingId(null);
      setPlayingId(null);
    }
  };

  const visibleCats = VOICE_CATEGORIES.filter(c => cats.includes(c.id) && (c.provider === provider || !c.provider));
  // Auto-switch active category when provider changes
  useEffect(() => {
    if (!visibleCats.find(c => c.id === activeCat)) {
      if (visibleCats.length > 0) setActiveCat(visibleCats[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider]);
  const visibleVoices = VOICE_LIBRARY.filter(v => v.category === activeCat && cats.includes(v.category));

  return (
    <View>
      {/* Provider Toggle: edge-tts vs Sarvam */}
      <View style={s.providerRow}>
        <TouchableOpacity style={[s.providerPill, provider === 'edge-tts' && s.providerPillActive]} onPress={() => setProvider('edge-tts')}>
          <Ionicons name="globe" size={12} color={provider === 'edge-tts' ? '#fff' : '#94A3B8'} />
          <Text style={[s.providerText, provider === 'edge-tts' && { color: '#fff' }]}>edge-tts (Free)</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.providerPill, provider === 'sarvam' && { backgroundColor: '#F59E0B', borderColor: '#F59E0B' }]} onPress={() => setProvider('sarvam')}>
          <Ionicons name="star" size={12} color={provider === 'sarvam' ? '#fff' : '#F59E0B'} />
          <Text style={[s.providerText, provider === 'sarvam' && { color: '#fff' }]}>Sarvam (Premium)</Text>
        </TouchableOpacity>
      </View>
      {/* Category Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.catRow}>
        {visibleCats.map(c => (
          <TouchableOpacity
            key={c.id}
            style={[s.catChip, activeCat === c.id && { backgroundColor: c.color + '30', borderColor: c.color }]}
            onPress={() => setActiveCat(c.id)}
          >
            <Ionicons name={c.icon as any} size={14} color={activeCat === c.id ? c.color : '#94A3B8'} />
            <Text style={[s.catLabel, activeCat === c.id && { color: c.color, fontWeight: '700' }]}>{c.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      {/* Voice Chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingVertical: 4 }}>
        {visibleVoices.map(v => {
          const isSelected = selectedId === v.id;
          const isPlaying = playingId === v.id;
          const isLoading = loadingId === v.id;
          return (
            <View key={v.id} style={[s.voiceChip, isSelected && s.voiceChipActive]}>
              <TouchableOpacity onPress={() => onSelect(v.id)} style={s.voiceTap}>
                <Text style={[s.voiceName, isSelected && { color: '#fff' }]}>{v.name}</Text>
                <Text style={[s.voiceSub, isSelected && { color: '#E2E8F0' }]}>
                  {v.lang}{v.age ? ` · ${v.age}` : ''}{v.note ? ` · ${v.note}` : ''}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => playPreview(v.id)} style={s.previewBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                {isLoading ? (
                  <ActivityIndicator size="small" color="#A78BFA" />
                ) : (
                  <Ionicons
                    name={isPlaying ? 'stop-circle' : 'play-circle'}
                    size={22}
                    color={isPlaying ? '#EF4444' : (isSelected ? '#fff' : '#A78BFA')}
                  />
                )}
              </TouchableOpacity>
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  providerRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  providerPill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 14, borderWidth: 1, borderColor: '#475569', backgroundColor: '#1E293B' },
  providerPillActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  providerText: { color: '#94A3B8', fontSize: 11, fontWeight: '700' },
  catRow: { flexDirection: 'row', marginBottom: 8, maxHeight: 40 },
  catChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 18, borderWidth: 1, borderColor: '#334155', backgroundColor: '#1E293B', marginRight: 8 },
  catLabel: { color: '#94A3B8', fontSize: 12 },
  voiceChip: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155', borderRadius: 14, paddingLeft: 12, paddingRight: 6, paddingVertical: 8, marginRight: 8, minWidth: 135 },
  voiceChipActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  voiceTap: { flex: 1, paddingRight: 6 },
  voiceName: { color: '#E2E8F0', fontSize: 13, fontWeight: '700' },
  voiceSub: { color: '#94A3B8', fontSize: 10, marginTop: 2 },
  previewBtn: { paddingLeft: 4, paddingVertical: 2 },
});
