# MagiCAi Studio 🪄

> Turn any idea into a scroll-stopping AI video in under 60 seconds.

MagiCAi Studio is a premium, mobile-first AI creator suite that combines a **Creative Plan Engine** (GPT-4o-mini), **multi-lingual expressive TTS** (Sarvam AI), **stock scene search** (Pixabay), and **AI image generation** (Gemini Nano Banana) into one seamless pipeline — wrapped in an Aurora + Glassmorphism UI that feels genuinely native on Android & iOS.

Built as an Emergent Labs *Builders Contest* V1.0 submission.

---

## ✨ Highlights

- 🎬 **One-tap AI Video Generation** — idea → hook → scenes → voice → BGM → rendered MP4
- 🧠 **Creative Plan Engine** — structured JSON output (hook, script, scene keywords, voice style, mood, BGM) so every clip, line, and beat aligns perfectly
- 🗣️ **Expressive Voices** — Sarvam AI Indic TTS + English voices with speed / pitch / emotion control
- 🎨 **AI Avatars & Thumbnails** — Gemini Nano Banana (image generation) with style presets
- 📚 **Template Marketplace** — 40+ pre-made templates (Bhajans, Festival Reels, Motivational Shorts, Funny Dialogues) tier-gated as Free / Starter / Creator / Pro
- 🎞️ **Inspiration Reels** — baked-audio MP4 feed users can remix with one tap
- 🌅 **Premium Neon Glass UI** — Aurora gradients, frosted-glass cards, spring animations, 12+ polished screens
- 💳 **Subscription Tiers** — Free (300 credits) / Starter / Creator (3000 credits) / Pro (6000 credits) with Razorpay checkout (mocked in beta)
- 🔐 **Production Auth** — JWT + bcrypt, Google SSO (Emergent), admin role, tier-gated feature flags

---

## 📱 Tech Stack

### Frontend
- **Expo (React Native)** — cross-platform mobile, file-based routing via Expo Router
- **TypeScript** strict mode
- **react-native-reanimated** — 60fps spring animations
- **@shopify/flash-list** — virtualised feeds
- **expo-av / expo-video** — video & audio playback
- **AsyncStorage + SecureStore** — tokens & prefs
- **Axios** — HTTP client
- Custom `AuroraBackground`, `BottomTabBar`, `GlassCard` components

### Backend
- **FastAPI** (Python 3.11) — async uvicorn, routes split by domain
- **MongoDB** (Motor async driver) — users, templates, projects, jobs, reels
- **FFmpeg** — video/audio muxing, frame extraction for moderation
- **APScheduler-style async loops** — nightly trending recompute, trial-expiry cron

### AI / 3rd-Party Integrations
| Service | Use | Key type |
|---|---|---|
| **OpenAI GPT-4o-mini** | Creative Plan Engine, prompt structuring, moderation | Emergent LLM Key |
| **Gemini 2.5 Flash / Nano Banana** | Avatars, thumbnails, vision moderation | Emergent LLM Key |
| **Sarvam AI** | Indic + English TTS (expressive) | User API key |
| **Pixabay** | Stock videos / images / music | User API key |
| **Razorpay** | Subscription payments (mocked in beta) | User API key |

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
```

**`frontend/.env`**
```env
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001
```

### 3. Seed demo users
```bash
cd backend
ENV=BETA python scripts/seed_beta_users.py
```

> Note: the backend also **auto-seeds demo accounts on first boot** when the users collection is empty and `ENV != DEV`. So you can skip this step for fresh deployments.

### 4. Run
```bash
# Terminal 1 — backend
cd backend && uvicorn server:app --reload --host 0.0.0.0 --port 8001

# Terminal 2 — frontend
cd frontend && yarn start
# Scan the QR code with Expo Go, or press `w` for web preview
```

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

Plus 10 beta users `beta_user_1..10@test.com` across tiers.

---

## 🗂️ Project Structure

```
magicai-studio/
├── backend/
│   ├── server.py              # FastAPI app, startup hooks, legacy routes
│   ├── core/
│   │   ├── config.py          # ENV + DB routing (DEV/BETA/PROD)
│   │   ├── auth.py            # JWT + bcrypt
│   │   ├── moderation.py      # Text / image / video content filter
│   │   ├── marketplace_seed.py
│   │   ├── dialogues_seed.py
│   │   └── scheduler.py       # Async cron (trending, trial expiry)
│   ├── routes/
│   │   ├── auth.py            # /api/auth/* (register, login, me, google SSO)
│   │   ├── marketplace.py     # /api/marketplace/*
│   │   ├── templates.py       # /api/templates/*
│   │   ├── creative_plan.py   # /api/creative-plan — GPT-4o-mini JSON output
│   │   ├── users.py, admin.py, subscriptions.py
│   │   └── ...
│   ├── scripts/
│   │   ├── seed_beta_users.py
│   │   ├── seed_festival_templates.py
│   │   └── restore_previews.py
│   └── static/previews/       # Baked-audio inspiration MP4s
│
├── frontend/
│   ├── app/                   # Expo Router file-based screens
│   │   ├── _layout.tsx
│   │   ├── index.tsx          # Home (Aurora header, Quick Access, Onboarding, Reels)
│   │   ├── login.tsx
│   │   ├── onboarding.tsx
│   │   ├── marketplace.tsx
│   │   ├── create-wizard.tsx  # AI Video Gen wizard
│   │   ├── videogen.tsx, imagegen.tsx, avatarstudio.tsx
│   │   ├── reels.tsx          # Inspiration feed
│   │   ├── subscription.tsx, credits.tsx
│   │   ├── library.tsx, profile.tsx
│   │   └── preview-export.tsx
│   └── src/
│       ├── AuroraBackground.tsx
│       ├── components/        # BottomTabBar, GlassCard, etc.
│       └── theme.ts
│
├── contest_assets/            # App icon, hero banner, 30s demo video
├── memory/                    # Internal handoff docs (gitignored)
└── README.md
```

---

## 📡 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/api/`                      | Health check + version |
| `POST` | `/api/auth/register`         | Create account (free/starter/creator/pro tier) |
| `POST` | `/api/auth/login`            | JWT login |
| `POST` | `/api/auth/google-finish`    | Google SSO exchange (Emergent) |
| `GET`  | `/api/auth/me`               | Current user profile |
| `GET`  | `/api/marketplace/templates` | List templates (filter by tier, category, trending) |
| `POST` | `/api/creative-plan`         | **GPT-4o-mini → structured JSON plan** |
| `POST` | `/api/video/generate`        | Kick off video render job |
| `GET`  | `/api/jobs/{id}`             | Job status polling |
| `POST` | `/api/tts/generate`          | Sarvam TTS (Indic + EN) |
| `POST` | `/api/image/generate`        | Gemini Nano Banana image generation |
| `GET`  | `/api/mode`                  | Returns current env (DEV/BETA/PROD) |

Full OpenAPI docs available at `/docs` when backend is running.

---

## 🧠 Creative Plan Engine (Flagship Feature)

The `POST /api/creative-plan` endpoint is the brain that makes every video *feel* intentional. It takes a raw user idea or marketplace template and returns a strictly-typed JSON plan:

```json
{
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
- Pixabay scene search (via `scene_keywords`)
- Sarvam TTS voice & cadence (via `voice_style` + `script`)
- BGM selection (via `bgm_style` + `mood`)
- Video timing/pacing (via `pacing`)

Result: every video feels directed, not generated.

---

## 🚢 Deployment

### Emergent Native Deployment
1. Push to GitHub (ensure `/app/memory/` and `/app/backend/uploads/` are gitignored — they're huge)
2. Deploy via `app.emergent.sh` → connect repo → "Deploy"
3. **IMPORTANT** — Emergent does *not* auto-provision MongoDB. Configure a [MongoDB Atlas free cluster](https://www.mongodb.com/cloud/atlas/register) and set these env vars on your deployment:
   - `MONGO_URL` (Atlas connection string)
   - `ENV=BETA`
   - `JWT_SECRET`
   - `EMERGENT_LLM_KEY`, `PIXABAY_API_KEY`, `SARVAM_API_KEY`
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
- **Content moderation** on all user-generated text + images + videos (blocklist + Gemini vision)
- Tier-gated endpoints via middleware (e.g., Motion Control → Creator/Pro only)
- No sensitive data in logs

---

## 🛣️ Roadmap

### V1.0 (Shipped — Feb 2026) ✅
- Premium Neon Glass UI across 12 screens
- Creative Plan Engine
- Marketplace + Inspiration Reels
- Subscription tiers + Onboarding carousel
- Auto-seed on startup

### V2.0 (In Progress)
- 💬 ChatGPT-style Prompt Selection UI (3 AI-generated prompt cards per idea)
- 🧩 Backend modular refactor (split `server.py` into `routes/*`)
- ☀️ Light Mode theme
- 🎥 Auto-preview MP4 renderer for marketplace templates

### V3.0 (Future)
- Custom voice cloning (user uploads 15s sample)
- In-app video editor (trim / caption / overlay)
- Social sharing (direct to Instagram Reels / TikTok)
- Batch generation (1 idea → 5 variations)
- Web app (same codebase via React Native Web)

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/amazing-thing`)
3. Run backend + frontend locally (see Quick Start)
4. Add tests if you're touching core logic
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
- **Expo** — for making cross-platform mobile actually pleasant

---

**Built with 💜 by [dbamkj](https://github.com/dbamkj) — Emergent Builders Contest 2026**
