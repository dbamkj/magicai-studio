import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { useAuth } from '../src/AuthContext';

/**
 * Minimal invisible wrapper.
 *
 * Previous versions rendered an opaque yellow BETA bar at the top which
 * covered content and was un-themed. The user requested this removed in
 * favour of an admin-gated env switcher inside the profile modal + admin
 * panel. We keep a tiny corner pill ONLY for admins in non-PROD so the
 * current env/version is always visible during internal testing.
 */
export default function BetaChrome({ children }: { children: React.ReactNode }) {
  const { user, mode } = useAuth();
  const showPill = !!user?.is_admin && !!mode && mode.env !== 'PROD';
  return (
    <View style={{ flex: 1 }}>
      {children}
      {showPill && (
        <View pointerEvents="none" style={s.pillWrap}>
          <View
            style={[
              s.pill,
              mode!.env === 'DEV'
                ? { backgroundColor: 'rgba(16,185,129,0.18)', borderColor: 'rgba(16,185,129,0.55)' }
                : { backgroundColor: 'rgba(251,191,36,0.18)', borderColor: 'rgba(251,191,36,0.55)' },
            ]}
          >
            <Text
              style={[
                s.pillText,
                { color: mode!.env === 'DEV' ? '#10B981' : '#FBBF24' },
              ]}
            >
              {mode!.env} · {mode!.version || 'v1.0'}
            </Text>
          </View>
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  pillWrap: {
    position: 'absolute',
    bottom: Platform.OS === 'ios' ? 34 : 16,
    right: 12,
    zIndex: 999,
  },
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
  },
  pillText: { fontSize: 10, fontWeight: '900', letterSpacing: 0.8 },
});
