# Changelog

All notable changes to **MagiCAi Studio** are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/).

---

## [Unreleased]

### Planned (V2.0 — Mar–Apr 2026)
- 12-screen Premium Neon Glass UI redesign (handoff at `memory/HANDOFF_NEXT_SESSION_v2.md`)
- Light Mode theme with `useColorScheme()` + AsyncStorage persistence
- Low-res 3-second draft preview before full generation
- Hindi UI localisation (Phase 1)

---

## [1.0.0-beta.34d] — 2026-05-04

### Added
- **`POST /api/waitlist-signup`** — public email-capture endpoint with EmailStr validation, UTM extraction, IP/UA spam triage, and idempotent re-submits.
- **`GET /api/waitlist-stats`** — public counter for the landing-page banner ("X creators waiting · Y seats left").
- **`GET /api/admin/waitlist`** — admin-only export with filter on uninvited users for batch invitation flow.
- **Landing page email-capture form** — glassmorphism waitlist card with live counter pill, gradient submit button, JS handler with success/error messaging, and mobile-responsive layout.
- **`useMyLimits` hook + UsageCard / UpgradeBanner / LockBadge components** — reusable building blocks driven by `GET /api/me/limits` for tier-aware UI throughout the app.
- **Subscription screen** now shows `<UsageCard>` with progress bars for reels/lipsync/AI videos/daily images plus upgrade-hint banners that route to `/subscription?focus=<tier>`.

### Changed
- `templates` collection now uses `plan_tier` field (was `tier`) — backfilled all 26 docs via aggregation pipeline. Idempotent migration runs on every backend startup so it stays consistent. Final state: 68/68 templates tagged across both collections.
- Landing page CTAs updated: "Try the App" → "Join the waitlist".

### Verified
- Watermark FFmpeg pipeline (drawtext overlay + image stamp + DB updates) — already implemented in `apply_watermark_if_free()`. No-op task.

---

## [1.0.0-beta.34b] — 2026-05-04

### Added
- **Tier gating enforcement** — backend now properly 402s users who exceed plan limits:
  - New feature gates: `head_swap`, `body_swap`, `video_to_video`, `divine`, `ai_bg_lipsync` (split out from generic `face_swap`)
  - Quality-mode gates: Kling 2.5 Studio = Creator+, Kling 3.0 Pro / Veo = Pro-only, FLUX Pro = Creator+
  - Monthly quota enforcement via `can_run_this_month()` + automatic month-rollover in `settle_credits()`
  - Free tier daily image cap (5 FLUX Schnell / day) via `can_run_today()` + `daily_image_usage` counter
- **`GET /api/me/limits`** — one-shot read of tier + month-to-date usage + 12 feature gates + contextual upsell hints.
- **Corrected pricing in catalog** — ₹249 / ₹599 / ₹1,499 (was stale ₹299/499/899). Added 4 credit top-up SKUs (₹99 / ₹249 / ₹799 / ₹1,499).

### Changed
- `preflight_and_reserve()` now accepts `quality_mode=` kwarg.
- `settle_credits()` now accepts `job_type=` kwarg and bumps monthly/daily counters with automatic roll-over.
- All 9 MH-touching endpoints in `server.py` updated with correct `feature=`, `job_type=`, `quality_mode=` kwargs.
- `/api/create-video-to-video` now runs preflight BEFORE file-exists check so upgrade 402 surfaces before 400.

### Fixed
- `routes/account.py` — `KeyError 'user_id'` regression in `/api/usage` (now falls through `user_id → id → email`).

---

## [1.0.0-beta.34] — 2026-05-04

### Added
- **Phase-B refactor round 2** — `/api/preview-voice` extracted from `server.py` into `routes/catalog.py` (uses lazy import of `server.generate_tts_audio` to avoid circular dependency).
- **Phase-B refactor round 1** — `/api/usage`, `/api/credits-info`, `/api/mh-models` extracted from `server.py` into a new `routes/account.py` module (~200 LOC shed from `server.py`).
- **Template auto-preview backfill** — new `POST /api/templates/backfill-previews` (admin BackgroundTask) + `GET /api/templates/preview-stats` observability endpoint. Current BETA DB has 100% preview coverage (26/26).
- **Beta v1 launch strategy doc** — comprehensive pricing analysis, capacity planning, beta launch plan, and AI-vs-human testing strategy at `docs/PRICING_AND_LAUNCH_STRATEGY.md`.

### Changed
- `server.py` is now down to **3,335 lines** (from ~3,508 at session start).
- `routes/account.py` imports MH constants directly from `core.constants` / `core.pricing` (removed circular dep on `server.py`).
- `routes/templates.py`: moved `GET /preview-stats` above `/{template_id}` so FastAPI's path matcher doesn't shadow it; removed the duplicate at end-of-file.

### Fixed
- FastAPI signature bug — `Optional[Request]` is not a valid response-field type. Changed to `request: Request = None`.
- `KeyError: 'user_id'` in `/api/usage` — `core.auth.get_current_user` returns `id` not `user_id`. Fix falls through `user_id → id → email` to support both dialects.

---

## [1.0.0-beta.33] — 2026-04-28

### Added
- **4-phase Cinematic Avatar Engine** complete:
  - Phase 1: 6 cinematic presets (Bhakti / Funny / Cinematic / Emotional / Viral / Story) with Free/Pro paywall
  - Phase 2: Emotion detection via LLM (12 emotions: happy, angry, sad, surprised, neutral, excited, mysterious, peaceful, confident, devotional, playful, fierce) + auto-tinting
  - Phase 3: FFmpeg camera + motion engine (vignette, soft-glow, shake, depth-of-field, ken-burns, pan, zoom)
  - Phase 4: Remix Dialogue UI (Rewrite / Funny / Emotional / Viral) via GPT-4o-mini + Free vs Pro Before/After toggle
- **Procedural cartoon lipsync** — fully local FFmpeg solo (`core/mouth_animator.py`) and dual (`core/dual_mouth_animator.py`) lipsync. Saves ~600 MH credits per dual-avatar reel.
- New endpoints: `GET /api/cinematic-presets`, `POST /api/avatar/detect-emotion`, `POST /api/avatar/remix-dialogue`.

### Fixed
- Double-zoompan bug: `apply_motion_to_video_clip` was running AFTER `camera_effects.apply_camera_effects()` for cinematic/funny presets, producing `avatar_motion_*.mp4` filenames instead of the expected `*_fx_*.mp4`.
- Dual procedural pipeline now correctly merges preset's `motion=ken_burns` into the request before `_bg()` execution (was reading `motion=None` from the test body).
- `UnboundLocalError` in `routes/avatar.py` cleanup loop — `split_img`, `still_v`, `list_txt` are now initialised before the procedural/MH branch split.
- DB mismatch: `routes/avatar.py` was importing `from core.config import DB_NAME` (returns `magicai_beta` under BETA env) while `routes/projects.py` imports `from core.db import db` (returns `videoai_database` via explicit `DB_NAME` env var). Avatar.py now uses `core.db.db` consistently.

---

## [1.0.0-beta.32] — 2026-04-25

### Added
- **Creative Plan Engine** — `POST /api/creative-plan` returns strict JSON `{hook, script[], scene_keywords[], voice_style, bgm_style, mood, pacing}` via GPT-4o-mini. Caches results in `db.creative_plans`.
- **V2.0 ChatGPT-style Prompt Generator** — `POST /api/generate-prompts` returns 3 differentiated prompt cards per idea (varied duration / style_tag / mood). LRU 30-min cache. Supports English + Hindi (Devanagari).

### Changed
- "Magic Hour" / "MH credits" → "MagiCAi" / "credits" rebrand across the entire app.
- `AuroraBackground` blob opacity reduced 0.55 → 0.22 (no more bleed-through).
- Dark overlay strengthened 0.18 → 0.55.
- BottomTabBar: flattened glass + raised gradient FAB ("+ Create") opens Quick-Action Sheet.
- 100px scroll padding added to all 5 tab-bar screens to fix Generate-button overlap.

### Fixed
- `expo-notifications` warning silenced in Expo Go via `Constants.appOwnership` guard.
- `demo_creator@test.com` login chip added to login screen.

---

## [1.0.0-beta.20] — 2026-04-15

### Added
- **Sarvam AI integration** — 7 premium Indic voices (anushka, manisha, vidya, arya, abhilash, karun, hitesh) using bulbul:v2 model, prefixed with `sarvam:` voice IDs.
- **Image normalization** — `normalize_image_for_mh()` PIL helper re-encodes any image (HEIC/WebP/CMYK/16-bit/alpha) into a clean RGB JPEG ≤2048px before MH upload. Fixes "couldn't process your image" errors.
- **Kling-style home screen** — hero banner carousel + 3 big primary pills (All Tools / AI Image / AI Video) + Trends horizontal thumbnails.
- New `/explore-tools` route — 2-col grid of all 9 tools.

### Changed
- Voice library expanded from 8 → 43 voices.
- VOICE_LIBRARY moved to `core/voice_library.py`; `/voices` moved to `routes/catalog.py`.

---

## [1.0.0-beta.10] — 2026-04-01

### Added
- **Pattern Lab** — auto-generated trending templates with admin moderation. Flag button on every Trending card; admin panel "Pattern Lab" tab with Approve / Hide / Delete actions; 5-flag auto-deactivation; 14-day expiry.
- **Voice Preview** — `GET /api/preview-voice?voice_id=...` streams cached MP3 sample. Disk-cached so repeat calls are <500ms.
- **Idea Image Generation** — `POST /api/generate-idea-image` with 16 outfit + head presets and 12 detailed deity prompts (Krishna, Shiva, Ganesha, Ram, Hanuman, Durga, Lakshmi, Saraswati, Kali, Parvati, Vishnu, Brahma).
- Lip Sync `target_duration` field for the duration selector.

### Changed
- Voice library: each voice entry now includes `preview_text` for TTS sampling.

---

## [1.0.0-beta.5] — 2026-03-15

### Added
- **Body Swap & Head Swap** endpoints (`POST /api/create-bodyswap`, `POST /api/create-headswap`) using MH `ai_clothes_changer` and `head_swap`.
- **Auth gating** — Bearer-token requirement on `/api/projects`, `/api/upload-image`, `/api/upload-face-image`, `/api/upload-video`. Anonymous endpoints kept for `/voices`, `/credits-info`, `/mh-models`.
- **Emergent Auth** — `POST /api/auth/session` (session_id → token) and `GET /api/auth/me` (token → user).

---

## [1.0.0-beta.1] — 2026-02-15

### Added
- Initial Expo + FastAPI + MongoDB scaffold.
- Aurora + Glassmorphism design system.
- Custom `AuroraBackground`, `BottomTabBar`, `AnimatedSplash` components.
- 12 hero screens (Home, Login, Marketplace, Avatar Studio, AI Video Gen, Preview & Export, Subscription, Credits, Library, Profile, Onboarding, Splash).
- Magic Hour integrations: Lip Sync, Face Swap (image + video), Image-to-Video, Video-to-Video, AI Image Generator.
- Razorpay test-mode integration (orders + verify).
- Pixabay scene/image/music search.
- 4-tier subscription model (Free / Starter / Creator / Pro).
- 4 demo accounts pre-seeded + 10 beta users.

---

## Conventions

- **`Added`** — new features.
- **`Changed`** — changes in existing functionality.
- **`Deprecated`** — soon-to-be-removed features.
- **`Removed`** — features removed in this release.
- **`Fixed`** — bug fixes.
- **`Security`** — vulnerabilities addressed.

Refactoring-only changes that don't affect behaviour go under `Changed`.
Breaking changes are flagged with **⚠️ BREAKING** at the start of the line.

---

*Built with 💜 by [dbamkj](https://github.com/dbamkj) — Emergent Builders Contest 2026*
