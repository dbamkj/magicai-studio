import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

type Tier = { id: string; label: string; enabled: boolean; credits_per_sec?: number; credits_per_image?: number; default?: boolean; desc?: string };
type Props = {
  feature: 'text_to_video' | 'image_to_video' | 'video_to_video' | 'ai_image_generator';
  selectedId: string;
  onSelect: (id: string) => void;
  // optional: unit label override, e.g. '/sec' or '/image'
  unit?: string;
};

// Fallback tiers (used if fetch fails). Keeps UI functional offline.
const FALLBACK_TIERS: Record<string, Tier[]> = {
  text_to_video: [
    { id: 'quick', label: 'Quick', enabled: true, credits_per_sec: 8, desc: 'Faster, lower cost' },
    { id: 'studio', label: 'Studio', enabled: true, credits_per_sec: 10, default: true, desc: 'Default balanced' },
    { id: 'cinematic', label: 'Cinematic', enabled: false, credits_per_sec: 15, desc: 'Premium (coming soon)' },
  ],
  image_to_video: [
    { id: 'quick', label: 'Quick', enabled: true, credits_per_sec: 8, desc: 'Faster animation' },
    { id: 'studio', label: 'Studio', enabled: true, credits_per_sec: 10, default: true, desc: 'Default balanced' },
    { id: 'cinematic', label: 'Cinematic', enabled: false, credits_per_sec: 15, desc: 'Premium (coming soon)' },
  ],
  video_to_video: [
    { id: 'quick', label: 'Quick', enabled: true, credits_per_sec: 6, desc: 'Fast style transfer' },
    { id: 'studio', label: 'Studio', enabled: true, credits_per_sec: 8, default: true, desc: 'Default' },
    { id: 'cinematic', label: 'Cinematic', enabled: false, credits_per_sec: 12, desc: 'Premium (coming soon)' },
  ],
  ai_image_generator: [
    { id: 'quick', label: 'Quick', enabled: true, credits_per_image: 3, desc: 'FLUX Schnell' },
    { id: 'studio', label: 'Studio', enabled: true, credits_per_image: 5, default: true, desc: 'FLUX Dev' },
    { id: 'cinematic', label: 'Cinematic', enabled: false, credits_per_image: 8, desc: 'FLUX Pro (coming soon)' },
  ],
};

export default function QualityPicker({ feature, selectedId, onSelect, unit }: Props) {
  const [tiers, setTiers] = useState<Tier[]>(FALLBACK_TIERS[feature] || []);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/mh-models`);
        const f = r.data?.features?.[feature];
        if (f?.models?.length) setTiers(f.models);
      } catch (e) {}
    })();
  }, [feature]);

  const unitLabel = unit || (feature === 'ai_image_generator' ? '/image' : '/sec');

  return (
    <View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
        {tiers.map(t => {
          const active = selectedId === t.id;
          const disabled = !t.enabled;
          const credits = t.credits_per_sec ?? t.credits_per_image ?? 0;
          return (
            <TouchableOpacity
              key={t.id}
              style={[s.chip, active && s.chipActive, disabled && s.chipDisabled]}
              onPress={() => !disabled && onSelect(t.id)}
              disabled={disabled}
              activeOpacity={0.8}
            >
              <View style={s.chipHead}>
                <Text style={[s.chipLabel, active && { color: '#fff' }, disabled && s.chipLabelDisabled]}>{t.label}</Text>
                {disabled && <Ionicons name="lock-closed" size={11} color="#64748B" style={{ marginLeft: 4 }} />}
              </View>
              <Text style={[s.chipCost, active && { color: '#fff' }, disabled && s.chipLabelDisabled]}>
                MH: {credits} cr{unitLabel}
              </Text>
              {t.desc ? (
                <Text style={[s.chipDesc, active && { color: '#fff' }, disabled && s.chipLabelDisabled]} numberOfLines={2}>
                  {t.desc}
                </Text>
              ) : null}
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  chip: {
    minWidth: 130,
    backgroundColor: '#1E293B',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  chipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  chipDisabled: { opacity: 0.5, borderStyle: 'dashed' },
  chipHead: { flexDirection: 'row', alignItems: 'center' },
  chipLabel: { color: '#E2E8F0', fontSize: 14, fontWeight: '700' },
  chipLabelDisabled: { color: '#64748B' },
  chipCost: { color: '#F97316', fontSize: 11, fontWeight: '700', marginTop: 3 },
  chipDesc: { color: '#94A3B8', fontSize: 10, marginTop: 3, lineHeight: 13 },
});
