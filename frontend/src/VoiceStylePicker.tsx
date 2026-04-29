import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export type VoiceStyle = {
  id: string;
  label: string;
  emoji: string;
  desc: string;
  rate?: string | null;
  pitch?: string | null;
  bgm_suggest?: string;
  bgm_volume?: number;
  voice_volume?: number;
  pause_multiplier?: number;
};

// Fallback catalog (used if /api/voice-styles fetch fails so UI remains usable)
const FALLBACK_STYLES: VoiceStyle[] = [
  { id: 'neutral', label: 'Neutral', emoji: '🎙️', desc: 'Default, no adjustments.' },
  { id: 'devotional', label: 'Devotional', emoji: '🪔', desc: 'Slow, reverent, warm.' },
  { id: 'motivation', label: 'Motivation', emoji: '🔥', desc: 'Punchy, confident, energetic.' },
  { id: 'story', label: 'Story', emoji: '📖', desc: 'Natural narrator tone.' },
  { id: 'funny', label: 'Funny', emoji: '😂', desc: 'Faster, playful, higher-pitched.' },
];

type Props = {
  selectedId?: string | null;
  onSelect: (id: string | null) => void;  // null = reset to neutral/default
  compact?: boolean;                       // for per-shot inline use
  label?: string;                          // section label; default "Voice Style"
  // Sprint 2 Phase B — optional custom rate/pitch override fields
  customRate?: string | null;
  customPitch?: string | null;
  onCustomRate?: (v: string | null) => void;
  onCustomPitch?: (v: string | null) => void;
};

export default function VoiceStylePicker({ selectedId, onSelect, compact, label, customRate, customPitch, onCustomRate, onCustomPitch }: Props) {
  const [styles, setStyles] = useState<VoiceStyle[]>(FALLBACK_STYLES);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [rateInput, setRateInput] = useState(customRate || '');
  const [pitchInput, setPitchInput] = useState(customPitch || '');

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/voice-styles`, { timeout: 8000 });
        if (r.data?.styles && Array.isArray(r.data.styles) && r.data.styles.length > 0) {
          setStyles(r.data.styles);
        }
      } catch (e) {
        // keep fallback
      }
    })();
  }, []);

  const current = selectedId || 'neutral';
  const selected = styles.find((s) => s.id === current);

  return (
    <View style={[s.wrap, compact && s.wrapCompact]}>
      {!compact && (
        <View style={s.labelRow}>
          <Ionicons name="color-wand" size={16} color="#A78BFA" />
          <Text style={s.label}>{label || 'Voice Style'}</Text>
        </View>
      )}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={s.chipsRow}
      >
        {styles.map((style) => {
          const active = style.id === current;
          return (
            <TouchableOpacity
              key={style.id}
              onPress={() => onSelect(style.id === 'neutral' ? null : style.id)}
              style={[s.chip, active && s.chipActive]}
              activeOpacity={0.85}
            >
              <Text style={s.emoji}>{style.emoji}</Text>
              <Text style={[s.chipLabel, active && s.chipLabelActive]} numberOfLines={1}>
                {style.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      {!compact && selected && selected.id !== 'neutral' && (
        <Text style={s.desc}>{selected.desc}</Text>
      )}
      {!compact && (onCustomRate || onCustomPitch) && (
        <View style={{ marginTop: 8 }}>
          <TouchableOpacity onPress={() => setShowAdvanced((p) => !p)} style={s.advBtn} activeOpacity={0.7}>
            <Ionicons name={showAdvanced ? 'chevron-down' : 'chevron-forward'} size={14} color="#9CA3AF" />
            <Text style={s.advBtnText}>Advanced (custom rate / pitch)</Text>
          </TouchableOpacity>
          {showAdvanced && (
            <View style={s.advPanel}>
              {onCustomRate && (
                <View style={s.advRow}>
                  <Text style={s.advLabel}>Rate</Text>
                  <TextInput
                    style={s.advInput}
                    placeholder="e.g. +5% or -10%"
                    placeholderTextColor="#4B5563"
                    value={rateInput}
                    onChangeText={(v) => { setRateInput(v); onCustomRate(v.trim() || null); }}
                    autoCapitalize="none"
                    autoCorrect={false}
                  />
                </View>
              )}
              {onCustomPitch && (
                <View style={s.advRow}>
                  <Text style={s.advLabel}>Pitch</Text>
                  <TextInput
                    style={s.advInput}
                    placeholder="e.g. +10Hz or -15Hz"
                    placeholderTextColor="#4B5563"
                    value={pitchInput}
                    onChangeText={(v) => { setPitchInput(v); onCustomPitch(v.trim() || null); }}
                    autoCapitalize="none"
                    autoCorrect={false}
                  />
                </View>
              )}
              <Text style={s.advHelp}>Overrides the preset. Leave empty to use preset defaults.</Text>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { marginVertical: 10 },
  wrapCompact: { marginVertical: 6 },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  label: { color: '#E5E7EB', fontSize: 14, fontWeight: '600' },
  chipsRow: { gap: 8, paddingRight: 12 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
    minHeight: 36,
  },
  chipActive: {
    backgroundColor: 'rgba(139,92,246,0.22)',
    borderColor: 'rgba(167,139,250,0.65)',
  },
  emoji: { fontSize: 15 },
  chipLabel: { color: '#9CA3AF', fontSize: 13, fontWeight: '500' },
  chipLabelActive: { color: '#E0D4FF', fontWeight: '700' },
  desc: { color: '#9CA3AF', fontSize: 12, marginTop: 8, fontStyle: 'italic' },
  advBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4 },
  advBtnText: { color: '#9CA3AF', fontSize: 12 },
  advPanel: { marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.06)', gap: 8 },
  advRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  advLabel: { color: '#9CA3AF', fontSize: 12, width: 45 },
  advInput: { flex: 1, backgroundColor: 'rgba(255,255,255,0.04)', color: '#E5E7EB', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  advHelp: { color: '#6B7280', fontSize: 11, marginTop: 4 },
});
