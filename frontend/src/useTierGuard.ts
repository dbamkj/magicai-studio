/* useTierGuard — Centralized subscription-tier authorization for MagiCAi tools.
 *
 * Single source of truth for the Plan Benefits Matrix declared in
 * /app/frontend/app/subscription.tsx.  Use this hook in any screen
 * that needs to gate a feature behind a subscription tier OR display
 * tier-aware option lists (e.g. resolution / duration dropdowns).
 *
 *   const tier = useTierGuard();
 *   if (!tier.requirePlan('creator', 'Talking Avatar')) return;  // shows upgrade alert
 *   const allowed = tier.allowedResolutions();                    // ['480p','720p','1080p']
 */
import { useCallback, useMemo } from 'react';
import { Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from './AuthContext';

export type PlanTier = 'free' | 'starter' | 'creator' | 'pro';

const TIER_RANK: Record<PlanTier, number> = {
  free: 0,
  starter: 1,
  creator: 2,
  pro: 3,
};

const TIER_LABEL: Record<PlanTier, string> = {
  free: 'Free',
  starter: 'Starter',
  creator: 'Creator',
  pro: 'Pro',
};

/* ───────────── Plan Benefits Matrix (sync with subscription.tsx) ───────────── */
const MAX_RESOLUTION: Record<PlanTier, '480p' | '720p' | '1080p' | '4K'> = {
  free:    '480p',
  starter: '720p',
  creator: '1080p',
  pro:     '4K',
};
const ALLOWED_RESOLUTIONS: Record<PlanTier, Array<'480p' | '720p' | '1080p' | '4K'>> = {
  free:    ['480p'],
  starter: ['480p', '720p'],
  creator: ['480p', '720p', '1080p'],
  pro:     ['480p', '720p', '1080p', '4K'],
};
const ALLOWED_DURATIONS: Record<PlanTier, number[]> = {
  free:    [5, 10, 15],
  starter: [5, 10, 15, 20],
  creator: [5, 10, 15, 20, 30],
  pro:     [5, 10, 15, 20, 30, 60],
};
const STORY_LENGTH_MAX: Record<PlanTier, number> = {
  free: 15, starter: 20, creator: 30, pro: 60,
};
const CONCURRENT_RENDERS: Record<PlanTier, number> = {
  free: 1, starter: 1, creator: 2, pro: 4,
};
const WATERMARK: Record<PlanTier, boolean> = {
  free: true, starter: false, creator: false, pro: false,
};

/* ───────────── Per-feature minimum tier ───────────── */
const FEATURE_MIN_TIER = {
  /* Generation tools */
  ai_video_gen:           'starter' as PlanTier,   // AI Video Gen (Kling/Veo)
  talking_avatar_lipsync: 'creator' as PlanTier,   // Avatar Talking Lip-sync — matrix row
  story_mode_30s:         'creator' as PlanTier,   // Smart-Plan stories > 20s
  motion_control:         'creator' as PlanTier,   // Motion Control (image → animated video) — Creator+ feature
  /* Output / quality */
  download_to_gallery:    'starter' as PlanTier,   // Asset download (mobile gallery)
  no_watermark:           'starter' as PlanTier,
  resolution_720p:        'starter' as PlanTier,
  resolution_1080p:       'creator' as PlanTier,
  resolution_4K:          'pro'     as PlanTier,
  /* Premium TTS */
  premium_tts:            'creator' as PlanTier,   // Gemini TTS (free → Edge-TTS)
  /* Templates */
  starter_templates:      'starter' as PlanTier,
  creator_templates:      'creator' as PlanTier,
  pro_templates:          'pro'     as PlanTier,
  /* Misc premium */
  priority_queue:         'creator' as PlanTier,
} as const;

export type FeatureKey = keyof typeof FEATURE_MIN_TIER;

export function useTierGuard() {
  const { user } = useAuth();
  const router = useRouter();

  const userTier: PlanTier = useMemo(() => {
    const t = (user?.subscription_tier || 'free').toLowerCase();
    return (['free', 'starter', 'creator', 'pro'].includes(t) ? t : 'free') as PlanTier;
  }, [user]);

  const userRank = TIER_RANK[userTier];

  const isAtLeast = useCallback(
    (min: PlanTier) => userRank >= TIER_RANK[min],
    [userRank],
  );

  /** Show a localized upgrade Alert and return false if the user is below the
   *  required tier. Otherwise return true.  Use the return value as a guard:
   *
   *    if (!tier.requirePlan('creator', 'Talking Avatar')) return;
   */
  const requirePlan = useCallback(
    (min: PlanTier, featureLabel: string): boolean => {
      if (TIER_RANK[userTier] >= TIER_RANK[min]) return true;
      Alert.alert(
        `${TIER_LABEL[min]} plan required`,
        `${featureLabel} is available on the ${TIER_LABEL[min]} plan and above. Upgrade to unlock this feature plus a lot more.`,
        [
          { text: 'Maybe later', style: 'cancel' },
          { text: 'View plans', onPress: () => router.push('/subscription' as any) },
        ],
      );
      return false;
    },
    [userTier, router],
  );

  /** Same as `requirePlan` but uses a feature key from FEATURE_MIN_TIER. */
  const requireFeature = useCallback(
    (key: FeatureKey, featureLabel: string): boolean => {
      const min = FEATURE_MIN_TIER[key];
      return requirePlan(min, featureLabel);
    },
    [requirePlan],
  );

  /** Quiet check (no alert) — useful for disabled UI states. */
  const canUseFeature = useCallback(
    (key: FeatureKey): boolean => isAtLeast(FEATURE_MIN_TIER[key]),
    [isAtLeast],
  );

  return {
    user,
    userTier,
    userTierLabel: TIER_LABEL[userTier],
    userRank,
    isFree: userTier === 'free',
    isAtLeast,
    requirePlan,
    requireFeature,
    canUseFeature,
    /* Dropdown helpers — pass to ResolutionPicker / duration chips */
    maxResolution: MAX_RESOLUTION[userTier],
    allowedResolutions: ALLOWED_RESOLUTIONS[userTier],
    allowedDurations: ALLOWED_DURATIONS[userTier],
    storyLengthMax: STORY_LENGTH_MAX[userTier],
    concurrentRenders: CONCURRENT_RENDERS[userTier],
    hasWatermark: WATERMARK[userTier],
    /* Constants for UI rendering (badge colors, labels) */
    TIER_LABEL,
    TIER_RANK,
    FEATURE_MIN_TIER,
  };
}

export default useTierGuard;
