/* ResolutionPicker — tier-aware video resolution selector.
 *
 * Behaviour:
 *   - Free    → 480p enabled · 720p / 1080p / 4K locked (tap → Upgrade alert)
 *   - Starter → 480p, 720p enabled · 1080p / 4K locked
 *   - Creator → 480p, 720p, 1080p enabled · 4K locked
 *   - Pro     → all 4 enabled
 *
 * Uses the central useTierGuard hook for the tier→allowed-resolutions map
 * declared in src/useTierGuard.ts.
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTierGuard } from './useTierGuard';

type Res = '480p' | '720p' | '1080p' | '4K';

type Props = {
  selected: string;
  onSelect: (res: string) => void;
  /** Optional override — restrict the visible options (e.g. some tools cap at 1080p) */
  visibleOptions?: Res[];
};

const ALL_OPTIONS: Array<{ id: Res; note: string; minTier: 'free' | 'starter' | 'creator' | 'pro' }> = [
  { id: '480p',  note: 'Fast · small',     minTier: 'free' },
  { id: '720p',  note: 'HD default',       minTier: 'starter' },
  { id: '1080p', note: 'Full HD',          minTier: 'creator' },
  { id: '4K',    note: 'Ultra HD',         minTier: 'pro' },
];

export default function ResolutionPicker({ selected, onSelect, visibleOptions }: Props) {
  const tier = useTierGuard();
  const visible = ALL_OPTIONS.filter(o => !visibleOptions || visibleOptions.includes(o.id));

  return (
    <View style={s.row}>
      {visible.map(o => {
        const allowed = tier.allowedResolutions.includes(o.id);
        const active = selected === o.id;
        return (
          <TouchableOpacity
            key={o.id}
            style={[s.chip, active && s.chipActive, !allowed && s.chipLocked]}
            onPress={() => {
              if (!allowed) {
                // Show upgrade alert for the *exact* tier that unlocks this res.
                tier.requirePlan(o.minTier, `${o.id} resolution`);
                return;
              }
              onSelect(o.id);
            }}
            activeOpacity={0.8}
          >
            <View style={s.chipHead}>
              <Text style={[s.chipLabel, active && { color: '#fff' }, !allowed && s.chipLabelLocked]}>
                {o.id}
              </Text>
              {!allowed && (
                <Ionicons name="lock-closed" size={10} color="#FBBF24" style={{ marginLeft: 4 }} />
              )}
            </View>
            <Text style={[s.chipNote, active && { color: '#fff' }, !allowed && s.chipLabelLocked]}>
              {allowed ? o.note : `${o.minTier[0].toUpperCase()}${o.minTier.slice(1)}+`}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8 },
  chip: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
  },
  chipActive: { backgroundColor: '#F97316', borderColor: '#F97316' },
  chipLocked: { borderStyle: 'dashed', backgroundColor: 'rgba(30,41,59,0.55)', borderColor: 'rgba(251,191,36,0.45)' },
  chipHead: { flexDirection: 'row', alignItems: 'center' },
  chipLabel: { color: '#E2E8F0', fontSize: 14, fontWeight: '700' },
  chipLabelLocked: { color: '#94A3B8' },
  chipNote: { color: '#94A3B8', fontSize: 10, marginTop: 2 },
});
