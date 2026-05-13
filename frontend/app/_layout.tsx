import React, { useEffect, useState } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { View, StyleSheet, Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useFonts } from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import { AuthProvider, useAuth } from '../src/AuthContext';
import { ThemeProvider } from '../src/ThemeContext';
import BetaChrome from '../src/BetaChrome';
import { usePushNotifications } from '../src/usePushNotifications';
import AnimatedSplash from '../src/AnimatedSplash';

export const APP_SOUNDS_KEY = 'magicai.appSoundsEnabled';
const ONBOARD_KEY = 'magicai.onboarded';

// Routes that are always accessible (no auth required), even in BETA mode
const PUBLIC_ROUTES = new Set(['login', 'onboarding']);

function RouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const segments = useSegments();
  const { user, mode, loading } = useAuth();
  const [onboarded, setOnboarded] = useState<boolean | null>(null);

  // Check onboarding status once on mount
  useEffect(() => {
    (async () => {
      try {
        const v = await AsyncStorage.getItem(ONBOARD_KEY);
        setOnboarded(v === '1');
      } catch { setOnboarded(true); }  // be defensive — never block on storage error
    })();
  }, []);

  // Session 27g — register Expo push token once per login (mobile only; web is no-op)
  usePushNotifications(user?.id || null);

  useEffect(() => {
    if (loading || onboarded === null) return;
    const first = (segments[0] as string) || '';
    // First-run users see Onboarding before login.
    // Skip onboarding if already on it OR already on a public route AND user has been here.
    if (!onboarded && !user && first !== 'onboarding' && first !== 'login') {
      router.replace('/onboarding' as any);
      return;
    }
    // Guest-friendly landing — home is default. /login redirect for logged-in users.
    if (user && first === 'login') {
      router.replace('/');
    }
  }, [user, mode, segments, loading, onboarded]);

  return <>{children}</>;
}

export default function RootLayout() {
  // ---- Splash gate ----
  const [splashDone, setSplashDone] = useState(false);
  const [soundsEnabled, setSoundsEnabled] = useState<boolean | null>(null);

  // Pre-load Ionicons font BEFORE any screen renders.
  // This fixes the "ExpoFontLoader.loadAsync rejected — Font file for ionicons is empty"
  // crash that occurred when @expo/vector-icons tried to lazy-load Ionicons.ttf
  // mid-render on real Android devices.
  const [fontsLoaded, fontsError] = useFonts({
    ...Ionicons.font,
  });

  useEffect(() => {
    (async () => {
      try {
        const v = await AsyncStorage.getItem(APP_SOUNDS_KEY);
        setSoundsEnabled(v === '1');
      } catch {
        setSoundsEnabled(false);
      }
    })();
  }, []);

  // Block first paint until fonts are ready (or error — fall through after error so
  // users aren't stuck on a black screen if font network fetch fails).
  if (!fontsLoaded && !fontsError) {
    return (
      <SafeAreaProvider>
        <View style={{ flex: 1, backgroundColor: '#070314' }} />
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <AuthProvider>
          <RouteGuard>
            <BetaChrome>
              <Stack screenOptions={{ headerShown: false, animation: 'fade' }} />
            </BetaChrome>
          </RouteGuard>
          {!splashDone && soundsEnabled !== null && (
            <View style={StyleSheet.absoluteFill}>
              <AnimatedSplash onDone={() => setSplashDone(true)} playChime={!!soundsEnabled} />
            </View>
          )}
        </AuthProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
