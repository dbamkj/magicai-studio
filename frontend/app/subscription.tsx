import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert, RefreshControl, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import axios from 'axios';
import { useAuth } from '../src/AuthContext';
import { useTheme } from '../src/ThemeContext';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Plan = {
  id: 'free' | 'starter' | 'creator' | 'pro';
  label: string;
  price_inr: number;
  price_annual_inr?: number;
  credits: number;
  daily_template_limit: number;
  monthly_reels_limit: number;
  monthly_lipsync_limit: number;
  monthly_ai_videos_limit: number;
  ai_video_max_seconds: number;
  max_images: number;
  watermark: boolean;
  allow_ai_video: boolean;
  allow_multishot?: boolean;
  max_multishot_shots?: number;
  trial_eligible?: boolean;
  highlight?: boolean;
};

type Addon = {
  sku: string;
  label: string;
  price_inr: number;
  ai_videos: number;
  ai_video_max_seconds: number;
  desc: string;
};

type Usage = {
  reels: { used: number; limit: number | 'unlimited'; remaining: number | 'unlimited' };
  lipsync: { used: number; limit: number | 'unlimited'; remaining: number | 'unlimited' };
  ai_videos: { used: number; limit: number | 'unlimited'; remaining: number | 'unlimited' };
};

const ACCENT_BY_TIER: Record<string, string> = {
  free: '#94A3B8',
  starter: '#60A5FA',
  creator: '#EC4899',
  pro: '#FBBF24',
};

export default function SubscriptionScreen() {
  const router = useRouter();
  const { user, token, refresh } = useAuth();
  const { isDark } = useTheme();
  // Theme-aware overrides for the most-prominent text in light mode
  const titleColor = isDark ? '#FFFFFF' : '#0F0C29';
  const subColor = isDark ? '#94A3B8' : '#64748B';
  const [plans, setPlans] = useState<Plan[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [trialInfo, setTrialInfo] = useState<{ price_inr: number; days: number; eligible_plans: string[] } | null>(null);
  const [annualInfo, setAnnualInfo] = useState<{ multiplier: number; savings_pct: number }>({ multiplier: 10, savings_pct: 17 });
  const [balance, setBalance] = useState<any>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [addonRemaining, setAddonRemaining] = useState(0);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, b] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/subscription/plans`),
        axios.get(`${BACKEND_URL}/api/subscription/balance`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }).catch(() => null),
      ]);
      setPlans(p.data?.plans || []);
      setAddons(p.data?.addons || []);
      setTrialInfo(p.data?.trial || null);
      if (p.data?.annual) setAnnualInfo(p.data.annual);
      if (b?.data) {
        setBalance(b.data);
        setUsage(b.data.usage || null);
        setAddonRemaining(Number(b.data.addons?.ai_videos_remaining || 0));
      }
    } catch (e: any) {
      console.warn('subscription load fail:', e?.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const doUpgrade = async (planId: string) => {
    if (!token) { router.push('/login'); return; }
    if (planId === 'free') {
      // free downgrade still uses the legacy endpoint
      setBusy(planId + '_' + billingCycle);
      try {
        const r = await axios.post(
          `${BACKEND_URL}/api/subscription/upgrade`,
          { plan_id: planId, billing_cycle: billingCycle },
          { headers: { Authorization: `Bearer ${token}` } },
        );
        Alert.alert('Updated', r.data?.message || 'Plan updated');
        await refresh();
        await load();
      } catch (e: any) {
        Alert.alert('Update failed', e.response?.data?.detail || e.message);
      } finally {
        setBusy(null);
      }
      return;
    }
    // Phase-3 — paid upgrades go through the real Razorpay /buy flow
    router.push({ pathname: '/buy', params: { tab: 'tier' } });
  };

  const startTrial = async (planId: string) => {
    if (!token) { router.push('/login'); return; }
    setBusy('trial_' + planId);
    try {
      const r = await axios.post(
        `${BACKEND_URL}/api/subscription/start-trial`,
        { plan_id: planId },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      Alert.alert('🎉 Trial started (MOCK)', r.data?.message || `${planId} trial activated for ₹1`);
      await refresh();
      await load();
    } catch (e: any) {
      Alert.alert('Trial failed', e.response?.data?.detail || e.message);
    } finally {
      setBusy(null);
    }
  };

  const buyAddon = async (sku: string) => {
    if (!token) { router.push('/login'); return; }
    setBusy(sku);
    try {
      const r = await axios.post(
        `${BACKEND_URL}/api/subscription/addons/purchase`,
        { sku },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      Alert.alert('🎁 Unlocked', r.data?.message || 'Add-on purchased');
      await refresh();
      await load();
    } catch (e: any) {
      Alert.alert('Purchase failed', e.response?.data?.detail || e.message);
    } finally {
      setBusy(null);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await refresh();
    await load();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <AuroraBackground>
        <SafeAreaView style={s.container}>
          <View style={s.centerWrap}>
            <ActivityIndicator color="#FBBF24" size="large" />
            <Text style={{ color: '#94A3B8', marginTop: 10 }}>Loading plans…</Text>
          </View>
        </SafeAreaView>
      </AuroraBackground>
    );
  }

  const currentTier = user?.subscription_tier || 'free';

  return (
    <AuroraBackground>
      <SafeAreaView style={s.container} edges={['top']}>
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 60 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FBBF24" />}
        >
          {/* Premium glass header */}
          <GlassHeader
            icon="diamond"
            title="Plans & Pricing"
            subtitle={`Currently · ${currentTier.toUpperCase()}`}
            onBack={() => router.back()}
            style={{ marginBottom: 14, paddingHorizontal: 0 }}
          />

          {/* Current usage ribbon (authenticated only) */}
          {usage && user && (
            <View style={s.usageCard}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Ionicons name="stats-chart" size={16} color={ACCENT_BY_TIER[currentTier]} />
                <Text style={[s.usageTitle, { color: ACCENT_BY_TIER[currentTier] }]}>
                  Your {currentTier.toUpperCase()} usage this month
                </Text>
              </View>
              <UsageRow label="Reels" data={usage.reels} emoji="🎬" />
              <UsageRow label="Lip sync" data={usage.lipsync} emoji="🎤" />
              <UsageRow label="AI Videos" data={usage.ai_videos} emoji="✨" extra={addonRemaining > 0 ? `+${addonRemaining} from add-ons` : undefined} />
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.08)' }}>
                <Text style={{ color: '#94A3B8', fontSize: 12 }}>🪙 Credits</Text>
                <Text style={{ color: '#FBBF24', fontSize: 13, fontWeight: '800' }}>{user.credits_balance}</Text>
              </View>
            </View>
          )}

          {/* ===== MOCK MODE BANNER ===== */}
          <View style={{ backgroundColor: 'rgba(251,191,36,0.12)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.4)', padding: 10, borderRadius: 10, marginBottom: 12, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Ionicons name="construct" size={14} color="#FBBF24" />
            <Text style={{ color: '#FEF3C7', fontSize: 11, flex: 1, lineHeight: 16 }}>
              TEST MODE · No payment gateway active. All upgrades & trials are MOCK — no real charges.
            </Text>
          </View>

          {/* Billing cycle toggle: Monthly / Annual / Credits (one-time) */}
          <View style={s.cycleToggle}>
            <TouchableOpacity
              style={[s.cycleOpt, billingCycle === 'monthly' && s.cycleOptActive]}
              onPress={() => setBillingCycle('monthly')}
            >
              <Text style={[s.cycleTxt, billingCycle === 'monthly' && s.cycleTxtActive]}>Monthly</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.cycleOpt, billingCycle === 'annual' && s.cycleOptActive]}
              onPress={() => setBillingCycle('annual')}
            >
              <Text style={[s.cycleTxt, billingCycle === 'annual' && s.cycleTxtActive]}>Annual</Text>
              <View style={s.saveBadge}><Text style={s.saveBadgeTxt}>SAVE {annualInfo.savings_pct}%</Text></View>
            </TouchableOpacity>
            <TouchableOpacity
              style={s.cycleOpt}
              onPress={() => router.push('/buy' as any)}
            >
              <Text style={s.cycleTxt}>Credits</Text>
              <View style={[s.saveBadge, { backgroundColor: 'rgba(251,191,36,0.2)', borderColor: 'rgba(251,191,36,0.5)' }]}>
                <Text style={[s.saveBadgeTxt, { color: '#FBBF24' }]}>ONE-TIME</Text>
              </View>
            </TouchableOpacity>
          </View>

          {/* Trial banner (free & not used) */}
          {trialInfo && user && currentTier === 'free' && !balance?.trial_used && (
            <LinearGradient colors={['#8B5CF6', '#EC4899']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={s.trialBanner}>
              <View style={{ flex: 1 }}>
                <Text style={s.trialTitle}>🎁 ₹{trialInfo.price_inr} First-Month Trial</Text>
                <Text style={s.trialSub}>Try any paid plan for {trialInfo.days} days — unlock all features for just ₹{trialInfo.price_inr}.</Text>
              </View>
              <Ionicons name="sparkles" size={32} color="#fff" />
            </LinearGradient>
          )}

          {/* Trial active reminder */}
          {balance?.trial_active && balance?.trial_end && (
            <View style={s.trialActiveCard}>
              <Ionicons name="time" size={14} color="#10B981" />
              <Text style={s.trialActiveTxt}>Trial active · ends {new Date(balance.trial_end).toLocaleDateString()}</Text>
            </View>
          )}

          {/* Plan cards */}
          <View style={{ gap: 14, marginTop: 10 }}>
            {plans.map(p => {
              const isCurrent = p.id === currentTier;
              const accent = ACCENT_BY_TIER[p.id];
              const popular = !!p.highlight;
              const displayedPrice = billingCycle === 'annual' ? (p.price_annual_inr || p.price_inr * annualInfo.multiplier) : p.price_inr;
              const perLabel = p.price_inr === 0 ? '' : (billingCycle === 'annual' ? '/ year' : '/ month');
              const effMonthly = billingCycle === 'annual' && p.price_inr > 0 ? Math.round(displayedPrice / 12) : null;
              const trialEligibleHere = !!p.trial_eligible && !balance?.trial_used && currentTier === 'free';
              return (
                <View
                  key={p.id}
                  style={[
                    s.planCard,
                    { borderColor: popular ? accent : 'rgba(255,255,255,0.1)' },
                    popular && {
                      borderWidth: 2,
                      backgroundColor: `${accent}12`,
                      ...Platform.select({
                        web: { boxShadow: `0 0 28px ${accent}55` as any },
                        default: { shadowColor: accent, shadowOpacity: 0.45, shadowRadius: 14, shadowOffset: { width: 0, height: 0 }, elevation: 8 },
                      }),
                    },
                    isCurrent && !popular && {
                      borderColor: '#10B981',
                      backgroundColor: 'rgba(16,185,129,0.06)',
                    },
                  ]}
                >
                  {popular && (
                    <View style={[s.popularBadge, { backgroundColor: accent }]}>
                      <Ionicons name="star" size={10} color="#fff" />
                      <Text style={s.popularText}>MOST POPULAR</Text>
                    </View>
                  )}
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Text style={[s.planName, { color: accent }]}>{p.label}</Text>
                    {isCurrent && (
                      <View style={s.currentPill}>
                        <Text style={s.currentPillText}>CURRENT</Text>
                      </View>
                    )}
                  </View>
                  <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 6, marginTop: 6 }}>
                    <Text style={s.planPrice}>{p.price_inr === 0 ? 'Free' : `₹${displayedPrice}`}</Text>
                    {perLabel ? <Text style={s.planPer}>{perLabel}</Text> : null}
                  </View>
                  {effMonthly ? (
                    <Text style={{ color: '#10B981', fontSize: 11, fontWeight: '700', marginBottom: 10 }}>Just ₹{effMonthly}/mo when billed annually</Text>
                  ) : <View style={{ marginBottom: 10 }} />}

                  {/* ✨ Credits highlight banner */}
                  {p.credits > 0 && (
                    <View style={[s.creditsBanner, { borderColor: accent + '55', backgroundColor: accent + '14' }]}>
                      <Text style={{ fontSize: 18 }}>🪙</Text>
                      <View style={{ flex: 1 }}>
                        <Text style={[s.creditsBannerValue, { color: accent }]}>
                          {p.credits.toLocaleString()} credits
                        </Text>
                        <Text style={s.creditsBannerSub}>
                          {billingCycle === 'annual' ? 'every month for 12 months' : 'refilled every month'}
                        </Text>
                      </View>
                    </View>
                  )}

                  <View style={{ gap: 8 }}>
                    {p.id === 'free' ? (
                      <>
                        <Feat emoji="📂" label={`${p.daily_template_limit} template downloads / day`} />
                        <Feat emoji="💧" label="Watermark on exports" warn />
                        <Feat emoji="🚫" label="No AI videos" warn />
                      </>
                    ) : (
                      <>
                        <Feat emoji="♾️" label="Unlimited templates" />
                        <Feat emoji="🎬" label={p.monthly_reels_limit >= 9999 ? 'Unlimited reels / month' : `${p.monthly_reels_limit} reels / month`} />
                        <Feat emoji="🎤" label={`${p.monthly_lipsync_limit} lip sync / month`} />
                        <Feat emoji="🖼️" label={`${p.max_images} AI images / month`} />
                        {p.allow_ai_video ? (
                          <Feat emoji="✨" label={`${p.monthly_ai_videos_limit} AI videos (up to ${p.ai_video_max_seconds}s) / month`} />
                        ) : (
                          <Feat emoji="✨" label="AI videos via add-ons" />
                        )}
                        {p.allow_multishot && (p.max_multishot_shots || 0) > 0 && (
                          <Feat emoji="🎞️" label={`Multi-shot up to ${p.max_multishot_shots} shots`} />
                        )}
                        <Feat emoji="🚫" label="No watermark" />
                      </>
                    )}
                  </View>

                  {!isCurrent && (
                    <View style={{ gap: 8, marginTop: 16 }}>
                      {trialEligibleHere && (
                        <TouchableOpacity onPress={() => startTrial(p.id)} disabled={busy === `trial_${p.id}`} activeOpacity={0.85}>
                          <LinearGradient colors={['#8B5CF6', '#EC4899']} style={s.upgradeBtn} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}>
                            {busy === `trial_${p.id}` ? <ActivityIndicator color="#fff" /> : (
                              <Text style={s.upgradeText}>🎁 Try for ₹{trialInfo?.price_inr} ({trialInfo?.days} days)</Text>
                            )}
                          </LinearGradient>
                        </TouchableOpacity>
                      )}
                      <TouchableOpacity
                        onPress={() => doUpgrade(p.id)}
                        disabled={busy === `${p.id}_${billingCycle}`}
                        activeOpacity={0.85}
                      >
                        <LinearGradient
                          colors={popular ? ['#EC4899', '#F97316'] : p.id === 'pro' ? ['#FBBF24', '#F97316'] : p.id === 'starter' ? ['#60A5FA', '#3B82F6'] : ['#64748B', '#475569']}
                          style={s.upgradeBtn}
                          start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                        >
                          {busy === `${p.id}_${billingCycle}` ? <ActivityIndicator color="#fff" /> : (
                            <Text style={s.upgradeText}>{p.id === 'free' ? 'Downgrade to Free' : `${trialEligibleHere ? 'Or skip trial · ' : ''}Upgrade · ₹${displayedPrice}${billingCycle === 'annual' ? '/yr' : '/mo'}`}</Text>
                          )}
                        </LinearGradient>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              );
            })}
          </View>

          {/* ===== Compare-all-plans matrix ===== */}
          <View style={{ marginTop: 26 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <Ionicons name="grid" size={16} color="#A78BFA" />
              <Text style={[s.sectionTitle, { color: titleColor }]}>Compare all plans</Text>
            </View>
            <Text style={[s.sectionSub, { color: subColor }]}>Every feature, side-by-side</Text>
            <BenefitsTable />
          </View>

          {/* Add-ons */}
          <View style={{ marginTop: 26 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <Ionicons name="add-circle" size={16} color="#FBBF24" />
              <Text style={s.sectionTitle}>One-time Add-ons</Text>
            </View>
            <Text style={s.sectionSub}>Buy AI video credits without upgrading your plan</Text>
            <View style={{ gap: 10, marginTop: 12 }}>
              {addons.map(a => (
                <View key={a.sku} style={s.addonCard}>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 6 }}>
                      <Text style={s.addonLabel}>{a.label}</Text>
                      <Text style={s.addonPrice}>₹{a.price_inr}</Text>
                    </View>
                    <Text style={s.addonDesc}>{a.desc}</Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => buyAddon(a.sku)}
                    disabled={busy === a.sku}
                    activeOpacity={0.85}
                    style={s.buyBtn}
                  >
                    {busy === a.sku ? <ActivityIndicator color="#fff" /> : (
                      <>
                        <Ionicons name="cart" size={13} color="#fff" />
                        <Text style={s.buyBtnText}>Buy</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          </View>

          <Text style={s.footNote}>
            Payments are mocked in BETA. In production, Stripe/Razorpay handles checkout.
          </Text>
        </ScrollView>
      </SafeAreaView>
    </AuroraBackground>
  );
}

/* ============== Compare-all-plans matrix ============== */
const BENEFIT_ROWS: Array<{ label: string; values: [string, string, string, string] }> = [
  { label: 'Monthly credits',                 values: ['300', '1,500', '3,000', '6,000'] },
  { label: 'Stock-clip Quick Reels',          values: ['✓', '✓', '✓', '✓'] },
  { label: 'AI Video Gen (Kling/Veo)',        values: ['—', 'Lite', '2.5', 'Pro / Veo'] },
  { label: 'AI Image Gen',                    values: ['5/mo + WM', '∞ no-WM', '∞ + 12 styles', '∞ + 24 styles'] },
  { label: '🪄 AI Scene Visuals in Wizard',    values: ['—', '—', '✓ gpt-image-1', '✓ gpt-image-1'] },
  { label: 'Cartoon Avatars',                 values: ['3 styles + WM', '8 styles', '12 styles HD', '24 styles 4K'] },
  { label: 'Avatar Talking Lip-sync',         values: ['—', '—', '480p', '1080p'] },
  { label: 'Output resolution',               values: ['480p', '720p', '720p / 1080p', '1080p / 4K'] },
  { label: 'Watermark',                       values: ['Yes', 'Removed', 'Removed', 'Removed'] },
  { label: 'Concurrent renders',              values: ['1', '1', '2', '4'] },
  { label: 'Free templates',                  values: ['✓', '✓', '✓', '✓'] },
  { label: 'Starter templates',               values: ['—', '✓', '✓', '✓'] },
  { label: 'Creator templates',               values: ['—', '—', '✓', '✓'] },
  { label: 'Pro templates',                   values: ['—', '—', '—', '✓'] },
  { label: 'Smart Plan story length',         values: ['15s', '15-20s', '15-30s', '15-30s+'] },
  { label: 'Premium TTS (Gemini, soon)',      values: ['—', '—', '✓', '✓'] },
  { label: 'Asset download (mobile gallery)', values: ['—', '✓', '✓', '✓ + 4K'] },
  { label: 'Priority queue',                  values: ['—', '—', '✓', '✓'] },
];

function BenefitsTable() {
  const COL_LABELS: ['FREE', 'STARTER', 'CREATOR', 'PRO'] = ['FREE', 'STARTER', 'CREATOR', 'PRO'];
  const COL_COLORS = ['#10B981', '#3B82F6', '#A78BFA', '#FBBF24'];
  return (
    <View style={{
      marginTop: 12, borderRadius: 14, overflow: 'hidden',
      borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
      backgroundColor: 'rgba(255,255,255,0.04)',
    }}>
      <View style={{ flexDirection: 'row', backgroundColor: 'rgba(255,255,255,0.06)' }}>
        <View style={{ flex: 2, padding: 10 }}>
          <Text style={{ color: '#94A3B8', fontSize: 10, fontWeight: '900', letterSpacing: 0.6 }}>FEATURE</Text>
        </View>
        {COL_LABELS.map((l, i) => (
          <View key={l} style={{ flex: 1, padding: 10, alignItems: 'center' }}>
            <Text style={{ color: COL_COLORS[i], fontSize: 10, fontWeight: '900', letterSpacing: 0.6 }}>{l}</Text>
          </View>
        ))}
      </View>
      {BENEFIT_ROWS.map((row, idx) => (
        <View key={row.label} style={{ flexDirection: 'row', borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.06)', backgroundColor: idx % 2 ? 'rgba(255,255,255,0.025)' : 'transparent' }}>
          <View style={{ flex: 2, paddingHorizontal: 10, paddingVertical: 9, justifyContent: 'center' }}>
            <Text style={{ color: '#E2E8F0', fontSize: 11, lineHeight: 15 }}>{row.label}</Text>
          </View>
          {row.values.map((v, i) => {
            const isCheck = v === '✓';
            const isDash  = v === '—';
            return (
              <View key={i} style={{ flex: 1, paddingHorizontal: 4, paddingVertical: 9, alignItems: 'center', justifyContent: 'center' }}>
                {isCheck ? <Ionicons name="checkmark-circle" size={14} color="#10B981" />
                : isDash ? <Text style={{ color: '#475569', fontSize: 13 }}>—</Text>
                : <Text style={{ color: '#fff', fontSize: 10, fontWeight: '700', textAlign: 'center', lineHeight: 13 }} numberOfLines={2}>{v}</Text>}
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}



function UsageRow({ label, data, emoji, extra }: { label: string; data: Usage['reels']; emoji: string; extra?: string }) {
  const u = typeof data.used === 'number' ? data.used : 0;
  const l = typeof data.limit === 'number' ? data.limit : 0;
  const isUnlimited = data.limit === 'unlimited';
  const pct = isUnlimited ? 100 : (l > 0 ? Math.min(100, (u / l) * 100) : 0);
  return (
    <View style={{ marginBottom: 10 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
        <Text style={{ color: '#CBD5E1', fontSize: 12, fontWeight: '600' }}>{emoji} {label}</Text>
        <Text style={{ color: '#94A3B8', fontSize: 11 }}>
          {isUnlimited ? `${u} · unlimited` : `${u} / ${l}`}
          {extra ? `  ${extra}` : ''}
        </Text>
      </View>
      <View style={{ height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
        <View style={{ height: '100%', width: `${pct}%`, backgroundColor: pct >= 90 ? '#EF4444' : pct >= 70 ? '#FBBF24' : '#10B981' }} />
      </View>
    </View>
  );
}

function Feat({ emoji, label, warn }: { emoji: string; label: string; warn?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <Text style={{ fontSize: 14 }}>{emoji}</Text>
      <Text style={{ color: warn ? '#94A3B8' : '#E2E8F0', fontSize: 12.5, flex: 1 }}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  centerWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 6 },
  back: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)' },
  title: { fontSize: 20, fontWeight: '800', color: '#fff' },
  subtitle: { color: '#94A3B8', fontSize: 12, marginTop: 2 },

  usageCard: { marginTop: 14, padding: 14, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  usageTitle: { fontSize: 12, fontWeight: '800', letterSpacing: 0.5 },

  planCard: { position: 'relative', padding: 18, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.045)', borderWidth: 1.5 },
  popularBadge: { position: 'absolute', top: -10, right: 16, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, flexDirection: 'row', alignItems: 'center', gap: 4 },
  popularText: { color: '#fff', fontSize: 10, fontWeight: '900', letterSpacing: 0.8 },
  planName: { fontSize: 20, fontWeight: '900', letterSpacing: 0.3 },
  currentPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, backgroundColor: 'rgba(16,185,129,0.2)', borderWidth: 1, borderColor: 'rgba(16,185,129,0.6)' },
  currentPillText: { color: '#10B981', fontSize: 9, fontWeight: '900', letterSpacing: 0.5 },
  planPrice: { color: '#fff', fontSize: 28, fontWeight: '900' },
  planPer: { color: '#94A3B8', fontSize: 12 },

  upgradeBtn: { paddingVertical: 12, borderRadius: 12, alignItems: 'center' },
  upgradeText: { color: '#fff', fontSize: 14, fontWeight: '800' },

  sectionTitle: { color: '#fff', fontSize: 15, fontWeight: '800', letterSpacing: 0.3 },
  sectionSub: { color: '#94A3B8', fontSize: 12, marginTop: 4 },

  addonCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  addonLabel: { color: '#fff', fontSize: 13, fontWeight: '800' },
  addonPrice: { color: '#FBBF24', fontSize: 13, fontWeight: '900' },
  addonDesc: { color: '#94A3B8', fontSize: 11, marginTop: 4 },
  buyBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, backgroundColor: '#10B981' },
  buyBtnText: { color: '#fff', fontSize: 12, fontWeight: '800' },

  footNote: { color: '#64748B', fontSize: 10, textAlign: 'center', marginTop: 18 },

  // Session 27c — cycle toggle + trial
  cycleToggle: { flexDirection: 'row', backgroundColor: 'rgba(30,41,59,0.8)', borderRadius: 12, padding: 4, marginTop: 2, marginBottom: 14 },
  cycleOpt: { flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 },
  cycleOptActive: { backgroundColor: '#8B5CF6' },
  cycleTxt: { color: '#94A3B8', fontSize: 13, fontWeight: '700' },
  cycleTxtActive: { color: '#fff' },
  saveBadge: { backgroundColor: '#10B981', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  saveBadgeTxt: { color: '#fff', fontSize: 9, fontWeight: '800', letterSpacing: 0.4 },
  trialBanner: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 14, marginBottom: 14, gap: 12 },
  trialTitle: { color: '#fff', fontSize: 15, fontWeight: '800' },
  trialSub: { color: 'rgba(255,255,255,0.92)', fontSize: 12, marginTop: 4, lineHeight: 17 },
  trialActiveCard: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(16,185,129,0.12)', borderWidth: 1, borderColor: 'rgba(16,185,129,0.4)', padding: 10, borderRadius: 10, marginBottom: 10 },
  trialActiveTxt: { color: '#6EE7B7', fontSize: 12, fontWeight: '700' },

  /* Credits banner inside plan cards */
  creditsBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 12, paddingVertical: 10,
    borderRadius: 12, borderWidth: 1, marginBottom: 12,
  },
  creditsBannerValue: { fontSize: 15, fontWeight: '900', letterSpacing: 0.2 },
  creditsBannerSub: { color: '#94A3B8', fontSize: 11, marginTop: 1, fontWeight: '600' },
});
