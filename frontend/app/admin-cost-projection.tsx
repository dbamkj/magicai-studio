/**
 * /admin-cost-projection — Session 40
 *
 * Real-time MagicHour cost + revenue projection. Admin-only.
 * Pulls from new GET /api/admin/cost-projection?window_days=30.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  Pressable, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { useAuth } from '../src/AuthContext';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Projection = {
  window_days: number;
  revenue: { monthly_run_rate: number; breakdown: any[] };
  cogs: {
    variable_monthly_inr: number;
    mh_subscription_inr: number;
    emergent_llm_inr: number;
    sarvam_inr: number;
    razorpay_fee_inr: number;
    total_monthly_inr: number;
    feature_breakdown: any[];
  };
  profit: { monthly_inr: number; margin_pct: number };
  assumptions: any;
};

export default function CostProjection() {
  const router = useRouter();
  const { user } = useAuth();
  const [data, setData] = useState<Projection | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [window_, setWindow] = useState<7 | 30 | 90>(30);

  const fetchProjection = useCallback(async () => {
    try {
      const token = await AsyncStorage.getItem('magicai_jwt_v1');
      const r = await axios.get(
        `${BACKEND_URL}/api/admin/cost-projection?window_days=${window_}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setData(r.data);
    } catch (e) {
      // silent
    }
  }, [window_]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await fetchProjection();
      setLoading(false);
    })();
  }, [fetchProjection]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchProjection();
    setRefreshing(false);
  }, [fetchProjection]);

  if (!user?.is_admin) {
    return (
      <View style={styles.root}>
        <AuroraBackground />
        <SafeAreaView style={{ flex: 1 }}>
          <GlassHeader icon="analytics" title="Cost Projection" subtitle="Admin only" onBack={() => router.back()} />
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 }}>
            <Ionicons name="lock-closed" size={48} color="#EF4444" />
            <Text style={{ color: '#fff', fontWeight: '700', marginTop: 12 }}>Admin access required</Text>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <AuroraBackground />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <GlassHeader
          icon="analytics"
          title="Cost Projection"
          subtitle="MH spend vs revenue · run-rate"
          onBack={() => router.back()}
        />
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 110 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#7afcff" />}
        >
          {/* Window selector */}
          <View style={styles.toggleRow}>
            {([7, 30, 90] as const).map((w) => (
              <Pressable key={w} onPress={() => setWindow(w)} style={[styles.pill, window_ === w && styles.pillActive]}>
                <Text style={[styles.pillText, window_ === w && styles.pillTextActive]}>{w}d</Text>
              </Pressable>
            ))}
          </View>

          {loading || !data ? (
            <ActivityIndicator color="#7afcff" size="large" style={{ marginVertical: 40 }} />
          ) : (
            <>
              {/* Hero cards */}
              <View style={styles.heroRow}>
                <View style={[styles.heroCard, { borderColor: 'rgba(122,255,199,0.5)' }]}>
                  <Text style={styles.heroLabel}>REVENUE MRR</Text>
                  <Text style={[styles.heroValue, { color: '#7affc7' }]}>₹{data.revenue.monthly_run_rate.toLocaleString('en-IN')}</Text>
                </View>
                <View style={[styles.heroCard, { borderColor: 'rgba(239,68,68,0.5)' }]}>
                  <Text style={styles.heroLabel}>TOTAL COST</Text>
                  <Text style={[styles.heroValue, { color: '#FCA5A5' }]}>₹{data.cogs.total_monthly_inr.toLocaleString('en-IN')}</Text>
                </View>
              </View>

              <View style={[styles.profitCard, data.profit.monthly_inr < 0 && styles.profitNegative]}>
                <Text style={styles.profitLabel}>PROJECTED MONTHLY PROFIT</Text>
                <Text style={[styles.profitValue, { color: data.profit.monthly_inr < 0 ? '#EF4444' : '#22d3ee' }]}>
                  {data.profit.monthly_inr < 0 ? '−' : ''}₹{Math.abs(data.profit.monthly_inr).toLocaleString('en-IN')}
                </Text>
                <Text style={styles.profitMargin}>{data.profit.margin_pct}% margin</Text>
              </View>

              {/* Revenue breakdown */}
              <Text style={styles.sectionTitle}>Revenue by tier</Text>
              {data.revenue.breakdown.filter(b => b.users > 0).map((b: any) => (
                <View key={b.tier} style={styles.row}>
                  <Text style={styles.rowLabel}>{b.tier.toUpperCase()}</Text>
                  <Text style={styles.rowSub}>{b.users} × ₹{b.price_inr}</Text>
                  <Text style={[styles.rowValue, { color: '#7affc7' }]}>₹{b.monthly_revenue_inr.toLocaleString('en-IN')}</Text>
                </View>
              ))}

              {/* Fixed costs */}
              <Text style={styles.sectionTitle}>Fixed monthly costs</Text>
              <CostRow label="MagicHour subscription" inr={data.cogs.mh_subscription_inr} />
              <CostRow label="Emergent LLM (estimate)" inr={data.cogs.emergent_llm_inr} />
              <CostRow label="Sarvam TTS (estimate)" inr={data.cogs.sarvam_inr} />
              <CostRow label="Razorpay 2% fee" inr={data.cogs.razorpay_fee_inr} />
              <CostRow label="Variable COGS (last {N}d → run-rate)".replace('{N}', String(window_))
                       inr={data.cogs.variable_monthly_inr} bold />

              {/* Feature-level cost */}
              <Text style={styles.sectionTitle}>Variable COGS by feature (last {window_}d)</Text>
              {data.cogs.feature_breakdown.length === 0 ? (
                <Text style={styles.empty}>No generations in the last {window_} days.</Text>
              ) : (
                data.cogs.feature_breakdown.map((f: any) => (
                  <View key={f.feature} style={styles.row}>
                    <Text style={styles.rowLabel}>{f.feature}</Text>
                    <Text style={styles.rowSub}>{f.count} × {f.mh_credits_per_call} MH cr</Text>
                    <Text style={[styles.rowValue, { color: '#FCA5A5' }]}>₹{f.cogs_inr}</Text>
                  </View>
                ))
              )}

              <Text style={styles.note}>
                ℹ️ {data.assumptions?.note ?? ''} Assumptions: ₹{data.assumptions?.mh_inr_per_credit ?? 0.135}/MH credit, base MH ₹{data.assumptions?.mh_base_subscription_inr ?? 1350}/mo.
              </Text>
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

function CostRow({ label, inr, bold }: { label: string; inr: number; bold?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={[styles.rowLabel, { flex: 2 }, bold && { fontWeight: '800' }]}>{label}</Text>
      <Text style={[styles.rowValue, { color: '#FCA5A5' }, bold && { fontWeight: '800' }]}>₹{inr.toLocaleString('en-IN')}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#070314' },
  toggleRow: {
    flexDirection: 'row', alignSelf: 'center', marginTop: 12, marginBottom: 8,
    backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: 999, padding: 4,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
  },
  pill: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999 },
  pillActive: { backgroundColor: 'rgba(122,252,255,0.20)' },
  pillText: { color: '#94A3B8', fontSize: 12, fontWeight: '700' },
  pillTextActive: { color: '#fff' },
  heroRow: { flexDirection: 'row', gap: 10, marginTop: 12, marginBottom: 12 },
  heroCard: {
    flex: 1, padding: 16, borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1,
  },
  heroLabel: { fontSize: 10, color: '#94A3B8', fontWeight: '800', letterSpacing: 1 },
  heroValue: { fontSize: 22, fontWeight: '800', marginTop: 4 },
  profitCard: {
    padding: 20, borderRadius: 18, alignItems: 'center',
    backgroundColor: 'rgba(34,211,238,0.10)',
    borderWidth: 1, borderColor: 'rgba(34,211,238,0.40)',
    marginBottom: 16,
  },
  profitNegative: { backgroundColor: 'rgba(239,68,68,0.10)', borderColor: 'rgba(239,68,68,0.40)' },
  profitLabel: { fontSize: 10, color: '#94A3B8', fontWeight: '800', letterSpacing: 1 },
  profitValue: { fontSize: 36, fontWeight: '800', marginTop: 4 },
  profitMargin: { fontSize: 13, color: '#cbd2e8', marginTop: 4, fontWeight: '600' },
  sectionTitle: { color: '#fff', fontSize: 14, fontWeight: '800', marginTop: 18, marginBottom: 8, letterSpacing: 0.5 },
  row: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  rowLabel: { flex: 1, color: '#cbd2e8', fontSize: 13, fontWeight: '600' },
  rowSub: { color: '#94A3B8', fontSize: 11, marginRight: 10 },
  rowValue: { fontSize: 13, fontWeight: '700' },
  empty: { color: '#94A3B8', fontSize: 12, padding: 12, textAlign: 'center' },
  note: { color: '#94A3B8', fontSize: 11, marginTop: 16, lineHeight: 16, fontStyle: 'italic' },
});
