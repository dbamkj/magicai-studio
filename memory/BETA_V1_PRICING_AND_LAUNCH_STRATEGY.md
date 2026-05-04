# MagiCAi Studio — Pricing, Feature Matrix & Launch Strategy

> Generated 2026-05-04 · Updated with actual MH Creator bill of ₹1,350/mo.
> Treat this as a living doc — update as economics shift (MH rates,
> Razorpay/GST, Sarvam pricing, feature mix).

---

## 0. Cost Anchor — what 1 credit really costs you

| Item                            | Value                 |
|---------------------------------|-----------------------|
| MH Creator plan cost (your actual bill) | **₹1,350 / month** |
| MH credits available            | 10,000 / month        |
| **Raw cost per MH credit**      | **₹0.135 / credit**   |
| Reserve buffer (20%)            | 2,000 credits         |
| **Sellable credits / month**    | **8,000**             |
| Cost of sellable credits        | **₹1,080 / month**    |

> **This is a 3× better cost structure than my earlier ₹0.41/credit estimate.**
> Net effect: every margin number in the old doc gets ~3× more profitable.
> This is now a healthy SaaS unit economics lane, not a marginal one.

**Why the 20% reserve:**
1. **Add-on credit purchases** — power users buying top-ups mid-month
2. **MH retries / wasted polls** — failed jobs bill ~10–20% of their cost
3. **Internal QA / regenerations** — when you re-render for CS goodwill
4. **Procedural pipeline fallback margin** — if the local Wizard fails and falls back to MH, you need headroom

---

## 1. 📋 Feature Matrix — what's built, what bills, which tier gets it

### Legend
- 🟢 = included in tier
- 🔒 = gated / upgrade required
- ⚪ = N/A for this tier
- **MH** = consumes Magic Hour credits (hits your ₹1,350/mo budget)
- **EMG** = uses Emergent LLM Key (free to you — doesn't hit MH)
- **LOCAL** = ffmpeg / Pixabay / edge-tts (zero marginal cost)
- **SARVAM** = Sarvam AI (₹1 / 1,000 chars ≈ ₹0.02 per voice line)

### 1.1 Pricing row (for reference across the matrix)

| Plan       | ₹ Price / mo | Credits / mo  | ₹ / credit sold | Your MH COGS (100% redemption) | Your MH COGS @ 35% redemption |
|------------|--------------|---------------|-----------------|--------------------------------|-------------------------------|
| **Free**       | 0            | 300           | —               | ₹41                            | ₹14                           |
| **Starter**    | ₹249         | 1,500         | ₹0.166          | ₹202                           | ₹71                           |
| **Creator** ⭐  | ₹599         | 3,000         | ₹0.200          | ₹405                           | ₹142                          |
| **Pro**        | ₹1,499       | 6,000         | ₹0.250          | ₹810                           | ₹284                          |

> **Existing credit grants preserved** (your current schema: 300/1500/3000/6000).
> See §4 for revised pricing if you want to raise prices — the current ones
> are already healthy at the corrected cost basis.

### 1.2 Core creation features

| # | Feature | Cost type | Per-use cost (MH credits unless noted) | Free | Starter | Creator | Pro |
|---|---------|-----------|----------------------------------------|------|---------|---------|-----|
| 1 | **Creator Wizard (0-MH instant reel)** | LOCAL + EMG | 0 MH (Pixabay + edge-tts + FFmpeg) | 🟢 480p + watermark | 🟢 720p | 🟢 720p | 🟢 1080p |
| 2 | **Creative Plan Engine** (`/creative-plan`) | EMG | 0 MH (GPT-4o-mini) | 🟢 3/day | 🟢 unlimited | 🟢 unlimited | 🟢 unlimited |
| 3 | **V2 Prompt Generator** (`/generate-prompts`) | EMG | 0 MH (GPT-4o-mini) | 🟢 5/day | 🟢 unlimited | 🟢 unlimited | 🟢 unlimited |
| 4 | **Scene Suggestor** (`/suggest-scenes`) | EMG | 0 MH (Gemini 2.5) | 🟢 | 🟢 | 🟢 | 🟢 |
| 5 | **Lip Sync (MH)** (`/create-lipsync`) | **MH** | 7 / sec · min 5s (35 cr min-billed) | 🔒 | 🟢 | 🟢 priority | 🟢 priority + 1080p |
| 6 | **Face Swap — Photo** (`/create-faceswap`) | **MH** | 6 / image | 🔒 | 🟢 | 🟢 | 🟢 |
| 7 | **Face Swap — Video** (`/create-faceswap`) | **MH** | 3 / sec · min 5s (15 cr min-billed) | 🔒 | 🟢 | 🟢 | 🟢 |
| 8 | **Head Swap** (`/create-headswap`) | **MH** | 10 / image | 🔒 | 🟢 | 🟢 | 🟢 |
| 9 | **Body Swap / Outfit Swap** (`/create-bodyswap`) | **MH** | 10 / image | 🔒 | 🟢 | 🟢 | 🟢 |
| 10 | **AI Image Generator — FLUX Schnell** | **MH** | 5 / image | 🟢 5/day | 🟢 | 🟢 | 🟢 |
| 11 | **AI Image Generator — FLUX Dev** | **MH** | 6 / image | 🔒 | 🟢 | 🟢 | 🟢 |
| 12 | **AI Image Generator — FLUX Pro** | **MH** | 10 / image | 🔒 | 🔒 | 🟢 | 🟢 |
| 13 | **Text-to-Video — Kling Lite** | **MH** | 60 / sec · min 5s (300 cr min) | 🔒 | 🟢 | 🟢 | 🟢 |
| 14 | **Text-to-Video — Kling 2.5 (Studio)** | **MH** | 80 / sec · min 5s (400 cr min) | 🔒 | 🔒 | 🟢 | 🟢 |
| 15 | **Text-to-Video — Kling 3.0 / Veo** | **MH** | 120 / sec · min 5s (600 cr min) | 🔒 | 🔒 | 🔒 | 🟢 |
| 16 | **Image-to-Video (Kling)** | **MH** | 60–120 / sec | 🔒 | 🟢 | 🟢 | 🟢 |
| 17 | **Video-to-Video Style Transfer** | **MH** | 50–70 / sec | 🔒 | 🔒 | 🟢 | 🟢 |
| 18 | **Video Re-dub** (`/redub`) | **MH** | 7 / sec | 🔒 | 🟢 | 🟢 | 🟢 |
| 19 | **AI BG Lipsync** (character + scene + dialogue) | **MH** | 7/sec lipsync + 60/sec video ≈ 67/sec combo | 🔒 | 🔒 | 🟢 | 🟢 |
| 20 | **Talking Avatar (MH lipsync)** | **MH** | 60 / sec · min 5s (300 cr min) | 🔒 | 🟢 | 🟢 | 🟢 |
| 21 | **Idea Image (preset deity/outfit)** | **MH** | 5 / image (FLUX Schnell) | 🟢 5/day | 🟢 | 🟢 | 🟢 |
| 22 | **Divine Transform** (`/divine`) | **MH** | ~80 / transform | 🔒 | 🔒 | 🟢 | 🟢 |

### 1.3 Avatar & Cinematic Engine (4-phase)

| # | Feature | Cost type | Per-use cost | Free | Starter | Creator | Pro |
|---|---------|-----------|--------------|------|---------|---------|-----|
| 23 | **Cartoon Avatar (Nano Banana)** (`/avatar/cartoonize`) | EMG | 0 MH (Gemini 2.5 Flash, Emergent key) | 🟢 3/day + watermark | 🟢 10/day | 🟢 unlimited | 🟢 unlimited + 1080p |
| 24 | **Procedural Solo Lipsync** (FFmpeg mouth animator) | LOCAL | **0 MH — fully local** | 🟢 watermark | 🟢 | 🟢 | 🟢 1080p |
| 25 | **Procedural Dual Lipsync** (2-char split-screen) | LOCAL | **0 MH — saves ~600 MH credits/reel vs MH lipsync** | 🔒 | 🟢 | 🟢 | 🟢 |
| 26 | **Cinematic Presets catalog** (6 presets) | metadata | 0 | 🟢 2 free (Funny, Emotional) | 🟢 2 free | 🟢 all 6 | 🟢 all 6 |
| 27 | **Preset — Bhakti / Cinematic / Viral / Story** | LOCAL | 0 (uses procedural pipeline) | 🔒 | 🔒 | 🟢 | 🟢 |
| 28 | **Emotion Detection** (12 emotions) | EMG | 0 MH (GPT-4o-mini) | 🟢 | 🟢 | 🟢 | 🟢 |
| 29 | **Emotion-aware TTS tinting** | LOCAL | 0 | 🟢 4 emotions | 🟢 8 emotions | 🟢 all 12 | 🟢 all 12 |
| 30 | **Camera Effects** (vignette/glow/shake/DoF/ken-burns/pan/zoom) | LOCAL | 0 (FFmpeg) | 🟢 2 effects | 🟢 4 effects | 🟢 all 7 | 🟢 all 7 |
| 31 | **Dialogue Remix** (Rewrite / Funny / Emotional / Viral) | EMG | 0 MH (GPT-4o-mini) | 🟢 3/day | 🟢 5/mo (1 style) | 🟢 unlimited all styles | 🟢 unlimited all styles |
| 32 | **Before/After Free vs Pro toggle** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |

### 1.4 Voice library

| # | Feature | Cost type | Per-use cost | Free | Starter | Creator | Pro |
|---|---------|-----------|--------------|------|---------|---------|-----|
| 33 | **Voice catalog (43 voices)** (`/voices`) | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 34 | **edge-tts voices (36)** Hindi/English/Baby | LOCAL | **0** | 🟢 | 🟢 | 🟢 | 🟢 |
| 35 | **Sarvam Premium voices (7)** | SARVAM | ~₹0.02 / voice line (by char count) | 🔒 | 🟢 1 voice | 🟢 all 7 | 🟢 all 7 |
| 36 | **Voice Preview** (`/preview-voice`) | LOCAL/SARVAM | ~₹0.01 cached | 🟢 | 🟢 | 🟢 | 🟢 |
| 37 | **Voice Styles catalog** (devotional/motivation/story/funny/neutral) | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 38 | **Pseudo-effect voices** (baby/deep/young) | LOCAL | 0 | 🟢 | 🟢 | 🟢 | 🟢 |

### 1.5 Marketplace & discovery

| # | Feature | Cost type | Per-use cost | Free | Starter | Creator | Pro |
|---|---------|-----------|--------------|------|---------|---------|-----|
| 39 | **Marketplace Templates** (26 curated) | metadata | 0 to browse | 🟢 browse all | 🟢 | 🟢 | 🟢 |
| 40 | **"Use Template"** (spawns wizard job) | LOCAL + EMG | 0 MH (wizard path) | 🟢 Free-tier templates only | 🟢 Free + Starter | 🟢 Free + Starter + Creator | 🟢 all tiers |
| 41 | **Template preview MP4s** (100% coverage) | LOCAL | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 42 | **Trending / Pattern Lab feed** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 43 | **Pattern Lab flag-for-moderation** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 44 | **Viral Dialogues catalog** (100 one-liners) | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 45 | **Festival Packs** (Janmashtami/Shivratri/Navratri) | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |

### 1.6 Infrastructure features

| # | Feature | Cost type | Per-use cost | Free | Starter | Creator | Pro |
|---|---------|-----------|--------------|------|---------|---------|-----|
| 46 | **Account — /usage, /credits-info, /mh-models** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 47 | **Catalog — /voices, /sound-effects, /voice-styles, /motion-presets** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 48 | **Library / My Projects** (`/projects`) | metadata | 0 | 🟢 last 10 projects | 🟢 last 50 | 🟢 unlimited | 🟢 unlimited + export CSV |
| 49 | **Subscription + Credits purchase** (Razorpay) | metadata | 0 | 🟢 view only | 🟢 | 🟢 | 🟢 |
| 50 | **Add-on credit top-ups** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 51 | **Push notifications** | LOCAL | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 52 | **Login (email + JWT + Google SSO)** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 53 | **Profile / Settings / Purchase History** | metadata | 0 | 🟢 | 🟢 | 🟢 | 🟢 |
| 54 | **Admin Panel** (5 tabs) | metadata | 0 | ⚪ admin-only | ⚪ | ⚪ | ⚪ |
| 55 | **Content Moderation** (blocklist + Gemini vision) | EMG | 0 MH (runs on every upload) | 🟢 auto | 🟢 auto | 🟢 auto | 🟢 auto |
| 56 | **Upload Safety Guardrails** (magic-byte + size checks) | LOCAL | 0 | 🟢 | 🟢 | 🟢 | 🟢 |

### 1.7 Output quality & export

| # | Feature | Free | Starter | Creator | Pro |
|---|---------|------|---------|---------|-----|
| 57 | **Watermark** | ✅ applied | ❌ removed | ❌ removed | ❌ removed |
| 58 | **Max resolution** | 480p | 720p | 720p (1080p for image outputs) | **1080p** |
| 59 | **Priority queue** | ⚪ | ⚪ | 🟢 | 🟢 |
| 60 | **Batch generation** (1 idea → 5 variations) | ⚪ | ⚪ | 🔒 V3 | 🟢 V3 |
| 61 | **Commercial license** | ⚪ | ⚪ | ⚪ | 🟢 |
| 62 | **Public API access** | ⚪ | ⚪ | ⚪ | 🟢 V3 |
| 63 | **Team seats (multi-user)** | ⚪ | ⚪ | ⚪ | 🟢 V3 |

---

## 2. Typical user journey — MH burn by tier

### A Free user (300 credits/mo cap)

Mostly stays in LOCAL/EMG lane:
| Journey step | MH credits burned |
|--------------|-------------------|
| 1 Wizard reel (60s) | 0 (Pixabay + edge-tts) |
| 1 Cartoon avatar | 0 (Emergent key) |
| 3 FLUX Schnell images | 15 |
| 1 procedural lipsync cartoon | 0 |
| **Total typical free-user MH spend / mo** | **15 credits ≈ ₹2** |

**Even at ABSOLUTE MAX redemption (300 credits), free user costs you ₹41.**
Since real redemption is 60–80%, expected cost per free user = **₹24–32 / mo**.

### A Starter user (₹249, 1,500 credits/mo)

| Journey step | MH credits burned |
|--------------|-------------------|
| 4 Wizard reels | 0 |
| 2 MH lipsyncs (30s each) | 420 |
| 1 face-swap photo | 6 |
| 10 FLUX Dev images | 60 |
| 1 Kling Lite 5s video | 300 |
| 5 cartoon avatars | 0 |
| **Typical MH spend / mo** | **~786 (52% of grant)** |

- COGS = 786 × ₹0.135 = **₹106**
- Razorpay = 2% × ₹249 = ₹5
- **Net margin = ₹138 = 55%** 🎉

### A Creator user ⭐ (₹599, 3,000 credits/mo)

| Journey step | MH credits burned |
|--------------|-------------------|
| 8 Wizard reels | 0 |
| 4 MH lipsyncs (45s avg) | 1,260 |
| 2 Kling 2.5 videos (10s) | 1,600 |
| 20 FLUX Dev + 3 FLUX Pro images | 150 |
| 2 face-swap videos (30s) | 180 |
| 15 cartoon avatars + 10 procedural lipsyncs | 0 |
| 10 dialogue remixes | 0 |
| **Typical MH spend / mo** | **~3,190 (106% — hits cap!)** |

**Creator users WILL hit their cap.** This is expected — they upgrade to Pro
or buy an add-on pack (see §3). Your effective exposure per Creator user:
- If they cap out exactly at 3,000: 3,000 × ₹0.135 = **₹405 COGS**
- Revenue ₹599, Razorpay ₹12 → **Net margin = ₹182 = 30%**

But in reality only ~45% of Creators burn their full allowance (industry
data). Real expected margin **≈ 50–55%**.

### A Pro user (₹1,499, 6,000 credits/mo)

Pros pay for headroom, not usage. Typical redemption: 25–40%.

| Journey step | MH credits burned |
|--------------|-------------------|
| 15 Wizard reels | 0 |
| 3 Kling 3.0 Pro videos (15s) | 5,400 |
| 6 MH lipsyncs (60s) | 2,520 |
| 30 mixed FLUX images | 200 |
| 40 cartoon avatars + 20 procedural | 0 |
| **Absolute max if they go hard** | ~8,120 (goes over — top-up sale!) |
| **Typical (35% redemption)** | **~2,100** |

- Typical COGS = 2,100 × ₹0.135 = **₹284**
- Razorpay = ₹30 → **Net margin = ₹1,185 = 79%** 🎉🎉

---

## 3. Add-on credit packs (upsell lane)

Because redemption > 100% is common for power users, add-on packs turn
"I hit my cap" pain into revenue.

| Pack         | ₹ Price | Credits | Effective ₹ / credit | Your cost (@ 40% redemption) | Net margin |
|--------------|---------|---------|----------------------|------------------------------|-----------|
| Top-up 500   | ₹99     | 500     | ₹0.20                | ₹27 (200 cr used)            | **₹70 = 71%** |
| Top-up 1500  | ₹249    | 1,500   | ₹0.166               | ₹81 (600 cr used)            | **₹163 = 65%** |
| Top-up 5000  | ₹799    | 5,000   | ₹0.16                | ₹270 (2,000 cr used)         | **₹514 = 64%** |
| Top-up 10000 | ₹1,499  | 10,000  | ₹0.15                | ₹540 (4,000 cr used)         | **₹935 = 62%** |

**Set a 6-month expiry on add-on credits** so unused credits don't haunt
your liability sheet forever.

---

## 4. Should you change your prices?

**Short answer: keep current prices (₹249 / ₹599 / ₹1,499) for beta.** They
already generate 55–79% net margins at the corrected ₹0.135/credit basis.

| Tier | Current | Recommended action | Why |
|------|---------|--------------------|-----|
| Free | 0 / 300 cr | ✅ keep | Funnel is more important than unit cost |
| Starter | ₹249 / 1,500 cr | ✅ keep | 55% margin, competitive in India |
| Creator | ₹599 / 3,000 cr | ✅ keep | 30–55% margin, hits users at cap (drives top-ups = extra revenue) |
| Pro | ₹1,499 / 6,000 cr | ⚠️ consider ₹1,299 OR add perks | 79% margin → room to cut to drive upgrades, OR add commercial license + API to justify |

### Alternative: tighter pricing for volume

If you want to accelerate conversions (year-1 100-user target):

| Tier | Discount-push price | New credits | Margin @ 35% redemption |
|------|---------------------|-------------|--------------------------|
| Starter | ₹199 | 1,200 | **46%** |
| Creator | ₹499 | 2,500 | **24%** ← thin, skip |
| Pro | ₹999 | 5,000 | **54%** |

**Verdict**: don't discount Creator — it's already your mid-tier sweet spot.
Either keep everything OR drop Starter to ₹199 and drop Pro to ₹999 to
force more conversions.

---

## 5. Capacity / scaling triggers

### 20 paying users (Phase 1, months 1–6)

Assumed mix: 10 Free + 7 Starter + 2 Creator + 1 Pro.
- MH credits needed/mo (typical redemption):
  - 10 Free × 32 = 320
  - 7 Starter × 786 = 5,502
  - 2 Creator × 1,430 (47% redemption) = 2,860
  - 1 Pro × 2,100 = 2,100
- **Total: ~10,782 MH credits/mo**

Your sellable budget: 8,000. **Shortfall ≈ 2,800.**

### 🚨 Action before hitting 12 paying users

You will blow the 8,000 sellable cap. Three ways out (in order of preference):

1. **Push procedural features harder in UX** — make Wizard + Cartoon
   Avatar + Procedural Lipsync the default first-touch. Each user swayed
   away from MH lipsync saves ~200 credits/mo. Realistic: saves ~25–30%.
2. **Buy MH add-on credit packs** — if MH offers them at ~same unit price,
   this is the simplest lever. Cost scales linearly with revenue.
3. **Upgrade MH subscription** — check if the next tier (Studio/Pro)
   improves per-credit pricing. At ₹0.135/credit on Creator, you need MH's
   next tier to beat ₹0.11/credit to be worth the jump at 20 users.

### 100 users scale (Phase 2, months 7–12)

Assumed mix: 50 Free + 30 Starter + 15 Creator + 5 Pro.
- MH credits needed/mo: 50×32 + 30×786 + 15×1,430 + 5×2,100 = **57,550 credits/mo**

You'd need **~58k MH credits = ~₹7,830 MH cost**.

Revenue at 100 users (see §6 below) ≈ ₹28,450/mo.
**MH cost as % of revenue = 28%.** Healthy SaaS COGS target is <35%, so
you're clear.

---

## 6. Revenue projection at 100 users (50/30/15/5 mix)

| Tier     | Users | ARPU (₹/mo) | MRR contribution |
|----------|-------|-------------|------------------|
| Free     | 50    | 0           | ₹0               |
| Starter  | 30    | 249         | ₹7,470           |
| Creator  | 15    | 599         | ₹8,985           |
| Pro      | 5     | 1,499       | ₹7,495           |
| **Sub-total**  | **100** | **₹239 blended** | **₹23,950 / mo** |
| Add-on credit revenue (~19% uplift) | | | **+₹4,550** |
| **Total MRR @ 100 users** | | | **~₹28,500 / mo** |

**Costs at that scale:**
| Item                | Monthly |
|---------------------|---------|
| MH subscription (or add-ons at equivalent rate) | ~₹7,830 |
| Razorpay (~2%) | ~₹570 |
| Sarvam TTS (~8% of users using it avg 30 min/mo) | ~₹500 |
| MongoDB Atlas (M10 at this scale) | ~₹4,500 |
| Emergent LLM key (platform) | ~₹0 (or platform-included) |
| Domain + email + monitoring | ~₹500 |
| **Total variable + infra cost** | **~₹13,900** |
| **Net margin before your own time** | **~₹14,600 / mo (51%)** |

**ARR target year 1: ₹3.4 lakh (~$4,100) with ~₹1.75L margin.**

This isn't a unicorn — it's an indie SaaS lane that comfortably funds your
MH bill, MongoDB, and a part-time CS hire by month 10.

---

## 7. Beta v1 Launch Plan — 50 users on the waitlist

### Phase A: Pre-launch (week 0)
- [ ] Tag `v1.0-beta` in git
- [ ] Build production landing page with email-capture form that POSTs to
      `/api/waitlist-signup` (you still need to build this endpoint)
- [ ] Write a 90-second demo video showing: idea → reel in 60s + cartoon
      avatar with lipsync
- [ ] BETA mode badge pinned ("BETA v1 — invite only")

### Phase B: Waitlist build (weeks 1–2, target 50 signups)

| Channel | Effort | Likely signups |
|---------|--------|----------------|
| Twitter/X build-in-public thread w/ demo video | 4h | 10–25 |
| ProductHunt "Coming Soon" page | 2h | 8–15 |
| 3 niche Reddit posts (r/IndianGaming, r/SmallYTChannels, r/IndianCreators) | 6h | 15–30 |
| WhatsApp / Telegram broadcast to your network | 2h | 10–20 |
| 2 Indian creator Discord servers | 3h | 5–15 |
| Single LinkedIn post with demo video | 1h | 5–10 |
| **Total expected** | **~18h** | **53–115 signups** |

→ Hitting 50 is realistic in 10–14 days.

### Phase C: Beta v1 invites (weeks 3–8, capped 20 users)
- Send invites in **batches of 5** every 5 days
- Mix: **8 Free + 7 Starter + 3 Creator + 2 Pro**
- Track per user: time-to-first-reel, time-to-aha, feature usage
  histogram, NPS after 5th reel
- Watch metrics daily: MH burn rate (alert at 300/day), p95 latency, 5xx error rate

### Phase D: Beta v1 retro (week 8)
1. Which 3 features got >70% usage? → Hero features
2. Which 3 features got <10% usage? → Kill or hide
3. Tier-by-tier "I'd pay more if you added X" → Pro upgrade path
4. MH burn per ARPU rupee? Target <30% (you'll likely be at 25–30%)
5. Free → Starter conversion rate? Target >8%

---

## 8. Production v1 Launch (after beta retro is green)

**Trigger criteria — DO NOT launch prod until:**
- [ ] NPS ≥ 35 from beta
- [ ] Zero P0 bugs open for >7 days
- [ ] p95 < 8s Wizard generate, < 25s cartoonize
- [ ] At least 3 beta users have **paid** (no free upgrades)
- [ ] 0% data loss in 30 days
- [ ] Razorpay live mode keys + KYC done
- [ ] Privacy + T&Cs lawyer-reviewed (~₹5,000 one-time)
- [ ] App Store / Play Store listings reviewed

**Launch week:**
1. **Mon** — Flip env BETA→PROD, swap Razorpay test→live, email blast
2. **Tue** — ProductHunt launch (fresh post around 12:01am PT)
3. **Wed** — Reddit post-mortem in 2 communities
4. **Thu** — Twitter recap thread + RT beta user reels
5. **Fri** — First weekly newsletter
6. Weekend — monitor + <4h support response

**Goal**: 50 waitlist + PH visibility → 30 paid signups.

---

## 9. Post-beta — hybrid scaling plan (12 months to 100 users)

**Recommendation: HYBRID — scale users in waves, ship 1 hero feature per wave.**

| Month | Cohort | New feature (1 max) | Why |
|-------|--------|---------------------|-----|
| 1 | Beta v1 (20) | 0 — stabilize | Prove zero data loss |
| 2 | Beta v1 | Light Mode toggle | Low-risk polish |
| 3 | Beta v2 (35) | Onboarding + Premium UI redesign | UX conversion |
| 4 | Beta v2 | Watermark FFmpeg pipeline | Closes Free→Pro gap |
| 5 | Beta v2 | Low-res 3s draft preview | Reduces wasted gens |
| 6 | Production v1 (60) | Marketplace plan_tier reseed | Drives template usage |
| 7 | Production v1 (75) | Public API access (Pro) | New $$$ angle |
| 8 | Production v1 | Brand asset library (Pro) | vs Veed differentiator |
| 9 | Production v1 (90) | Hindi UI localisation | Expands TAM |
| 10 | Production v1 | Auto-post to YT Shorts / Reels | Retention feature |
| 11 | Production v1 (100) | Team accounts | Agency lane |
| 12 | **Year-1 review** | None — stabilize, cut weak features | NPS/churn/margin audit |

Each wave gets **one Twitter-worthy feature update** — the sales excuse to
ping past-waitlist drop-outs.

---

## 10. AI agents as testers (vs real humans)

### TL;DR — 80% AI + 15% paid humans + 5% wildcards

### AI agents are GREAT at
- API contract + regression tests
- End-to-end flow validation (Playwright)
- Multi-language smoke (Hindi vs English)
- Load + concurrency probing
- Visual regression (pixel-diff)
- Edge-case fuzzing
- Perf budget / p95 latency checks
- Response shape + spec compliance

### AI agents are MEDIOCRE at
- "Does this feel premium?" (subjective)
- "Is the reel watchable?" (aesthetic)
- "Would I pay for this?" (real wallet)
- Onboarding confusion assessment
- Cultural / devotional appropriateness
- Pricing perception
- Exploratory bug discovery (humans wander; agents follow scripts)

### Practical launch plan
- **80% AI agent tests** — `deep_testing_backend_v2` on every PR,
  `expo_frontend_testing_agent` weekly + before each cohort wave
- **15% paid human testers** — 3 × ₹500 running a 20-step script before
  each cohort onboarding
- **5% wildcards** — 2 trusted early-access users with no script

### Tooling stack to layer on top
- **Maze.co** — automated user testing with humans (~$25/test)
- **Playwright Cloud / BrowserStack** — run agent scripts against staging every 4h
- **Sentry** — automatic error capture; pair with `troubleshoot_agent` for RCA loops
- **Promptfoo / OpenAI Evals** — LLM output quality grading at scale (esp. Creative Plan Engine + emotion detector)
- **Better Uptime** — synthetic monitoring every 5min against prod
- **Skip a dedicated QA hire until ~250 paying users**

---

## 11. Definition of Done — Beta v1 ready to open the door

- [ ] Phase-B refactor complete (server.py <2,500 LOC — currently 3,335)
- [ ] Marketplace templates have `plan_tier` tags
- [ ] Premium Neon Glass UI rolled across 12 hero screens
- [ ] Onboarding screen built
- [ ] Watermark pipeline live for free tier
- [ ] Razorpay LIVE mode keys + KYC
- [ ] Privacy + T&Cs reviewed
- [ ] Sentry + Better Uptime wired
- [ ] Demo video recorded
- [ ] Waitlist landing page live and collecting emails
- [ ] First 5 beta invites sent

When **9/11** green → open the door.

---

## 12. Quick-reference cheat sheet

### Your margins at a glance (corrected ₹0.135/credit)

| Tier      | Price  | Typical MH spend | MH COGS | Razorpay | **Net margin** |
|-----------|--------|------------------|---------|----------|----------------|
| Starter   | ₹249   | 786 credits      | ₹106    | ₹5       | **₹138 (55%)** |
| Creator ⭐ | ₹599   | 1,430 credits    | ₹193    | ₹12      | **₹394 (66%)** |
| Pro       | ₹1,499 | 2,100 credits    | ₹284    | ₹30      | **₹1,185 (79%)** |

### Break-even math
- MH subscription = ₹1,350/mo
- First paid user at any tier → you're already ~40% covered on MH bill
- **2 Starter users ≈ covers your entire MH bill**
- 1 Pro user ≈ covers your entire MH bill **with ₹165 profit to spare**

### Feature-cost mental model
- 🟢 Wizard reel = **FREE to you** (Pixabay + edge-tts + ffmpeg)
- 🟢 Cartoon avatar = **FREE to you** (Emergent LLM key)
- 🟢 Procedural lipsync = **FREE to you** (ffmpeg local)
- 🟠 FLUX image = cheap (~₹0.68/image)
- 🔴 MH lipsync 30s = ~₹28 per run
- 🔴 Kling 3.0 15s = ~₹243 per run ← push users to this only if they pay for it

---

*End of strategy doc. Updated 2026-05-04 with actual MH Creator bill
₹1,350/mo. Next refresh suggested: end of Beta v1 retro (week 8).*
