# MagiCAi Studio — Handoff for Next Agent Session

> Created at end of session 2026-04-26 by main agent. Context window was getting heavy after Phase 5b polish. The work below is **NOT yet started** but **fully scoped** so the next agent can pick up cleanly.

---

## ✅ What's been DONE (current state — verified working)

### Home screen (matches SL1 reference at ~85%)
- Header: hamburger (left) + clean MagiCAi wordmark+logo (center) + 🪙 credits pill (right, no + button)
- Auto-rotating glass hero carousel (3 slides: Magic / Avatar / Divine Transform) with dot indicators
- Quick Access (3 image-bg tiles): Templates / Avatar Studio / AI Tools
- Trending Templates horizontal scroll w/ NEW/HOT/TRENDING badges + center play overlay + uses count
- Featured Tool: Divine Transform card with crown icon
- Go Premium gradient banner (pink→orange) + Upgrade Now
- Library card → My Projects
- Compact legal footer

### Bottom Tab Bar (`src/components/BottomTabBar.tsx`)
- Floating glass bar — Home / Templates / **+ Create FAB (raised gradient)** / Library / Profile
- Tapping FAB opens Quick-Action Sheet (Reel / Avatar / Voice)
- 100px scroll padding added to all 5 screens with the bar

### Subscription page
- 3-tab cycle toggle: **Monthly / Annual / Credits (one-time)** — Credits tab navigates to `/buy`
- Plan cards now show prominent 🪙 credits banner

### Auth / demo accounts (re-seeded in BETA DB)
- `demo_free@test.com` / `Test@123` (free, 30 credits)
- `demo_starter@test.com` / `Test@123` (starter, 1500 credits)
- `demo_creator@test.com` / `Test@123` (creator, 3000 credits) ← NEW
- `demo_pro@test.com` / `Test@123` (pro, 6000 credits)
- Login screen has all 4 demo quick-pick chips

### Other polish
- AuroraBackground blob opacity reduced 0.55 → 0.22 (no more bleed-through)
- Dark overlay strengthened 0.18 → 0.55
- expo-notifications warning silenced in Expo Go via `Constants.appOwnership` guard
- "Magic Hour" / "MH credits" → "MagiCAi" / "credits" rebrand
- Marketplace `Use Template` routes to `/videogen` for video templates with prompt prefilled

---

## 🚀 PENDING WORK — what next agent must build

### 🎯 PRIORITY 1 — Creative Plan Engine (NEW BACKEND FEATURE)

User's exact spec from session:

> **Problem**: Pixabay videos don't match the idea, voice sounds like plain reading, output feels disconnected.
>
> **Solution**: For every user input (idea or template), generate structured Creative Plan JSON:
> ```json
> {
>   "hook": "...",
>   "script": ["scene1 voiceover", "scene2 voiceover"],
>   "scene_keywords": ["krishna flute", "vrindavan garden"],
>   "voice_style": "devotional warm slow",
>   "bgm_style": "indian classical flute",
>   "mood": "spiritual"
> }
> ```

**Implementation**:
1. **Backend route**: `POST /api/creative-plan` (in `/app/backend/routes/wizard.py` or new `creative_plan.py`)
   - Body: `{ idea?: string, template_id?: string, language?: string, duration?: int }`
   - Uses Emergent LLM key + GPT-4o-mini via `emergentintegrations`
   - Returns the JSON above + `creative_plan_id` (cache in Mongo `creative_plans` collection)
2. **Frontend wiring**:
   - In `/app/frontend/app/create-wizard.tsx` step 1 → call `/api/creative-plan` after user enters idea (with debounce)
   - Show preview of hook/script in step 2
   - Pass `creative_plan_id` into `/api/wizard/generate` payload
3. **Pixabay integration**:
   - In wizard generation, replace raw prompt with `scene_keywords` for Pixabay search
   - Fetch best 2-3 clips matching keywords
4. **Voice generation**:
   - Pass `voice_style` to TTS engine for emotional delivery
   - Add SSML pauses between script lines
5. **BGM matching**:
   - Use `bgm_style` to pick from `/app/backend/assets/bgm/` library

**Test before shipping**: backend testing agent on the new route.

---

### 🎯 PRIORITY 2 — Marketplace template re-seed (FIXES P0)

Templates in DB are missing `plan_tier` and rich prompts. User says "old templates not restored, no plan tags, prompts not fully filled".

**Action**:
1. Edit `/app/backend/scripts/seed_marketplace.py` — add `plan_tier` field (free / creator / pro) for each of the 24 templates
2. Each template must have:
   - 3 rich `prompts[]` (not just tagline)
   - `plan_tier` field
   - `wizard_payload` populated with full creative plan inputs
3. Add `seed_force=True` flag to overwrite existing
4. Frontend: marketplace card displays `plan_tier` badge (Free/Creator/Pro pill on top-left of each card)

---

### 🎯 PRIORITY 3 — Full UI System Redesign (matches user's apimg1.jpeg + apimg2.jpeg)

User shared 12-screen reference. Apply same Aurora+Glassmorphism design system across:

| # | Screen | File | Key changes |
|---|---|---|---|
| 1 | Splash | `src/AnimatedSplash.tsx` | Already polished — 1.5s logo fade. User wants 4s (extend duration). |
| 2 | Onboarding | NEW `app/onboarding.tsx` | "Create Stunning Reels in Seconds" + dot pagination + Next button |
| 3 | Login/Sign Up | `app/login.tsx` | Welcome Back! + Continue with Google/Apple buttons + email/password + gradient Sign In |
| 4 | Home | `app/index.tsx` | At ~85% — needs hero polish (bigger Krishna image, gradient title accent, pinker quick-access tiles) |
| 5 | Templates Marketplace | `app/marketplace.tsx` | Search bar + category chips (All/Trending/Love/Festival/Funny) + 2-col grid w/ NEW/HOT pills |
| 6 | Avatar Studio | `app/cartoon-avatar.tsx` | Large circular avatar preview + Style chips (Cartoon/Realistic/3D) + Expression emoji row |
| 7 | AI Video Generator | `app/videogen.tsx` | Idea textarea + Voice Style/Language/Length dropdowns + gradient Generate button |
| 8 | Preview & Export | `app/projects/[id].tsx` (or create) | Free/Pro toggle + video player + Download Free / Upgrade to Pro CTAs |
| 9 | Subscription | `app/subscription.tsx` | Basic/**Pro highlighted**/Ultra cards (₹49 wk / ₹199 mo / ₹499 mo) + checkmark features + bottom Continue |
| 10 | Credits Purchase | `app/buy.tsx` | "Your Credits 🪙 120" header + 4 packs (100/250/500/1000) with Popular & Best Value pills + Continue |
| 11 | Library / My Projects | `app/projects.tsx` | Filter chips (All/Videos/Images) + project cards with thumb + kebab menu |
| 12 | Profile / Settings | `app/profile.tsx` | Avatar circle + John Doe header + clean menu list (My Account / Subscription / Purchase History / Settings / Help / About / **Logout in red**) |

**Design tokens** (already defined in `/app/frontend/src/theme.ts`):
- Aurora bg: `#0F0C29 → #24243E → #302B63`
- Brand gradient: `#FF4D8D → #FF9A3C → #FBBF24`
- Glass: `rgba(255,255,255,0.06)` bg + `rgba(255,255,255,0.14)` border + BlurView intensity 30-40
- Card radius: 16-20px
- Typography: System font, weights 600/800/900

---

### 🎯 PRIORITY 4 — Light Mode (BONUS)

- Create `src/ThemeContext.tsx` with `useColorScheme()` + AsyncStorage persistence
- Light tokens: pastel aurora gradients, white glass `rgba(255,255,255,0.7)`, dark text `#1A1A1A`
- Toggle in Profile screen → Preferences section

---

## 🔧 Tech Stack & Constraints

- Expo SDK 53, React Native 0.79, expo-router file-based
- Backend: FastAPI + MongoDB (BETA db: `magicai_beta`)
- LLM: Emergent LLM key (works with OpenAI text/image, Gemini text/Nano Banana, Claude text)
- Razorpay test mode for payments
- Pixabay key set in backend `.env`
- DO NOT modify `EXPO_PACKAGER_PROXY_URL`, `EXPO_PACKAGER_HOSTNAME`, `MONGO_URL`, `metro.config.js`

---

## ⚠️ Known issues NOT yet addressed

1. **Home doesn't fully match apimg1 #4** — needs bigger Krishna image (60% wider), bigger "Magic" pink accent text (font-size 40+), more vibrant Quick Access tile colors (solid-fill instead of image+tint).
2. **Marketplace templates missing plan_tier badges** — DB needs reseed.
3. **Wizard prompt prefill incomplete** — only tagline, not 3-prompt array.
4. **Voice sounds robotic** — needs Creative Plan Engine + SSML pauses.
5. **Pixabay videos don't match idea** — needs scene_keywords from Creative Plan Engine.
6. **Many admin/internal screens still use legacy theme** — need Aurora rollout: `/admin`, `/legal`, `/lipsync`, `/redub`, `/explore-tools`, `/headswap`, `/faceswap`, etc.

---

## 📂 Key file references

```
/app/backend/
  ├── server.py                    (~4000 lines, needs refactor — split routes)
  ├── routes/wizard.py             (will host /api/creative-plan)
  ├── routes/marketplace.py
  ├── routes/payments.py
  ├── core/billing.py
  ├── core/pricing.py
  ├── scripts/seed_beta_users.py   (run with ENV=BETA python scripts/seed_beta_users.py)
  └── scripts/seed_marketplace.py  (needs plan_tier additions)

/app/frontend/
  ├── app/index.tsx                (Home — at ~85%)
  ├── app/_layout.tsx              (Splash + Auth init)
  ├── app/marketplace.tsx
  ├── app/subscription.tsx         (3-tab cycle toggle done)
  ├── app/buy.tsx                  (Credits purchase, needs polish)
  ├── app/login.tsx                (4 demo chips done)
  ├── app/create-wizard.tsx        (will integrate Creative Plan Engine)
  ├── app/videogen.tsx
  ├── app/cartoon-avatar.tsx
  ├── app/projects.tsx
  ├── app/profile.tsx
  ├── src/AuroraBackground.tsx     (opacity reduced)
  ├── src/components/BottomTabBar.tsx (FAB + Quick Action Sheet)
  ├── src/AnimatedSplash.tsx
  ├── src/theme.ts                 (Aurora design tokens)
  └── src/usePushNotifications.ts  (Expo Go guard added)
```

---

## 🎬 Suggested Order for Next Agent

1. **Read this doc** + `/app/test_result.md` (last 200 lines = recent agent comm)
2. **Run** `cat /app/memory/test_credentials.md` to get fresh demo credentials
3. **Confirm with user**: "Should I tackle Creative Plan Engine first or full UI redesign first?"
4. **If Engine first** (recommended): integration_playbook_expert_v2 for OpenAI GPT-4o-mini → build route → wire wizard → backend test → frontend visual confirm
5. **Then UI redesign**: 1 screen at a time, screenshot+confirm with user before moving on
6. **Marketplace re-seed**: edit script, run, verify badges show

---

Good luck! 🚀 The user is detail-oriented and will share screenshots when something looks off. Take your time on each screen — they care about pixel-level match to apimg1/apimg2.
