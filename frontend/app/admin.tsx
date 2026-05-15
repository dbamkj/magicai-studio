import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert, TextInput, useWindowDimensions, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import { useAuth } from '../src/AuthContext';
import CosmicBackground from '../src/CosmicBackground';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

export default function AdminScreen() {
  const router = useRouter();
  const { user, token, mode, logout, loading: authLoading } = useAuth();
  const { width } = useWindowDimensions();
  const isDesktop = width >= 900;
  const [tab, setTab] = useState<'users' | 'usage' | 'profit' | 'env' | 'pattern_lab' | 'mh'>('users');
  const [users, setUsers] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [profitForm, setProfitForm] = useState({ total_users: '100', starter_users: '20', pro_users: '10', avg_videos_per_user_per_month: '10', avg_cost_per_video_inr: '8' });
  const [profitRes, setProfitRes] = useState<any>(null);
  const [switchingEnv, setSwitchingEnv] = useState(false);
  const [flagged, setFlagged] = useState<any[]>([]);
  const [plLoading, setPlLoading] = useState(false);
  const [plTriggerBusy, setPlTriggerBusy] = useState(false);
  const [mhUsage, setMhUsage] = useState<any>(null);
  const [mhLoading, setMhLoading] = useState(false);

  useEffect(() => {
    if (authLoading) return; // wait for auth to finish loading
    if (!user) { router.replace('/login'); return; }
    if (!user.is_admin) { Alert.alert('Access denied', 'Admin only'); router.replace('/'); return; }
    load();
  }, [user, authLoading]);

  const load = async () => {
    setLoading(true);
    try {
      const [u, s] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/admin/users`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${BACKEND_URL}/api/admin/usage`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setUsers(u.data.users || []); setStats(s.data);
    } catch (e: any) { Alert.alert('Error', e.message); }
    setLoading(false);
  };

  const adjustCredits = async (uid: string, delta: number) => {
    try {
      const r = await axios.post(`${BACKEND_URL}/api/admin/users/${uid}/credits`, { delta, reason: 'admin adjust' }, { headers: { Authorization: `Bearer ${token}` } });
      Alert.alert('✓', `New balance: ${r.data.new_balance}`); load();
    } catch (e: any) { Alert.alert('Error', e.message); }
  };

  const resetDaily = async (uid: string) => {
    try {
      await axios.post(`${BACKEND_URL}/api/admin/users/${uid}/reset-daily`, {}, { headers: { Authorization: `Bearer ${token}` } });
      Alert.alert('✓', 'Daily usage reset'); load();
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || e.message); }
  };

  const calcProfit = async () => {
    try {
      const r = await axios.post(`${BACKEND_URL}/api/admin/profit`, {
        total_users: parseInt(profitForm.total_users) || 0,
        starter_users: parseInt(profitForm.starter_users) || 0,
        pro_users: parseInt(profitForm.pro_users) || 0,
        avg_videos_per_user_per_month: parseFloat(profitForm.avg_videos_per_user_per_month) || 10,
        avg_cost_per_video_inr: parseFloat(profitForm.avg_cost_per_video_inr) || 8,
      }, { headers: { Authorization: `Bearer ${token}` } });
      setProfitRes(r.data);
    } catch (e: any) { Alert.alert('Error', e.message); }
  };

  const loadFlagged = async () => {
    setPlLoading(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/admin/pattern-lab/flagged`, { headers: { Authorization: `Bearer ${token}` } });
      setFlagged(r.data?.flagged || []);
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || e.message); }
    setPlLoading(false);
  };

  const moderatePL = async (templateId: string, action: 'approve' | 'deactivate' | 'delete') => {
    const title = action === 'delete' ? 'Delete this template permanently?' : action === 'deactivate' ? 'Deactivate (hide from feed)?' : 'Approve (clear all flags)?';
    // @ts-ignore
    const ok = (typeof window !== 'undefined' && window.confirm) ? window.confirm(title) : true;
    if (!ok) return;
    try {
      await axios.post(`${BACKEND_URL}/api/admin/pattern-lab/moderate/${templateId}`, { action }, { headers: { Authorization: `Bearer ${token}` } });
      loadFlagged();
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || e.message); }
  };

  const triggerPLRefresh = async () => {
    setPlTriggerBusy(true);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/admin/pattern-lab/trigger`, {}, { headers: { Authorization: `Bearer ${token}` }, timeout: 180000 });
      Alert.alert('Pattern Lab refresh', `inserted ${r.data?.inserted || 0} of ${r.data?.total_attempted || 5} templates`);
      loadFlagged();
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || e.message); }
    setPlTriggerBusy(false);
  };

  useEffect(() => {
    if (tab === 'pattern_lab' && token && user?.is_admin) loadFlagged();
    if (tab === 'mh' && token && user?.is_admin) loadMhUsage();
  }, [tab, token, user]);

  const loadMhUsage = async () => {
    setMhLoading(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/admin/mh-usage`, { headers: { Authorization: `Bearer ${token}` } });
      setMhUsage(r.data);
    } catch (e: any) { Alert.alert('Error', e.response?.data?.detail || e.message); }
    setMhLoading(false);
  };

  const switchEnv = async (target: 'DEV' | 'BETA' | 'PROD') => {
    if (target === mode?.env) return;
    const confirmMsg = `Switch backend ENV from ${mode?.env} to ${target}?\n\n• DB will flip (${target === 'DEV' ? 'magicai_dev' : target === 'BETA' ? 'magicai_beta' : 'magicai_prod'})\n• You will be LOGGED OUT — existing JWT won't match the new DB\n• Backend will reload (~3s)`;
    // web-friendly confirm
    // @ts-ignore
    const ok = (typeof window !== 'undefined' && window.confirm) ? window.confirm(confirmMsg) : true;
    if (!ok) return;
    setSwitchingEnv(true);
    try {
      await axios.post(`${BACKEND_URL}/api/admin/env/switch`, { env: target }, { headers: { Authorization: `Bearer ${token}` } });
      // Wait for uvicorn reload
      await new Promise(r => setTimeout(r, 3500));
      await logout();
      Alert.alert('✓ Env switched', `Backend is now in ${target} mode. Please log in again.`);
      router.replace('/login');
    } catch (e: any) {
      Alert.alert('Error', e.response?.data?.detail || e.message);
    } finally { setSwitchingEnv(false); }
  };

  if (!isDesktop) {
    // Mobile-friendly admin mini-panel: just the ENV switcher + link to desktop for full panel.
    return (
      <CosmicBackground>
      <AuroraBackground>
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.mobileTop}>
          <TouchableOpacity onPress={() => router.back()} style={s.mobileBack}>
            <Ionicons name="arrow-back" size={22} color="#fff" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.mobileHeaderTitle}>🛡️ Admin</Text>
            <Text style={s.mobileHeaderSub}>ENV switcher · mobile view</Text>
          </View>
          <View style={[s.mobileEnvPill, { borderColor: mode?.env === 'DEV' ? '#10B981' : mode?.env === 'BETA' ? '#FBBF24' : '#EF4444' }]}>
            <Text style={[s.mobileEnvPillText, { color: mode?.env === 'DEV' ? '#10B981' : mode?.env === 'BETA' ? '#FBBF24' : '#EF4444' }]}>
              {mode?.env || '—'}
            </Text>
          </View>
        </View>

        <ScrollView contentContainerStyle={{ padding: 18, gap: 16 }}>
          <View style={s.mobileCard}>
            <Text style={s.mobileCardTitle}>Switch Environment</Text>
            <Text style={s.mobileCardSub}>
              Flip backend DB. You will be logged out and must re-login to the new env.
            </Text>
            <View style={{ gap: 10, marginTop: 14 }}>
              {(['BETA', 'PROD'] as const).map(e => {
                const active = mode?.env === e;
                const accent = e === 'DEV' ? '#10B981' : e === 'BETA' ? '#FBBF24' : '#EF4444';
                return (
                  <TouchableOpacity
                    key={e}
                    disabled={switchingEnv || active}
                    onPress={() => switchEnv(e)}
                    activeOpacity={0.85}
                    style={[
                      s.mobileEnvBtn,
                      { borderColor: active ? accent : 'rgba(255,255,255,0.1)' },
                      active && { backgroundColor: `${accent}18` },
                    ]}
                  >
                    <View style={[s.mobileEnvDot, { backgroundColor: accent }]} />
                    <View style={{ flex: 1 }}>
                      <Text style={[s.mobileEnvTitle, active && { color: accent }]}>{e}</Text>
                      <Text style={s.mobileEnvSub}>
                        {e === 'DEV' ? 'magicai_dev · open (no JWT)' : e === 'BETA' ? 'magicai_beta · JWT required' : 'magicai_prod · live users'}
                      </Text>
                    </View>
                    {active && <Ionicons name="checkmark-circle" size={22} color={accent} />}
                  </TouchableOpacity>
                );
              })}
            </View>
            {switchingEnv && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 14 }}>
                <ActivityIndicator color="#A78BFA" />
                <Text style={{ color: '#A78BFA', fontSize: 13 }}>Reloading backend…</Text>
              </View>
            )}
          </View>

          <View style={s.mobileCard}>
            <Text style={s.mobileCardTitle}>Current state</Text>
            <Text style={s.mobileInfoLine}>Env: <Text style={{ color: '#FBBF24', fontWeight: '700' }}>{mode?.env}</Text></Text>
            <Text style={s.mobileInfoLine}>Version: <Text style={{ color: '#fff' }}>{mode?.version}</Text></Text>
            <Text style={s.mobileInfoLine}>Beta: {String(mode?.is_beta)} · Dev: {String(mode?.is_dev)} · Prod: {String(mode?.is_prod)}</Text>
          </View>

          {/* Session 38 — Safety dashboard entry-point (mobile-only path) */}
          <TouchableOpacity
            onPress={() => router.push('/admin-safety' as any)}
            activeOpacity={0.85}
            style={{
              marginTop: 12,
              paddingVertical: 14,
              paddingHorizontal: 16,
              borderRadius: 14,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 10,
              backgroundColor: 'rgba(239,68,68,0.12)',
              borderWidth: 1,
              borderColor: 'rgba(239,68,68,0.40)',
            }}
          >
            <Text style={{ fontSize: 22 }}>🛡️</Text>
            <View style={{ flex: 1 }}>
              <Text style={{ color: '#FCA5A5', fontWeight: '800', fontSize: 15 }}>Safety Dashboard</Text>
              <Text style={{ color: '#94A3B8', fontSize: 11 }}>Moderation records · Strikes · Bans</Text>
            </View>
            <Text style={{ color: '#FCA5A5', fontSize: 18 }}>›</Text>
          </TouchableOpacity>

          {/* Session 40 — Cost Projection entry-point */}
          <TouchableOpacity
            onPress={() => router.push('/admin-cost-projection' as any)}
            activeOpacity={0.85}
            style={{
              marginTop: 10,
              paddingVertical: 14,
              paddingHorizontal: 16,
              borderRadius: 14,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 10,
              backgroundColor: 'rgba(34,211,238,0.12)',
              borderWidth: 1,
              borderColor: 'rgba(34,211,238,0.40)',
            }}
          >
            <Text style={{ fontSize: 22 }}>📊</Text>
            <View style={{ flex: 1 }}>
              <Text style={{ color: '#7afcff', fontWeight: '800', fontSize: 15 }}>Cost Projection</Text>
              <Text style={{ color: '#94A3B8', fontSize: 11 }}>Revenue vs MH spend · run-rate</Text>
            </View>
            <Text style={{ color: '#7afcff', fontSize: 18 }}>›</Text>
          </TouchableOpacity>

          <Text style={s.mobileNote}>
            👉 Open on desktop (≥ 900px) for full admin dashboard: users, usage & profit tabs.
          </Text>
        </ScrollView>
      </SafeAreaView>
      </AuroraBackground>
      </CosmicBackground>
    );
  }

  return (
    <AuroraBackground>
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.topbar}>
        <Text style={s.brand}>🎬 MagiCAi Admin</Text>
        <Text style={s.envTag}>{mode?.env} · {mode?.version}</Text>
        <View style={{ flex: 1 }} />
        <TouchableOpacity onPress={() => router.push('/admin-safety' as any)} style={[s.navBtn, { marginRight: 8, backgroundColor: 'rgba(239,68,68,0.18)', borderColor: 'rgba(239,68,68,0.5)' }]}>
          <Text style={[s.navBtnText, { color: '#FCA5A5' }]}>🛡️ Safety</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => router.push('/')} style={s.navBtn}><Text style={s.navBtnText}>← App</Text></TouchableOpacity>
      </View>
      <View style={s.layout}>
        <View style={s.sidebar}>
          {(['users', 'usage', 'profit', 'env', 'pattern_lab', 'mh'] as const).map(t => (
            <TouchableOpacity key={t} onPress={() => setTab(t)} style={[s.sideItem, tab === t && s.sideItemActive]}>
              <Text style={[s.sideItemText, tab === t && s.sideItemTextActive]}>{t === 'users' ? '👥 Users' : t === 'usage' ? '📊 Usage' : t === 'profit' ? '💰 Profit Calc' : t === 'pattern_lab' ? '🧪 Pattern Lab' : t === 'mh' ? '🔥 MH Circuit' : '⚙️ Environment'}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <ScrollView style={s.main} contentContainerStyle={{ padding: 24 }}>
          {loading ? <ActivityIndicator color="#A78BFA" /> : (
            <>
              {tab === 'users' && (
                <>
                  <Text style={s.sectionTitle}>Users ({users.length})</Text>
                  <View style={s.table}>
                    <View style={[s.trow, s.thead]}>
                      <Text style={[s.th, { flex: 2 }]}>Email</Text>
                      <Text style={s.th}>Tier</Text>
                      <Text style={s.th}>Credits</Text>
                      <Text style={s.th}>Daily</Text>
                      <Text style={[s.th, { flex: 1.5 }]}>Actions</Text>
                    </View>
                    {users.map(u => (
                      <View key={u.id} style={s.trow}>
                        <Text style={[s.td, { flex: 2 }]}>{u.email}{u.is_admin && <Text style={{ color: '#FBBF24' }}> 🛡️</Text>}</Text>
                        <Text style={s.td}>{u.subscription_tier}</Text>
                        <Text style={s.td}>{u.credits_balance}</Text>
                        <Text style={s.td}>{u.daily_usage || 0}</Text>
                        <View style={[s.td, s.actions]}>
                          <TouchableOpacity onPress={() => adjustCredits(u.id, 50)} style={s.actBtn}><Text style={s.actBtnText}>+50</Text></TouchableOpacity>
                          <TouchableOpacity onPress={() => adjustCredits(u.id, -10)} style={[s.actBtn, { backgroundColor: '#7F1D1D' }]}><Text style={s.actBtnText}>-10</Text></TouchableOpacity>
                          <TouchableOpacity onPress={() => resetDaily(u.id)} style={[s.actBtn, { backgroundColor: '#1E40AF' }]}><Text style={s.actBtnText}>Reset</Text></TouchableOpacity>
                        </View>
                      </View>
                    ))}
                  </View>
                </>
              )}
              {tab === 'usage' && stats && (
                <>
                  <Text style={s.sectionTitle}>Usage Stats</Text>
                  <View style={s.cardsRow}>
                    <StatCard label="Total Users" value={stats.total_users} />
                    <StatCard label="Free" value={stats.by_tier?.free || 0} />
                    <StatCard label="Starter" value={stats.by_tier?.starter || 0} />
                    <StatCard label="Pro" value={stats.by_tier?.pro || 0} />
                    <StatCard label="Total Projects" value={stats.total_projects} />
                    <StatCard label="Last 7 days" value={stats.recent_projects} />
                    <StatCard label="Active Templates" value={stats.active_templates} />
                  </View>
                </>
              )}
              {tab === 'profit' && (
                <>
                  <Text style={s.sectionTitle}>Profit Calculator</Text>
                  <View style={s.formRow}>
                    {Object.entries(profitForm).map(([k, v]) => (
                      <View key={k} style={s.formField}>
                        <Text style={s.formLabel}>{k.replace(/_/g, ' ')}</Text>
                        <TextInput style={s.formInput} keyboardType="numeric" value={v} onChangeText={(t) => setProfitForm((p) => ({ ...p, [k]: t }))} />
                      </View>
                    ))}
                  </View>
                  <TouchableOpacity style={s.calcBtn} onPress={calcProfit}><Text style={{ color: '#fff', fontWeight: '800' }}>Calculate</Text></TouchableOpacity>
                  {profitRes && (
                    <View style={{ marginTop: 20 }}>
                      <View style={s.cardsRow}>
                        <StatCard label="Revenue" value={`₹${profitRes.revenue_inr}`} accent="#10B981" />
                        <StatCard label="Cost" value={`₹${profitRes.estimated_cost_inr}`} accent="#EF4444" />
                        <StatCard label="Profit" value={`₹${profitRes.profit_inr}`} accent="#A78BFA" />
                        <StatCard label="Margin" value={`${profitRes.margin_pct}%`} accent="#FBBF24" />
                        <StatCard label="Est. Videos" value={profitRes.estimated_videos} />
                        <StatCard label="Paid Users" value={profitRes.paid_users} />
                      </View>
                    </View>
                  )}
                </>
              )}
              {tab === 'env' && (
                <>
                  <Text style={s.sectionTitle}>Environment</Text>
                  <Text style={{ color: '#94A3B8', fontSize: 13, marginBottom: 20, lineHeight: 20 }}>
                    Switch backend between <Text style={{ color: '#10B981', fontWeight: '700' }}>DEV</Text> (open, guest access, dev DB),
                    {' '}<Text style={{ color: '#FBBF24', fontWeight: '700' }}>BETA</Text> (JWT required, beta DB), or
                    {' '}<Text style={{ color: '#EF4444', fontWeight: '700' }}>PROD</Text> (prod DB). Switching will reload the backend
                    and log you out — you must re-login with a user in the new database.
                  </Text>
                  <View style={s.envRow}>
                    {(['BETA', 'PROD'] as const).map(e => {
                      const active = mode?.env === e;
                      const accent = e === 'DEV' ? '#10B981' : e === 'BETA' ? '#FBBF24' : '#EF4444';
                      return (
                        <TouchableOpacity
                          key={e}
                          disabled={switchingEnv || active}
                          onPress={() => switchEnv(e)}
                          style={[s.envBtn, active && { borderColor: accent, backgroundColor: `${accent}22` }]}
                        >
                          {active && <Ionicons name="checkmark-circle" size={18} color={accent} />}
                          <Text style={[s.envBtnText, active && { color: accent }]}>{e}</Text>
                          <Text style={s.envBtnSub}>
                            {e === 'DEV' ? 'magicai_dev · open' : e === 'BETA' ? 'magicai_beta · auth' : 'magicai_prod · live'}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                  {switchingEnv && (
                    <View style={{ marginTop: 20, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                      <ActivityIndicator color="#A78BFA" />
                      <Text style={{ color: '#A78BFA', fontSize: 13 }}>Reloading backend…</Text>
                    </View>
                  )}
                  <View style={s.envInfoBox}>
                    <Text style={s.envInfoLine}>Current: <Text style={{ color: '#FBBF24', fontWeight: '700' }}>{mode?.env}</Text> ({mode?.version})</Text>
                    <Text style={s.envInfoLine}>Is BETA: {String(mode?.is_beta)}</Text>
                    <Text style={s.envInfoLine}>Is DEV: {String(mode?.is_dev)}</Text>
                    <Text style={s.envInfoLine}>Is PROD: {String(mode?.is_prod)}</Text>
                  </View>
                </>
              )}
              {tab === 'mh' && (
                <>
                  <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 12 }}>
                    <Text style={[s.sectionTitle, { marginBottom: 0 }]}>🔥 Magic Hour Circuit Breaker</Text>
                    <View style={{ flex: 1 }} />
                    <TouchableOpacity onPress={loadMhUsage} style={[s.actBtn, { backgroundColor: '#1E40AF' }]}>
                      <Text style={s.actBtnText}>↻ Refresh</Text>
                    </TouchableOpacity>
                  </View>
                  <Text style={{ color: '#94A3B8', fontSize: 13, marginBottom: 14, lineHeight: 19 }}>
                    Real-time Magic Hour credit burn — protects margins by auto-queueing jobs when daily or monthly caps are hit.
                  </Text>
                  {mhLoading || !mhUsage ? (
                    <ActivityIndicator color="#A78BFA" />
                  ) : (
                    <View>
                      {/* Alert banner */}
                      {mhUsage.alert_active && (
                        <View style={{ backgroundColor: 'rgba(239,68,68,0.15)', borderWidth: 1, borderColor: 'rgba(239,68,68,0.4)', padding: 14, borderRadius: 12, marginBottom: 14 }}>
                          <Text style={{ color: '#F87171', fontSize: 15, fontWeight: '800' }}>⚠️ CIRCUIT BREAKER ACTIVE</Text>
                          <Text style={{ color: '#FCA5A5', fontSize: 12, marginTop: 4 }}>{mhUsage.alert_reason || 'Daily or monthly budget exhausted — new jobs are being queued.'}</Text>
                        </View>
                      )}

                      {/* Daily card */}
                      <View style={{ backgroundColor: '#0F172A', borderWidth: 1, borderColor: '#1E293B', borderRadius: 14, padding: 16, marginBottom: 12 }}>
                        <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}>
                          <Text style={{ color: '#94A3B8', fontSize: 12, fontWeight: '700', letterSpacing: 0.5 }}>TODAY · {mhUsage.day}</Text>
                          <Text style={{ color: mhUsage.day_pct > 80 ? '#F87171' : '#A78BFA', fontSize: 12, fontWeight: '700' }}>{mhUsage.day_pct}%</Text>
                        </View>
                        <Text style={{ color: '#fff', fontSize: 26, fontWeight: '800', marginTop: 6 }}>{mhUsage.day_total} <Text style={{ color: '#64748B', fontSize: 14, fontWeight: '600' }}>/ {mhUsage.daily_cap} credits</Text></Text>
                        <View style={{ height: 8, backgroundColor: '#1E293B', borderRadius: 4, marginTop: 10, overflow: 'hidden' }}>
                          <View style={{ width: `${Math.min(100, mhUsage.day_pct)}%`, height: '100%', backgroundColor: mhUsage.day_pct > 90 ? '#EF4444' : mhUsage.day_pct > 70 ? '#F59E0B' : '#10B981' }} />
                        </View>
                      </View>

                      {/* Monthly card */}
                      <View style={{ backgroundColor: '#0F172A', borderWidth: 1, borderColor: '#1E293B', borderRadius: 14, padding: 16, marginBottom: 12 }}>
                        <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}>
                          <Text style={{ color: '#94A3B8', fontSize: 12, fontWeight: '700', letterSpacing: 0.5 }}>THIS MONTH · {mhUsage.month}</Text>
                          <Text style={{ color: mhUsage.month_pct > 80 ? '#F87171' : '#A78BFA', fontSize: 12, fontWeight: '700' }}>{mhUsage.month_pct}%</Text>
                        </View>
                        <Text style={{ color: '#fff', fontSize: 26, fontWeight: '800', marginTop: 6 }}>{mhUsage.month_total} <Text style={{ color: '#64748B', fontSize: 14, fontWeight: '600' }}>/ {mhUsage.monthly_cap} credits</Text></Text>
                        <View style={{ height: 8, backgroundColor: '#1E293B', borderRadius: 4, marginTop: 10, overflow: 'hidden' }}>
                          <View style={{ width: `${Math.min(100, mhUsage.month_pct)}%`, height: '100%', backgroundColor: mhUsage.month_pct > 90 ? '#EF4444' : mhUsage.month_pct > 70 ? '#F59E0B' : '#10B981' }} />
                        </View>
                        <Text style={{ color: '#94A3B8', fontSize: 12, marginTop: 10 }}>
                          📈 Projected end-of-month: <Text style={{ color: mhUsage.projected_month_total > mhUsage.monthly_cap ? '#F87171' : '#10B981', fontWeight: '700' }}>{mhUsage.projected_month_total} cr</Text>
                          {mhUsage.projected_month_total > mhUsage.monthly_cap && ' — upgrade MH tier!'}
                        </Text>
                      </View>

                      {/* Two-column: top users + by model */}
                      <View style={{ flexDirection: 'row', gap: 12 }}>
                        <View style={{ flex: 1, backgroundColor: 'transparent', borderWidth: 1, borderColor: '#1E293B', borderRadius: 14, padding: 16 }}>
                          <Text style={{ color: '#94A3B8', fontSize: 12, fontWeight: '700', marginBottom: 10, letterSpacing: 0.5 }}>TOP USERS TODAY</Text>
                          {(mhUsage.top_users_today || []).length === 0 ? (
                            <Text style={{ color: '#64748B', fontSize: 12 }}>No MH usage today yet.</Text>
                          ) : (
                            (mhUsage.top_users_today || []).map((u: any, i: number) => (
                              <View key={u.user_id || i} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#1E293B' }}>
                                <Text style={{ color: '#CBD5E1', fontSize: 13, flex: 1 }} numberOfLines={1}>{(u.email || u.user_id || 'unknown').slice(0, 28)}</Text>
                                <Text style={{ color: '#A78BFA', fontSize: 13, fontWeight: '700' }}>{u.credits} cr</Text>
                              </View>
                            ))
                          )}
                        </View>

                        <View style={{ flex: 1, backgroundColor: '#0F172A', borderWidth: 1, borderColor: '#1E293B', borderRadius: 14, padding: 16 }}>
                          <Text style={{ color: '#94A3B8', fontSize: 12, fontWeight: '700', marginBottom: 10, letterSpacing: 0.5 }}>BY MODEL (TODAY)</Text>
                          {Object.keys(mhUsage.by_model_day || {}).length === 0 ? (
                            <Text style={{ color: '#64748B', fontSize: 12 }}>No model activity yet.</Text>
                          ) : (
                            Object.entries(mhUsage.by_model_day || {}).map(([m, c]: any) => (
                              <View key={m} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#1E293B' }}>
                                <Text style={{ color: '#CBD5E1', fontSize: 13, flex: 1 }} numberOfLines={1}>{m}</Text>
                                <Text style={{ color: '#A78BFA', fontSize: 13, fontWeight: '700' }}>{c as number} cr</Text>
                              </View>
                            ))
                          )}
                        </View>
                      </View>
                    </View>
                  )}
                </>
              )}
              {tab === 'pattern_lab' && (
                <>
                  <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 12 }}>
                    <Text style={[s.sectionTitle, { marginBottom: 0 }]}>🧪 Pattern Lab Moderation</Text>
                    <View style={{ flex: 1 }} />
                    <TouchableOpacity onPress={loadFlagged} style={[s.actBtn, { backgroundColor: '#1E40AF', marginRight: 8 }]}>
                      <Text style={s.actBtnText}>↻ Reload</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={triggerPLRefresh} disabled={plTriggerBusy} style={[s.actBtn, { backgroundColor: '#8B5CF6' }]}>
                      <Text style={s.actBtnText}>{plTriggerBusy ? 'Running…' : '✨ Trigger Refresh (~2min)'}</Text>
                    </TouchableOpacity>
                  </View>
                  <Text style={{ color: '#94A3B8', fontSize: 13, marginBottom: 14, lineHeight: 19 }}>
                    AI-generated templates via Gemini + Nano Banana. Users can flag inappropriate content; templates with ≥5 flags auto-deactivate. Templates expire after 14 days.
                  </Text>
                  {plLoading ? (
                    <ActivityIndicator color="#A78BFA" />
                  ) : flagged.length === 0 ? (
                    <View style={{ padding: 24, backgroundColor: 'rgba(16,185,129,0.08)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(16,185,129,0.3)' }}>
                      <Text style={{ color: '#10B981', fontSize: 14, fontWeight: '700' }}>✓ No flagged Pattern Lab templates</Text>
                      <Text style={{ color: '#94A3B8', fontSize: 12, marginTop: 4 }}>Everything is clean. Users haven't reported any AI-generated templates.</Text>
                    </View>
                  ) : (
                    <View style={s.table}>
                      <View style={[s.trow, s.thead]}>
                        <Text style={[s.th, { flex: 2 }]}>Title</Text>
                        <Text style={s.th}>Category</Text>
                        <Text style={s.th}>Flags</Text>
                        <Text style={s.th}>Active</Text>
                        <Text style={[s.th, { flex: 2 }]}>Reasons</Text>
                        <Text style={[s.th, { flex: 2 }]}>Actions</Text>
                      </View>
                      {flagged.map((t) => (
                        <View key={t.id} style={s.trow}>
                          <Text style={[s.td, { flex: 2 }]} numberOfLines={2}>{t.title}</Text>
                          <Text style={s.td}>{t.category}</Text>
                          <Text style={[s.td, { color: '#F87171', fontWeight: '800' }]}>{t.flag_count}</Text>
                          <Text style={[s.td, { color: t.is_active ? '#10B981' : '#EF4444' }]}>{t.is_active ? 'YES' : 'NO'}</Text>
                          <View style={[s.td, { flex: 2 }]}>
                            {(t.flags || []).slice(0, 3).map((f: any, i: number) => (
                              <Text key={i} style={{ color: '#CBD5E1', fontSize: 11 }} numberOfLines={1}>• {f.reason || 'user_flagged'}</Text>
                            ))}
                          </View>
                          <View style={[s.td, s.actions, { flex: 2 }]}>
                            <TouchableOpacity onPress={() => moderatePL(t.id, 'approve')} style={[s.actBtn, { backgroundColor: '#065F46' }]}><Text style={s.actBtnText}>✓ Approve</Text></TouchableOpacity>
                            <TouchableOpacity onPress={() => moderatePL(t.id, 'deactivate')} style={[s.actBtn, { backgroundColor: '#92400E' }]}><Text style={s.actBtnText}>✗ Hide</Text></TouchableOpacity>
                            <TouchableOpacity onPress={() => moderatePL(t.id, 'delete')} style={[s.actBtn, { backgroundColor: '#7F1D1D' }]}><Text style={s.actBtnText}>🗑 Delete</Text></TouchableOpacity>
                          </View>
                        </View>
                      ))}
                    </View>
                  )}
                </>
              )}
            </>
          )}
        </ScrollView>
      </View>
    </SafeAreaView>
    </AuroraBackground>
  );
}

function StatCard({ label, value, accent }: { label: string; value: any; accent?: string }) {
  return <View style={[s.statCard, accent ? { borderColor: accent } : null]}><Text style={s.statLabel}>{label}</Text><Text style={[s.statValue, accent ? { color: accent } : null]}>{value}</Text></View>;
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  // Mobile-specific styles
  mobileTop: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingBottom: 12 },
  mobileBack: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)' },
  mobileHeaderTitle: { color: '#fff', fontSize: 20, fontWeight: '800' },
  mobileHeaderSub: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  mobileEnvPill: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, borderWidth: 1.5, backgroundColor: 'rgba(0,0,0,0.2)' },
  mobileEnvPillText: { fontSize: 11, fontWeight: '900', letterSpacing: 1 },
  mobileCard: { backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 16, padding: 18, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  mobileCardTitle: { color: '#fff', fontSize: 16, fontWeight: '800', marginBottom: 6 },
  mobileCardSub: { color: '#94A3B8', fontSize: 12, lineHeight: 18 },
  mobileEnvBtn: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 14, borderWidth: 1.5, backgroundColor: 'rgba(255,255,255,0.03)' },
  mobileEnvDot: { width: 10, height: 10, borderRadius: 5 },
  mobileEnvTitle: { color: '#fff', fontSize: 15, fontWeight: '800' },
  mobileEnvSub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },
  mobileInfoLine: { color: '#CBD5E1', fontSize: 12, marginTop: 4 },
  mobileNote: { color: '#64748B', fontSize: 11, textAlign: 'center', marginTop: 6 },
  topbar: { flexDirection: 'row', alignItems: 'center', gap: 16, paddingHorizontal: 24, paddingVertical: 14, borderBottomWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  brand: { color: '#fff', fontWeight: '800', fontSize: 18 },
  envTag: { color: '#FBBF24', fontSize: 12, fontWeight: '700', backgroundColor: 'rgba(251,191,36,0.1)', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  navBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: 'rgba(255,255,255,0.08)' },
  navBtnText: { color: '#fff', fontSize: 13 },
  layout: { flex: 1, flexDirection: 'row' },
  sidebar: { width: 200, borderRightWidth: 1, borderColor: 'rgba(255,255,255,0.08)', padding: 12, gap: 4 },
  sideItem: { paddingHorizontal: 14, paddingVertical: 11, borderRadius: 8 },
  sideItemActive: { backgroundColor: 'rgba(139,92,246,0.18)' },
  sideItemText: { color: '#94A3B8', fontSize: 14, fontWeight: '500' },
  sideItemTextActive: { color: '#E0D4FF', fontWeight: '700' },
  main: { flex: 1 },
  sectionTitle: { color: '#fff', fontSize: 20, fontWeight: '800', marginBottom: 16 },
  table: { borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)', borderRadius: 10, overflow: 'hidden' },
  trow: { flexDirection: 'row', paddingVertical: 11, paddingHorizontal: 14, borderBottomWidth: 1, borderColor: 'rgba(255,255,255,0.06)', alignItems: 'center' },
  thead: { backgroundColor: 'rgba(255,255,255,0.04)' },
  th: { flex: 1, color: '#94A3B8', fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  td: { flex: 1, color: '#E5E7EB', fontSize: 13 },
  actions: { flexDirection: 'row', gap: 6 },
  actBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, backgroundColor: '#059669' },
  actBtnText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  cardsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  statCard: { minWidth: 160, padding: 16, backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  statLabel: { color: '#94A3B8', fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  statValue: { color: '#fff', fontSize: 24, fontWeight: '800', marginTop: 4 },
  formRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  formField: { minWidth: 180 },
  formLabel: { color: '#94A3B8', fontSize: 12, marginBottom: 4, textTransform: 'capitalize' },
  formInput: { backgroundColor: 'rgba(255,255,255,0.06)', color: '#fff', borderRadius: 8, padding: 10, fontSize: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)' },
  calcBtn: { marginTop: 16, alignSelf: 'flex-start', paddingHorizontal: 24, paddingVertical: 12, backgroundColor: '#8B5CF6', borderRadius: 10 },
  envRow: { flexDirection: 'row', gap: 16, flexWrap: 'wrap' },
  envBtn: { minWidth: 180, padding: 20, backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 12, borderWidth: 2, borderColor: 'rgba(255,255,255,0.1)', gap: 8, alignItems: 'flex-start' },
  envBtnText: { color: '#fff', fontSize: 22, fontWeight: '800', letterSpacing: 1 },
  envBtnSub: { color: '#94A3B8', fontSize: 11 },
  envInfoBox: { marginTop: 24, padding: 16, backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)', gap: 6 },
  envInfoLine: { color: '#E5E7EB', fontSize: 13, fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace' },
  mobileBlock: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40, gap: 16 },
  mobileTitle: { color: '#fff', fontSize: 22, fontWeight: '800' },
  mobileText: { color: '#94A3B8', fontSize: 14, textAlign: 'center', lineHeight: 22 },
  mobileBtn: { paddingHorizontal: 24, paddingVertical: 12, backgroundColor: '#8B5CF6', borderRadius: 10, marginTop: 10 },
});
