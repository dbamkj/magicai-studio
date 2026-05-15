# MagiCAi Studio — Pricing & Launch Strategy v2 (Session 35-39)

> **Source of truth**: `backend/core/pricing.py`. This doc reflects the v1.0 lock-in
> after Sprints 1-4. The original v1 doc has been superseded; consult git history
> for the older 4-tier (Free/Starter/Creator/Pro) model.

Last updated: 2026-05-14.

---

## 0. Cost Anchor — what 1 in-app credit really costs you

| Item | Value |
|---|---|
| MagicHour Creator subscription | **₹1,350 / month** |
| MH credits available           | 10,000 / month |
| **Raw cost per MH credit**     | **₹0.135 / credit** |
| 20% buffer (retries, top-ups, QA) | 2,000 credits |
| **Sellable MH credits**        | **8,000 / month** |

**1 in-app credit ≈ ₹0.135 of MagicHour cost** (when MH is invoked; procedural reels cost ₹0).

---

## 1. Active Pricing — Phase v1.0

### Visible at `/pricing` (filtered server-side via `is_visible_in_pricing_page`)

| Plan | ₹/mo | Credits | Margin @ 100% | Margin @ 35% redemption |
|---|---|---|---|---|
| **Trial** (7-day, auto-enrolled) | ₹0 | 50 | n/a | n/a |
| **Basic** | ₹99 | 100 | 86% (₹85 profit) | 96% (₹95 profit) |
| **Creator** ⭐ | ₹599 | 1,200 | 73% (₹437 profit) | 93% (₹557 profit) |

### Hidden (architecturally supported, admin can flip via `POST /api/admin/plans/{id}/toggle-visibility`)

| Plan | ₹/mo | Credits | Reveal phase |
|---|---|---|---|
| Free (legacy) | ₹0 | 300 | never — only existing legacy users |
| Starter | ₹249 | 1,500 | v1.4 (Week 10-12) |
| Pro | ₹1,499 | 6,000 | v1.3 (Week 6-8) |

---

## 2. Feature Matrix (locked v1.0)

Legend: 🟢 included · 🔒 gated · ⚪ N/A · MH = MagicHour billed · LOCAL = zero marginal cost

| Feature                       | Trial | Basic | Creator | Starter* | Pro* | Provider |
|-------------------------------|:-----:|:-----:|:-------:|:--------:|:----:|:--------:|
| **Wizard reel (procedural)**  | 🟢    | 🟢    | 🟢      | 🟢       | 🟢   | LOCAL    |
| **Templates marketplace**     | 🟢    | 🟢    | 🟢      | 🟢       | 🟢   | LOCAL    |
| **Remix Dialogue**            | 🟢    | 🟢    | 🟢      | 🟢       | 🟢   | EMG      |
| **Procedural Animation**      | 🟢    | 🟢    | 🟢      | 🟢       | 🟢   | LOCAL    |
| **AI Image (FLUX schnell)**   | 🟢    | 🟢    | 🟢      | 🟢       | 🟢   | MH       |
| **Basic Avatar**              | 🟢    | 🟢    | 🟢      | 🟢       | 🟢   | EMG      |
| **Basic Lip Sync (procedural)** | 🟢  | 🟢    | 🟢      | 🟢       | 🟢   | LOCAL    |
| **Watermark removed**         | 🔒    | 🔒    | 🟢      | 🟢       | 🟢   | LOCAL    |
| **720p export**               | 🔒    | 🔒    | 🟢      | 🟢       | 🟢   | LOCAL    |
| **Face Swap (image/video)**   | 🔒    | 🔒    | 🟢      | 🟢       | 🟢   | MH       |
| **Head Swap / Body Swap**     | 🔒    | 🔒    | 🟢      | 🟢       | 🟢   | MH       |
| **Talking Avatar (real lipsync)** | 🔒| 🔒    | 🟢      | 🟢       | 🟢   | MH       |
| **Dynamic Camera FX**         | 🔒    | 🔒    | 🟢      | 🔒       | 🟢   | MH       |
| **Multi-shot (2 shots)**      | 🔒    | 🔒    | 🟢      | 🔒       | 🟢   | MH       |
| **Video-to-Video**            | 🔒    | 🔒    | 🟢      | 🔒       | 🟢   | MH       |
| **Image-to-Video**            | 🔒    | 🔒    | 🟢      | 🔒       | 🟢   | MH       |
| **AI Video (Kling 2.5 Studio)** | 🔒  | 🔒    | 🟢 (4/mo, ≤3s) | 🔒 | 🟢 (8/mo, ≤5s) | MH |
| **Divine Transform**          | 🔒    | 🔒    | 🟢      | 🔒       | 🟢   | MH       |
| **AI BG Lipsync**             | 🔒    | 🔒    | 🟢      | 🔒       | 🟢   | MH       |
| **Image Cinematic (FLUX Pro)**| 🔒    | 🔒    | 🟢      | 🔒       | 🟢   | MH       |
| **Multi-shot (4 shots)**      | 🔒    | 🔒    | 🔒      | 🔒       | 🟢   | MH       |
| **Video Cinematic (Kling 3.0)** | 🔒  | 🔒    | 🔒      | 🔒       | 🟢   | MH       |
| **1080p export**              | 🔒    | 🔒    | 🔒      | 🔒       | 🟢   | LOCAL    |

\* = hidden in v1.0

---

## 3. Phase-wise Rollout

| Phase  | Codename       | Target | Visible plans                  | Razorpay | Goal |
|--------|----------------|--------|--------------------------------|----------|------|
| v1.0   | Internal Alpha | NOW    | Trial / Basic / Creator        | TEST     | Single-user QA |
| v1.1   | Closed Beta    | +1 wk  | Trial / Basic / Creator        | TEST + gift coupons | 10 users feedback |
| v1.2   | Public Launch  | +3 wk  | Trial / Basic / Creator        | **LIVE** | Open signups |
| v1.3   | Power tier     | +6 wk  | + Pro                          | LIVE     | Power-user upsell |
| v1.4   | Wedge tier     | +10 wk | + Starter                      | LIVE     | Conversion middle |

---

## 4. Trial mechanics (auto-enrolment funnel)

1. **Signup** (email or Google) → `subscription_tier='trial'`, `credits_balance=50`, `trial_expires_at=now+7d`
2. Days 1-7: full Basic-equivalent feature set, watermark ON, 480p cap
3. **Day 7 expiry**: cron `_expire_trials()` runs every 6h → force-downgrades to Basic with `credits_balance=0` and `requires_upgrade=true`
4. User cannot use any feature until they purchase Basic ₹99 (no permanent Free tier)
5. Strikes / bans persist across the trial→basic transition

---

## 5. Cost economics (per-generation real ₹)

| Generation type | In-app credits | MH credits used | Real ₹ COGS |
|---|---|---|---|
| Procedural cartoon reel | 10-30 | 0 | **₹0** + ₹0.40 LLM = **₹0.40** |
| Basic Lip Sync (5s, procedural) | 50 | 0 | **₹0** + ₹0.50 = **₹0.50** |
| Face Swap (image) | 6 | 6 | ₹0.81 + ₹0.30 LLM = **₹1.11** |
| Face Swap (video, 5s) | 15 | 15 | ₹2.03 + ₹0.40 = **₹2.43** |
| Talking Avatar (10s, real lipsync) | 70 | 70 | ₹9.45 + ₹0.40 + Sarvam ₹0.60 = **₹10.45** |
| AI Video (3s, Studio) | 240 | 30 | ₹4.05 + ₹0.40 = **₹4.45** |
| Video-to-Video (5s) | 40 | 40 | ₹5.40 + ₹0.40 = **₹5.80** |
| Multi-shot (4 shots) | 800 | 80 | ₹10.80 + ₹1.60 + ₹2.40 = **₹14.80** |

---

## 6. Margin per tier @ realistic 35% credit redemption

| Tier | Revenue | Avg COGS (35%) | **Profit / user / month** |
|---|---|---|---|
| Trial | ₹0 | ₹2-5 (LLM + Sarvam + Pixabay) | **−₹3** (acquisition cost) |
| Basic | ₹99 | ₹4 | **₹95 (96%)** |
| Creator | ₹599 | ₹42 (mix of MH features) | **₹557 (93%)** |
| Pro | ₹1,499 | ₹120 | **₹1,379 (92%)** |

**At 10 paying users with current mix (5 Basic, 5 Creator):**
- Revenue: 5×99 + 5×599 = **₹3,490 / mo**
- COGS: ~₹230
- Add MH base ₹1,350 + Razorpay ~2% (₹70) + Emergent LLM ~₹50
- **Net: ₹1,790 / mo profit** at 10 users

---

## 7. Break-even projections

| MRR target | # Basic | # Creator | Total users | MH ops cost | Profit |
|---|---|---|---|---|---|
| ₹1,500 (covers MH base) | 15 | 0 | 15 | ₹1,350 | **₹130** |
| ₹5,000 | 10 | 7 | 17 | ₹1,640 | **₹3,360** |
| ₹20,000 | 30 | 30 | 60 | ₹2,820 | **₹17,180** |
| ₹50,000 | 50 | 75 | 125 | ₹4,750 | **₹45,200** |

---

## 8. Add-on credit packs (one-time IAP)

| SKU | Price | Credits | Use case |
|---|---|---|---|
| `topup_small` | ₹49 | 1 × AI video (3s) | "Just one more reel" |
| `topup_medium` | ₹79 | 1 × AI video (5s) | Longer single video |
| `topup_large` | ₹149 | 3 × AI videos (3s) | Volume top-up |

Stored in `backend/core/pricing.py::ADDONS`. Available to Basic+ tiers only.

---

## 9. Runtime levers (no code deploy)

| Action | API |
|---|---|
| Show/hide Starter | `POST /api/admin/plans/starter/toggle-visibility {visible:true}` |
| Show/hide Pro | `POST /api/admin/plans/pro/toggle-visibility {visible:true}` |
| Emergency hide Creator | `POST /api/admin/plans/creator/toggle-visibility {visible:false}` |
| Gradual feature rollout | `POST /api/admin/feature-flags {key:"x",enabled:true,rollout_pct:10}` |
| Ban a misbehaving user | `POST /api/admin/users/{id}/ban {reason:"..."}` |
| Force-expire a trial (Phase A) | `POST /api/admin/users/{id}/expire-trial` (Session 39 — TBA) |

---

## 10. Decisions locked-in (Session 35)

1. ✅ Trial auto-enrolls every signup; expires to Basic (no permanent Free)
2. ✅ Basic = protected lightweight scope (watermark ON, 480p, no Face Swap / Talking Avatar / AI Video / Dynamic Camera)
3. ✅ Creator slashed 3000 → 1200 credits; monthly_ai_videos 3 → 4
4. ✅ All existing creator-tier users force-migrated to 1200 cap
5. ✅ Local signed-URL storage (Sprint 2)
6. ✅ DPDPA 2023 compliance baseline (Sprint 2)
7. ✅ Content moderation v2 with strikes + auto-ban (Sprint 3)
8. ✅ Persistent queue Mongo-backed + Arq-ready (Sprint 4)
9. ✅ Razorpay LIVE deferred until KYC complete
