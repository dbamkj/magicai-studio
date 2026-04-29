/**
 * GlassHeader — unified Premium Neon Glass header used on Library,
 * Subscription, Avatar Studio, Marketplace, Profile etc.
 */
import React, { ReactNode } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Platform, ViewStyle,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

type IconName = keyof typeof Ionicons.glyphMap;

type Props = {
  title: string;
  subtitle?: string;
  icon?: IconName;
  gradient?: [string, string, ...string[]];
  onBack?: (() => void) | null;
  right?: ReactNode;
  style?: ViewStyle;
};

export default function GlassHeader({
  title, subtitle, icon = 'sparkles',
  gradient = ['#A78BFA', '#EC4899', '#FBBF24'],
  onBack, right, style,
}: Props) {
  return (
    <View style={[s.row, style]}>
      {onBack !== null ? (
        <TouchableOpacity onPress={onBack || (() => {})} style={s.btn} activeOpacity={0.7}>
          <Ionicons name="arrow-back" size={22} color="#fff" />
        </TouchableOpacity>
      ) : (
        <View style={{ width: 40 }} />
      )}

      <View style={s.titleWrap}>
        <View style={s.glyph}>
          <LinearGradient
            colors={gradient}
            start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
            style={StyleSheet.absoluteFill}
          />
          <Ionicons name={icon} size={16} color="#fff" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.title} numberOfLines={1}>{title}</Text>
          {subtitle ? (
            <Text style={s.subtitle} numberOfLines={2} ellipsizeMode="tail">{subtitle}</Text>
          ) : null}
        </View>
      </View>

      <View style={s.rightSlot}>{right}</View>
    </View>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingTop: 6, paddingBottom: 10,
  },
  btn: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  titleWrap: {
    flex: 1, flexDirection: 'row', alignItems: 'center',
    gap: 10, marginHorizontal: 12,
  },
  glyph: {
    width: 32, height: 32, borderRadius: 16,
    overflow: 'hidden', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)',
    ...Platform.select({
      web: { boxShadow: '0 0 14px rgba(236,72,153,0.4)' as any },
      default: {
        shadowColor: '#EC4899', shadowOpacity: 0.4,
        shadowRadius: 8, shadowOffset: { width: 0, height: 0 },
      },
    }),
  },
  title: { fontSize: 19, fontWeight: '900', color: '#fff', letterSpacing: 0.3 },
  subtitle: { fontSize: 11, color: '#A78BFA', fontWeight: '700', marginTop: 1 },
  rightSlot: { minWidth: 40, alignItems: 'flex-end', justifyContent: 'center' },
});
