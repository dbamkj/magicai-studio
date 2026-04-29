# MagiCAi Studio — v1.0 Contest Assets

Generated **Apr 29, 2026** for the builders contest submission.

```
/app/contest_assets/
├── app_icon_1024.png          ← App store / Play store icon (1024×1024 PNG, AI-generated via Nano Banana)
├── hero_banner_1080.png       ← Marketing poster / store hero (1080×1920 vertical, AI-generated)
├── magicai_demo_30s.mp4       ← 30-second walkthrough demo (1080×1920 9:16 @ 30 fps · 3.3 MB · cinematic BGM)
└── screenshots/               ← 12 mobile screenshots (390×844 → upscale for stores)
    ├── 01_home_top.png            Home — header + Hero carousel
    ├── 02_home_quick.png          Home — Quick Access + Discover MagiCAi
    ├── 03_home_inspiration.png    Inspiration Reels grid (curated media)
    ├── 04_marketplace.png         Templates Marketplace top
    ├── 05_marketplace_tiles.png   Marketplace template cards (Devi Maa, Soldier, Coffee Shop)
    ├── 06_videogen.png            AI Video Gen with new Model Picker
    ├── 07_imagegen.png            AI Image Gen with Image Model Picker
    ├── 08_motion_control.png      Motion Control (Creator+ gated)
    ├── 09_avatar_studio.png       Avatar Studio
    ├── 10_subscription.png        Plans & Pricing
    ├── 11_create_wizard.png       Creator Wizard
    └── 12_trending.png            Trending / Inspiration Reels feed
```

## What's in each asset

### 🎨 `app_icon_1024.png`
- 1024×1024 PNG, square with rounded edges
- AI-generated via Gemini Nano Banana (`gemini-3.1-flash-image-preview`)
- Aurora gradient "M" wordmark on deep space-indigo background
- Drop in as the app store icon for iOS / Play store
- Optional: replace `/app/frontend/assets/images/icon.png` to use as the live app icon

### 📸 `hero_banner_1080.png`
- 1080×1920 portrait, AI-generated marketing poster
- Brand wordmark + tagline + tilted-phone showcase
- Ready for App Store screenshots, social media, contest landing page

### 🎬 `magicai_demo_30s.mp4`
- 30-second mobile walkthrough video
- 12 screens × ~2.5s each, smooth 0.4s crossfades
- Background music: cinematic_score.mp3 (faded in / out, 0.55 volume)
- 1080×1920 9:16 vertical · 30 fps · h.264/AAC · 3.3 MB

### 📱 `screenshots/`
- 12 mobile screenshots covering every key flow
- Native 390×844 from Playwright on the live preview environment
- Use directly OR upscale to 1290×2796 (iOS XL) via any image tool

## Regenerate

If you tweak the UI and want fresh assets, run:

```bash
# AI assets (icon + hero banner)
cd /app/backend && python -m scripts.gen_contest_assets

# 12 fresh screenshots — the screenshot tool handles this; or run the
# Playwright script in /app/scripts/ if you prefer

# Demo video (uses whatever's in /app/contest_assets/screenshots/)
cd /app/backend && python -m scripts.build_demo_video
```

## Submission tips

- App stores want at least 5 screenshots; pick `01, 03, 06, 09, 10` for a strong first impression.
- Contest landing page → put `hero_banner_1080.png` at the top and embed `magicai_demo_30s.mp4` as the auto-play hero video.
- For Apple/Google reviewers' privacy compliance, the demo uses only the demo accounts from `/app/memory/test_credentials.md`.
