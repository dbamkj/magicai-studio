/**
 * Profile screen — Premium Neon Glass UI redesign.
 * User info, plan, credits, settings shortcuts, sign out.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert, Platform, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Audio } from 'expo-av';
import { useAuth } from '../src/AuthContext';
import { useTheme } from '../src/ThemeContext';
import AuroraBackground from '../src/AuroraBackground';
import BottomTabBar from '../src/components/BottomTabBar';
import MagicAiLogo from '../src/MagicAiLogo';
import BrandLogo from '../src/BrandLogo';
import { brandGradient, glass, text as txt, radius, space } from '../src/theme';
import { colors as nc, spacing as ns } from '../src/ui/theme';
import { GlassCard as NeonGlass, NeonButton, GlassPill } from '../src/ui/Glass';
import { APP_SOUNDS_KEY } from './_layout';

// Tier visual treatment — drives the hero badge color + gradient ring
const TIER_VIS: Record<string, { label: string; color: string; gradient: readonly [string, string, ...string[]]; icon: keyof typeof Ionicons.glyphMap }> = {
  guest:   { label: 'GUEST',   color: '#94A3B8', gradient: ['#475569', '#334155'] as const, icon: 'person-outline' },
  free:    { label: 'FREE',    color: '#10B981', gradient: ['#10B981', '#059669'] as const, icon: 'flash' },
  starter: { label: 'STARTER', color: '#3B82F6', gradient: ['#3B82F6', '#1D4ED8'] as const, icon: 'rocket' },
  creator: { label: 'CREATOR', color: '#A78BFA', gradient: ['#A78BFA', '#7C3AED'] as const, icon: 'sparkles' },
  pro:     { label: 'PRO',     color: '#FBBF24', gradient: ['#FBBF24', '#F97316'] as const, icon: 'diamond' },
};

export default function ProfileScreen() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { mode: themeMode, isDark, setMode: setThemeMode, colors: tc } = useTheme();
  // Theme-aware text color overrides (used inline below to avoid full restyle).
  const titleColor = isDark ? '#FFFFFF' : '#0F0C29';
  const labelColor = isDark ? '#FFFFFF' : '#0F0C29';
  const subColor   = isDark ? '#94A3B8' : '#64748B';

  // ---- App Sounds toggle ----
  const [soundsOn, setSoundsOn] = useState<boolean>(false);
  useEffect(() => {
    (async () => {
      try {
        const v = await AsyncStorage.getItem(APP_SOUNDS_KEY);
        setSoundsOn(v === '1');
      } catch {}
    })();
  }, []);

  const toggleSounds = async (next: boolean) => {
    setSoundsOn(next);
    try { await AsyncStorage.setItem(APP_SOUNDS_KEY, next ? '1' : '0'); } catch {}
    // Play a quick preview chime when turning ON, so user knows what to expect
    if (next) {
      try {
        await Audio.setAudioModeAsync({ playsInSilentModeIOS: false, shouldDuckAndroid: true });
        const { sound } = await Audio.Sound.createAsync(
          require('../assets/sounds/splash_chime.mp3'),
          { volume: 0.55, shouldPlay: true },
        );
        setTimeout(() => { sound.unloadAsync().catch(() => {}); }, 1700);
      } catch {}
    }
  };

  // For guests (no user logged in), show "GUEST" tier instead of "FREE"
  const tier = user
    ? (user.subscription_tier || 'free').toLowerCase()
    : 'guest';
  const tierLabel = tier === 'free' ? 'Free' : tier.charAt(0).toUpperCase() + tier.slice(1);
  const credits = (user as any)?.credits_balance ?? 0;

  const handleSignOut = () => {
    Alert.alert('Sign out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: async () => {
        try { await logout?.(); } catch {}
        router.replace('/login');
      }},
    ]);
  };

  return (
    <AuroraBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
          {/* Header: title + neon highlight */}
          <View style={s.titleRow}>
            <Text style={[s.title, { color: titleColor }]}>Profile</Text>
            <Text style={s.titleAccent}>·</Text>
            <Text style={s.titleTag}>{(TIER_VIS[tier] || TIER_VIS.free).label}</Text>
          </View>

          {/* HERO USER CARD — gradient ring around avatar, tier badge */}
          <NeonGlass style={s.heroCard} radius={24} borderHi glow="purple">
            <View style={s.heroRow}>
              <View style={s.avatarRing}>
                {/* Hide the colorful tier-ring entirely for guests so the
                    splash/profile looks clean (no "outer rectangle box"). */}
                {tier !== 'guest' && (
                  <LinearGradient
                    colors={(TIER_VIS[tier] || TIER_VIS.free).gradient as any}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                    style={StyleSheet.absoluteFill}
                  />
                )}
                <View style={s.avatar}>
                  <BrandLogo size="lg" glyphOnly />
                </View>
              </View>
              <View style={{ flex: 1, marginLeft: 14 }}>
                {user ? (
                  <>
                    <Text style={[s.userName, { color: titleColor }]} numberOfLines={1}>{user.name || user.email?.split('@')[0] || 'You'}</Text>
                    <Text style={[s.userEmail, { color: subColor }]} numberOfLines={1}>{user.email}</Text>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 }}>
                      <GlassPill bg={`${(TIER_VIS[tier] || TIER_VIS.free).color}22`} border={`${(TIER_VIS[tier] || TIER_VIS.free).color}55`}>
                        <Ionicons name={(TIER_VIS[tier] || TIER_VIS.free).icon} size={10} color={(TIER_VIS[tier] || TIER_VIS.free).color} />
                        <Text style={{ color: (TIER_VIS[tier] || TIER_VIS.free).color, fontSize: 10, fontWeight: '900', letterSpacing: 0.5 }}>{(TIER_VIS[tier] || TIER_VIS.free).label}</Text>
                      </GlassPill>
                      <GlassPill>
                        <Ionicons name="flash" size={10} color="#FBBF24" />
                        <Text style={{ color: '#fff', fontSize: 11, fontWeight: '800' }}>{credits}</Text>
                      </GlassPill>
                    </View>
                  </>
                ) : (
                  <>
                    <Text style={s.userName}>Guest</Text>
                    <Text style={s.userEmail}>Sign in to sync your projects</Text>
                  </>
                )}
              </View>
              {!user && (
                <TouchableOpacity onPress={() => router.push('/login')} style={s.loginBtn}>
                  <Text style={s.loginBtnTxt}>Log in</Text>
                </TouchableOpacity>
              )}
            </View>
          </NeonGlass>

          {/* Upgrade CTA — only for logged-in Free tier (not guests) */}
          {tier === 'free' && (
            <TouchableOpacity activeOpacity={0.85} onPress={() => router.push('/buy?tab=tier' as any)} style={s.upgradeWrap}>
              <LinearGradient
                colors={['#FF6B08', '#FF007F', '#AE29FF']}
                start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
                style={s.upgrade}
              >
                <Ionicons name="rocket" size={16} color="#fff" />
                <Text style={s.upgradeTxt}>Upgrade · Unlock HD &amp; remove watermark</Text>
                <Ionicons name="arrow-forward" size={14} color="#fff" />
              </LinearGradient>
            </TouchableOpacity>
          )}

          {/* Menu */}
          <Text style={[s.sectionTitle, { color: subColor }]}>Account</Text>
          <MenuItem icon="card" label="Buy Credits" labelColor={labelColor} onPress={() => router.push('/buy' as any)} />
          <MenuItem icon="diamond" label="Subscription &amp; Plans" labelColor={labelColor} onPress={() => router.push('/subscription' as any)} />
          <MenuItem icon="folder" label="My Projects" labelColor={labelColor} onPress={() => router.push('/projects' as any)} />

          <Text style={[s.sectionTitle, { color: subColor }]}>Preferences</Text>
          {/* Theme mode segmented control (Light / Dark / System) */}
          <View style={s.toggleRow}>
            <View style={s.menuIcon}>
              <Ionicons name={isDark ? 'moon' : 'sunny'} size={16} color={isDark ? '#A78BFA' : '#FBBF24'} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[s.menuLabel, { color: labelColor }]}>Appearance</Text>
              <Text style={[s.toggleHint, { color: subColor }]}>
                {themeMode === 'system' ? 'Follows your device setting' : isDark ? 'Dark theme · Aurora glass' : 'Light theme · Pastel glass'}
              </Text>
            </View>
            <View style={s.themeSegmented}>
              {(['light', 'dark', 'system'] as const).map((opt) => {
                const active = themeMode === opt;
                return (
                  <TouchableOpacity
                    key={opt}
                    onPress={() => setThemeMode(opt)}
                    style={[s.themeSegBtn, active && s.themeSegBtnActive]}
                    activeOpacity={0.8}
                  >
                    <Ionicons
                      name={opt === 'light' ? 'sunny' : opt === 'dark' ? 'moon' : 'phone-portrait'}
                      size={12}
                      color={active ? '#0B1120' : '#94A3B8'}
                    />
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          <View style={s.toggleRow}>
            <View style={s.menuIcon}>
              <Ionicons name="musical-notes" size={16} color={txt.secondary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[s.menuLabel, { color: labelColor }]}>App Sounds</Text>
              <Text style={[s.toggleHint, { color: subColor }]}>
                Splash chime &amp; subtle UI feedback
              </Text>
            </View>
            <Switch
              value={soundsOn}
              onValueChange={toggleSounds}
              trackColor={{ false: '#1E293B', true: '#7B5CFF' }}
              thumbColor={soundsOn ? '#FBBF24' : '#94A3B8'}
              ios_backgroundColor="#1E293B"
            />
          </View>

          <Text style={[s.sectionTitle, { color: subColor }]}>Support &amp; Legal</Text>
          <MenuItem icon="document-text" label="Terms of Service" labelColor={labelColor} onPress={() => router.push('/legal?doc=terms' as any)} />
          <MenuItem icon="shield-checkmark" label="Privacy Policy" labelColor={labelColor} onPress={() => router.push('/legal?doc=privacy' as any)} />
          <MenuItem icon="mail" label="Contact" labelColor={labelColor} onPress={() => router.push('/legal?doc=contact' as any)} />

          {!!user && (
            <TouchableOpacity onPress={handleSignOut} style={s.signOutBtn} activeOpacity={0.85}>
              <Ionicons name="log-out-outline" size={16} color="#F87171" />
              <Text style={s.signOutTxt}>Sign out</Text>
            </TouchableOpacity>
          )}

          <Text style={s.version}>MagiCAi Studio · v1.0-beta</Text>
        </ScrollView>
      </SafeAreaView>
      <BottomTabBar active="profile" />
    </AuroraBackground>
  );
}

/* ============ Sub-components ============ */
function MenuItem({ icon, label, onPress, labelColor }: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void; labelColor?: string }) {
  return (
    <TouchableOpacity activeOpacity={0.7} onPress={onPress} style={s.menuItem}>
      <View style={s.menuIcon}>
        <Ionicons name={icon} size={16} color={txt.secondary} />
      </View>
      <Text style={[s.menuLabel, labelColor ? { color: labelColor } : null]}>{label}</Text>
      <Ionicons name="chevron-forward" size={16} color={txt.muted} />
    </TouchableOpacity>
  );
}

/* ============ Styles ============ */
const s = StyleSheet.create({
  scroll: { padding: space.md, paddingBottom: 120 },

  // Title row with neon highlight
  titleRow: { flexDirection: 'row', alignItems: 'baseline', marginBottom: 14 },
  title: { color: txt.primary, fontSize: 28, fontWeight: '900', letterSpacing: -0.3 },
  titleAccent: { color: '#FBBF24', fontSize: 28, fontWeight: '900', marginHorizontal: 6 },
  titleTag: { color: '#FBBF24', fontSize: 12, fontWeight: '900', letterSpacing: 1.2 },

  // Hero user card
  heroCard: { marginBottom: 14 },
  heroRow: { flexDirection: 'row', alignItems: 'center' },
  avatarRing: {
    width: 68, height: 68, borderRadius: 34,
    overflow: 'hidden',
    alignItems: 'center', justifyContent: 'center',
    padding: 3,
  },
  avatar: {
    width: 62, height: 62, borderRadius: 31,
    backgroundColor: '#0B1120',
    alignItems: 'center', justifyContent: 'center',
  },
  userName: { color: txt.primary, fontSize: 18, fontWeight: '800' },
  userEmail: { color: txt.muted, fontSize: 12, marginTop: 2 },

  loginBtn: {
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 999, backgroundColor: '#7B5CFF',
  },
  loginBtnTxt: { color: '#fff', fontWeight: '800', fontSize: 12 },

  upgradeWrap: {
    marginTop: 4, marginBottom: 4, borderRadius: 999, overflow: 'hidden',
    shadowColor: '#FF6B08', shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5, shadowRadius: 14, elevation: 10,
  },
  upgrade: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14, paddingHorizontal: 16,
  },
  upgradeTxt: { color: '#fff', fontWeight: '900', fontSize: 13, letterSpacing: 0.3, flex: 1 },

  sectionTitle: {
    color: txt.muted, fontSize: 11, fontWeight: '700',
    letterSpacing: 0.6, textTransform: 'uppercase',
    marginTop: 22, marginBottom: 10, paddingHorizontal: 4,
  },
  menuItem: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 14, paddingHorizontal: 14,
    backgroundColor: glass.background,
    borderWidth: 1, borderColor: glass.border,
    borderRadius: radius.md, marginBottom: 8,
  },
  menuIcon: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center', justifyContent: 'center',
  },
  menuLabel: { flex: 1, color: txt.primary, fontSize: 14, fontWeight: '600' },

  toggleRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 12, paddingHorizontal: 14,
    backgroundColor: glass.background,
    borderWidth: 1, borderColor: glass.border,
    borderRadius: radius.md, marginBottom: 8,
  },
  toggleHint: {
    color: txt.muted, fontSize: 11, marginTop: 2,
  },

  // Theme mode segmented control (Light / Dark / System)
  themeSegmented: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
    borderRadius: 999, padding: 3, gap: 2,
  },
  themeSegBtn: {
    width: 30, height: 24, borderRadius: 999,
    alignItems: 'center', justifyContent: 'center',
  },
  themeSegBtnActive: { backgroundColor: '#FBBF24' },

  signOutBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, marginTop: 18, paddingVertical: 12,
    borderRadius: radius.md, borderWidth: 1, borderColor: 'rgba(248,113,113,0.30)',
    backgroundColor: 'rgba(248,113,113,0.08)',
  },
  signOutTxt: { color: '#F87171', fontWeight: '800', fontSize: 13 },

  version: { color: txt.faint, fontSize: 10, textAlign: 'center', marginTop: 18, letterSpacing: 0.4 },
});
