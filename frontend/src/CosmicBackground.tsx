import React from 'react';
import { View, StyleSheet, Platform } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

/**
 * Cosmic purple/pink gradient background — shared across non-editor screens
 * to match the redesigned login screen.
 *
 * Usage:
 *   <CosmicBackground>
 *     <SafeAreaView style={{ flex: 1, backgroundColor: 'transparent' }}>
 *       ...screen...
 *     </SafeAreaView>
 *   </CosmicBackground>
 *
 * Media-editor screens (videogen, multishot, lipsync, faceswap, avatar, etc.)
 * intentionally keep their solid dark slate background for contrast while
 * working with media.
 */
export default function CosmicBackground({
  children,
  orbs = true,
}: {
  children: React.ReactNode;
  orbs?: boolean;
}) {
  return (
    <View style={s.root}>
      <LinearGradient
        colors={['#0A0118', '#1E0C3A', '#2D1B5A', '#1A0B2E']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      {orbs && (
        <>
          <View style={[s.orb, { top: 40, left: -60, backgroundColor: '#EC4899' }]} />
          <View style={[s.orb, { bottom: 120, right: -80, backgroundColor: '#8B5CF6' }]} />
          <View
            style={[
              s.orb,
              { top: '45%', right: 30, backgroundColor: '#FBBF24', opacity: 0.15, width: 160, height: 160 },
            ]}
          />
        </>
      )}
      {children}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0A0118' },
  orb: {
    position: 'absolute',
    width: 240,
    height: 240,
    borderRadius: 200,
    opacity: 0.25,
    ...Platform.select({
      web: { filter: 'blur(80px)' as any },
      default: {
        shadowColor: '#fff',
        shadowOpacity: 0.8,
        shadowRadius: 80,
        shadowOffset: { width: 0, height: 0 },
      },
    }),
  },
});
