/**
 * useMyLimits — fetches GET /api/me/limits and exposes:
 *   { limits, loading, error, refetch }
 *
 * Powers the Credits / Subscription screen's progress bars + upsell banners
 * + per-feature lock badges. See backend/routes/account.py:me_limits.
 */
import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export type UsageBar = {
  used: number;
  cap: number;
  unlimited: boolean;
  pct: number;
  exhausted: boolean;
};

export type FeatureGates = {
  face_swap: boolean;
  lip_sync: boolean;
  head_swap: boolean;
  body_swap: boolean;
  video_to_video: boolean;
  divine: boolean;
  ai_bg_lipsync: boolean;
  multishot: boolean;
  ai_video: boolean;
  video_studio: boolean;
  video_cinematic: boolean;
  image_cinematic: boolean;
};

export type UpgradeHint = {
  icon: string;
  text: string;
  cta: string;
  target_tier: 'starter' | 'creator' | 'pro';
};

export type MyLimits = {
  tier: {
    id: 'free' | 'starter' | 'creator' | 'pro';
    label: string;
    price_inr: number;
    max_resolution: string;
    watermark: boolean;
  };
  credits: { balance: number; monthly_grant: number };
  usage_this_month: {
    month: string;
    reels: UsageBar;
    lipsync: UsageBar;
    ai_videos: UsageBar;
    images: UsageBar;
  };
  usage_today: { date: string; images: UsageBar };
  feature_gates: FeatureGates;
  upgrade_hints: UpgradeHint[];
};

export function useMyLimits() {
  const { token } = useAuth();
  const [limits, setLimits] = useState<MyLimits | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOnce = useCallback(async () => {
    if (!token) {
      setLimits(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/me/limits`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 8000,
      });
      setLimits(r.data as MyLimits);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load limits');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchOnce();
  }, [fetchOnce]);

  return { limits, loading, error, refetch: fetchOnce };
}
