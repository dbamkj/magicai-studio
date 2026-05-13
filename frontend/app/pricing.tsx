/**
 * /pricing — Public Pricing Page (Session 35)
 *
 * Marketing-first conversion page styled like Pollo AI / MagicHour.
 *
 * Sections (top → bottom):
 *   1. Hero with rotating tagline + "Start free trial" CTA
 *   2. Plan cards grid (Trial → Basic → Creator; Starter/Pro hidden by default)
 *   3. Feature matrix (sticky-header table)
 *   4. FAQ accordion
 *
 * Authentication: NOT required. This is a public/landing surface.
 * Account management lives in /subscription (signed-in view).
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Pressable, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import axios from 'axios';
import AuroraBackground from '../src/AuroraBackground';
import GlassHeader from '../src/components/GlassHeader';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Plan = {
  id: string;
  label: string;
  price_inr: number;
  price_annual_inr?: number;
  credits: number;
  trial_days?: number;
  watermark: boolean;
  max_resolution: string;
  monthly_reels_limit: number;
  monthly_lipsync_limit: number;
  monthly_ai_videos_limit: number;
  allow_face_swap: boolean;
  allow_talking_avatar?: boolean;
  allow_video_to_video: boolean;
  allow_dynamic_camera?: boolean;
  allow_image_cinematic: boolean;
  highlight?: boolean;
};

const MATRIX_ROWS: Array<{ key: string; label: string; render: (p: Plan) => string }> = [
  { key: 'credits',          label: 'Credits',                render: (p) => `${p.credits}` },
  { key: 'watermark',        label: 'No watermark',           render: (p) => (p.watermark ? '—' : '✓') },
  { key: 'res',              label: 'Max resolution',         render: (p) => p.max_resolution },
  { key: 'reels',            label: 'Reels / month',          render: (p) => p.monthly_reels_limit >= 9999 ? '∞' : `${p.monthly_reels_limit}` },
  { key: 'lipsync',          label: 'Lip sync / month',       render: (p) => `${p.monthly_lipsync_limit}` },
  { key: 'aivideos',         label: 'AI Videos / month',      render: (p) => `${p.monthly_ai_videos_limit}` },
  { key: 'faceswap',         label: 'Face Swap',              render: (p) => (p.allow_face_swap ? '✓' : '—') },
  { key: 'talk',             label: 'Talking Avatar',         render: (p) => (p.allow_talking_avatar ? '✓' : '—') },
  { key: 'v2v',              label: 'Video-to-Video',         render: (p) => (p.allow_video_to_video ? '✓' : '—') },
  { key: 'camera',           label: 'Dynamic Camera FX',      render: (p) => (p.allow_dynamic_camera ? '✓' : '—') },
  { key: 'cinematic',        label: 'Cinematic image mode',   render: (p) => (p.allow_image_cinematic ? '✓' : '—') },
];

const FAQS = [
  { q: 'How does the 7-day Trial work?',
    a: 'Sign up and you instantly get 50 credits, watermarked exports, and 480p. After 7 days you must upgrade to Basic (₹99) or higher to keep creating.' },
  { q: 'Can I cancel anytime?',
    a: 'Yes — cancel any time from Account → Subscription. You keep access until the end of the paid period.' },
  { q: 'What happens if I run out of credits?',
    a: 'You can buy a top-up pack (from ₹99 for 500 credits) or wait for your monthly refresh.' },
  { q: 'Is Razorpay safe?',
    a: 'Razorpay is the largest payments gateway in India, RBI-regulated, PCI-DSS compliant. We never store card details.' },
  { q: 'Do you offer refunds?',
    a: 'You can request a refund within 24 hours of purchase if you have not generated any media on the new plan.' },
];

export default function PricingPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly');
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${BACKEND_URL}/api/subscription/plans`);
        setPlans(r.data?.plans || []);
      } catch (e) {
        // Public endpoint — should not normally fail
        setPlans([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const priceText = (p: Plan) => {
    if (p.price_inr === 0) return 'Free';
    if (billing === 'annual') {
      const annual = p.price_annual_inr ?? p.price_inr * 10;
      return `₹${annual}/yr`;
    }
    return `₹${p.price_inr}/mo`;
  };

  const subPriceText = (p: Plan) => {
    if (billing === 'annual' && p.price_inr > 0) {
      const monthlyEquiv = Math.round((p.price_annual_inr ?? p.price_inr * 10) / 12);
      return `≈ ₹${monthlyEquiv}/mo billed yearly`;
    }
    if (p.id === 'trial') return `${p.trial_days || 7} days free`;
    return '';
  };

  const onSelect = (p: Plan) => {
    // Public CTA → push to login; existing subscription.tsx handles paid checkout.
    if (p.id === 'trial') {
      router.push('/login' as any);
    } else {
      router.push({ pathname: '/subscription' as any, params: { upgradeTo: p.id, cycle: billing } });
    }
  };

  return (
    <View style={styles.root}>
      <AuroraBackground />
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <GlassHeader
          icon="pricetags"
          title="Pricing"
          subtitle="Simple, transparent plans"
          onBack={() => router.back()}
        />
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingBottom: 110, paddingHorizontal: 16 }}
          showsVerticalScrollIndicator={false}
        >
          {/* ── 1. HERO ── */}
          <View style={styles.hero}>
            <LinearGradient
              colors={['rgba(255,93,177,0.18)', 'rgba(122,252,255,0.08)']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={styles.heroBg}
            />
            <Text style={styles.heroEyebrow}>MAGICAI STUDIO</Text>
            <Text style={styles.heroTitle}>Create cinematic{'\n'}AI videos in minutes</Text>
            <Text style={styles.heroSubtitle}>
              Start with 50 free credits. Upgrade only when you're hooked.
            </Text>
            <TouchableOpacity
              activeOpacity={0.85}
              onPress={() => router.push('/login' as any)}
              style={styles.heroCtaWrap}
            >
              <LinearGradient
                colors={['#ff5db1', '#ff8a4c']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={styles.heroCta}
              >
                <Ionicons name="sparkles" size={18} color="#fff" />
                <Text style={styles.heroCtaText}>Start 7-day free trial</Text>
              </LinearGradient>
            </TouchableOpacity>
            <Text style={styles.heroFinePrint}>No credit card · Cancel anytime</Text>
          </View>

          {/* ── 2. BILLING TOGGLE ── */}
          <View style={styles.toggleRow}>
            <Pressable
              onPress={() => setBilling('monthly')}
              style={[styles.togglePill, billing === 'monthly' && styles.togglePillActive]}
            >
              <Text style={[styles.toggleText, billing === 'monthly' && styles.toggleTextActive]}>
                Monthly
              </Text>
            </Pressable>
            <Pressable
              onPress={() => setBilling('annual')}
              style={[styles.togglePill, billing === 'annual' && styles.togglePillActive]}
            >
              <Text style={[styles.toggleText, billing === 'annual' && styles.toggleTextActive]}>
                Annual
              </Text>
              <View style={styles.saveBadge}>
                <Text style={styles.saveBadgeText}>−17%</Text>
              </View>
            </Pressable>
          </View>

          {/* ── 3. PLAN CARDS ── */}
          {loading ? (
            <ActivityIndicator size="large" color="#ff5db1" style={{ marginVertical: 40 }} />
          ) : (
            <View style={styles.cardsCol}>
              {plans.map((p) => (
                <PlanCard
                  key={p.id}
                  plan={p}
                  priceText={priceText(p)}
                  subPriceText={subPriceText(p)}
                  onSelect={() => onSelect(p)}
                />
              ))}
            </View>
          )}

          {/* ── 4. FEATURE MATRIX ── */}
          {plans.length > 0 && (
            <View style={styles.matrixCard}>
              <Text style={styles.sectionTitle}>What's included</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View>
                  <View style={styles.matrixHeader}>
                    <Text style={[styles.matrixCell, styles.matrixHeaderCell, { width: 160 }]}>Feature</Text>
                    {plans.map((p) => (
                      <Text
                        key={p.id}
                        style={[
                          styles.matrixCell,
                          styles.matrixHeaderCell,
                          { width: 110, color: p.highlight ? '#ff5db1' : '#cbd2e8' },
                        ]}
                      >
                        {p.label}
                      </Text>
                    ))}
                  </View>
                  {MATRIX_ROWS.map((row, idx) => (
                    <View
                      key={row.key}
                      style={[styles.matrixRow, idx % 2 === 0 && styles.matrixRowAlt]}
                    >
                      <Text style={[styles.matrixCell, { width: 160, color: '#cbd2e8' }]}>{row.label}</Text>
                      {plans.map((p) => (
                        <Text
                          key={p.id}
                          style={[
                            styles.matrixCell,
                            { width: 110 },
                            row.render(p) === '✓' && { color: '#7affc7', fontWeight: '700' },
                            row.render(p) === '—' && { color: '#475569' },
                          ]}
                        >
                          {row.render(p)}
                        </Text>
                      ))}
                    </View>
                  ))}
                </View>
              </ScrollView>
            </View>
          )}

          {/* ── 5. FAQ ── */}
          <View style={{ marginTop: 24 }}>
            <Text style={styles.sectionTitle}>FAQ</Text>
            {FAQS.map((f, i) => (
              <Pressable
                key={i}
                onPress={() => setOpenFaq(openFaq === i ? null : i)}
                style={styles.faqRow}
              >
                <View style={styles.faqQRow}>
                  <Text style={styles.faqQ}>{f.q}</Text>
                  <Ionicons
                    name={openFaq === i ? 'chevron-up' : 'chevron-down'}
                    size={18}
                    color="#94A3B8"
                  />
                </View>
                {openFaq === i && <Text style={styles.faqA}>{f.a}</Text>}
              </Pressable>
            ))}
          </View>

          {/* ── 6. FOOTER ── */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>
              Have questions? Email{' '}
              <Text style={{ color: '#7afcff' }}>hello@magicai.studio</Text>
            </Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}


// ────────────────────────────────────────────────────────────
// Plan card sub-component
// ────────────────────────────────────────────────────────────
function PlanCard({
  plan, priceText, subPriceText, onSelect,
}: { plan: Plan; priceText: string; subPriceText: string; onSelect: () => void }) {
  const highlight = !!plan.highlight;
  const ctaLabel = plan.id === 'trial'
    ? 'Start free trial'
    : plan.id === 'basic'
      ? 'Get Basic'
      : `Choose ${plan.label}`;

  return (
    <View style={[styles.planCard, highlight && styles.planCardHero]}>
      {highlight && (
        <View style={styles.bestBadge}>
          <Ionicons name="star" size={11} color="#0a0418" />
          <Text style={styles.bestBadgeText}>BEST VALUE</Text>
        </View>
      )}
      <Text style={[styles.planLabel, highlight && { color: '#ff5db1' }]}>{plan.label}</Text>
      <View style={{ flexDirection: 'row', alignItems: 'baseline', marginTop: 4 }}>
        <Text style={styles.planPrice}>{priceText}</Text>
      </View>
      {!!subPriceText && <Text style={styles.planSub}>{subPriceText}</Text>}

      <View style={styles.planFeatures}>
        <Bullet ok>{plan.credits} credits / month</Bullet>
        <Bullet ok>Max {plan.max_resolution}</Bullet>
        {plan.watermark
          ? <Bullet>Watermark on exports</Bullet>
          : <Bullet ok>No watermark</Bullet>
        }
        {plan.allow_face_swap   ? <Bullet ok>Face Swap</Bullet>          : <Bullet>Face Swap not included</Bullet>}
        {plan.allow_talking_avatar ? <Bullet ok>Talking Avatar</Bullet>  : null}
        {plan.allow_video_to_video ? <Bullet ok>Video-to-Video</Bullet>  : null}
        {plan.monthly_ai_videos_limit > 0 && (
          <Bullet ok>{plan.monthly_ai_videos_limit} AI videos / month</Bullet>
        )}
      </View>

      <TouchableOpacity activeOpacity={0.85} onPress={onSelect} style={{ marginTop: 16 }}>
        <LinearGradient
          colors={highlight ? ['#ff5db1', '#ff8a4c'] : ['rgba(255,255,255,0.10)', 'rgba(255,255,255,0.04)']}
          start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={styles.planCta}
        >
          <Text style={[styles.planCtaText, !highlight && { color: '#ffffff' }]}>
            {ctaLabel}
          </Text>
        </LinearGradient>
      </TouchableOpacity>
    </View>
  );
}

function Bullet({ children, ok }: { children: React.ReactNode; ok?: boolean }) {
  return (
    <View style={styles.bulletRow}>
      <Ionicons
        name={ok ? 'checkmark-circle' : 'remove-circle-outline'}
        size={15}
        color={ok ? '#7affc7' : '#475569'}
      />
      <Text style={[styles.bulletText, !ok && { color: '#64748B' }]}>{children}</Text>
    </View>
  );
}


// ────────────────────────────────────────────────────────────
// Styles
// ────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#070314' },

  // Hero
  hero: {
    borderRadius: 24,
    padding: 24,
    paddingTop: 28,
    marginTop: 8,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
    backgroundColor: 'rgba(255,255,255,0.04)',
    overflow: 'hidden',
  },
  heroBg: { ...StyleSheet.absoluteFillObject },
  heroEyebrow: {
    fontSize: 11, fontWeight: '800', color: '#FBBF24', letterSpacing: 2,
  },
  heroTitle: {
    fontSize: 28, fontWeight: '800', color: '#fff', marginTop: 6, lineHeight: 34, letterSpacing: 0.2,
  },
  heroSubtitle: {
    fontSize: 14, color: '#cbd2e8', marginTop: 8, lineHeight: 20,
  },
  heroCtaWrap: { marginTop: 18 },
  heroCta: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14, borderRadius: 14,
  },
  heroCtaText: { color: '#fff', fontSize: 15, fontWeight: '800', letterSpacing: 0.3 },
  heroFinePrint: { color: '#94A3B8', fontSize: 12, marginTop: 10, textAlign: 'center' },

  // Toggle
  toggleRow: {
    flexDirection: 'row', alignSelf: 'center', backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 999, padding: 4, marginVertical: 16, gap: 4,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
  },
  togglePill: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999,
  },
  togglePillActive: { backgroundColor: 'rgba(255,93,177,0.20)' },
  toggleText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  toggleTextActive: { color: '#fff', fontWeight: '700' },
  saveBadge: { backgroundColor: '#7affc7', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 999 },
  saveBadgeText: { color: '#0a0418', fontSize: 9, fontWeight: '800' },

  // Cards
  cardsCol: { gap: 14 },
  planCard: {
    borderRadius: 18,
    padding: 18,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
  },
  planCardHero: {
    borderColor: 'rgba(255,93,177,0.50)',
    backgroundColor: 'rgba(255,93,177,0.08)',
  },
  bestBadge: {
    position: 'absolute', top: -10, right: 14,
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999,
    backgroundColor: '#FBBF24',
  },
  bestBadgeText: { color: '#0a0418', fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  planLabel: { fontSize: 13, fontWeight: '800', color: '#cbd2e8', letterSpacing: 1.2, textTransform: 'uppercase' },
  planPrice: { fontSize: 28, fontWeight: '800', color: '#fff', letterSpacing: 0.2 },
  planSub: { fontSize: 12, color: '#94A3B8', marginTop: 2 },
  planFeatures: { marginTop: 14, gap: 8 },
  bulletRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  bulletText: { fontSize: 13, color: '#cbd2e8', flex: 1, lineHeight: 18 },
  planCta: { paddingVertical: 12, borderRadius: 14, alignItems: 'center' },
  planCtaText: { color: '#fff', fontSize: 14, fontWeight: '800', letterSpacing: 0.4 },

  // Matrix
  matrixCard: {
    marginTop: 24, padding: 16, borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  sectionTitle: { fontSize: 18, fontWeight: '800', color: '#fff', marginBottom: 12, letterSpacing: 0.3 },
  matrixHeader: { flexDirection: 'row', paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.08)' },
  matrixRow: { flexDirection: 'row', paddingVertical: 10 },
  matrixRowAlt: { backgroundColor: 'rgba(255,255,255,0.02)' },
  matrixCell: { fontSize: 12, color: '#cbd2e8', textAlign: 'center' },
  matrixHeaderCell: { fontSize: 11, fontWeight: '800', letterSpacing: 0.5, textTransform: 'uppercase' },

  // FAQ
  faqRow: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 14, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)',
  },
  faqQRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  faqQ: { color: '#fff', fontSize: 14, fontWeight: '700', flex: 1, paddingRight: 8 },
  faqA: { color: '#cbd2e8', fontSize: 13, lineHeight: 20, marginTop: 10 },

  // Footer
  footer: { marginTop: 24, alignItems: 'center', paddingVertical: 16 },
  footerText: { color: '#64748B', fontSize: 12 },
});
