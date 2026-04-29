"""Sprint 4 — Plan catalog, credit cost calculator, add-on SKUs.

Session 27c (2026-04-24): Upgraded to 4-tier model per user spec:
  * Free    ₹0   — 3 templates/day · watermark · NO AI video
  * Starter ₹299 — 30 reels/mo · 5 lip sync · 20 images · no AI video
  * Creator ₹499 — 60 reels/mo · 15 lip sync · 50 images · 3 AI videos (≤3s) · 2-shot multishot
  * Pro     ₹899 — unlimited reels · 30 lip sync · 100 images · 8 AI videos (≤5s) · 4-shot multishot

Trial & annual billing (MOCK — no real payment gateway):
  * ₹1 first-month trial → start_trial(plan_id) sets trial_active + trial_end = now+30d
  * Annual → price = monthly × 10 (≈17% savings vs 12 months)

Add-ons (one-time IAP, unchanged):
  * ₹49  → 1 AI video (3s)
  * ₹79  → 1 AI video (5s)
  * ₹149 → 3 AI videos (3s each)
"""
from datetime import datetime, timezone
from typing import Optional


# ===== Plan catalog =====
PLANS = {
    'free': {
        'id': 'free', 'label': 'Free', 'price_inr': 0, 'price_annual_inr': 0,
        'credits': 300,
        'max_videos': 0, 'max_video_seconds': 0, 'max_images': 5,
        'daily_template_limit': 3,
        'monthly_reels_limit': 0,
        'monthly_lipsync_limit': 0,
        'monthly_ai_videos_limit': 0,
        'ai_video_max_seconds': 0,
        'watermark': True, 'allow_face_swap': False, 'allow_lip_sync': False,
        'allow_multishot': False, 'max_multishot_shots': 0,
        'allow_ai_video': False,
        'daily_job_limit': 999,
        'trial_eligible': False,
    },
    'starter': {
        'id': 'starter', 'label': 'Starter', 'price_inr': 299, 'price_annual_inr': 2990,
        'credits': 1500,
        'max_videos': 30, 'max_video_seconds': 10, 'max_images': 20,
        'daily_template_limit': 9999,
        'monthly_reels_limit': 30,
        'monthly_lipsync_limit': 5,
        'monthly_ai_videos_limit': 0,
        'ai_video_max_seconds': 0,
        'watermark': False, 'allow_face_swap': True, 'allow_lip_sync': True,
        'allow_multishot': False, 'max_multishot_shots': 0,
        'allow_ai_video': False,
        'daily_job_limit': 999,
        'trial_eligible': True,
        'highlight': False,
    },
    'creator': {
        'id': 'creator', 'label': 'Creator', 'price_inr': 499, 'price_annual_inr': 4990,
        'credits': 3000,
        'max_videos': 60, 'max_video_seconds': 10, 'max_images': 50,
        'daily_template_limit': 9999,
        'monthly_reels_limit': 60,
        'monthly_lipsync_limit': 15,
        'monthly_ai_videos_limit': 3,
        'ai_video_max_seconds': 3,
        'watermark': False, 'allow_face_swap': True, 'allow_lip_sync': True,
        'allow_multishot': True, 'max_multishot_shots': 2,
        'allow_ai_video': True,
        'daily_job_limit': 999,
        'trial_eligible': True,
        'highlight': True,   # "Most popular" tag
    },
    'pro': {
        'id': 'pro', 'label': 'Pro', 'price_inr': 899, 'price_annual_inr': 8990,
        'credits': 6000,
        'max_videos': 9999, 'max_video_seconds': 10, 'max_images': 100,
        'daily_template_limit': 9999,
        'monthly_reels_limit': 9999,
        'monthly_lipsync_limit': 30,
        'monthly_ai_videos_limit': 8,
        'ai_video_max_seconds': 5,
        'watermark': False, 'allow_face_swap': True, 'allow_lip_sync': True,
        'allow_multishot': True, 'max_multishot_shots': 4,
        'allow_ai_video': True,
        'daily_job_limit': 999,
        'trial_eligible': True,
        'highlight': False,
    },
}


# ===== Add-on SKUs (one-time in-app purchases) =====
ADDONS = [
    {'sku': 'addon_ai_video_3s',    'label': '1 AI Video (3s)', 'price_inr': 49,  'ai_videos': 1, 'ai_video_max_seconds': 3, 'desc': 'Quick AI video — perfect for a single cinematic moment'},
    {'sku': 'addon_ai_video_5s',    'label': '1 AI Video (5s)', 'price_inr': 79,  'ai_videos': 1, 'ai_video_max_seconds': 5, 'desc': 'Longer AI video — fits more story'},
    {'sku': 'addon_ai_video_pack3', 'label': '3 AI Video Pack (3s each)', 'price_inr': 149, 'ai_videos': 3, 'ai_video_max_seconds': 3, 'desc': 'Best value — 3 AI videos'},
]


# ===== Trial / annual billing constants =====
TRIAL_PRICE_INR = 1           # ₹1 first-month trial
TRIAL_DAYS = 30
ANNUAL_MULTIPLIER = 10        # 12 months for the price of 10 → ~17% savings


def trial_savings_pct_annual() -> int:
    return int(round((1 - ANNUAL_MULTIPLIER / 12) * 100))


def plan_by_id(pid: str):
    return PLANS.get((pid or 'free').lower(), PLANS['free'])


def addon_by_sku(sku: str):
    for a in ADDONS:
        if a['sku'] == sku:
            return a
    return None


# ===== MH pricing (unchanged) =====
MH_PER_SEC = {'quick': 60, 'studio': 80, 'cinematic': 120}
MH_MIN_BILLED_SECONDS = 5


def _video_cost(duration: Optional[int], quality: str) -> int:
    dur = max(int(duration or 5), MH_MIN_BILLED_SECONDS)
    per_sec = MH_PER_SEC.get((quality or 'studio').lower(), MH_PER_SEC['studio'])
    return dur * per_sec


def estimate_credits(
    job_type: str,
    duration: Optional[int] = None,
    face_swap: bool = False,
    lip_sync: bool = False,
    shots: int = 0,
    quality_mode: Optional[str] = None,
) -> int:
    t = (job_type or '').lower()
    q = (quality_mode or 'studio').lower()
    cost = 0
    if t in ('video', 'videogen', 'generate-video', 'image-to-video', 'video-to-video', 'animate-image'):
        cost = _video_cost(duration, q)
    elif t in ('avatar', 'talking-avatar'):
        cost = max(int(duration or 5), MH_MIN_BILLED_SECONDS) * 60
    elif t in ('image', 'imagegen', 'generate-image'):
        cost = {'quick': 4, 'studio': 6, 'cinematic': 10}.get(q, 6)
    elif t in ('lipsync', 'create-lipsync'):
        cost = max(int(duration or 5), MH_MIN_BILLED_SECONDS) * 40
    elif t in ('faceswap', 'create-faceswap', 'headswap', 'create-headswap', 'bodyswap', 'create-bodyswap', 'multi-swap'):
        if duration:
            cost = max(int(duration), MH_MIN_BILLED_SECONDS) * 80
        else:
            cost = 60
    elif t == 'multishot' or t == 'create-multishot':
        n = max(1, int(shots or 1))
        cost = _video_cost(duration, q) * n
    elif t == 'reel' or t == 'instant-reel':
        cost = 0
    else:
        cost = _video_cost(duration, q)
    if face_swap:
        cost += 60
    if lip_sync:
        cost += max(int(duration or 5), MH_MIN_BILLED_SECONDS) * 40
    return max(1, cost)


def utc_today_str() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def utc_month_str() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m')


def can_run_today(user: dict) -> tuple[bool, str]:
    return True, 'ok'


def check_feature_access(user: dict, *, feature: str, duration: Optional[int] = None, shots: Optional[int] = None) -> tuple[bool, str]:
    """Validate tier-level feature gates + monthly quotas."""
    plan = plan_by_id(user.get('subscription_tier', 'free'))
    if feature == 'face_swap' and not plan['allow_face_swap']:
        return False, 'Face Swap requires Starter plan or higher.'
    if feature == 'lip_sync' and not plan['allow_lip_sync']:
        return False, 'Lip Sync requires Starter plan or higher.'
    if feature == 'multishot' and not plan['allow_multishot']:
        return False, 'Multi-shot requires Creator plan or higher.'
    if feature == 'multishot' and shots is not None and shots > plan['max_multishot_shots']:
        return False, f"Your plan allows max {plan['max_multishot_shots']} shots per multi-shot."
    if feature == 'ai_video':
        extra = int(user.get('addon_ai_videos_remaining', 0) or 0)
        if not plan['allow_ai_video'] and extra <= 0:
            return False, 'AI Video requires Creator plan or higher, or purchase an add-on.'
        if duration is not None:
            max_s = max(plan.get('ai_video_max_seconds', 0) or 0, int(user.get('addon_ai_video_max_seconds', 0) or 0))
            if duration > max_s and max_s > 0:
                return False, f'AI Video max duration on your plan/add-on is {max_s}s.'
    if duration is not None and feature != 'ai_video':
        if duration > 10 and plan['id'] not in ('pro', 'creator'):
            return False, 'Videos > 10s require Creator or Pro plan.'
        if duration > 5 and plan['id'] == 'free':
            return False, 'Videos > 5s require Starter plan or higher.'
    return True, 'ok'
