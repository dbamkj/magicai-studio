"""Plan catalog, credit cost calculator, add-on SKUs, tier-gating helpers.

Session 27c (2026-04-24): 4-tier model.
Session 34   (2026-05-04): Corrected pricing to match your MH cost
  basis (₹1,350/mo = ₹0.135/credit). Added quality-mode gates,
  head/body/ai_bg_lipsync/divine/video_to_video feature gates, monthly
  quota enforcement, and a real `can_run_today`.

Tiers (revised prices match docs/PRICING_AND_LAUNCH_STRATEGY.md §1.1):
  * Free    ₹0       — 300 credits · watermark · 5 FLUX images/day · 3 templates/day
  * Starter ₹249     — 1,500 credits · 30 reels/mo · 5 lip syncs/mo
  * Creator ₹599     — 3,000 credits · 60 reels/mo · 15 lip syncs/mo · 3 AI videos/mo (≤3s) · Kling 2.5 Studio
  * Pro     ₹1,499   — 6,000 credits · unlimited reels · 30 lip syncs/mo · 8 AI videos/mo (≤5s) · Kling 3.0 Pro / Veo

Add-ons (one-time IAP):
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
        'daily_image_limit': 5,           # session 34 — enforced in can_run_today
        'monthly_reels_limit': 0,
        'monthly_lipsync_limit': 0,
        'monthly_ai_videos_limit': 0,
        'ai_video_max_seconds': 0,
        'watermark': True, 'allow_face_swap': False, 'allow_lip_sync': False,
        'allow_head_swap': False, 'allow_body_swap': False,
        'allow_video_to_video': False, 'allow_divine': False, 'allow_ai_bg_lipsync': False,
        'allow_multishot': False, 'max_multishot_shots': 0,
        'allow_ai_video': False,
        'allow_video_studio': False,   # Kling 2.5 Studio requires Creator+
        'allow_video_cinematic': False, # Kling 3.0 Pro requires Pro
        'allow_image_cinematic': False, # FLUX Pro requires Creator+
        'max_resolution': '480p',
        'daily_job_limit': 999,
        'trial_eligible': False,
    },
    'starter': {
        'id': 'starter', 'label': 'Starter', 'price_inr': 249, 'price_annual_inr': 2490,
        'credits': 1500,
        'max_videos': 30, 'max_video_seconds': 10, 'max_images': 20,
        'daily_template_limit': 9999,
        'daily_image_limit': 9999,
        'monthly_reels_limit': 30,
        'monthly_lipsync_limit': 5,
        'monthly_ai_videos_limit': 0,
        'ai_video_max_seconds': 0,
        'watermark': False, 'allow_face_swap': True, 'allow_lip_sync': True,
        'allow_head_swap': True, 'allow_body_swap': True,
        'allow_video_to_video': False, 'allow_divine': False, 'allow_ai_bg_lipsync': False,
        'allow_multishot': False, 'max_multishot_shots': 0,
        'allow_ai_video': False,
        'allow_video_studio': False,
        'allow_video_cinematic': False,
        'allow_image_cinematic': False,
        'max_resolution': '720p',
        'daily_job_limit': 999,
        'trial_eligible': True,
        'highlight': False,
    },
    'creator': {
        'id': 'creator', 'label': 'Creator', 'price_inr': 599, 'price_annual_inr': 5990,
        'credits': 3000,
        'max_videos': 60, 'max_video_seconds': 10, 'max_images': 50,
        'daily_template_limit': 9999,
        'daily_image_limit': 9999,
        'monthly_reels_limit': 60,
        'monthly_lipsync_limit': 15,
        'monthly_ai_videos_limit': 3,
        'ai_video_max_seconds': 3,
        'watermark': False, 'allow_face_swap': True, 'allow_lip_sync': True,
        'allow_head_swap': True, 'allow_body_swap': True,
        'allow_video_to_video': True, 'allow_divine': True, 'allow_ai_bg_lipsync': True,
        'allow_multishot': True, 'max_multishot_shots': 2,
        'allow_ai_video': True,
        'allow_video_studio': True,   # Kling 2.5 Studio
        'allow_video_cinematic': False, # Kling 3.0 Pro still Pro-only
        'allow_image_cinematic': True,  # FLUX Pro
        'max_resolution': '720p',
        'daily_job_limit': 999,
        'trial_eligible': True,
        'highlight': True,
    },
    'pro': {
        'id': 'pro', 'label': 'Pro', 'price_inr': 1499, 'price_annual_inr': 14990,
        'credits': 6000,
        'max_videos': 9999, 'max_video_seconds': 15, 'max_images': 100,
        'daily_template_limit': 9999,
        'daily_image_limit': 9999,
        'monthly_reels_limit': 9999,
        'monthly_lipsync_limit': 30,
        'monthly_ai_videos_limit': 8,
        'ai_video_max_seconds': 5,
        'watermark': False, 'allow_face_swap': True, 'allow_lip_sync': True,
        'allow_head_swap': True, 'allow_body_swap': True,
        'allow_video_to_video': True, 'allow_divine': True, 'allow_ai_bg_lipsync': True,
        'allow_multishot': True, 'max_multishot_shots': 4,
        'allow_ai_video': True,
        'allow_video_studio': True,
        'allow_video_cinematic': True,  # Kling 3.0 Pro / Veo
        'allow_image_cinematic': True,
        'max_resolution': '1080p',
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
    # Session 34 — credit top-up packs (matches docs/PRICING_AND_LAUNCH_STRATEGY.md §3)
    {'sku': 'addon_credits_500',    'label': 'Top-up 500 credits',   'price_inr': 99,   'credits': 500,   'expiry_days': 180, 'desc': 'Best for occasional bursts'},
    {'sku': 'addon_credits_1500',   'label': 'Top-up 1,500 credits', 'price_inr': 249,  'credits': 1500,  'expiry_days': 180, 'desc': 'Covers a productive week'},
    {'sku': 'addon_credits_5000',   'label': 'Top-up 5,000 credits', 'price_inr': 799,  'credits': 5000,  'expiry_days': 180, 'desc': 'Power-user pack — best value/credit'},
    {'sku': 'addon_credits_10000',  'label': 'Top-up 10,000 credits','price_inr': 1499, 'credits': 10000, 'expiry_days': 180, 'desc': 'Agency-size pack'},
]


# ===== Trial / annual billing constants =====
TRIAL_PRICE_INR = 1
TRIAL_DAYS = 30
ANNUAL_MULTIPLIER = 10


def trial_savings_pct_annual() -> int:
    return int(round((1 - ANNUAL_MULTIPLIER / 12) * 100))


def plan_by_id(pid: str):
    return PLANS.get((pid or 'free').lower(), PLANS['free'])


def addon_by_sku(sku: str):
    for a in ADDONS:
        if a['sku'] == sku:
            return a
    return None


# ===== MH pricing (unchanged — what MH actually charges per action) =====
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


# ═══════════════════════════════════════════════════════════════════
# Session 34 — Daily + Monthly quota enforcement
# ═══════════════════════════════════════════════════════════════════

# Job-type → monthly bucket that should be decremented.
# Keep this in sync with settle_credits() in core/billing.py.
_MONTHLY_BUCKET = {
    'reel': 'reels', 'instant-reel': 'reels', 'wizard': 'reels',
    'lipsync': 'lipsync', 'create-lipsync': 'lipsync',
    'video': 'ai_videos', 'videogen': 'ai_videos', 'generate-video': 'ai_videos',
    'image-to-video': 'ai_videos', 'video-to-video': 'ai_videos', 'animate-image': 'ai_videos',
    'image': 'images', 'imagegen': 'images', 'generate-image': 'images',
}


def monthly_bucket_for(job_type: str) -> Optional[str]:
    return _MONTHLY_BUCKET.get((job_type or '').lower())


def can_run_today(user: dict, *, job_type: Optional[str] = None) -> tuple[bool, str]:
    """Enforce daily caps — today only the Free-tier image limit matters.

    Called for every paid job. Very cheap — reads only `daily_usage` / `daily_image_usage`
    fields already on the user doc.
    """
    plan = plan_by_id(user.get('subscription_tier', 'free'))
    today = utc_today_str()

    # Reset counters if day rolled over (defensive — settle_credits also handles this)
    if user.get('daily_usage_date') != today:
        return True, 'ok'

    if job_type and monthly_bucket_for(job_type) == 'images':
        used = int(user.get('daily_image_usage', 0) or 0)
        cap = int(plan.get('daily_image_limit', 9999))
        if used >= cap:
            return False, (
                f"Daily image limit reached ({cap}/day on {plan['label']}). "
                f"Resets tomorrow UTC — or upgrade to Starter for unlimited."
            )

    return True, 'ok'


def can_run_this_month(user: dict, bucket: str) -> tuple[bool, str]:
    """Enforce monthly caps for reels / lipsync / ai_videos.

    The user doc is expected to carry:
        monthly_usage_month: '2026-05'
        monthly_usage: {reels: 12, lipsync: 3, ai_videos: 0, images: 45}

    If the stored `monthly_usage_month` is stale, we assume the counter has
    rolled over and allow the call. `settle_credits` is responsible for
    resetting the dict when bumping a new month.
    """
    plan = plan_by_id(user.get('subscription_tier', 'free'))
    month = utc_month_str()

    if user.get('monthly_usage_month') != month:
        return True, 'ok'

    used = int((user.get('monthly_usage') or {}).get(bucket, 0) or 0)

    caps = {
        'reels':     plan.get('monthly_reels_limit'),
        'lipsync':   plan.get('monthly_lipsync_limit'),
        'ai_videos': plan.get('monthly_ai_videos_limit'),
    }
    cap = caps.get(bucket)
    if cap is None or cap >= 9999:
        return True, 'ok'

    if used >= cap:
        pretty = {'reels': 'reel', 'lipsync': 'lip-sync', 'ai_videos': 'AI video'}.get(bucket, bucket)
        upsell = {
            'reels':     'Upgrade to Pro for unlimited reels.',
            'lipsync':   'Upgrade to Pro for 30 lip syncs/month.',
            'ai_videos': 'Buy an add-on pack (₹49 → 1 video) or upgrade to Pro for 8 AI videos/month.',
        }.get(bucket, 'Upgrade your plan.')
        return False, (
            f"Monthly {pretty} limit reached ({used}/{cap} this month on {plan['label']}). "
            f"{upsell}"
        )

    return True, 'ok'


def check_feature_access(
    user: dict,
    *,
    feature: str,
    duration: Optional[int] = None,
    shots: Optional[int] = None,
    quality_mode: Optional[str] = None,
) -> tuple[bool, str]:
    """Validate tier-level feature gates + monthly quotas.

    Supported `feature` values:
      face_swap, lip_sync, head_swap, body_swap, multishot, ai_video,
      video_to_video, divine, ai_bg_lipsync, reel, image
    """
    plan = plan_by_id(user.get('subscription_tier', 'free'))
    q = (quality_mode or '').lower()

    # ——— Boolean feature switches ———
    gate_map = {
        'face_swap':     ('allow_face_swap',     'Face Swap requires Starter plan or higher.'),
        'lip_sync':      ('allow_lip_sync',      'Lip Sync requires Starter plan or higher.'),
        'head_swap':     ('allow_head_swap',     'Head Swap requires Starter plan or higher.'),
        'body_swap':     ('allow_body_swap',     'Body Swap requires Starter plan or higher.'),
        'video_to_video':('allow_video_to_video','Video-to-Video style transfer requires Creator plan or higher.'),
        'divine':        ('allow_divine',        'Divine Transform requires Creator plan or higher.'),
        'ai_bg_lipsync': ('allow_ai_bg_lipsync', 'AI BG Lipsync (character + scene + dialogue) requires Creator plan or higher.'),
        'multishot':     ('allow_multishot',     'Multi-shot requires Creator plan or higher.'),
    }
    if feature in gate_map:
        key, msg = gate_map[feature]
        if not plan.get(key, False):
            return False, msg

    # ——— Multishot shot-count limit ———
    if feature == 'multishot' and shots is not None and shots > plan.get('max_multishot_shots', 0):
        return False, f"Your plan allows max {plan['max_multishot_shots']} shots per multi-shot."

    # ——— AI video (Kling / Veo) ———
    if feature == 'ai_video':
        extra = int(user.get('addon_ai_videos_remaining', 0) or 0)
        if not plan['allow_ai_video'] and extra <= 0:
            return False, 'AI Video requires Creator plan or higher, or purchase an add-on (₹49 → 1 video).'
        if duration is not None:
            max_s = max(
                plan.get('ai_video_max_seconds', 0) or 0,
                int(user.get('addon_ai_video_max_seconds', 0) or 0),
            )
            if max_s > 0 and duration > max_s:
                return False, f'AI Video max duration on your plan/add-on is {max_s}s.'
        # Quality-mode gate
        if q == 'studio' and not plan.get('allow_video_studio', False):
            return False, 'Kling 2.5 Studio quality requires Creator plan or higher. Use Kling Lite on your current plan.'
        if q == 'cinematic' and not plan.get('allow_video_cinematic', False):
            return False, 'Kling 3.0 Pro / Veo (cinematic) quality requires Pro plan. Use Kling Lite or upgrade to Pro.'
        # Monthly quota
        ok_m, msg_m = can_run_this_month(user, 'ai_videos')
        if not ok_m:
            return False, msg_m

    # ——— Image quality gate + daily cap ———
    if feature == 'image':
        if q == 'cinematic' and not plan.get('allow_image_cinematic', False):
            return False, 'FLUX Pro (cinematic) image quality requires Creator plan or higher.'
        ok_d, msg_d = can_run_today(user, job_type='image')
        if not ok_d:
            return False, msg_d

    # ——— Reel monthly quota ———
    if feature == 'reel':
        ok_m, msg_m = can_run_this_month(user, 'reels')
        if not ok_m:
            return False, msg_m

    # ——— Lip-sync monthly quota ———
    if feature == 'lip_sync':
        ok_m, msg_m = can_run_this_month(user, 'lipsync')
        if not ok_m:
            return False, msg_m

    # ——— Generic duration caps ———
    if duration is not None and feature != 'ai_video':
        if duration > 10 and plan['id'] not in ('pro', 'creator'):
            return False, 'Videos > 10s require Creator or Pro plan.'
        if duration > 5 and plan['id'] == 'free':
            return False, 'Videos > 5s require Starter plan or higher.'

    return True, 'ok'
