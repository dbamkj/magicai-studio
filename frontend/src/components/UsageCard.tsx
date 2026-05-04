/**
 * Usage progress + upgrade banner UI bits driven by /api/me/limits.
 * Drop into Subscription / Profile / Home screens for instant context.
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Pressable } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import type { UpgradeHint, UsageBar, MyLimits } from './useMyLimits';

const ICON_BY_BUCKET: Record<string, keyof typeof Ionicons.glyphMap> = {
  reels: 'film-outline',
  lipsync: 'mic-outline',
  ai_videos: 'sparkles-outline',
  images: 'image-outline',
};
const LABEL_BY_BUCKET: Record<string, string> = {
  reels: 'Reels',
  lipsync: 'Lip syncs',
  ai_videos: 'AI videos',
  images: 'Images',
};

export function UsageRow({ bucket, bar }: { bucket: string; bar: UsageBar }) {
  const icon = ICON_BY_BUCKET[bucket] || 'stats-chart-outline';
  const label = LABEL_BY_BUCKET[bucket] || bucket;
  const danger = bar.exhausted;
  const warning = !bar.unlimited && bar.pct >= 80 && !bar.exhausted;
  const barColor = danger ? '#ef4444' : warning ? '#f59e0b' : '#7afcff';
  return (
    <View style={s.row}>
      <View style={s.rowHead}>
        <View style={s.rowLeft}>
          <Ionicons name={icon} size={16} color="#cbd2e8" style={{ marginRight: 8 }} />
          <Text style={s.rowLabel}>{label}</Text>
        </View>
        <Text style={[s.rowMeta, danger && { color: '#ff8c9c' }]}>
          {bar.unlimited ? 'Unlimited' : `${bar.used}/${bar.cap}`}
        </Text>
      </View>
      {!bar.unlimited && (
        <View style={s.barTrack}>
          <View style={[s.barFill, { width: `${Math.min(100, bar.pct)}%`, backgroundColor: barColor }]} />
        </View>
      )}
    </View>
  );
}

export function UsageCard({ limits }: { limits: MyLimits }) {
  const m = limits.usage_this_month;
  return (
    <LinearGradient
      colors={['rgba(255,93,177,0.10)', 'rgba(122,252,255,0.06)']}
      style={s.card}
    >
      <View style={s.cardHead}>
        <Text style={s.cardTitle}>This month · {limits.tier.label}</Text>
        <Text style={s.cardSub}>{limits.credits.balance.toLocaleString()} credits left</Text>
      </View>
      <UsageRow bucket="reels" bar={m.reels} />
      <UsageRow bucket="lipsync" bar={m.lipsync} />
      <UsageRow bucket="ai_videos" bar={m.ai_videos} />
      {/* Daily image cap (only really matters for Free) */}
      {!limits.usage_today.images.unlimited && (
        <View style={{ marginTop: 8, paddingTop: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: 'rgba(255,255,255,0.12)' }}>
          <UsageRow bucket="images" bar={limits.usage_today.images} />
          <Text style={s.dailyHint}>Resets daily at 00:00 UTC</Text>
        </View>
      )}
    </LinearGradient>
  );
}

export function UpgradeBanner({ hint }: { hint: UpgradeHint }) {
  const accent = hint.target_tier === 'pro' ? ['#ff8a4c', '#ff5db1'] : ['#7afcff', '#5db1ff'];
  return (
    <Pressable
      onPress={() => router.push({ pathname: '/subscription', params: { focus: hint.target_tier } } as any)}
      style={({ pressed }) => [s.banner, pressed && { opacity: 0.85 }]}
    >
      <LinearGradient colors={accent as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.bannerGrad}>
        <View style={{ flex: 1 }}>
          <Text style={s.bannerText}>{hint.text}</Text>
          <Text style={s.bannerCta}>{hint.cta} →</Text>
        </View>
        <Ionicons name="chevron-forward" size={20} color="#fff" />
      </LinearGradient>
    </Pressable>
  );
}

export function LockBadge({ label = 'Pro' }: { label?: string }) {
  return (
    <View style={s.lockBadge}>
      <Ionicons name="lock-closed" size={10} color="#fff" />
      <Text style={s.lockText}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  card: {
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
  },
  cardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  cardTitle: { color: '#fff', fontSize: 14, fontWeight: '800', letterSpacing: 0.4 },
  cardSub: { color: '#7afcff', fontSize: 12, fontWeight: '700' },
  row: { marginBottom: 12 },
  rowHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  rowLeft: { flexDirection: 'row', alignItems: 'center' },
  rowLabel: { color: '#cbd2e8', fontSize: 13, fontWeight: '600' },
  rowMeta: { color: '#cbd2e8', fontSize: 12, fontWeight: '700' },
  barTrack: {
    height: 6,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 3,
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: 3 },
  dailyHint: { color: '#8a93b0', fontSize: 11, marginTop: 4, fontStyle: 'italic' },

  banner: { marginBottom: 10, borderRadius: 14, overflow: 'hidden' },
  bannerGrad: { flexDirection: 'row', alignItems: 'center', padding: 14 },
  bannerText: { color: '#fff', fontSize: 13, fontWeight: '600', lineHeight: 18 },
  bannerCta: { color: '#fff', fontSize: 12, fontWeight: '800', marginTop: 4, letterSpacing: 0.3 },

  lockBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,90,160,0.85)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  lockText: { color: '#fff', fontSize: 9, fontWeight: '800', marginLeft: 3, letterSpacing: 0.4 },
});
