import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { router } from 'expo-router';
import { Alert } from 'react-native';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const TOKEN_KEY = 'magicai_jwt_v1';

// Axios 401 interceptor — on any backend 401/403 response while browsing
// *generate* endpoints, bounce the guest to /login with a toast. This is the
// primary guest-gating mechanism per user feedback: "guest can browse but
// any generate action must force login".
let _interceptor_installed = false;
function installAuthInterceptor(getToken: () => string | null) {
  if (_interceptor_installed) return;
  _interceptor_installed = true;
  axios.interceptors.response.use(
    (r) => r,
    (err) => {
      try {
        const status = err?.response?.status;
        const url: string = err?.config?.url || '';
        const method: string = (err?.config?.method || 'get').toUpperCase();
        // Only fire guest-gate on POST/PUT generate endpoints — GET should never force login.
        const isGenerate =
          method !== 'GET' &&
          /\/api\/(create-|generate-|divine-transform|story\/create|template-remix|render|upload-)/i.test(url);
        if ((status === 401) && isGenerate && !getToken()) {
          Alert.alert(
            'Login required',
            'Please log in or create an account to use this feature.',
            [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Log in', onPress: () => router.push('/login') },
            ],
          );
        }
      } catch {}
      return Promise.reject(err);
    },
  );
}

/** Batch 3: call from any generation tile's onPress to show login popup for guests.
 * Returns true if the user may proceed, false if blocked (popup shown).
 */
export function requireAuth(user: any, opts?: { feature?: string }): boolean {
  if (user) return true;
  const featureMsg = opts?.feature ? `You need an account to use ${opts.feature}.` : 'You need an account to use this feature.';
  Alert.alert(
    '🔒 Login required',
    `${featureMsg}\n\nCreate a free account in seconds — Free plan includes 3 templates per day.`,
    [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Log in', onPress: () => router.push({ pathname: '/login', params: { mode: 'login' } as any }) },
      { text: 'Sign up', onPress: () => router.push({ pathname: '/login', params: { mode: 'register' } as any }) },
    ],
  );
  return false;
}

export type User = {
  id: string;
  email: string;
  name?: string;
  subscription_tier: 'free' | 'starter' | 'pro';
  credits_balance: number;
  daily_usage: number;
  daily_usage_date?: string | null;
  is_admin: boolean;
  env?: string;
};

export type Mode = { env: string; is_beta: boolean; is_dev: boolean; is_prod: boolean; version: string };

type AuthCtx = {
  user: User | null;
  token: string | null;
  mode: Mode | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string, plan?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    // Install global 401 interceptor ONCE — guards against guests hitting generate endpoints.
    installAuthInterceptor(() => token);
    // Ultra safety: flip loading to false quickly so app is never stuck.
    // Auth bootstrap proceeds in background and updates state when complete.
    const safety = setTimeout(() => { if (active) setLoading(false); }, 3500);
    (async () => {
      try {
        const m = await axios.get(`${BACKEND_URL}/api/mode`, { timeout: 6000 });
        if (active) setMode(m.data);
      } catch (e) {}
      try {
        const t = await AsyncStorage.getItem(TOKEN_KEY);
        if (t) {
          if (active) setToken(t);
          axios.defaults.headers.common['Authorization'] = `Bearer ${t}`;
          const r = await axios.get(`${BACKEND_URL}/api/auth/me`, { headers: { Authorization: `Bearer ${t}` }, timeout: 6000 });
          if (active) setUser(r.data.user);
        }
      } catch (e) {
        await AsyncStorage.removeItem(TOKEN_KEY);
        delete axios.defaults.headers.common['Authorization'];
      } finally {
        if (active) setLoading(false);
        clearTimeout(safety);
      }
    })();
    return () => { active = false; clearTimeout(safety); };
  }, []);

  const login = async (email: string, password: string) => {
    const r = await axios.post(`${BACKEND_URL}/api/auth/login`, { email, password });
    setToken(r.data.token);
    setUser(r.data.user);
    await AsyncStorage.setItem(TOKEN_KEY, r.data.token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${r.data.token}`;
  };
  const register = async (email: string, password: string, name?: string, plan: string = 'free') => {
    const r = await axios.post(`${BACKEND_URL}/api/auth/register`, { email, password, name: name || '', plan });
    setToken(r.data.token);
    setUser(r.data.user);
    await AsyncStorage.setItem(TOKEN_KEY, r.data.token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${r.data.token}`;
  };
  const logout = async () => {
    setToken(null); setUser(null);
    await AsyncStorage.removeItem(TOKEN_KEY);
    delete axios.defaults.headers.common['Authorization'];
  };
  const refresh = async () => {
    if (!token) return;
    try {
      const r = await axios.get(`${BACKEND_URL}/api/subscription/balance`, { headers: { Authorization: `Bearer ${token}` } });
      setUser((prev) => prev ? { ...prev, credits_balance: r.data.credits_balance, daily_usage: r.data.daily_used, subscription_tier: r.data.subscription_tier } : prev);
    } catch (e) {}
  };

  return <Ctx.Provider value={{ user, token, mode, loading, login, register, logout, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth must be inside AuthProvider');
  return c;
}
