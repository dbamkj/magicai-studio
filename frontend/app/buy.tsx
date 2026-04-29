/* Phase-3 Payments — Buy screen (Credit Packs + Tier Upgrades)
 *
 * Cross-platform flow:
 *  • Web → loads Razorpay Checkout JS, opens modal, calls /verify on success.
 *  • Native → opens hosted page in `expo-web-browser`, polls /transactions until paid.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  Pressable, StatusBar, Platform, Alert,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as WebBrowser from 'expo-web-browser';
import axios from 'axios';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';
import { useTheme } from '../src/ThemeContext';

const API = (process.env.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_BACKEND_URL || '') + '/api';
const PUBLIC_API_BASE = (process.env.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_BACKEND_URL || '') + '/api';

type Pack = { id: string; label: string; credits: number; price_inr: number; popular: boolean; savings?: string | null };
type Tier = { id: string; tier: string; label: string; subtitle: string; price_inr: number; duration_days: number; perks: string[]; popular: boolean };
type Tab = 'credits' | 'tier';

declare global { interface Window { Razorpay?: any } }


/** Inject Razorpay Checkout JS once on web */
async function ensureRazorpayScript(): Promise<boolean> {
  if (Platform.OS !== 'web') return false;
  if (typeof window === 'undefined') return false;
  if (window.Razorpay) return true;
  return new Promise((resolve) => {
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.async = true;
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}


export default function BuyScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ tab?: string }>();
  const { isDark } = useTheme();
  const titleColor = isDark ? '#FFFFFF' : '#0F0C29';
  const subColor = isDark ? '#94A3B8' : '#64748B';

  const [tab, setTab] = useState<Tab>((params?.tab === 'tier') ? 'tier' : 'credits');
  const [packs, setPacks] = useState<Pack[]>([]);
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasingId, setPurchasingId] = useState<string | null>(null);
  const [config, setConfig] = useState<any>(null);

  // ---------- load catalogs once ----------
  useEffect(() => {
    (async () => {
      try {
        const [pRes, tRes, cRes] = await Promise.all([
          axios.get(`${API}/payments/credit-packs`, { timeout: 12000 }),
          axios.get(`${API}/payments/tier-upgrades`, { timeout: 12000 }),
          axios.get(`${API}/payments/config`, { timeout: 12000 }),
        ]);
        setPacks(pRes.data?.packs || []);
        setTiers(tRes.data?.tiers || []);
        setConfig(cRes.data || {});
      } catch (e) {
        console.warn('payments catalog load failed', e);
      } finally { setLoading(false); }
    })();
  }, []);

  // ---------- buy ----------
  const buy = useCallback(async (kind: 'credit_pack' | 'tier_upgrade', item_id: string) => {
    if (purchasingId) return;
    setPurchasingId(item_id);
    try {
      // 1. Create order
      const r = await axios.post(`${API}/payments/razorpay/create-order`, { kind, item_id }, { timeout: 15000 });
      const order = r.data;
      if (!order?.order_id || !order?.key_id) throw new Error('Invalid order response');

      // 2. Open Checkout — Web vs Native
      if (Platform.OS === 'web') {
        const ok = await ensureRazorpayScript();
        if (!ok) throw new Error('Could not load Razorpay Checkout');
        await new Promise<void>((resolve) => {
          const rzp = new window.Razorpay({
            key: order.key_id,
            order_id: order.order_id,
            amount: order.amount_paise,
            currency: order.currency,
            name: order.name,
            description: order.description,
            prefill: order.prefill,
            theme: order.theme,
            handler: async (resp: any) => {
              // 3. Verify
              try {
                const v = await axios.post(`${API}/payments/razorpay/verify`, {
                  razorpay_order_id: resp.razorpay_order_id,
                  razorpay_payment_id: resp.razorpay_payment_id,
                  razorpay_signature: resp.razorpay_signature,
                }, { timeout: 15000 });
                if (v.data?.fulfilled) {
                  Alert.alert('🎉 Payment successful', _formatSummary(v.data.summary));
                } else {
                  Alert.alert('Payment received', 'Verified but fulfillment had an issue. Refresh in a moment.');
                }
              } catch (e: any) {
                Alert.alert('Verification failed', e?.response?.data?.detail || e?.message || 'Please contact support with your order id.');
              }
              resolve();
            },
            modal: { ondismiss: () => resolve() },
          });
          rzp.open();
        });
      } else {
        // Native — open the backend-hosted Checkout page in the in-app browser
        const url = `${PUBLIC_API_BASE}/payments/checkout-page?order_id=${encodeURIComponent(order.order_id)}` +
                    `&key_id=${encodeURIComponent(order.key_id)}` +
                    `&description=${encodeURIComponent(order.description)}` +
                    `&email=${encodeURIComponent(order.prefill?.email || '')}` +
                    `&contact=${encodeURIComponent(order.prefill?.contact || '')}`;
        await WebBrowser.openBrowserAsync(url);
        // After the browser closes, poll the order status once
        try {
          const t = await axios.get(`${API}/payments/transactions`, { timeout: 12000 });
          const found = (t.data?.transactions || []).find((x: any) => x.id === order.order_id);
          if (found?.status === 'fulfilled') {
            Alert.alert('🎉 Payment successful', _formatSummary(found.fulfillment));
          } else if (found?.status === 'paid') {
            Alert.alert('Payment received', 'Verifying with our servers — please refresh in a moment.');
          } else {
            // Could be cancelled — silent
          }
        } catch {}
      }
    } catch (e: any) {
      Alert.alert('Could not start payment', e?.response?.data?.detail || e?.message || 'Please try again.');
    } finally {
      setPurchasingId(null);
    }
  }, [purchasingId]);

  return (
    <AuroraBackground>
    <SafeAreaView style={s.root} edges={['top']}>
      <StatusBar barStyle="light-content" />

      {/* header */}
      <GlassHeader
        icon="diamond"
        title="Get Credits & Premium"
        subtitle={config?.is_test ? '🧪 Test mode · no real charge' : 'Secure payments by Razorpay'}
        onBack={() => router.back()}
        gradient={['#FBBF24', '#EC4899', '#A78BFA']}
      />

      {/* Tab switch */}
      <View style={s.tabs}>
        {([['credits', '🪙 Credit Packs'], ['tier', '✨ Premium']] as [Tab, string][]).map(([k, label]) => (
          <Pressable
            key={k}
            onPress={() => setTab(k)}
            style={[s.tab, tab === k && s.tabActive]}
          >
            <Text style={[s.tabTxt, tab === k && { color: '#fff' }]}>{label}</Text>
          </Pressable>
        ))}
      </View>

      {loading ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color="#8B5CF6" />
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {tab === 'credits'
            ? packs.map(p => (
                <PackCard
                  key={p.id}
                  pack={p}
                  busy={purchasingId === p.id}
                  onBuy={() => buy('credit_pack', p.id)}
                />
              ))
            : tiers.map(t => (
                <TierCard
                  key={t.id}
                  tier={t}
                  busy={purchasingId === t.id}
                  onBuy={() => buy('tier_upgrade', t.id)}
                />
              ))
          }

          <View style={s.footer}>
            <Ionicons name="shield-checkmark" size={14} color="#94A3B8" />
            <Text style={s.footerTxt}>
              {config?.is_test
                ? 'Test mode — use card 4111 1111 1111 1111 or UPI success@razorpay'
                : 'Payments secured by Razorpay · 256-bit encryption'}
            </Text>
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
    </AuroraBackground>
  );
}


/* --- Pack Card --- */
function PackCard({ pack, busy, onBuy }: { pack: Pack; busy: boolean; onBuy: () => void }) {
  return (
    <View style={[s.card, pack.popular && s.cardPopular]}>
      {pack.popular && (
        <View style={s.popularRibbon}>
          <Ionicons name="star" size={10} color="#0B1120" />
          <Text style={s.popularRibbonTxt}>MOST POPULAR</Text>
        </View>
      )}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
        <View style={[s.coinCircle, pack.popular && { backgroundColor: '#FBBF24' }]}>
          <Text style={{ fontSize: 26 }}>🪙</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.cardTitle}>{pack.label}</Text>
          <Text style={s.cardCredits}>{pack.credits.toLocaleString()} credits</Text>
          {pack.savings && <Text style={s.savingsTxt}>{pack.savings}</Text>}
        </View>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={onBuy}
          disabled={busy}
          style={[s.buyBtn, pack.popular && { backgroundColor: '#FBBF24' }]}
        >
          {busy ? (
            <ActivityIndicator size="small" color={pack.popular ? '#0B1120' : '#fff'} />
          ) : (
            <Text style={[s.buyBtnTxt, pack.popular && { color: '#0B1120' }]}>₹{pack.price_inr}</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}


/* --- Tier Card --- */
function TierCard({ tier, busy, onBuy }: { tier: Tier; busy: boolean; onBuy: () => void }) {
  return (
    <View style={[s.tierCard, tier.popular && s.cardPopular]}>
      {tier.popular && (
        <View style={s.popularRibbon}>
          <Ionicons name="flame" size={10} color="#0B1120" />
          <Text style={s.popularRibbonTxt}>RECOMMENDED</Text>
        </View>
      )}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <Text style={s.tierLabel}>{tier.label}</Text>
        <View>
          <Text style={s.tierPrice}>₹{tier.price_inr}</Text>
          <Text style={s.tierPriceSub}>for {tier.duration_days} days</Text>
        </View>
      </View>
      <Text style={s.tierSub}>{tier.subtitle}</Text>
      <View style={{ marginTop: 12, gap: 6 }}>
        {tier.perks.map(p => (
          <View key={p} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Ionicons name="checkmark-circle" size={14} color={tier.popular ? '#FBBF24' : '#10B981'} />
            <Text style={s.perkTxt}>{p}</Text>
          </View>
        ))}
      </View>
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={onBuy}
        disabled={busy}
        style={[s.tierBuyBtn, tier.popular && { backgroundColor: '#FBBF24' }]}
      >
        {busy ? (
          <ActivityIndicator size="small" color={tier.popular ? '#0B1120' : '#fff'} />
        ) : (
          <>
            <Ionicons name="lock-closed" size={12} color={tier.popular ? '#0B1120' : '#fff'} />
            <Text style={[s.tierBuyBtnTxt, tier.popular && { color: '#0B1120' }]}>Upgrade for ₹{tier.price_inr}</Text>
          </>
        )}
      </TouchableOpacity>
      <Text style={s.tierFooter}>One-time payment · No auto-debit · Renew anytime</Text>
    </View>
  );
}


function _formatSummary(summary: any): string {
  if (!summary) return 'Your purchase has been applied.';
  if (summary.kind === 'credit_pack') {
    return `+${summary.credits_added} credits added! New balance: ${summary.new_balance}`;
  }
  if (summary.kind === 'tier_upgrade') {
    return `${summary.tier?.toUpperCase()} tier active until ${new Date(summary.tier_expires_at).toLocaleDateString()}.\n+${summary.credits_added} bonus credits.`;
  }
  return 'Your purchase has been applied.';
}


/* --- styles --- */
const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: 'transparent' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '800' },
  headerSub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },

  tabs: { flexDirection: 'row', marginHorizontal: 16, gap: 8, marginTop: 4, marginBottom: 8 },
  tab: { flex: 1, paddingVertical: 10, borderRadius: 12, backgroundColor: '#1E293B', alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  tabActive: { backgroundColor: '#8B5CF6', borderColor: '#8B5CF6' },
  tabTxt: { color: '#94A3B8', fontWeight: '700', fontSize: 13 },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  card: { backgroundColor: '#111827', borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: '#1F2937', position: 'relative' },
  cardPopular: { borderColor: '#FBBF24', shadowColor: '#FBBF24', shadowOpacity: 0.25, shadowRadius: 12, elevation: 4 },
  popularRibbon: {
    position: 'absolute', top: -10, right: 12, flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#FBBF24', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8,
  },
  popularRibbonTxt: { color: '#0B1120', fontSize: 9, fontWeight: '900', letterSpacing: 0.4 },

  coinCircle: { width: 52, height: 52, borderRadius: 14, backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' },
  cardTitle: { color: '#fff', fontSize: 14, fontWeight: '800' },
  cardCredits: { color: '#94A3B8', fontSize: 12, marginTop: 1 },
  savingsTxt: { color: '#10B981', fontSize: 11, fontWeight: '700', marginTop: 2 },
  buyBtn: { backgroundColor: '#8B5CF6', paddingHorizontal: 18, paddingVertical: 10, borderRadius: 10, minWidth: 70, alignItems: 'center' },
  buyBtnTxt: { color: '#fff', fontSize: 15, fontWeight: '800' },

  /* tier */
  tierCard: { backgroundColor: '#111827', borderRadius: 14, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: '#1F2937', position: 'relative' },
  tierLabel: { color: '#fff', fontSize: 18, fontWeight: '800' },
  tierPrice: { color: '#fff', fontSize: 20, fontWeight: '900', textAlign: 'right' },
  tierPriceSub: { color: '#94A3B8', fontSize: 10, textAlign: 'right' },
  tierSub: { color: '#94A3B8', fontSize: 12 },
  perkTxt: { color: '#E2E8F0', fontSize: 12 },
  tierBuyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    marginTop: 14, backgroundColor: '#8B5CF6', borderRadius: 11, paddingVertical: 12 },
  tierBuyBtnTxt: { color: '#fff', fontSize: 14, fontWeight: '800' },
  tierFooter: { color: '#64748B', fontSize: 10, textAlign: 'center', marginTop: 8 },

  footer: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, marginTop: 12 },
  footerTxt: { color: '#94A3B8', fontSize: 11, textAlign: 'center', flex: 1 },
});
