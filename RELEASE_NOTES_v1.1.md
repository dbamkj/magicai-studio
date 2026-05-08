# 🚀 MagiCAi Studio v1.1 — Beta Release Notes

**Release date:** 2026-05-08
**Tag:** `v1.1.0`
**Status:** Production-ready for Phase 1 rollout (20-user cap)

---

## 🎯 What this release is for

This is the **first fully-shippable build** of MagiCAi Studio — the backend has real tier-gating enforcement, monetization economics are correctly calibrated against actual MH cost (₹0.135/credit), and the waitlist signup pipeline is live. It is suitable for:

- Pushing to GitHub as the public anchor release
- Opening Beta v1 invite-only access (cap 20 paying users for 3 months)
- Recording the demo video and starting waitlist marketing

---

## ✨ Highlights

### Backend (production-ready)
- ✅ Real tier-gating across **12 feature gates** + **3 quality modes**
- ✅ Monthly + daily quota tracking with auto-rollover
- ✅ `GET /api/me/limits` for tier-aware UI everywhere
- ✅ Public waitlist endpoints (signup / stats / admin export)
- ✅ Watermark FFmpeg pipeline for Free/Trial tier
- ✅ 100% template preview MP4 coverage (68/68 tagged)
- ✅ Phase-B refactor — `server.py` 3,508 → 3,335 LOC
- ✅ **32/32 backend tests green** via `deep_testing_backend_v2`

### Frontend
- ✅ `useMyLimits` hook + UsageCard / UpgradeBanner / LockBadge components
- ✅ Subscription screen consumes `/api/me/limits` with progress bars + upsell hints
- ✅ Landing page email-capture form with live waitlist counter
- ⚠️ 12-screen Premium Neon Glass UI redesign — **deferred to v1.2** (handoff at `memory/HANDOFF_NEXT_SESSION_v2.md`)

### Docs
- ✅ `README.md` with full plan comparison + feature access matrix
- ✅ `CHANGELOG.md` (Keep-a-Changelog format)
- ✅ `docs/PRICING_AND_LAUNCH_STRATEGY.md` — 5-phase rollout plan, capacity math, Beta v1 launch checklist
- ✅ MIT `LICENSE`
- ✅ GitHub Actions CI workflow

---

## 💳 Pricing structure (v1.1)

| Tier | ₹/mo | Credits | Watermark | Resolution | Net margin |
|---|---|---|---|---|---|
| Free | 0 | 300 | ✅ | 480p | -₹24 funnel |
| Starter | ₹249 | 1,500 | ❌ | 720p | ~55% |
| Creator ⭐ | ₹599 | 3,000 | ❌ | 720p (1080p img) | ~66% |
| Pro | ₹1,499 | 6,000 | ❌ | 1080p | ~79% |

> **Trial + Basic ₹99 hybrid** is recommended for v1.2 rollout. See strategy doc § 1.

---

## 🛣️ What ships in v1.1 vs v1.2+

### ✅ Shipping in v1.1 (Phase 1 — 20 users)
- Auth (email/Google SSO)
- Creator Wizard (0-MH instant reels)
- Cartoon Avatar (Nano Banana, 0-MH)
- Procedural Solo Lipsync (0-MH)
- AI Image — FLUX Schnell only
- Marketplace browse + Use Template (Free-tier templates)
- 36 edge-tts voices
- Subscription + Razorpay LIVE checkout
- `/api/me/limits` UI integration
- Watermark for Free tier
- Profile, Library, Onboarding, Login

### 📅 Coming in v1.2 (Phase 2 — 30 users, ~Aug 2026)
- Lip Sync (MH) for Starter+
- Face Swap Photo (MH)
- Procedural Dual Lipsync
- Image-to-Video Kling Lite
- 7 Sarvam Premium voices
- 2 Cinematic Presets in production UI
- Premium Neon Glass UI on remaining screens

### 📅 Coming in v1.3 (Phase 3 — 40 users)
- Full 4-phase Cinematic Engine
- Face Swap Video, Head Swap, Body Swap
- FLUX Dev images
- Talking Avatar (MH)
- Video Re-dub
- Multi-shot videos
- Add-on credit packs in UI

### 📅 Coming in v2.0 (Phase 4 — 50 users)
- Kling 2.5 Studio video
- FLUX Pro cinematic images
- Video-to-Video style transfer
- Divine Transform + AI BG Lipsync combo
- 1080p output for Pro
- Light Mode theme

### 📅 Coming in v2.1 (Phase 5 — 100 users)
- Kling 3.0 Pro / Veo
- Hindi UI localization
- Auto-post to YT Shorts / Reels
- Public API access (Pro)
- Team accounts / multi-seat

---

## 🚀 How to push this release to GitHub

```bash
cd /app
git add .
git commit -m "release: v1.1.0 — beta-ready with tier gating, waitlist, monetization economics"
git tag -a v1.1.0 -m "MagiCAi Studio v1.1 — first fully-shippable beta release"
git push origin main
git push origin v1.1.0
```

Then on GitHub.com → **Releases** → **Draft a new release** → choose `v1.1.0` tag → paste the contents of this file as the release body.

---

## 🔬 Test verification

All 32 backend assertions passed against the deployed preview URL:
- 10/10 waitlist endpoint tests (idempotency, EmailStr validation, admin auth, meta-stripping)
- 2/2 plan_tier migration tests (distribution matches spec)
- 16/16 regression sweep (root, auth, /me/limits with 12 gates, 4 tier 402s, credits-info, mh-models, usage, preview-stats, creative-plan, cinematic-presets, preview-voice, voices, mode)
- 4/4 edge cases (XSS in name field, malformed UTM, non-admin → 403, only_uninvited filter)

---

## ⚠️ Known limitations in v1.1

1. **12-screen Premium Neon Glass UI redesign deferred** — only Home + Subscription have the new design tokens. Other screens still use older glass patterns. Not a functional regression — purely visual.
2. **Razorpay test mode** — LIVE keys + KYC pending (operational task before opening Beta).
3. **No Sentry / monitoring wired yet** — recommended before flipping ENV BETA → PROD.
4. **Demo video not yet recorded** — required for waitlist marketing campaigns.
5. **Trial + Basic ₹99 tier** — recommended in strategy doc but NOT yet implemented in `core/pricing.py`. Current tiers remain Free/Starter/Creator/Pro.

These are **NOT blockers** for the v1.1 GitHub tag — they're operational items for the Beta v1 launch separately.

---

## 🙏 Credits

- **Emergent Labs** — universal LLM key, native deployment, Builders Contest
- **Sarvam AI** — Indic TTS voices
- **MagicHour** — lipsync / face-swap / video infrastructure
- **Pixabay** — stock footage library
- **OpenAI / Google Gemini** — underlying models
- **Expo** — cross-platform mobile

Built with 💜 by [@dbamkj](https://github.com/dbamkj)
