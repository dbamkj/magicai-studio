import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator,
  Alert, KeyboardAvoidingView, Platform, Animated, Easing, ScrollView, Pressable, Linking, Dimensions, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import { useRouter, useLocalSearchParams } from 'expo-router';
import * as ExpoLinking from 'expo-linking';
import axios from 'axios';
import { useAuth } from '../src/AuthContext';
import MagicAiLogo from '../src/MagicAiLogo';
import BrandLogo from '../src/BrandLogo';
import AuroraBackground from '../src/AuroraBackground';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const { width: SCREEN_W } = Dimensions.get('window');

const DEMO_ACCOUNTS = [
  { id: 'free', email: 'demo_free@test.com', label: 'Free Demo', credits: 300, icon: '🎈', color: '#10B981' },
  { id: 'starter', email: 'demo_starter@test.com', label: 'Starter Demo', credits: 1500, icon: '⭐', color: '#F59E0B' },
  { id: 'creator', email: 'demo_creator@test.com', label: 'Creator Demo', credits: 3000, icon: '🎨', color: '#EC4899' },
  { id: 'pro', email: 'demo_pro@test.com', label: 'Pro Demo', credits: 6000, icon: '💎', color: '#A78BFA' },
  { id: 'custom', email: '', label: 'Custom Email', credits: 0, icon: '✍️', color: '#60A5FA' },
];

const FEATURES = [
  { icon: '🎭', title: 'Talking Avatars', desc: 'Turn a photo into a speaking character', color: '#A78BFA' },
  { icon: '🎬', title: 'AI Reels', desc: 'Cinematic short videos in seconds', color: '#EC4899' },
  { icon: '💋', title: 'Lip Sync', desc: 'Perfect dialogue-to-face matching', color: '#F59E0B' },
  { icon: '🔄', title: 'Face Swap', desc: 'Swap faces in images & videos', color: '#10B981' },
  { icon: '🕉️', title: 'Divine Stories', desc: 'Festival-ready devotional reels', color: '#FBBF24' },
  { icon: '🎤', title: 'Bhajan Creator', desc: 'AI-generated devotional lyrics', color: '#60A5FA' },
];

/* ================================================================== *
 *   Feature Carousel — auto-scroll with fade + slide animations      *
 * ================================================================== */
function FeatureCarousel() {
  const [idx, setIdx] = useState(0);
  const fade = useRef(new Animated.Value(1)).current;
  const slide = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const tick = setInterval(() => {
      // Fade + slide out, then swap + fade+slide in
      Animated.parallel([
        Animated.timing(fade, { toValue: 0, duration: 350, easing: Easing.ease, useNativeDriver: Platform.OS !== 'web' }),
        Animated.timing(slide, { toValue: -40, duration: 350, easing: Easing.ease, useNativeDriver: Platform.OS !== 'web' }),
      ]).start(() => {
        setIdx(i => (i + 1) % FEATURES.length);
        slide.setValue(40);
        Animated.parallel([
          Animated.timing(fade, { toValue: 1, duration: 400, easing: Easing.ease, useNativeDriver: Platform.OS !== 'web' }),
          Animated.timing(slide, { toValue: 0, duration: 400, easing: Easing.ease, useNativeDriver: Platform.OS !== 'web' }),
        ]).start();
      });
    }, 3200);
    return () => clearInterval(tick);
  }, []);

  const f = FEATURES[idx];
  return (
    <View style={s.carousel}>
      <Animated.View
        style={[
          s.carouselCard,
          { borderColor: f.color + '55', opacity: fade, transform: [{ translateX: slide }] },
        ]}
      >
        <View style={[s.carouselIconBox, { backgroundColor: f.color + '22', borderColor: f.color }]}>
          <Text style={{ fontSize: 34 }}>{f.icon}</Text>
        </View>
        <Text style={s.carouselTitle}>{f.title}</Text>
        <Text style={s.carouselDesc}>{f.desc}</Text>
      </Animated.View>
      {/* Dots */}
      <View style={s.dotRow}>
        {FEATURES.map((_, i) => (
          <View
            key={i}
            style={[
              s.dot,
              i === idx && { backgroundColor: f.color, width: 18 },
            ]}
          />
        ))}
      </View>
    </View>
  );
}

/* ================================================================== *
 *   Account Dropdown (demo chooser)                                  *
 * ================================================================== */
function AccountDropdown({ value, onPick }: { value: string; onPick: (a: typeof DEMO_ACCOUNTS[0]) => void }) {
  const [open, setOpen] = useState(false);
  const selected = DEMO_ACCOUNTS.find(a => a.id === value) || DEMO_ACCOUNTS[3];
  return (
    <View style={{ width: '100%', zIndex: 20 }}>
      <TouchableOpacity activeOpacity={0.85} onPress={() => setOpen(o => !o)} style={s.ddTrigger}>
        <Text style={s.ddIcon}>{selected.icon}</Text>
        <View style={{ flex: 1 }}>
          <Text style={s.ddLabel}>{selected.label}</Text>
          {selected.credits > 0 && <Text style={s.ddSub}>{selected.credits} credits · password auto-filled</Text>}
          {selected.credits === 0 && <Text style={s.ddSub}>Enter your own credentials</Text>}
        </View>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={18} color="#94A3B8" />
      </TouchableOpacity>
      {open && (
        <View style={s.ddMenu}>
          {DEMO_ACCOUNTS.map(a => {
            const isSelected = a.id === selected.id;
            return (
              <Pressable
                key={a.id}
                onPress={() => { onPick(a); setOpen(false); }}
                style={({ pressed }) => [s.ddItem, (isSelected || pressed) && s.ddItemActive]}
              >
                <Text style={s.ddIcon}>{a.icon}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={s.ddLabel}>{a.label}</Text>
                  {a.email ? <Text style={s.ddSub}>{a.email}</Text> : <Text style={s.ddSub}>use your own email</Text>}
                </View>
                {a.credits > 0 && (
                  <View style={[s.credChip, { borderColor: a.color }]}>
                    <Text style={[s.credChipText, { color: a.color }]}>{a.credits}¢</Text>
                  </View>
                )}
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

/* ================================================================== *
 *   Main Landing / Login / Signup Screen                             *
 * ================================================================== */
export default function LandingScreen() {
  const router = useRouter();
  const { login, register, mode } = useAuth();
  const urlParams = useLocalSearchParams<{ mode?: string; next?: string }>();
  const nextRoute = (urlParams?.next && urlParams.next.startsWith('/') ? String(urlParams.next) : '/') as any;
  const [authMode, setAuthMode] = useState<'login' | 'register' | null>(
    urlParams?.mode === 'login' ? 'login' : urlParams?.mode === 'register' ? 'register' : null,
  );
  const [accountId, setAccountId] = useState<string>('pro');
  const [email, setEmail] = useState<string>(DEMO_ACCOUNTS[2].email);
  const [password, setPassword] = useState<string>('Test@123');
  const [name, setName] = useState<string>('');
  const [signupPlan, setSignupPlan] = useState<'free' | 'starter' | 'creator' | 'pro'>('free');
  const [busy, setBusy] = useState(false);

  // Handle Google SSO return (session_id in URL)
  useEffect(() => {
    const handleUrl = async (rawUrl: string) => {
      if (!rawUrl) return;
      const m = rawUrl.match(/session_id=([^&]+)/);
      if (!m) return;
      const session_id = m[1];
      setBusy(true);
      try {
        const res = await axios.post(`${BACKEND_URL}/api/auth/google-finish`, { session_id }, { timeout: 10000 });
        if (res.data?.token) {
          // Trigger re-read via AuthContext by reloading. AuthContext stores
          // the JWT under key 'magicai_jwt_v1' — must match or the next page
          // boot will see guest state instead of the freshly-logged-in user.
          const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
          await AsyncStorage.setItem('magicai_jwt_v1', res.data.token);
          if (Platform.OS === 'web' && typeof window !== 'undefined') {
            window.location.hash = '';
            window.location.href = '/';
          } else {
            router.replace('/');
          }
        }
      } catch (e: any) {
        Alert.alert('Google sign-in failed', e.response?.data?.detail || e.message);
      } finally { setBusy(false); }
    };
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      if (window.location.hash?.includes('session_id=')) handleUrl(window.location.hash);
    }
    const sub = ExpoLinking.addEventListener('url', (e) => handleUrl(e.url));
    ExpoLinking.getInitialURL().then(url => { if (url) handleUrl(url); });
    return () => sub.remove();
  }, []);

  const onPickAccount = (a: typeof DEMO_ACCOUNTS[0]) => {
    setAccountId(a.id);
    if (a.id === 'custom') { setEmail(''); setPassword(''); }
    else { setEmail(a.email); setPassword('Test@123'); }
  };

  const submit = async () => {
    if (!email || !password) { Alert.alert('Required', 'Enter email and password'); return; }
    setBusy(true);
    try {
      if (authMode === 'login') {
        await login(email.trim().toLowerCase(), password);
        router.replace(nextRoute);
      } else {
        await register(email.trim().toLowerCase(), password, name || undefined, signupPlan);
        // Auth state is now set (token in AsyncStorage, axios default header set, user state populated).
        // For free plan: go to home or the intended next route.
        // For paid plan: go to subscription so user can review/upgrade (mock checkout).
        if (signupPlan === 'free') {
          router.replace(nextRoute);
        } else {
          router.replace('/subscription');
        }
      }
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Auth failed';
      console.warn('Auth error:', msg, e.response?.status);
      Alert.alert(authMode === 'login' ? 'Login failed' : 'Sign-up failed', msg);
    } finally { setBusy(false); }
  };

  const googleLogin = () => {
    const scheme = ExpoLinking.createURL('/login');
    const redirect = Platform.OS === 'web' && typeof window !== 'undefined' ? `${window.location.origin}/login` : scheme;
    const url = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirect)}`;
    if (Platform.OS === 'web') window.location.href = url;
    else Linking.openURL(url);
  };

  return (
    <AuroraBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
          <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
            {/* BETA chip */}
            {mode?.is_beta && (
              <View style={s.betaChipRow}>
                <View style={s.betaChip}>
                  <View style={s.betaDot} />
                  <Text style={s.betaChipText}>BETA · {mode.version || 'v1.0'}</Text>
                </View>
              </View>
            )}

            {/* HERO */}
            <View style={s.hero}>
              <BrandLogo size="xl" stacked imageWordmark />
              <Text style={s.subtext}>Create AI videos · avatars · reels in seconds</Text>
            </View>

            {/* FEATURE CAROUSEL */}
            <FeatureCarousel />

            {/* CTA + Glass Card */}
            <View style={s.cardWrap}>
              <BlurView intensity={30} tint="dark" style={s.cardBlur}>
                <View style={s.card}>
                  {authMode === null ? (
                    <>
                      <Text style={s.cardHeading}>Get started free</Text>
                      <Text style={s.cardSubheading}>Sign up for 300 free credits · no card needed</Text>

                      <TouchableOpacity onPress={() => setAuthMode('register')} activeOpacity={0.85}>
                        <LinearGradient
                          colors={['#6C3BFF', '#A855F7', '#FF4FD8']}
                          start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
                          style={s.primaryCta}
                        >
                          <Text style={s.primaryCtaText}>Get Started</Text>
                          <Ionicons name="arrow-forward" size={18} color="#fff" />
                        </LinearGradient>
                      </TouchableOpacity>

                      <TouchableOpacity onPress={() => setAuthMode('login')} style={s.secondaryCta}>
                        <Text style={s.secondaryCtaText}>I already have an account · Log in</Text>
                      </TouchableOpacity>

                      <View style={s.divider}>
                        <View style={s.dividerLine} />
                        <Text style={s.dividerText}>or</Text>
                        <View style={s.dividerLine} />
                      </View>

                      <TouchableOpacity onPress={googleLogin} style={s.googleBtn} activeOpacity={0.85}>
                        <View style={s.googleIconBox}>
                          <Text style={{ fontSize: 16, fontWeight: '900', color: '#4285F4' }}>G</Text>
                        </View>
                        <Text style={s.googleText}>Continue with Google</Text>
                      </TouchableOpacity>
                    </>
                  ) : (
                    <>
                      <TouchableOpacity onPress={() => setAuthMode(null)} style={s.backBtn}>
                        <Ionicons name="arrow-back" size={16} color="#A78BFA" />
                        <Text style={s.backBtnText}>Back</Text>
                      </TouchableOpacity>
                      <Text style={s.cardHeading}>{authMode === 'login' ? 'Welcome back' : 'Create your account'}</Text>
                      <Text style={s.cardSubheading}>
                        {authMode === 'login' ? 'Log in to continue creating' : 'Sign up · get 300 free credits'}
                      </Text>

                      {authMode === 'login' && (
                        <View style={{ marginBottom: 12 }}>
                          <AccountDropdown value={accountId} onPick={onPickAccount} />
                        </View>
                      )}

                      {authMode === 'register' && (
                        <View style={s.inputWrap}>
                          <Ionicons name="person-outline" size={16} color="#94A3B8" />
                          <TextInput style={s.input} placeholder="Name (optional)" placeholderTextColor="#64748B" value={name} onChangeText={setName} />
                        </View>
                      )}
                      <View style={s.inputWrap}>
                        <Ionicons name="mail-outline" size={16} color="#94A3B8" />
                        <TextInput
                          style={s.input} placeholder="Email" placeholderTextColor="#64748B"
                          keyboardType="email-address" autoCapitalize="none"
                          value={email}
                          onChangeText={(v) => { setEmail(v); if (accountId !== 'custom') setAccountId('custom'); }}
                        />
                      </View>
                      <View style={s.inputWrap}>
                        <Ionicons name="lock-closed-outline" size={16} color="#94A3B8" />
                        <TextInput style={s.input} placeholder="Password" placeholderTextColor="#64748B" secureTextEntry value={password} onChangeText={setPassword} />
                      </View>

                      {authMode === 'register' && (
                        <View style={{ marginTop: 10 }}>
                          <Text style={{ color: '#CBD5E1', fontSize: 12, fontWeight: '700', marginBottom: 8, letterSpacing: 0.3 }}>
                            CHOOSE YOUR PLAN
                          </Text>
                          <View style={{ gap: 8 }}>
                            {[
                              { id: 'free' as const,    label: 'Free',    price: '₹0',   desc: '3 templates/day · watermark', tag: null },
                              { id: 'starter' as const, label: 'Starter', price: '₹299', desc: '30 reels/mo · 5 lip sync · no watermark', tag: null },
                              { id: 'creator' as const, label: 'Creator', price: '₹499', desc: '60 reels · 15 lip sync · 3 AI videos · multi-shot', tag: 'Popular' },
                              { id: 'pro' as const,     label: 'Pro',     price: '₹899', desc: 'Unlimited reels · 8 AI videos · 4-shot multi', tag: null },
                            ].map(pl => {
                              const active = signupPlan === pl.id;
                              return (
                                <TouchableOpacity
                                  key={pl.id}
                                  onPress={() => setSignupPlan(pl.id)}
                                  activeOpacity={0.85}
                                  style={{
                                    flexDirection: 'row', alignItems: 'center', gap: 10,
                                    paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10,
                                    borderWidth: 1.5, borderColor: active ? '#FBBF24' : 'rgba(255,255,255,0.12)',
                                    backgroundColor: active ? 'rgba(251,191,36,0.12)' : 'rgba(255,255,255,0.04)',
                                  }}
                                >
                                  <View style={{
                                    width: 18, height: 18, borderRadius: 9, borderWidth: 2,
                                    borderColor: active ? '#FBBF24' : '#475569',
                                    alignItems: 'center', justifyContent: 'center',
                                  }}>
                                    {active && <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: '#FBBF24' }} />}
                                  </View>
                                  <View style={{ flex: 1 }}>
                                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                                      <Text style={{ color: '#fff', fontSize: 13, fontWeight: '800' }}>{pl.label}</Text>
                                      {pl.tag && (
                                        <View style={{ paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4, backgroundColor: 'rgba(236,72,153,0.25)', borderWidth: 1, borderColor: 'rgba(236,72,153,0.6)' }}>
                                          <Text style={{ color: '#F9A8D4', fontSize: 8, fontWeight: '800' }}>{pl.tag.toUpperCase()}</Text>
                                        </View>
                                      )}
                                      <Text style={{ color: active ? '#FBBF24' : '#94A3B8', fontSize: 12, fontWeight: '800', marginLeft: 'auto' }}>{pl.price}</Text>
                                    </View>
                                    <Text style={{ color: '#94A3B8', fontSize: 11, marginTop: 2 }}>{pl.desc}</Text>
                                  </View>
                                </TouchableOpacity>
                              );
                            })}
                          </View>
                        </View>
                      )}

                      <TouchableOpacity onPress={submit} disabled={busy} activeOpacity={0.85} style={{ marginTop: 6 }}>
                        <LinearGradient colors={['#FF6B08', '#FF007F', '#AE29FF']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={s.primaryCta}>
                          {busy ? <ActivityIndicator color="#fff" /> : (
                            <>
                              <Text style={s.primaryCtaText}>{authMode === 'login' ? 'Log in' : 'Sign up'}</Text>
                              <Ionicons name="arrow-forward" size={18} color="#fff" />
                            </>
                          )}
                        </LinearGradient>
                      </TouchableOpacity>

                      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 14 }}>
                        <Text style={s.switchText}>
                          {authMode === 'login' ? 'New here?' : 'Already have an account?'}
                        </Text>
                        <Pressable onPress={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
                          <Text style={s.switchTextLink}>
                            {authMode === 'login' ? 'Create account' : 'Log in'}
                          </Text>
                        </Pressable>
                      </View>

                      <View style={s.divider}>
                        <View style={s.dividerLine} />
                        <Text style={s.dividerText}>or</Text>
                        <View style={s.dividerLine} />
                      </View>

                      <TouchableOpacity onPress={googleLogin} style={s.googleBtn} activeOpacity={0.85}>
                        <View style={s.googleIconBox}>
                          <Text style={{ fontSize: 16, fontWeight: '900', color: '#4285F4' }}>G</Text>
                        </View>
                        <Text style={s.googleText}>Continue with Google</Text>
                      </TouchableOpacity>
                    </>
                  )}
                </View>
              </BlurView>
            </View>

            {/* Feature chip strip */}
            <View style={s.featureChipRow}>
              {FEATURES.slice(0, 4).map(f => (
                <View key={f.title} style={s.featureChip}>
                  <Text style={{ fontSize: 16 }}>{f.icon}</Text>
                  <Text style={s.featureChipText}>{f.title}</Text>
                </View>
              ))}
            </View>

            {/* Footer */}
            <View style={s.footer}>
              <Pressable onPress={() => Linking.openURL('https://example.com/terms')}>
                <Text style={s.footerLink}>Terms</Text>
              </Pressable>
              <Text style={s.footerDot}>·</Text>
              <Pressable onPress={() => Linking.openURL('https://example.com/privacy')}>
                <Text style={s.footerLink}>Privacy</Text>
              </Pressable>
              <Text style={s.footerDot}>·</Text>
              <Text style={s.footerVersion}>v1.0-beta</Text>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </AuroraBackground>
  );
}

/* ============================== Styles ============================== */
const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0A0118' },
  scroll: { flexGrow: 1, paddingHorizontal: 18, paddingBottom: 40, alignItems: 'center' },
  orb: {
    position: 'absolute',
    width: 260, height: 260, borderRadius: 200,
    opacity: 0.3,
    ...Platform.select({
      web: { filter: 'blur(80px)' as any },
      default: { shadowColor: '#fff', shadowOpacity: 0.9, shadowRadius: 80, shadowOffset: { width: 0, height: 0 } },
    }),
  },

  betaChipRow: { alignItems: 'center', marginTop: 4, marginBottom: 12 },
  betaChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 4, backgroundColor: 'rgba(251,191,36,0.12)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(251,191,36,0.35)' },
  betaDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#FBBF24' },
  betaChipText: { color: '#FBBF24', fontSize: 10, fontWeight: '800', letterSpacing: 1 },

  hero: { alignItems: 'center', marginTop: 8, marginBottom: 16 },
  tagline: { color: '#fff', fontSize: 18, fontWeight: '700', marginTop: 14, textAlign: 'center', maxWidth: 320, lineHeight: 24 },
  subtext: { color: '#94A3B8', fontSize: 13, marginTop: 6, textAlign: 'center' },

  /* Carousel */
  carousel: { width: '100%', maxWidth: 440, alignItems: 'center', marginTop: 4, marginBottom: 18 },
  carouselCard: {
    width: '100%', padding: 18,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 18, borderWidth: 1,
    alignItems: 'center', gap: 8,
    ...Platform.select({
      web: { backdropFilter: 'blur(10px)' as any },
      default: {},
    }),
  },
  carouselIconBox: { width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5 },
  carouselTitle: { color: '#fff', fontSize: 17, fontWeight: '800', marginTop: 4 },
  carouselDesc: { color: '#94A3B8', fontSize: 13, textAlign: 'center' },
  dotRow: { flexDirection: 'row', gap: 6, marginTop: 12 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.25)' },

  /* Glass card */
  cardWrap: { borderRadius: 22, overflow: 'hidden', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)', width: '100%', maxWidth: 440 },
  cardBlur: { borderRadius: 22 },
  card: { padding: 20, backgroundColor: 'rgba(15,23,42,0.35)' },
  cardHeading: { color: '#fff', fontSize: 22, fontWeight: '800', marginBottom: 4 },
  cardSubheading: { color: '#94A3B8', fontSize: 13, marginBottom: 16 },

  /* CTA */
  primaryCta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 15, borderRadius: 14 },
  primaryCtaText: { color: '#fff', fontSize: 16, fontWeight: '800', letterSpacing: 0.5 },
  secondaryCta: { marginTop: 12, paddingVertical: 14, borderRadius: 14, alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)' },
  secondaryCtaText: { color: '#A78BFA', fontSize: 14, fontWeight: '700' },

  divider: { flexDirection: 'row', alignItems: 'center', gap: 10, marginVertical: 16 },
  dividerLine: { flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.1)' },
  dividerText: { color: '#64748B', fontSize: 11, fontWeight: '600' },

  googleBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, paddingVertical: 13, borderRadius: 14, backgroundColor: '#fff' },
  googleIconBox: { width: 22, height: 22, borderRadius: 4, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  googleText: { color: '#0A0118', fontSize: 14, fontWeight: '700' },

  /* Inputs */
  inputWrap: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 12, paddingHorizontal: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)', marginBottom: 10 },
  input: { flex: 1, color: '#fff', paddingVertical: 12, fontSize: 14, outlineWidth: 0 as any },

  /* Dropdown */
  ddTrigger: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12 },
  ddIcon: { fontSize: 20 },
  ddLabel: { color: '#fff', fontSize: 14, fontWeight: '700' },
  ddSub: { color: '#94A3B8', fontSize: 11, marginTop: 2 },
  ddMenu: { marginTop: 6, backgroundColor: '#1E1B35', borderRadius: 12, padding: 4, borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)', ...Platform.select({ web: { boxShadow: '0 10px 30px rgba(0,0,0,0.4)' as any }, default: { shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 18, shadowOffset: { width: 0, height: 6 } } }) },
  ddItem: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8 },
  ddItemActive: { backgroundColor: 'rgba(139,92,246,0.15)' },
  credChip: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, borderWidth: 1 },
  credChipText: { fontSize: 11, fontWeight: '800' },

  /* Back */
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', marginBottom: 8 },
  backBtnText: { color: '#A78BFA', fontSize: 13, fontWeight: '700' },

  switchText: { color: '#94A3B8', fontSize: 13 },
  switchTextLink: { color: '#A78BFA', fontSize: 13, fontWeight: '800' },

  /* Feature chip strip below card */
  featureChipRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 8, marginTop: 20, maxWidth: 440 },
  featureChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: 20, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  featureChipText: { color: '#E5E7EB', fontSize: 12, fontWeight: '600' },

  /* Footer */
  footer: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 22, justifyContent: 'center' },
  footerLink: { color: '#64748B', fontSize: 12, fontWeight: '600' },
  footerDot: { color: '#475569', fontSize: 12 },
  footerVersion: { color: '#64748B', fontSize: 12 },
});
