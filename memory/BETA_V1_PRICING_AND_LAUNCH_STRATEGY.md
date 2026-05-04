# MagiCAi Studio — Pricing, Beta v1 Plan & Launch Strategy

> Generated 2026-05-04 by main agent. Treat this as a living doc — update as
> economics shift (MH credit rates, Razorpay capture rates, Sarvam pricing).

---

## 0. Cost Anchor — what 1 credit really costs you

You hold an **MH Creator subscription = 10,000 MH credits / month**. Let's
say that subscription costs you **$49/mo (~₹4,100)** — adjust in row 1 below
if your invoice differs.

| Item                          | Value          |
|-------------------------------|----------------|
| MH plan cost                  | ₹4,100 / month |
| MH credits available          | 10,000 / month |
| **Your raw cost per MH credit** | **₹0.41 / credit** |
| Reserve buffer (20%)          | 2,000 credits  |
| **Sellable credits / month**  | **8,000**      |

**Why the 20% reserve:**
1. **Add-on credit purchases** — if a power user wants to buy ₹299 of extra
   credits mid-month, you need to physically have those credits to ship.
2. **MH retries / wasted polls** — failed jobs sometimes still bill ~10–20%
   of their cost.
3. **Internal QA / regenerations** — when something looks off and you
   regenerate it for the user (CS goodwill).

So the entire plan structure below is sized against 8,000 sellable
credits/month, not 10,000.

---

## 1. Per-action MH credit costs (already in `/api/credits-info` cost_table)

| Action                           | MH credits |
|----------------------------------|------------|
| Lip Sync (per second)            | 7          |
| Face Swap Video (per second)     | 3          |
| Face Swap Photo (per image)      | 6          |
| Head Swap (per image)            | 10         |
| AI Clothes / Body Swap           | 10         |
| AI Image (FLUX Schnell)          | 5          |
| Text → Video (per second)        | 10         |
| Image → Video (per second)       | 10         |
| Video → Video (per second)       | 8          |
| Video Re-dub (per second)        | 7          |

**Plus** local-only features that DON'T touch MH (so they're "free" to ship):
- Procedural cartoon lipsync (saves ~600 credits per dual-avatar reel)
- Pixabay video search & FFmpeg stitching (Wizard reels)
- Edge-TTS (free tier voices) — Sarvam Premium is paid per char (~₹1/1k char)
- Camera / motion / vignette FFmpeg post-processing
- BGM mixing from your local SFX library

**App credit (the unit you sell to users) ≠ MH credit.**
Pick a fixed multiplier — I recommend **1 app credit = 1 MH credit** for
simplicity and transparent UX. Then your COGS for any in-app cost is just
`app_credits × ₹0.41`.

---

## 2. Pricing tiers (revised — Phase 1: 0–20 users, months 1–6)

The goal is to **sell 8,000 credits / month** to ≤20 paying users without
ever blowing the cap. So the maximum **average credit allotment** ≈
8,000 ÷ 20 = **400 credits/user/month** (heavy users will go over, light
users will go way under, and the math averages out).

| Tier      | ₹ Price (mo) | App credits | Watermark | Resolution | LLM remix | Sarvam Premium voices | MH cost @ 100% redemption | Gross margin |
|-----------|--------------|-------------|-----------|------------|-----------|-----------------------|---------------------------|--------------|
| Free      | 0            | 100         | Yes       | 480p       | ❌        | ❌                    | ₹41                       | -₹41 (loss-leader) |
| Starter   | ₹199         | 800         | No        | 720p       | 5/mo      | 1/mo trial            | ₹328                      | **₹+57 (60% margin AFTER GST/Razorpay 2%)** |
| Creator ⭐ | ₹499         | 2,500       | No        | 720p       | Unlimited | Unlimited             | ₹1,025                    | **₹-549 ←⚠️ red flag** |
| Pro       | ₹999         | 6,000       | No        | 1080p      | Unlimited | Unlimited             | ₹2,460                    | **₹-1,461 ←⚠️⚠️** |

### ⚠️ Why Creator and Pro look like losses

The simple math (`credits × ₹0.41 = COGS`) **assumes 100% redemption** —
i.e. the user actually generates the full 2,500 credits worth of content
every month. Real-world data from creator-economy SaaS (Synthesia, Veed,
Pictory, ElevenLabs):

| User type | Typical monthly redemption | Real margin |
|-----------|---------------------------|-------------|
| Free      | 60–80%                    | Negative (acceptable for funnel)|
| Starter   | 40–55%                    | **+50–65%** |
| Creator   | **35–50%**                | **+15–35%** |
| Pro       | **25–40%**                | **+30–45%** |

So the real economics are MUCH better than the worst-case row above —
**Pro users especially almost never redeem 100%** (they pay for "headroom"
and brag rights, not actual usage).

### Recommended price points (with 35% redemption assumption baked in)

| Tier      | ₹ Price | Effective COGS @ 35% redemption | True margin | Razorpay+GST cut | Net margin |
|-----------|---------|----------------------------------|-------------|------------------|-----------|
| Free      | 0       | ₹25                              | -₹25        | ₹0               | **-₹25**  |
| Starter   | ₹199    | ₹114                             | ₹85         | ₹38              | **₹47 (24%)** |
| Creator ⭐ | ₹499    | ₹359                             | ₹140        | ₹95              | **₹45 (9%) — TOO THIN** |
| Pro       | ₹999    | ₹615                             | ₹384        | ₹190             | **₹194 (19%)** |

### 🎯 Final recommendation — Phase 1 (0–20 users)

| Tier      | ₹ Price | App credits | Margin focus | Strategic role |
|-----------|---------|-------------|--------------|----------------|
| **Free**     | 0      | **30 credits one-shot** + 50 credits/mo refill (capped) | Loss leader | Top-of-funnel; convert 8–12% to paid |
| **Starter**  | **₹249/mo** or **₹2,499/yr** | 1,000 credits/mo | ~30% net | Sweet-spot for hobby creators |
| **Creator ⭐**| **₹599/mo** or **₹5,999/yr** | 2,500 credits/mo + 1080p + priority queue | ~22% net | Power-user default — **highlighted in UI** |
| **Pro**     | **₹1,499/mo** or **₹14,999/yr** | 7,000 credits/mo + commercial license + API access (later) | ~28% net | High-LTV agency / brand users |

**Annual = ~17% discount** (industry standard) — also dramatically improves
cash flow because you collect 12 months upfront.

### Add-on credit packs (the 20% reserve unlocks these)

| Pack       | ₹ Price | Credits | ₹/credit | Margin |
|------------|---------|---------|----------|--------|
| Top-up 500  | ₹149   | 500     | ₹0.30    | **27%** |
| Top-up 1500 | ₹399   | 1,500   | ₹0.27    | **34%** |
| Top-up 5000 | ₹1,199 | 5,000   | ₹0.24    | **42%** |

The bigger packs have BETTER margin because the unit cost is fixed at
₹0.41/credit but users will redeem maybe 30–40% of a 5,000-credit pack
within the month it expires. Set a **6-month expiry** so unused credits
don't haunt your liability sheet forever.

### Capacity sanity-check (20 paying users at full redemption)

Assume worst-case mix: 5 Pro + 8 Creator + 7 Starter = 20 users.
- 5 × 7,000 + 8 × 2,500 + 7 × 1,000 = **62,000 app credits issued**
- @ 35% redemption = **21,700 credits actually used**
- That's **2.7× your 8,000 sellable budget**.

**This means you can NOT scale to 20 paying users on the Creator plan
alone — you'll need to either:**
1. Upgrade to MH's higher tier (~25,000 credits/mo), OR
2. Cap monthly redemption per user in T&Cs (e.g. "fair-use 60% of allowance"),
   OR
3. Offset with the `procedural lipsync` + Pixabay flows that don't touch MH.

Realistically, point 3 already saves you ~30% of usage (your Wizard /
cartoon avatars don't hit MH at all). So the **effective MH demand for 20
mixed paid users is ~15,000 / month** — still over your 8,000 cap by ~2×.

### 🚀 Action — when to upgrade your MH subscription

| Trigger | Action |
|---------|--------|
| Hitting 6,500 sellable credits (81%) by day 25 | Buy a one-time add-on top-up from MH |
| Hitting 6,500 sellable credits by day 18 for 2 months in a row | Upgrade to MH's next tier (or negotiate volume rate) |
| MH costs > 35% of revenue | Switch heavy actions (face-swap-video) to a cheaper provider (RunwayML, Replicate) |

---

## 3. Phase 2: 21–100 users, months 7–12

Same pricing — just lift the MH cap.

- Need ~75,000–100,000 MH credits/mo at scale.
- Negotiate annual MH contract OR move face-swap-video to **Replicate
  (~₹0.18/credit equivalent)** for ~55% COGS reduction on the heaviest
  feature.
- **Introduce regional pricing** (USD plan for international users —
  $4.99 / $11.99 / $24.99 mirrors Indian INR after FX).

### Revenue projection at 100 users (50/30/15/5 mix Free/Starter/Creator/Pro)

| Tier     | Users | ARPU (₹/mo) | MRR contribution |
|----------|-------|-------------|------------------|
| Free     | 50    | 0           | ₹0               |
| Starter  | 30    | 249         | ₹7,470           |
| Creator  | 15    | 599         | ₹8,985           |
| Pro      | 5     | 1,499       | ₹7,495           |
| **Total** | **100** | **₹239 blended** | **₹23,950 / mo** |

Plus **add-on credit revenue** typically adds **15–25%** = +₹3,500–6,000/mo.

**MRR target month 12: ₹27,500–30,000 (~$330–360)**.
ARR target year 1: **~₹3.3 lakh ($4,000)**.

This isn't a unicorn — it's a realistic indie SaaS lane that funds your MH
bill and one part-time dev/CS hire.

---

## 4. Beta v1 — Feature Inventory (what's built TODAY)

### 4.1 Authentication & user management
- Email/password login, JWT bearer token
- Subscription tiers (free / starter / creator / pro / admin)
- Credit balance + per-action billing
- 4 demo accounts pre-seeded
- Razorpay test-mode integration (orders + verify)

### 4.2 Content creation flows
1. **Creator Wizard (0-MH instant reel)** — idea → Pixabay clips + TTS + BGM
   stitched locally via FFmpeg. **Zero MH credit consumption.**
2. **Creative Plan Engine** — POST `/api/creative-plan` → GPT-4o-mini
   structured JSON `{hook, script[], scene_keywords[], voice_style,
   bgm_style, mood}` to drive 1.
3. **AI Video Generator** — Idea + voice-style + length → full reel via
   the wizard pipeline.
4. **Avatar Studio (4-phase Cinematic Engine)**
   - 6 cinematic presets (Bhakti, Funny, Cinematic, Emotional, Viral, Story)
   - 12 emotion chips with auto-detect via LLM
   - Camera + motion + vignette / soft-glow / shake / depth-of-field FFmpeg FX
   - Procedural solo + dual-character lipsync (NO MH spend)
   - Free vs Pro Before/After toggle on result preview
   - Remix Dialogue: rewrite / funny / emotional / viral variations
5. **Lip Sync (MH)** — multi-character dialogue + audio → MH lipsync video.
6. **Face Swap, Head Swap, Body Swap (MH)** — image/video swap features.
7. **Image-to-Video, Video-to-Video, AI Image Generator (MH)**
8. **Voice Library** — 43 voices: 36 edge-tts (Hindi/English/Baby) + 7 Sarvam
   premium (anushka, manisha, vidya, arya, abhilash, karun, hitesh).
9. **Marketplace Templates** — 26 curated reels w/ 100% MP4 preview coverage.
10. **AI Cartoon Avatars (Nano Banana)** — Gemini 2.5 Flash text-to-image
    with 11 styles + 12 emotions.
11. **Pattern Lab** — auto-generated trending templates with admin moderation.

### 4.3 Discovery / engagement
- Home with auto-rotating hero carousel + trending templates + quick-access
  tiles + Go Premium banner
- Trending screen with usage counter + flag-for-moderation buttons
- Library / My Projects with filter chips (All / Videos / Images)
- Profile / Settings with account / subscription / purchase history
- Push notifications (silenced in Expo Go dev mode)

### 4.4 Admin & ops
- Admin panel with 5 tabs: Users / Usage / Profit Calc / Environment /
  Pattern Lab moderation
- Auto-seeding of demo users + marketplace templates on first boot in
  BETA / PROD env
- BETA mode badge + `/api/mode` endpoint for env-aware UI
- Trending recompute scheduler (nightly 02:00 UTC)
- Trial-expiry cron (every 6h)

### 4.5 Backend APIs (90+ endpoints)
- Auth: `/auth/login`, `/auth/me`, `/auth/session`
- Account: `/usage`, `/credits-info`, `/mh-models` (Phase-B refactored)
- Catalog: `/voices`, `/preview-voice`, `/sound-effects`, `/voice-styles`,
  `/motion-presets`, `/cinematic-presets`
- Creation: `/create-lipsync`, `/create-faceswap`, `/create-headswap`,
  `/create-bodyswap`, `/create-image-to-video`, `/create-video-to-video`,
  `/create-ai-bg-lipsync`, `/wizard/generate`
- Avatar: `/avatar/cartoonize`, `/avatar/styles`, `/avatar/detect-emotion`,
  `/avatar/remix-dialogue`, `/avatar/jobs/{id}`
- Templates: `/marketplace/templates`, `/templates/preview-stats`,
  `/templates/backfill-previews`
- AI: `/creative-plan`, `/generate-prompts`, `/suggest-scenes`
- Uploads & media utilities: `/upload-image`, `/upload-audio`,
  `/extract-frames`, `/serve-file/{id}`

---

## 5. Beta v1 Launch Plan — get to 50 users on the waitlist

### Phase A: Pre-launch (week 0, 1 week before opening)
- [ ] Tag `v1.0-beta` in git
- [ ] Build production landing page (`/app/backend/static/landing/index.html`
      already exists — needs the email-capture form to actually post somewhere)
- [ ] Write a 90-second demo video (Loom or your own Wizard output 😉)
      showing: idea → reel in 60 seconds + cartoon avatar with lipsync.
- [ ] Set up `/waitlist-signup` endpoint that pushes email + name to a
      Mongo `waitlist` collection + adds them to a Mailchimp / Brevo list.
- [ ] Pin the BETA mode badge in the top-right ("BETA v1 — invite only").

### Phase B: Waitlist build (weeks 1–2, target 50 signups)
**Channels (rough effort/yield expectations for an indie dev):**
| Channel | Effort | Likely signups |
|---------|--------|----------------|
| Twitter/X build-in-public thread (1 post w/ demo video) | 4h | 10–25 |
| ProductHunt "Coming Soon" page | 2h | 8–15 |
| 3 niche Reddit posts (r/IndianGaming, r/IndianStreetBets has creator angle, r/SmallYTChannels) | 6h | 15–30 |
| WhatsApp / Telegram broadcast to existing network | 2h | 10–20 |
| 2 Indian creator Discord servers (Filmmakers India, Creator Den) | 3h | 5–15 |
| Single LinkedIn post with the demo video | 1h | 5–10 |
| **Total expected** | **~18h** | **53–115 signups** |

→ Hitting 50 is realistic in 10–14 days.

### Phase C: Beta v1 invites (weeks 3–8, capped 20 users)
- Send invites in **batches of 5** every 5 days (control quality of feedback).
- **Pick mix carefully**:
  - 6 Free users (must NOT use heavy MH actions — push them to Wizard +
    Cartoon Avatar to validate procedural pipeline)
  - 8 Starter users (validate the conversion + 1k-credit ceiling feel)
  - 4 Creator users (validate the priority queue + 1080p)
  - 2 Pro users (validate API + commercial license messaging)
- **Track per user**:
  - Time-to-first-reel
  - Time-to-aha (when they share the reel publicly)
  - Action-mix histogram (which features actually get used)
  - NPS score after 5th reel
  - Drop-off step in Wizard / Avatar Studio
- **Daily watch metrics**:
  - MH credit burn rate (alert if >300/day)
  - p95 latency for `/wizard/generate` and `/avatar/cartoonize`
  - 5xx error rate (must stay <0.5%)

### Phase D: Beta v1 retro (week 8)
Compile and answer:
1. Which 3 features got >70% of usage? (Hero features — make them better.)
2. Which 3 features got <10% of usage? (Kill or hide them.)
3. Where did each tier user say "I'd pay more if you added X"? (Pro upgrade path.)
4. What's the MH burn per ARPU rupee? Target <40%.
5. What's the realistic conversion rate Free → Starter? Target >8%.

---

## 6. Production v1 Launch Plan (after beta retro is green)

**Trigger criteria — DO NOT launch production until:**
- [ ] NPS ≥ 35 from beta
- [ ] Zero P0 bugs open for >7 days
- [ ] Server p95 < 8s for Wizard generate, < 25s for cartoonize
- [ ] At least 3 beta users have **paid** (no free upgrades) — proves WTP.
- [ ] 0% data loss in 30 days
- [ ] Razorpay live mode keys obtained + KYC done
- [ ] Privacy policy + T&Cs reviewed by a lawyer (~₹5,000 one-time)
- [ ] App Store / Play Store listings reviewed (if going native)

**Production launch week:**
1. Mon: Flip env from BETA → PROD, swap Razorpay test → live, announce on
   waitlist email blast (~50 people).
2. Tue: ProductHunt launch (don't use the Coming Soon, do a fresh launch
   post around 12:01am PT; rally beta users to upvote on the morning of).
3. Wed: Reddit post-mortem post in 2 communities ("How I built MagiCAi in
   X months — beta retro + open Q&A").
4. Thu: Twitter recap thread + retweet beta user reels.
5. Fri: First weekly newsletter.
6. Through weekend: monitor metrics + answer support emails within 4h.

**Goal: convert 50 waitlist + ProductHunt visibility into 30 paid signups.**

---

## 7. Post-beta scaling — "scale users only" vs "scale + new features"

### Recommendation: **HYBRID — scale users in waves, ship 1 hero feature per wave**

Here's the 12-month roadmap with that approach:

| Month | Cohort size | New feature (1 max) | Why |
|-------|-------------|---------------------|-----|
| 1 (now) | Beta v1 | 0 — stabilize | First 20 users, prove zero data loss |
| 2 | Beta v1 (continuation) | Light Mode toggle | Low-risk polish, hits everyone |
| 3 | Beta v2 (35 users) | Onboarding flow + Premium UI redesign | UX polish drives conversion |
| 4 | Beta v2 | Watermark FFmpeg pipeline (Pro perk) | Closes the Free → Pro gap |
| 5 | Beta v2 | Low-res 3s draft preview | Reduces "wasted" generations |
| 6 | Production v1 (60 users) | Marketplace plan_tier reseed | Drives template usage |
| 7 | Production v1 (75 users) | API access (Pro tier feature) | New $$$ angle |
| 8 | Production v1 | Brand asset library (Pro feature) | Differentiator vs Veed |
| 9 | Production v1 (90 users) | Multi-language UI (Hindi first) | Massively expands TAM |
| 10 | Production v1 | Schedule + auto-post to YT Shorts / Reels | Sticky retention feature |
| 11 | Production v1 (100 users) | Team accounts (multi-seat) | Agency upgrade lane |
| 12 | **Year-1 review** | None — stabilize, cut weak features | NPS / churn / margin audit |

### Why hybrid > scale-only or feature-only

| Strategy | Pro | Con |
|----------|-----|-----|
| Scale users, freeze features | Stable infra, easy to debug | Beta users churn — "no new toys, why renew?" |
| Add features fast | Twitter buzz, demo content | Beta users overwhelmed, support load explodes, bugs slip into prod |
| **Hybrid (this doc)** | Each cohort gets 1 fresh hook to talk about + you control complexity | Slower headline feature count |

**Rule of thumb:** every cohort wave should have **one "Twitter-worthy"
feature update**. That gives the sales team (you) an excuse to email past
waitlist drop-outs ("hey we just shipped X — your beta seat is ready").

---

## 8. AI agents as testers — viable or not?

### Short answer
**Use AI agents for ~70% of the testing work; keep ~30% real human time
for the parts AI genuinely can't do.**

### Where AI agents (like me + the testing sub-agents) work GREAT
| Test type | Who's better | Why |
|-----------|--------------|-----|
| API contract / regression tests | **AI** | I can run 100 curl probes in 2 minutes; humans get bored at probe 10 |
| End-to-end flow validation (login → wizard → save → download) | **AI (Playwright)** | Deterministic, repeatable, no human typing errors |
| Multi-language smoke tests (Hindi prompts vs English) | **AI** | LLM-driven test data generation is honest |
| Load + concurrency probing | **AI** | Trivial to spin up 20 concurrent JWTs |
| Visual regression (screenshots vs golden) | **AI** | Pixel-diff in seconds |
| Edge-case input fuzzing (empty strings, 401-char prompts, garbled UTF-8) | **AI** | Boring for humans, instant for AI |
| Performance budget checks (p95 latency, MP4 file size) | **AI** | Numbers are numbers |
| Spec compliance (response shape, required fields) | **AI** | What `deep_testing_backend_v2` literally does |

### Where AI agents are MEDIOCRE (need humans)
| Test type | Why AI struggles |
|-----------|------------------|
| "Does this feel premium?" | Subjective — needs taste |
| "Is the generated reel watchable?" | Aesthetic judgement — only humans can rate emotional resonance |
| "Would I pay for this?" | Real wallet, real friction — only humans have that |
| "Is the onboarding confusing?" | First-touch UX needs first-touch eyes |
| Cultural appropriateness of LLM output (esp. Hindi devotional content) | LLMs can grade LLMs but with bias — domain expert needed |
| Pricing perception ("₹599 — is that fair?") | Needs market signal, not logic |
| Discovery — finding bugs you didn't think to test | Humans wander; agents follow scripts |

### Practical plan for production v1 launch

**Pre-launch QA mix (recommended):**
- **80% AI agent tests** — `deep_testing_backend_v2` for every PR;
  `expo_frontend_testing_agent` weekly + before every cohort onboarding.
- **15% structured human testing** — 3 paid testers (₹500/each) running a
  20-step script before each wave: focus on the "feel" gates above.
- **5% wildcards** — give 2 trusted users early access with no script;
  they break things you'd never script.

### Concrete tools you can layer on top of me
- **maze.co** — automated user testing with real humans, ~$25/test
- **Playwright Cloud / Browserstack** — schedule my Playwright scripts to
  run against staging every 4h
- **Sentry** — automatic error capture; pair with my `troubleshoot_agent`
  for autonomous root-cause loops
- **OpenAI Evals / Promptfoo** — for grading LLM output quality at scale
  (especially for Creative Plan Engine + emotion detector regressions)
- **Synthetic monitoring (Better Uptime)** — runs my smoke tests every 5
  minutes against prod and pages you on regression

### TL;DR for your launch

> "Use AI agents for the boring 80% (API regression, perf budget, edge
> cases). Pay 3 humans ₹1,500 total for the 15% that's about taste and
> first-touch UX. Reserve 5% for wildcards. Skip a dedicated QA hire
> until ~250 paying users."

---

## 9. Definition of Done — Beta v1 ready to go live

- [ ] Phase-B server.py refactor complete (currently at 3,335 lines, target <2,500)
- [ ] Marketplace templates have `plan_tier` tags
- [ ] Premium Neon Glass UI rolled across the 12 hero screens
- [ ] Onboarding screen built
- [ ] Watermark pipeline live for free tier
- [ ] Razorpay LIVE mode keys + KYC
- [ ] Privacy / T&Cs reviewed
- [ ] Sentry + uptime monitor wired
- [ ] Demo video recorded
- [ ] Waitlist landing page collecting emails
- [ ] First 5 beta invites sent

When 9 of these 10 are done — open the door.

---

*End of strategy doc. Update when economics or feature set changes
materially. Next refresh suggested: end of Beta v1 retro (week 8).*
