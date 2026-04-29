import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

type Props = {
  // Called with the pause tag string to insert, e.g. "[pause:1.5]".
  onInsert: (tag: string) => void;
  // Optional label shown before chips. Defaults to 'Insert pause'.
  label?: string;
  // Compact mode renders smaller chips (for use next to dense inputs).
  compact?: boolean;
  // Allow caller to override the list of pause values.
  values?: number[];
};

const DEFAULTS = [0.3, 0.5, 1.0, 1.5, 2.0];

/** Row of tappable chips that insert a `[pause:X.Y]` tag into a dialogue / lyrics
 *  input. Eliminates the need for users to type the tag by hand and makes the
 *  feature discoverable in every dialogue-bearing tool (videogen / avatar /
 *  lipsync / multishot / story). */
export default function PauseChips({ onInsert, label, compact = false, values = DEFAULTS }: Props) {
  return (
    <View style={s.wrap}>
      <View style={s.headRow}>
        <Ionicons name="pause-circle" size={compact ? 12 : 14} color="#A78BFA" />
        <Text style={[s.label, compact && { fontSize: 10 }]}>{label || 'Tap to insert pause'}</Text>
      </View>
      <View style={s.row}>
        {values.map(v => {
          const tag = `[pause:${v.toFixed(1)}]`;
          return (
            <TouchableOpacity
              key={tag}
              onPress={() => onInsert(tag)}
              style={[s.chip, compact && s.chipCompact]}
              activeOpacity={0.75}
              accessibilityRole="button"
              accessibilityLabel={`Insert pause of ${v} seconds`}
            >
              <Text style={[s.chipText, compact && s.chipTextCompact]}>{tag}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { marginTop: 6, marginBottom: 2 },
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 6 },
  label: { color: '#94A3B8', fontSize: 11, fontWeight: '600' },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: {
    backgroundColor: 'rgba(167,139,250,0.12)',
    borderRadius: 999,
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: 'rgba(167,139,250,0.4)',
  },
  chipCompact: { paddingHorizontal: 8, paddingVertical: 3 },
  chipText: { color: '#C4B5FD', fontSize: 12, fontWeight: '700', fontFamily: 'monospace' },
  chipTextCompact: { fontSize: 10 },
});
