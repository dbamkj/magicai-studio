# MagiCAi Studio — v1.0 Baseline (Apr 29, 2026)

This file marks the v1.0 baseline state of the application as it heads
into the builders contest submission. Any rollback during the v2.0
refactor should restore to roughly the file states described here.

## Backend deep-test results
- 26/29 PASS, 0 user-facing regressions after Round-7i fix.
- Real bug fixed in Session 35i: 2 duplicate trending preview_urls
  patched via Pixabay live-search.
- Spec deviations are intentional / frontend-aligned (singular
  `/wizard/job/{id}`, `/api/subscription/plans`, etc.).

## Pricing matrix
- Free: 300 credits
- Starter: 1500 credits
- Creator: 3000 credits
- Pro: 6000 credits

## Templates
- `marketplace_templates` — 42 docs, all with thumbnail + preview_url
- `templates` (legacy) — 26 docs, no duplicate preview_urls
- `mp_funny_03` renamed: "Aunty Roast" → "AI Baba"
- 9 baked-audio narration mp4s on disk in `/app/backend/static/previews/`

## Frontend
- Glass-card sectioned layout applied to 9 tool screens via
  `/app/scripts/glassify_sections.py`.
- 4 screens (cartoon-avatar, motion-control, divine-transform,
  create-wizard) use their own well-styled card idioms — no further
  glassification needed.
- ModelPicker (video, MH catalog) on: motion-control, ai-bg-lipsync,
  videogen.
- ImageModelPicker (MH image catalog) on: imagegen, divine-transform.
- QualityPicker still present on: avatar, lipsync, redub.
- Inspiration Reels carousel: Discover MagiCAi (3 read-only slides),
  red-flag button removed.
- Free-mode UI watermark badge in FreeVsProToggle.
- expo-media-library plugin declared in app.json with writeOnly perm.
- Tier guard `motion_control: 'creator'` in useTierGuard.ts.

## Demo accounts (`/app/memory/test_credentials.md`)
- demo_free@test.com / Test@123 (Free, 300 credits)
- demo_creator@test.com / Test@123 (Creator, 3000 credits)
- demo_pro@test.com / Test@123 (Pro, 6000 credits)

## Tag for v2.0 rollback target
After contest submission, before starting:
- `server.py` 3,700-line refactor → split into modular routes
- ChatGPT-style Prompt Selection feature
- Light Mode theme

…check this file first to compare.
