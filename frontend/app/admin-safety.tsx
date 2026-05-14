/**
 * /admin-safety — Sprint 3 v2 Admin Safety Dashboard (Session 37)
 *
 * Visualizes moderation records, strike leaderboard, and ban management.
 * Admin-only. Drives off the new admin endpoints:
 *   GET  /api/admin/moderation/records
 *   POST /api/admin/moderation/records/{id}/override
 *   GET  /api/admin/moderation/users-strikes
 *   POST /api/admin/users/{id}/ban
 *   POST /api/admin/users/{id}/unban
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  Pressable, Alert, RefreshControl, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { useAuth } from '../src/AuthContext';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Record = {
  id: string;
  user_id: string | null;
  source: string;
  kind: string;
  content_preview: string;
  categories: string[];
  severity: number;
  confidence: number;
  reason: string;
  status: 'blocked' | 'overridden_allow' | 'confirmed_block';
  admin_note: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
};

type StrikeUser = {
  id: string;
  email: string;
  name?: string;
  subscription_tier?: string;
  strike_count?: number;
  strike_score?: number;
  is_banned?: boolean;
  banned_at?: string;
  ban_reason?: string;
};

type Stats = { total: number; open: number; overridden: number; confirmed: number };

type Tab = 'records' | 'strikes';

export default function AdminSafetyDashboard() {
  const router = useRouter();
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('records');
  const [records, setRecords] = useState<Record[]>([]);
  const [strikes, setStrikes] = useState<StrikeUser[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, open: 0, overridden: 0, confirmed: 0 });
  const [filter, setFilter] = useState<'all' | 'blocked' | 'overridden_allow' | 'confirmed_block'>('blocked');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionBusy, setActionBusy] = useState<string | null>(null);

  const adminGuard = user?.is_admin;

  const authHeaders = async () => {
    const token = await AsyncStorage.getItem('@auth_token');
    return { Authorization: `Bearer ${token}` };
  };

  const fetchRecords = useCallback(async () => {
    try {
      const headers = await authHeaders();
      const params: any = { limit: 100 };
      if (filter !== 'all') params.status = filter;
      const r = await axios.get(`${BACKEND_URL}/api/admin/moderation/records`, { headers, params });
      setRecords(r.data?.records || []);
      setStats(r.data?.stats || { total: 0, open: 0, overridden: 0, confirmed: 0 });
    } catch (e) {
      // silent
    }
  }, [filter]);

  const fetchStrikes = useCallback(async () => {
    try {
      const headers = await authHeaders();
      const r = await axios.get(`${BACKEND_URL}/api/admin/moderation/users-strikes`, {
        headers, params: { min_score: 1, limit: 100 },
      });
      setStrikes(r.data?.users || []);
    } catch (e) {
      // silent
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([fetchRecords(), fetchStrikes()]);
    setRefreshing(false);
  }, [fetchRecords, fetchStrikes]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([fetchRecords(), fetchStrikes()]);
      setLoading(false);
    })();
  }, [fetchRecords, fetchStrikes]);

  // ── Actions ──
  const onOverride = async (rec: Record, decision: 'overridden_allow' | 'confirmed_block') => {
    Alert.alert(
      decision === 'overridden_allow' ? 'Mark as false positive?' : 'Confirm this block?',
      decision === 'overridden_allow'
        ? 'This removes the strike from the user and re-allows similar content.'
        : 'This locks the decision as a correct block.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Confirm',
          onPress: async () => {
            try {
              setActionBusy(rec.id);
              const headers = await authHeaders();
              await axios.post(
                `${BACKEND_URL}/api/admin/moderation/records/${rec.id}/override`,
                { decision, admin_note: '' },
                { headers },
              );
              await refreshAll();
            } catch (e: any) {
              Alert.alert('Failed', e?.response?.data?.detail || e?.message || 'Unknown');
            } finally {
              setActionBusy(null);
            }
          },
        },
      ],
    );
  };

  const onBan = async (u: StrikeUser) => {
    Alert.alert(
      `Ban ${u.email}?`,
      'They will be blocked from all authenticated endpoints until unbanned.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Ban',
          style: 'destructive',
          onPress: async () => {
            try {
              setActionBusy(u.id);
              const headers = await authHeaders();
              await axios.post(
                `${BACKEND_URL}/api/admin/users/${u.id}/ban`,
                { reason: 'Banned from admin dashboard' },
                { headers },
              );
              await refreshAll();
            } catch (e: any) {
              Alert.alert('Failed', e?.response?.data?.detail || 'Unknown');
            } finally {
              setActionBusy(null);
            }
          },
        },
      ],
    );
  };

  const onUnban = async (u: StrikeUser) => {
    Alert.alert(
      `Unban ${u.email}?`,
      'Their strike score will reset to 0 and they regain full access.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Unban',
          onPress: async () => {
            try {
              setActionBusy(u.id);
              const headers = await authHeaders();
              await axios.post(
                `${BACKEND_URL}/api/admin/users/${u.id}/unban`, {},
                { headers },
              );
              await refreshAll();
            } catch (e: any) {
              Alert.alert('Failed', e?.response?.data?.detail || 'Unknown');
            } finally {
              setActionBusy(null);
            }
          },
        },
      ],
    );
  };

  if (!adminGuard) {
    return (
      <View style={styles.root}>
        <AuroraBackground />
        <SafeAreaView style={{ flex: 1 }}>
          <GlassHeader icon="shield-half" title="Safety Dashboard" subtitle="Admin only" onBack={() => router.back()} />
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 }}>
            <Ionicons name="lock-closed" size={48} color="#EF4444" />
            <Text style={{ color: '#fff', fontSize: 16, fontWeight: '700', marginTop: 12 }}>Admin access required</Text>
            <Text style={{ color: '#94A3B8', marginTop: 4 }}>This page is restricted to platform admins.</Text>
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
          icon="shield-half"
          title="Safety Dashboard"
          subtitle="Moderation · Strikes · Bans"
          onBack={() => router.back()}
        />
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 110 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refreshAll} tintColor="#7afcff" />}
        >
          {/* Stats cards */}
          <View style={styles.statsRow}>
            <StatCard label="Total" value={stats.total} color="#7afcff" icon="archive" />
            <StatCard label="Open" value={stats.open} color="#FBBF24" icon="flag" />
            <StatCard label="Overridden" value={stats.overridden} color="#7affc7" icon="checkmark-circle" />
            <StatCard label="Confirmed" value={stats.confirmed} color="#EF4444" icon="close-circle" />
          </View>

          {/* Tabs */}
          <View style={styles.tabRow}>
            <Pressable
              onPress={() => setTab('records')}
              style={[styles.tab, tab === 'records' && styles.tabActive]}
            >
              <Ionicons name="document-text" size={14} color={tab === 'records' ? '#fff' : '#94A3B8'} />
              <Text style={[styles.tabText, tab === 'records' && styles.tabTextActive]}>
                Records ({records.length})
              </Text>
            </Pressable>
            <Pressable
              onPress={() => setTab('strikes')}
              style={[styles.tab, tab === 'strikes' && styles.tabActive]}
            >
              <Ionicons name="warning" size={14} color={tab === 'strikes' ? '#fff' : '#94A3B8'} />
              <Text style={[styles.tabText, tab === 'strikes' && styles.tabTextActive]}>
                Users w/ strikes ({strikes.length})
              </Text>
            </Pressable>
          </View>

          {loading ? (
            <ActivityIndicator size="large" color="#7afcff" style={{ marginVertical: 40 }} />
          ) : tab === 'records' ? (
            <>
              {/* Filter chips */}
              <View style={styles.chipsRow}>
                {(['all', 'blocked', 'overridden_allow', 'confirmed_block'] as const).map((f) => (
                  <Pressable
                    key={f}
                    onPress={() => setFilter(f)}
                    style={[styles.chip, filter === f && styles.chipActive]}
                  >
                    <Text style={[styles.chipText, filter === f && styles.chipTextActive]}>
                      {f === 'all' ? 'All' : f.replace(/_/g, ' ')}
                    </Text>
                  </Pressable>
                ))}
              </View>

              {records.length === 0 ? (
                <View style={styles.empty}>
                  <Ionicons name="checkmark-circle" size={36} color="#7affc7" />
                  <Text style={styles.emptyText}>No moderation records match this filter.</Text>
                </View>
              ) : (
                records.map((r) => (
                  <RecordCard
                    key={r.id}
                    rec={r}
                    busy={actionBusy === r.id}
                    onAllow={() => onOverride(r, 'overridden_allow')}
                    onConfirm={() => onOverride(r, 'confirmed_block')}
                  />
                ))
              )}
            </>
          ) : (
            <>
              {strikes.length === 0 ? (
                <View style={styles.empty}>
                  <Ionicons name="checkmark-circle" size={36} color="#7affc7" />
                  <Text style={styles.emptyText}>No users with strikes — clean platform 🎉</Text>
                </View>
              ) : (
                strikes.map((u) => (
                  <StrikeCard
                    key={u.id}
                    user={u}
                    busy={actionBusy === u.id}
                    onBan={() => onBan(u)}
                    onUnban={() => onUnban(u)}
                  />
                ))
              )}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}


// ────────────────────────────────────────────────────────
// Sub-components
// ────────────────────────────────────────────────────────
function StatCard({ label, value, color, icon }: { label: string; value: number; color: string; icon: any }) {
  return (
    <View style={[styles.statCard, { borderColor: `${color}55` }]}>
      <Ionicons name={icon} size={14} color={color} />
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function severityColor(sev: number) {
  if (sev >= 3) return '#EF4444';
  if (sev === 2) return '#FBBF24';
  return '#A78BFA';
}

function RecordCard({ rec, busy, onAllow, onConfirm }: {
  rec: Record; busy: boolean; onAllow: () => void; onConfirm: () => void;
}) {
  const isPending = rec.status === 'blocked';
  return (
    <View style={[styles.recordCard, !isPending && { opacity: 0.7 }]}>
      <View style={styles.recordHeader}>
        <View style={[styles.sevPill, { backgroundColor: severityColor(rec.severity) + '22', borderColor: severityColor(rec.severity) + '88' }]}>
          <Text style={[styles.sevText, { color: severityColor(rec.severity) }]}>SEV {rec.severity}</Text>
        </View>
        <Text style={styles.recordSource} numberOfLines={1}>{rec.source}</Text>
        <StatusBadge status={rec.status} />
      </View>

      <Text style={styles.recordReason}>{rec.reason}</Text>
      <Text style={styles.recordPreview} numberOfLines={3}>"{rec.content_preview}"</Text>

      <View style={styles.recordMeta}>
        <Text style={styles.metaTag}>
          <Ionicons name="folder-outline" size={10} /> {rec.categories.join(', ')}
        </Text>
        <Text style={styles.metaTag}>
          <Ionicons name="trending-up-outline" size={10} /> {Math.round(rec.confidence * 100)}%
        </Text>
        <Text style={styles.metaTag}>
          <Ionicons name="time-outline" size={10} /> {new Date(rec.created_at).toLocaleString()}
        </Text>
      </View>

      {isPending && (
        <View style={styles.recordActions}>
          <TouchableOpacity onPress={onAllow} disabled={busy} style={styles.actionAllow} activeOpacity={0.85}>
            <Ionicons name="checkmark" size={14} color="#7affc7" />
            <Text style={[styles.actionText, { color: '#7affc7' }]}>False positive</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={onConfirm} disabled={busy} style={styles.actionConfirm} activeOpacity={0.85}>
            <Ionicons name="close" size={14} color="#EF4444" />
            <Text style={[styles.actionText, { color: '#EF4444' }]}>Confirm block</Text>
          </TouchableOpacity>
        </View>
      )}
      {rec.admin_note ? (
        <Text style={styles.adminNote}>Admin note: {rec.admin_note}</Text>
      ) : null}
    </View>
  );
}

function StatusBadge({ status }: { status: Record['status'] }) {
  const map: Record<string, { c: string; t: string }> = {
    blocked: { c: '#FBBF24', t: 'OPEN' },
    overridden_allow: { c: '#7affc7', t: 'OVERRIDDEN' },
    confirmed_block: { c: '#EF4444', t: 'CONFIRMED' },
  };
  const m = map[status] || map.blocked;
  return (
    <View style={[styles.statusBadge, { backgroundColor: m.c + '22', borderColor: m.c + '88' }]}>
      <Text style={[styles.statusText, { color: m.c }]}>{m.t}</Text>
    </View>
  );
}

function StrikeCard({ user, busy, onBan, onUnban }: {
  user: StrikeUser; busy: boolean; onBan: () => void; onUnban: () => void;
}) {
  return (
    <View style={[styles.strikeCard, user.is_banned && styles.strikeCardBanned]}>
      <View style={styles.strikeHead}>
        <View style={{ flex: 1 }}>
          <Text style={styles.strikeEmail} numberOfLines={1}>{user.email}</Text>
          <Text style={styles.strikeTier}>{user.subscription_tier || 'unknown tier'}</Text>
        </View>
        {user.is_banned ? (
          <View style={styles.bannedPill}>
            <Ionicons name="ban" size={12} color="#fff" />
            <Text style={styles.bannedText}>BANNED</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.strikeStats}>
        <View style={styles.strikeStatBox}>
          <Text style={styles.strikeStatValue}>{user.strike_count || 0}</Text>
          <Text style={styles.strikeStatLabel}>strikes</Text>
        </View>
        <View style={styles.strikeStatBox}>
          <Text style={[styles.strikeStatValue, { color: '#EF4444' }]}>{user.strike_score || 0}</Text>
          <Text style={styles.strikeStatLabel}>score</Text>
        </View>
      </View>

      {user.ban_reason ? (
        <Text style={styles.banReason} numberOfLines={2}>{user.ban_reason}</Text>
      ) : null}

      <View style={styles.strikeActions}>
        {user.is_banned ? (
          <TouchableOpacity onPress={onUnban} disabled={busy} style={styles.unbanBtn} activeOpacity={0.85}>
            {busy ? <ActivityIndicator color="#7affc7" /> : (
              <>
                <Ionicons name="lock-open" size={14} color="#7affc7" />
                <Text style={[styles.actionText, { color: '#7affc7' }]}>Unban</Text>
              </>
            )}
          </TouchableOpacity>
        ) : (
          <TouchableOpacity onPress={onBan} disabled={busy} style={styles.banBtn} activeOpacity={0.85}>
            {busy ? <ActivityIndicator color="#EF4444" /> : (
              <>
                <Ionicons name="ban" size={14} color="#EF4444" />
                <Text style={[styles.actionText, { color: '#EF4444' }]}>Ban user</Text>
              </>
            )}
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}


// ────────────────────────────────────────────────────────
// Styles
// ────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#070314' },
  statsRow: { flexDirection: 'row', gap: 8, marginTop: 12, marginBottom: 12 },
  statCard: {
    flex: 1, padding: 10, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, alignItems: 'center', gap: 2,
  },
  statValue: { fontSize: 20, fontWeight: '800' },
  statLabel: { fontSize: 9, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: '700' },

  tabRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  tab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 10, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  tabActive: { backgroundColor: 'rgba(122,252,255,0.15)', borderColor: 'rgba(122,252,255,0.50)' },
  tabText: { color: '#94A3B8', fontSize: 12, fontWeight: '700' },
  tabTextActive: { color: '#fff' },

  chipsRow: { flexDirection: 'row', gap: 6, marginBottom: 12, flexWrap: 'wrap' },
  chip: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  chipActive: { backgroundColor: 'rgba(255,93,177,0.18)', borderColor: 'rgba(255,93,177,0.5)' },
  chipText: { color: '#94A3B8', fontSize: 11, fontWeight: '600' },
  chipTextActive: { color: '#fff' },

  empty: { alignItems: 'center', padding: 40 },
  emptyText: { color: '#94A3B8', marginTop: 12, fontSize: 13 },

  // Record card
  recordCard: {
    padding: 14, marginBottom: 10, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  recordHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  sevPill: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, borderWidth: 1 },
  sevText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },
  recordSource: { color: '#cbd2e8', fontSize: 11, fontFamily: Platform.select({ ios: 'Menlo', default: 'monospace' }), flex: 1 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, borderWidth: 1 },
  statusText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },
  recordReason: { color: '#fff', fontSize: 13, fontWeight: '600', marginBottom: 4 },
  recordPreview: { color: '#94A3B8', fontSize: 12, fontStyle: 'italic', marginBottom: 8, lineHeight: 16 },
  recordMeta: { flexDirection: 'row', gap: 10, flexWrap: 'wrap', marginBottom: 4 },
  metaTag: { color: '#94A3B8', fontSize: 10 },
  recordActions: { flexDirection: 'row', gap: 8, marginTop: 10 },
  actionAllow: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 8, borderRadius: 8,
    backgroundColor: 'rgba(122,255,199,0.10)', borderWidth: 1, borderColor: 'rgba(122,255,199,0.40)',
  },
  actionConfirm: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 8, borderRadius: 8,
    backgroundColor: 'rgba(239,68,68,0.10)', borderWidth: 1, borderColor: 'rgba(239,68,68,0.40)',
  },
  actionText: { fontSize: 11, fontWeight: '700' },
  adminNote: { color: '#94A3B8', fontSize: 11, fontStyle: 'italic', marginTop: 8, padding: 6, backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 6 },

  // Strike card
  strikeCard: {
    padding: 14, marginBottom: 10, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  strikeCardBanned: { borderColor: 'rgba(239,68,68,0.40)', backgroundColor: 'rgba(239,68,68,0.06)' },
  strikeHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  strikeEmail: { color: '#fff', fontSize: 14, fontWeight: '700' },
  strikeTier: { color: '#94A3B8', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8 },
  bannedPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: '#EF4444' },
  bannedText: { color: '#fff', fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },
  strikeStats: { flexDirection: 'row', gap: 10, marginBottom: 8 },
  strikeStatBox: {
    flex: 1, paddingVertical: 10, borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.03)', alignItems: 'center',
  },
  strikeStatValue: { color: '#fff', fontSize: 22, fontWeight: '800' },
  strikeStatLabel: { color: '#94A3B8', fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5 },
  banReason: { color: '#FCA5A5', fontSize: 11, fontStyle: 'italic', marginBottom: 8, lineHeight: 14 },
  strikeActions: { flexDirection: 'row', gap: 8 },
  banBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 10, borderRadius: 10,
    backgroundColor: 'rgba(239,68,68,0.10)', borderWidth: 1, borderColor: 'rgba(239,68,68,0.40)',
  },
  unbanBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 10, borderRadius: 10,
    backgroundColor: 'rgba(122,255,199,0.10)', borderWidth: 1, borderColor: 'rgba(122,255,199,0.40)',
  },
});
