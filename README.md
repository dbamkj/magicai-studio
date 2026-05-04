# MagiCAi Studio 🪄

> Turn any idea into a scroll-stopping AI video in under 60 seconds.

MagiCAi Studio is a premium, mobile-first AI creator suite that combines a **Creative Plan Engine** (GPT-4o-mini), a **4-phase Cinematic Avatar Engine** with procedural lipsync, **multi-lingual expressive TTS** (Sarvam AI + edge-tts), **stock scene search** (Pixabay), and **AI image generation** (Gemini Nano Banana) into one seamless pipeline — wrapped in an Aurora + Glassmorphism UI that feels genuinely native on Android & iOS.

Built as an Emergent Labs *Builders Contest* V1.0 submission.

[![CI](https://github.com/dbamkj/magicai-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/dbamkj/magicai-studio/actions/workflows/ci.yml) [![Status](https://img.shields.io/badge/status-beta--v1-purple)]() [![Backend](https://img.shields.io/badge/backend-FastAPI-009688)]() [![Frontend](https://img.shields.io/badge/frontend-Expo%20SDK%2053-000020)]() [![Python](https://img.shields.io/badge/python-3.11-blue)]() [![Node](https://img.shields.io/badge/node-20-green)]() [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE) [![Changelog](https://img.shields.io/badge/changelog-keep%20a%20changelog-orange)](CHANGELOG.md)

---

## ✨ Highlights

- 🎬 **One-tap AI Video Generation** — idea → hook → scenes → voice → BGM → rendered MP4 (zero MagicHour spend via Wizard pipeline)
- 🧠 **Creative Plan Engine** — `POST /api/creative-plan` returns strict JSON `{hook, script[], scene_keywords[], voice_style, bgm_style, mood}` so every clip, line, and beat aligns
- 🎭 **4-Phase Cinematic Avatar Engine**
  - 6 cinematic presets (Bhakti / Funny / Cinematic / Emotional / Viral / Story)
  - 12 emotion chips with auto-detect via LLM
  - FFmpeg camera + motion + vignette / soft-glow / shake / depth-of-field FX
  - **Procedural solo + dual-character lipsync** — fully local, ZERO MH credits
  - Free vs Pro Before/After toggle on the result preview
  - Remix Dialogue: Rewrite / Funny / Emotional / Viral variations via GPT-4o-mini
- 🗣️ **43 Voices** — 36 edge-tts (Hindi / English / Baby) + 7 Sarvam Premium (anushka, manisha, vidya, arya, abhilash, karun, hitesh) with pitch / rate / emotion control
- 🎨 **AI Avatars & Thumbnails** — Gemini 2.5 Flash (Nano Banana) with 11 styles + 12 emotions
- 📚 **Template Marketplace** — 26 curated templates (Bhajans, Festival Reels, Motivational Shorts, Funny Dialogues) with 100% MP4 preview coverage
- 🎞️ **Pattern Lab** — auto-generated trending templates with admin moderation (5-flag auto-deactivation, 14-day expiry)
- 🌅 **Premium Neon Glass UI** — Aurora gradients, frosted-glass cards, spring animations
- 💳 **4-Tier Subscription** — Free / Starter / Creator / Pro with Razorpay checkout (test mode in beta)
- 🔐 **Production Auth** — JWT + bcrypt, Google SSO (Emergent), admin role, tier-gated feature flags

---

## 📱 Tech Stack

### Frontend
- **Expo SDK 53** (React Native 0.79) — cross-platform mobile, file-based routing via Expo Router
- **TypeScript** strict mode
- **react-native-reanimated** — 60fps spring animations
- **@shopify/flash-list** — virtualised feeds
- **expo-av / expo-video** — video & audio playback
- **AsyncStorage + SecureStore** — tokens & prefs
- **Axios** — HTTP client
- Custom `AuroraBackground`, `BottomTabBar`, `GlassCard`, `AnimatedSplash` components

### Backend
- **FastAPI** (Python 3.11) — async uvicorn, **routes split by domain into 20 modules**
- **MongoDB** (Motor async driver) — users, templates, projects, jobs, dialogues
- **FFmpeg** — procedural lipsync, camera FX, frame extraction, audio mixing, MP4 stitching
- **Async scheduler** — nightly trending recompute (02:00 UTC), 6h trial-expiry cron, marketplace seed on startup

### AI / 3rd-Party Integrations
| Service | Use | Key type |
|---|---|---|
| **OpenAI GPT-4o-mini** | Creative Plan Engine, prompt structuring, emotion detection, dialogue remix, moderation | Emergent LLM Key |
| **Gemini 2.5 Flash / Nano Banana** | Avatars, thumbnails, vision moderation | Emergent LLM Key |
| **Sarvam AI (bulbul:v2)** | Indic + English TTS (7 premium voices) | User API key |
| **edge-tts** | 36 free Hindi / English / Baby voices | None (free) |
| **Pixabay** | Stock videos / images / music | User API key |
| **MagicHour** | Lipsync / Face-swap / Head-swap / Body-swap / Image-to-Video / Video-to-Video | User API key |
| **Razorpay** | Subscription payments | User API key |

---

## 🚀 Quick Start (Local Dev)

### Prerequisites
- Node.js 18+, Yarn
- Python 3.11+
- MongoDB 6+ running locally (or Atlas connection string)
- FFmpeg on PATH

### 1. Clone & install
```bash
git clone https://github.com/dbamkj/magicai-studio.git
cd magicai-studio

# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
yarn install
```

### 2. Configure env vars

**`backend/.env`**
```env
MONGO_URL=mongodb://localhost:27017
ENV=BETA
DB_NAME_BETA=magicai_beta
JWT_SECRET=your_strong_jwt_secret_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=168
ADMIN_EMAIL=admin@magicai.test

# Integration keys
EMERGENT_LLM_KEY=sk-emergent-...
PIXABAY_API_KEY=your_pixabay_key
SARVAM_API_KEY=your_sarvam_key
MAGIC_HOUR_API_KEY=your_mh_key
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

**`frontend/.env`**
```env
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001
```

### 3. Seed demo users (optional)
```bash
cd backend
ENV=BETA python scripts/seed_beta_users.py
```

> The backend **auto-seeds demo accounts on first boot** when the users collection is empty and `ENV != DEV`. So you can skip this step for fresh deployments.

### 4. Run
```bash
# Terminal 1 — backend
cd backend && uvicorn server:app --reload --host 0.0.0.0 --port 8001

# Terminal 2 — frontend
cd frontend && yarn start
# Scan the QR code with Expo Go, or press `w` for web preview
```

API docs at `http://localhost:8001/docs` (FastAPI Swagger).

---

## 👤 Demo Accounts

Password for **all** demo accounts: `Test@123`

| Email | Tier | Credits |
|---|---|---|
| `admin@magicai.test` | Pro (admin) | 6000 |
| `demo_free@test.com` | Free | 300 |
| `demo_starter@test.com` | Starter | 1500 |
| `demo_creator@test.com` | Creator | 3000 |
| `demo_pro@test.com` | Pro | 6000 |

Plus 10 beta users `beta_user_1..10@test.com` distributed across tiers.

---

## 🗂️ Project Structure

```
magicai-studio/
├── backend/
│   ├── server.py                       # FastAPI app + startup hooks (~3,300 LOC, refactor in progress)
│   ├── core/
│   │   ├── config.py                   # ENV + DB routing (DEV / BETA / PROD)
│   │   ├── auth.py                     # JWT + bcrypt
│   │   ├── db.py                       # Shared Motor client
│   │   ├── constants.py                # MH credit costs, quality tiers, SFX, motion presets
│   │   ├── pricing.py                  # MH per-sec rates + min-billed seconds
│   │   ├── voice_library.py            # 43 voices catalog
│   │   ├── billing.py                  # Pre-flight credit check + atomic reservation
│   │   ├── moderation.py               # Text / image / video content filter
│   │   ├── upload_safety.py            # Magic-byte + size guards
│   │   ├── marketplace_seed.py
│   │   ├── dialogues_seed.py
│   │   ├── trending.py                 # Score recompute pipeline
│   │   ├── scheduler.py                # Async cron loops
│   │   ├── cinematic_presets.py        # 6 cinematic preset configs
│   │   ├── emotion_detector.py         # LLM emotion inference (12 emotions)
│   │   ├── camera_effects.py           # FFmpeg camera FX (zoom/pan/vignette/glow)
│   │   ├── mouth_animator.py           # Procedural solo lipsync (zero-MH)
│   │   └── dual_mouth_animator.py      # Procedural dual-character lipsync (zero-MH)
│   │
│   ├── routes/                         # Domain-split FastAPI routers
│   │   ├── auth.py                     # /api/auth/{register,login,me,google-finish}
│   │   ├── account.py                  # /api/usage, /api/credits-info, /api/mh-models
│   │   ├── catalog.py                  # /api/voices, /api/preview-voice, /api/sound-effects, /api/voice-styles, /api/motion-presets
│   │   ├── creative_plan.py            # /api/creative-plan — GPT-4o-mini structured JSON
│   │   ├── prompts.py                  # /api/generate-prompts — ChatGPT-style 3-card prompt selection
│   │   ├── avatar.py                   # /api/avatar/{cartoonize,styles,detect-emotion,remix-dialogue,jobs}
│   │   ├── talking.py                  # /api/talking/* — talking-photo + cinematic preset pipeline
│   │   ├── wizard.py                   # /api/wizard/generate — 0-MH instant reel
│   │   ├── marketplace.py              # /api/marketplace/templates
│   │   ├── templates.py                # /api/templates/* + preview backfill
│   │   ├── projects.py                 # CRUD on user projects
│   │   ├── uploads.py                  # /api/upload-{image,face-image,video,audio}
│   │   ├── media.py                    # /api/extract-frames, /api/serve-file
│   │   ├── payments.py                 # /api/payments/* — Razorpay orders + verify
│   │   ├── subscription.py             # /api/subscription/*
│   │   ├── dialogues.py                # /api/dialogues — viral one-liner catalog
│   │   ├── notifications.py            # /api/notifications/*
│   │   ├── admin.py                    # /api/admin/* — moderation, profit calc, env switcher
│   │   ├── divine.py                   # /api/divine — divine transform feature
│   │   └── story.py                    # /api/story — story generator
│   │
│   ├── scripts/
│   │   ├── seed_beta_users.py
│   │   ├── seed_marketplace.py
│   │   ├── seed_festival_templates.py
│   │   └── restore_previews.py
│   │
│   └── static/
│       ├── landing/                    # Production marketing landing page
│       └── (uploads, avatars, etc — gitignored)
│
├── frontend/
│   ├── app/                            # Expo Router file-based screens
│   │   ├── _layout.tsx
│   │   ├── index.tsx                   # Home — Aurora hero carousel + Quick Access + Trending
│   │   ├── login.tsx                   # 4 demo quick-pick chips
│   │   ├── onboarding.tsx
│   │   ├── marketplace.tsx
│   │   ├── trending.tsx                # Pattern Lab feed + flag-for-moderation
│   │   ├── create-wizard.tsx           # AI Video Gen wizard
│   │   ├── videogen.tsx
│   │   ├── avatar-studio.tsx           # 4-phase Cinematic Engine UI (~3000 LOC)
│   │   ├── cartoon-avatar.tsx
│   │   ├── lipsync.tsx, faceswap.tsx, headswap.tsx, redub.tsx
│   │   ├── reels.tsx                   # Inspiration feed
│   │   ├── subscription.tsx, buy.tsx
│   │   ├── projects.tsx, library.tsx, profile.tsx
│   │   ├── admin.tsx                   # 5-tab admin panel
│   │   └── preview-export.tsx
│   │
│   └── src/
│       ├── AuroraBackground.tsx
│       ├── AnimatedSplash.tsx
│       ├── components/                 # BottomTabBar (FAB), GlassCard, VoicePicker, etc.
│       ├── theme.ts                    # Aurora design tokens
│       └── usePushNotifications.ts     # Expo Go guarded
│
├── contest_assets/                     # App icon, hero banner, 30s demo video
├── memory/                             # Internal handoff docs (gitignored)
└── README.md
```

### Backend route count: 20 routers, 90+ endpoints

---

## 📡 Key API Endpoints

### Auth & account
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | JWT login |
| `POST` | `/api/auth/google-finish` | Google SSO exchange (Emergent) |
| `GET`  | `/api/auth/me` | Current user profile |
| `GET`  | `/api/usage` | Per-type project counts (auth required) |
| `GET`  | `/api/credits-info` | MH credit usage + cost table |
| `GET`  | `/api/mh-models` | Per-feature model + duration + resolution pickers |
| `GET`  | `/api/mode` | Current env (DEV / BETA / PROD) |

### Creative Plan & Prompt selection
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/creative-plan` | **GPT-4o-mini → structured JSON plan** (hook, script, scene_keywords, voice_style, bgm_style, mood) |
| `POST` | `/api/generate-prompts` | ChatGPT-style 3 prompt-card selection (LRU 30-min cache) |
| `POST` | `/api/suggest-scenes` | Scene-prompt suggestions for a hint |

### Cinematic Avatar Engine (4-phase)
| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/cinematic-presets` | 6 preset configs (Bhakti / Funny / Cinematic / Emotional / Viral / Story) |
| `GET`  | `/api/avatar/styles` | 11 styles + 12 emotions |
| `POST` | `/api/avatar/cartoonize` | Nano Banana avatar generation |
| `POST` | `/api/avatar/detect-emotion` | LLM emotion inference |
| `POST` | `/api/avatar/remix-dialogue` | 4 remix styles × N variations |
| `POST` | `/api/talking/generate` | Talking-photo + preset pipeline (procedural or MH lipsync) |

### Catalog
| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/voices` | 43 voices (36 edge-tts + 7 Sarvam) |
| `GET`  | `/api/preview-voice?voice_id=...` | Stream cached MP3 sample |
| `GET`  | `/api/sound-effects` | BGM / SFX catalog |
| `GET`  | `/api/voice-styles` | 5 emotion presets (devotional / motivation / story / funny / neutral) |
| `GET`  | `/api/motion-presets` | Ken-Burns motion presets |

### Wizard / Marketplace
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/wizard/generate` | 0-MH Pixabay+TTS+BGM reel |
| `GET`  | `/api/marketplace/templates` | Filtered template list |
| `POST` | `/api/templates/{id}/use` | Spawn a wizard job from template |
| `GET`  | `/api/templates/preview-stats` | Coverage observability |
| `POST` | `/api/templates/backfill-previews` | Auto-render missing MP4 previews |

### Magic Hour features
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/create-lipsync` | Lip-sync (multi-character, modes: images_only / ref_video_only) |
| `POST` | `/api/create-faceswap`, `/api/create-headswap`, `/api/create-bodyswap` | Image / video swaps |
| `POST` | `/api/create-image-to-video`, `/api/create-video-to-video` | MH motion generators |
| `POST` | `/api/create-ai-bg-lipsync` | Character + scene + dialogue → lipsync video |
| `POST` | `/api/generate-idea-image` | Outfit / head / deity preset image generation |

Full OpenAPI docs at `/docs` when backend is running.

---

## 🧠 Creative Plan Engine (Flagship Feature)

The `POST /api/creative-plan` endpoint is the brain that makes every video *feel* intentional. It takes a raw user idea or marketplace template and returns a strictly-typed JSON plan:

```json
{
  "creative_plan_id": "cp_a1b2c3...",
  "hook": "Krishna's flute silenced armies of demons...",
  "script": [
    "In the forests of Vrindavan, the air once trembled with fear.",
    "Then came a sound — soft as dawn, sharper than any sword.",
    "Krishna's flute. A melody that turned chaos into stillness."
  ],
  "scene_keywords": ["forest sunrise", "flute player silhouette", "peaceful river", "golden light"],
  "voice_style": "warm_storyteller_male",
  "bgm_style": "sacred_ambient_flute",
  "mood": "devotional_awe",
  "pacing": "slow_build"
}
```

This single JSON drives:
- **Pixabay** scene search (via `scene_keywords`)
- **Sarvam / edge-tts** voice & cadence (via `voice_style` + `script` + SSML pauses)
- **BGM** selection (via `bgm_style` + `mood`)
- **Video timing/pacing** (via `pacing`)

Result: every video feels directed, not generated.

---

## 🎭 Cinematic Avatar Engine (4 Phases)

| Phase | What it does | Files |
|---|---|---|
| **1 — Presets** | 6 cinematic preset chips with Free/Pro paywall | `core/cinematic_presets.py` |
| **2 — Emotions** | 12 emotion chips, auto-detect via LLM, expression tinting | `core/emotion_detector.py` |
| **3 — Camera** | FFmpeg vignette / soft-glow / shake / depth-of-field / ken-burns / pan / zoom | `core/camera_effects.py` |
| **4 — Remix** | LLM-powered Rewrite / Funny / Emotional / Viral dialogue variations | `routes/avatar.py:remix_dialogue` |

### Procedural Lipsync (Zero-MH-Credit Cartoon)
Solo + dual-character cartoon lipsync rendered fully locally via FFmpeg without ever touching MagicHour. Saves ~600 MH credits per dual-avatar reel. Toggle with `use_procedural_lipsync=true`. See `core/mouth_animator.py` and `core/dual_mouth_animator.py`.

---

## 🚢 Deployment

### Emergent Native Deployment
1. Push to GitHub (ensure `/app/memory/` and `/app/backend/uploads/` are gitignored — they're huge)
2. Deploy via `app.emergent.sh` → connect repo → "Deploy"
3. **IMPORTANT** — Emergent does *not* auto-provision MongoDB. Configure a [MongoDB Atlas free cluster](https://www.mongodb.com/cloud/atlas/register) and set these env vars on your deployment:
   - `MONGO_URL` (Atlas connection string)
   - `ENV=BETA`
   - `JWT_SECRET`
   - `EMERGENT_LLM_KEY`, `PIXABAY_API_KEY`, `SARVAM_API_KEY`, `MAGIC_HOUR_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
4. First boot auto-seeds demo accounts via the startup hook in `server.py`

### Play Store Beta (Android)
1. Set `EXPO_PUBLIC_BACKEND_URL` in `frontend/.env` to your production backend URL
2. `eas build --profile preview --platform android`
3. Upload the signed AAB to Play Console → Closed testing track

---

## 🔐 Security

- Passwords: **bcrypt** (rounds=10)
- Sessions: **JWT** (HS256, 7-day expiry, stateless)
- **CORS** allow-list configurable per env
- **Content moderation** on all user-generated text + images + videos (blocklist + Gemini vision + Pattern Lab 5-flag auto-deactivation)
- **Upload safety guardrails** — magic-byte signature check + size + empty-file detection BEFORE write to disk (`core/upload_safety.py`)
- Tier-gated endpoints via middleware (Cinematic Pro presets, 1080p output, etc.)
- No sensitive data in logs

---

## 🧪 Testing

The repo ships with **deep automated test coverage** via Emergent's testing sub-agents:

- **Backend** — `deep_testing_backend_v2` runs 90+ contract / regression assertions per release. Test artefacts at `/app/backend_test*.py`.
- **Frontend** — `expo_frontend_testing_agent` runs Playwright scripts at mobile viewports (390x844, 360x800).
- **Strategy** — recommended split for prod is **80% AI agents + 15% paid humans + 5% wildcards**. See `/app/memory/BETA_V1_PRICING_AND_LAUNCH_STRATEGY.md` § 8 for the full rationale.

---

## 🛣️ Roadmap

### V1.0 (Shipped — Feb 2026) ✅
- Premium Neon Glass UI across 12 screens
- Creative Plan Engine
- Marketplace + Inspiration Reels with 100% MP4 preview coverage
- Subscription tiers + Onboarding carousel
- Auto-seed on startup
- 4-phase Cinematic Avatar Engine (presets / emotions / camera FX / remix)
- Procedural solo + dual-character lipsync (zero-MH)
- Phase-B `server.py` modular refactor (account.py + catalog.py extracted)

### V2.0 (In Progress — Mar–Apr 2026)
- 💬 Marketplace template `plan_tier` reseed (Free / Creator / Pro tags)
- 🎨 Premium Neon Glass UI rollout to remaining admin / legal / lipsync / redub screens
- ☀️ Light Mode theme with `useColorScheme()` + AsyncStorage persistence
- 🔍 Low-res 3s draft preview before full generation
- 💧 Watermark FFmpeg pipeline for free tier
- 📨 `/api/waitlist-signup` + landing page email capture
- 🌐 Hindi UI localisation (Phase 1)

### V3.0 (Future — H2 2026)
- Custom voice cloning (user uploads 15s sample)
- In-app video editor (trim / caption / overlay)
- Direct social sharing (Instagram Reels / TikTok / YouTube Shorts)
- Batch generation (1 idea → 5 variations)
- Web app (same codebase via React Native Web)
- Public API access (Pro tier feature)
- Team accounts (multi-seat)

See [`docs/PRICING_AND_LAUNCH_STRATEGY.md`](docs/PRICING_AND_LAUNCH_STRATEGY.md) for the full 12-month feature/scaling roadmap and revenue projections, and [`CHANGELOG.md`](CHANGELOG.md) for the per-release history.

---

## 💳 Pricing (Beta v1)

| Tier | ₹/mo | Credits | Watermark | Resolution | Headline perks |
|---|---|---|---|---|---|
| **Free** | 0 | 30 + 50/mo refill | Yes | 480p | Try the wizard + cartoon avatar |
| **Starter** | ₹249 | 1,000 | No | 720p | 5 LLM remixes, 1 Sarvam Premium voice |
| **Creator ⭐** | ₹599 | 2,500 | No | 720p | Unlimited LLM remix, all Sarvam voices, priority queue |
| **Pro** | ₹1,499 | 7,000 | No | 1080p | Commercial license, API access (V3) |

Annual plans: ~17% discount. Add-on credit packs from ₹149 / 500 credits up to ₹1,199 / 5,000 credits.

> Full pricing rationale + cost-of-goods analysis in [`docs/PRICING_AND_LAUNCH_STRATEGY.md`](docs/PRICING_AND_LAUNCH_STRATEGY.md).

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/amazing-thing`)
3. Run backend + frontend locally (see Quick Start)
4. Add tests if you're touching core logic — `deep_testing_backend_v2` will rerun your contract assertions
5. Open a PR against `main`

---

## 📄 License

MIT — use it, fork it, ship it. A shout-out is appreciated but not required 💜

---

## 🙏 Credits

- **Emergent Labs** — for the universal LLM key, native deployment, and the Builders Contest
- **Sarvam AI** — for world-class Indic TTS
- **Pixabay** — for the stock footage library
- **OpenAI / Google Gemini** — for the underlying models
- **MagicHour** — for the lipsync / face-swap / image-to-video infrastructure
- **Expo** — for making cross-platform mobile actually pleasant

---

**Built with 💜 by [dbamkj](https://github.com/dbamkj) — Emergent Builders Contest 2026**
