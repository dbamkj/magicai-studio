import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export type MotionPreset = {
  id: string;
  label: string;
  emoji: string;
  desc: string;
};

const FALLBACK: MotionPreset[] = [
  { id: 'none', label: 'None', emoji: '⏸️', desc: 'Static image (no motion).' },
  { id: 'zoom_in', label: 'Zoom In', emoji: '🔍', desc: 'Slow zoom toward the center.' },
  { id: 'zoom_out', label: 'Zoom Out', emoji: '🔎', desc: 'Pull back from close-up.' },
  { id: 'pan_left', label: 'Pan Left', emoji: '⬅️', desc: 'Camera drifts left.' },
  { id: 'pan_right', label: 'Pan Right', emoji: '➡️', desc: 'Camera drifts right.' },
  { id: 'pan_up', label: 'Pan Up', emoji: '⬆️', desc: 'Camera tilts upward.' },
  { id: 'pan_down', label: 'Pan Down', emoji: '⬇️', desc: 'Camera tilts downward.' },
  { id: 'ken_burns', label: 'Ken Burns', emoji: '🎞️', desc: 'Slow zoom + diagonal drift.' },
];

type Props = {
  selectedId?: string | null;
  onSelect: (id: string | null) => void;
  compact?: boolean;
  label?: string;
  showSavingsHint?: boolean;  // show "saves credits" badge when a motion is active
};

export default function MotionPicker({ selectedId, onSelect, compact, label, showSavingsHint }: Props) {
  const [presets, setPresets] = useState<MotionPreset[]>(FALLBACK);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/motion-presets`, { timeout: 8000 });
        if (r.data?.presets && Array.isArray(r.data.presets) && r.data.presets.length > 0) {
          setPresets(r.data.presets);
        }
      } catch (e) {}
    })();
  }, []);

  const current = selectedId || 'none';
  const selected = presets.find((p) => p.id === current);
  const motionActive = current !== 'none';

  return (
    <View style={[s.wrap, compact && s.wrapCompact]}>
      {!compact && (
        <View style={s.labelRow}>
          <Ionicons name="videocam" size={16} color="#60A5FA" />
          <Text style={s.label}>{label || 'Motion'}</Text>
          {motionActive && showSavingsHint && (
            <View style={s.savingsBadge}>
              <Ionicons name="flash" size={11} color="#10B981" />
              <Text style={s.savingsText}>Saves credits</Text>
            </View>
          )}
        </View>
      )}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={s.chipsRow}
      >
        {presets.map((preset) => {
          const active = preset.id === current;
          return (
            <TouchableOpacity
              key={preset.id}
              onPress={() => onSelect(preset.id === 'none' ? null : preset.id)}
              style={[s.chip, active && s.chipActive]}
              activeOpacity={0.85}
            >
              <Text style={s.emoji}>{preset.emoji}</Text>
              <Text style={[s.chipLabel, active && s.chipLabelActive]} numberOfLines={1}>
                {preset.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      {!compact && selected && selected.id !== 'none' && (
        <Text style={s.desc}>{selected.desc}</Text>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { marginVertical: 10 },
  wrapCompact: { marginVertical: 6 },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  label: { color: '#E5E7EB', fontSize: 14, fontWeight: '600' },
  savingsBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: 'rgba(16,185,129,0.14)', paddingHorizontal: 7, paddingVertical: 3, borderRadius: 10, marginLeft: 6, borderWidth: 1, borderColor: 'rgba(16,185,129,0.35)' },
  savingsText: { color: '#10B981', fontSize: 10, fontWeight: '700' },
  chipsRow: { gap: 8, paddingRight: 12 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
    minHeight: 36,
  },
  chipActive: {
    backgroundColor: 'rgba(96,165,250,0.22)',
    borderColor: 'rgba(147,197,253,0.65)',
  },
  emoji: { fontSize: 15 },
  chipLabel: { color: '#9CA3AF', fontSize: 13, fontWeight: '500' },
  chipLabelActive: { color: '#DBEAFE', fontWeight: '700' },
  desc: { color: '#9CA3AF', fontSize: 12, marginTop: 8, fontStyle: 'italic' },
});
