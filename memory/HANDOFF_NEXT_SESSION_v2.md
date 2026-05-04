# 🎨 Premium Neon Glass UI — 12-Screen Redesign Handoff

> Created 2026-05-04 by Session 34-D agent.
> Estimated effort: **6–8 focused hours** of agent time.
> This is a UI polish task — no new backend endpoints required.

---

## Context

The user has provided two reference images (`apimg1`, `apimg2`) showing a
**Premium Neon Glass UI** target design. Aurora gradients + frosted-glass
cards + spring animations are partially rolled out across the app, but
12 hero screens still need the unified treatment.

---

## Current state (what's already at the target standard)

- ✅ `app/index.tsx` (Home) — partial polish (header, credits pill, FAB)
- ✅ `app/subscription.tsx` — usage cards + upsell banners (Session 34-D)
- ✅ `src/AuroraBackground.tsx` — opacity tuned (0.22 blobs + 0.55 dark layer)
- ✅ `src/components/BottomTabBar.tsx` — flattened glass + gradient FAB
- ✅ `src/components/AnimatedSplash.tsx` — devotional splash animation
- ✅ `src/components/GlassHeader.tsx` — reusable header component

---

## 12 Screens that need the redesign

| # | File | Priority | Notes |
|---|------|----------|-------|
| 1 | `app/login.tsx` | 🔴 P0 | Hero of first-touch. Glass card, tier-color accent, demo-account quick-pick chips |
| 2 | `app/onboarding.tsx` | 🔴 P0 | 3-slide carousel — currently barebones |
| 3 | `app/marketplace.tsx` | 🟠 P1 | Filter chips, grid w/ plan_tier lock badges (use new `<LockBadge>` component!) |
| 4 | `app/avatar-studio.tsx` | 🟠 P1 | ~3000 LOC — needs componentization too. Break into PresetPicker, RemixUI, DualConfig |
| 5 | `app/videogen.tsx` | 🟠 P1 | AI Video wizard — big primary action button, glass step cards |
| 6 | `app/preview-export.tsx` | 🟠 P1 | Result preview screen — Free vs Pro toggle prominence |
| 7 | `app/cartoon-avatar.tsx` | 🟡 P2 | Style picker grid + emotion chips |
| 8 | `app/credits.tsx` (or `buy.tsx`) | 🟡 P2 | Credit pack cards w/ ₹/credit math, gradient borders |
| 9 | `app/library.tsx` / `projects.tsx` | 🟡 P2 | Filter chips (All / Videos / Images), grid, swipe-to-delete |
| 10 | `app/profile.tsx` | 🟡 P2 | User avatar circle, tier badge w/ accent, 3 setting groups |
| 11 | `app/lipsync.tsx`, `redub.tsx`, `faceswap.tsx`, `headswap.tsx` | 🟢 P3 | Lower-traffic — copy the pattern from videogen.tsx |
| 12 | `app/admin.tsx` | 🟢 P3 | 5-tab admin panel — internal, lowest priority |

---

## Design system tokens (use these — don't reinvent)

Located in `src/theme.ts`. The Aurora palette:

```ts
export const colors = {
  // Aurora gradient stops
  auroraPink:   '#ff5db1',
  auroraOrange: '#ff8a4c',
  auroraCyan:   '#7afcff',
  auroraBlue:   '#5db1ff',
  auroraGold:   '#ffd17a',

  // Surfaces
  bgDark:       '#0a0418',
  bgDarker:     '#070314',
  glassFill:    'rgba(255,255,255,0.05)',
  glassBorder:  'rgba(255,255,255,0.10)',
  glassFillStrong: 'rgba(255,255,255,0.08)',

  // Text
  textPrimary:   '#ffffff',
  textSecondary: '#cbd2e8',
  textMuted:     '#8a93b0',

  // Tier accents
  tierFree:    '#94A3B8',
  tierStarter: '#60A5FA',
  tierCreator: '#EC4899',  // hero highlight color
  tierPro:     '#FBBF24',

  // Semantics
  success: '#7affc7',
  warning: '#f59e0b',
  danger:  '#ff5b6e',
};
```

---

## Reusable building blocks (already shipped — REUSE these)

```tsx
// Background
<AuroraBackground>...</AuroraBackground>

// Glass card pattern (use these styles, don't make new ones)
<View style={{
  backgroundColor: 'rgba(255,255,255,0.05)',
  borderWidth: 1,
  borderColor: 'rgba(255,255,255,0.10)',
  borderRadius: 18,
  padding: 16,
  // shadow optional, prefer subtle:
  shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 12, shadowOffset: { width: 0, height: 4 },
}} />

// Gradient buttons (Aurora pink-orange)
<LinearGradient
  colors={['#ff5db1', '#ff8a4c']}
  start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
  style={{ borderRadius: 14, padding: 14 }}
/>

// Headers
<GlassHeader icon="..." title="..." subtitle="..." onBack={() => router.back()} />

// Lock badges (Session 34-D)
import { LockBadge } from '../src/components/UsageCard';
<LockBadge label="Pro" />

// Usage cards (Session 34-D)
import { UsageCard, UpgradeBanner } from '../src/components/UsageCard';
import { useMyLimits } from '../src/useMyLimits';
```

---

## Strict design rules

1. **Spacing** — 8pt grid. Use 8 / 16 / 24 / 32. Never 7, 13, 19, etc.
2. **Border radius** — 14 (input), 18 (card), 24 (hero), 999 (pill).
3. **Touch targets** — min 44x44 (iOS) / 48x48 (Android).
4. **Typography** —
   - Title: `fontSize: 18-24, fontWeight: '800', letterSpacing: 0.4`
   - Body: `fontSize: 14, fontWeight: '500', lineHeight: 20`
   - Meta: `fontSize: 11-12, fontWeight: '600', color: textMuted`
5. **Animations** — react-native-reanimated only. Spring presets:
   `damping: 18, stiffness: 180` for springs.
6. **NO** absolute positioning for main content (only for FAB / overlays).
7. **Always** include `<KeyboardAvoidingView>` + `useSafeAreaInsets` on
   any screen with text input.
8. **Always** apply `paddingBottom: 110` to the bottom-most ScrollView so
   content clears the BottomTabBar's gradient FAB.

---

## Recommended execution order

**Day 1 (4h) — Hero screens:**
1. `login.tsx` — single glass card centered, demo chips at bottom (~45min)
2. `onboarding.tsx` — 3-slide carousel with parallax (~75min)
3. `marketplace.tsx` — filter chips + grid + LockBadge (~90min)
4. `videogen.tsx` — wizard polish (~30min)

**Day 2 (4h) — Avatar Studio + Polish:**
5. `avatar-studio.tsx` — break into 3 components, restyle (~150min)
6. `preview-export.tsx` — Before/After toggle hero (~45min)
7. `cartoon-avatar.tsx` — style/emotion grids (~45min)
8. `library.tsx` + `profile.tsx` — clean grid + settings groups (~30min)

**Day 3 (1h) — Lower priority:**
9. `lipsync` / `redub` / `faceswap` / `headswap` — apply pattern from videogen
10. `admin.tsx` — defer to V2.0 if time-pressed

---

## Tier-aware lock badge integration (NEW — pattern from Session 34-D)

The marketplace and tool grids should now show lock badges on tiles
the user can't access yet. Pattern:

```tsx
import { useMyLimits } from '../src/useMyLimits';
import { LockBadge } from '../src/components/UsageCard';

export default function ToolGridScreen() {
  const { limits } = useMyLimits();
  const gates = limits?.feature_gates;

  return (
    <View>
      <ToolTile
        name="Face Swap"
        locked={!gates?.face_swap}
        lockLabel="Starter"
      />
      <ToolTile
        name="Kling 3.0 Pro"
        locked={!gates?.video_cinematic}
        lockLabel="Pro"
      />
    </View>
  );
}

function ToolTile({ name, locked, lockLabel }) {
  return (
    <Pressable disabled={locked} style={[s.tile, locked && { opacity: 0.55 }]}>
      <Text>{name}</Text>
      {locked && <View style={s.lockSlot}><LockBadge label={lockLabel} /></View>}
    </Pressable>
  );
}
```

---

## What NOT to touch in this redesign

- ❌ Backend code (we just shipped tier gating, waitlist, /api/me/limits)
- ❌ `metro.config.js`, `app.json` framework values
- ❌ The `BottomTabBar` (already polished — only theme it if asked)
- ❌ The `AuroraBackground` opacity (final values from Session 33)
- ❌ `useAuth`, `useTheme`, `usePushNotifications` hooks (working as-is)

---

## Definition of Done for the redesign

- [ ] All 12 screens use Aurora background + glass cards
- [ ] Consistent header pattern (`GlassHeader` everywhere)
- [ ] Tier lock badges on every gated feature tile
- [ ] No mock/placeholder text — real copy throughout
- [ ] Tested at 360x800 (Galaxy S21) and 390x844 (iPhone 13)
- [ ] All screens scroll cleanly (no clipped content under tab bar)
- [ ] Run `expo_frontend_testing_agent` against subscription / marketplace / login

---

## References

- `docs/PRICING_AND_LAUNCH_STRATEGY.md` § 1 — feature matrix (drives lock badges)
- `frontend/src/components/UsageCard.tsx` — UsageCard, UpgradeBanner, LockBadge (NEW)
- `frontend/src/useMyLimits.ts` — typed hook for tier gates (NEW)
- `frontend/src/AuroraBackground.tsx` — gradient + blob composition
- `frontend/src/theme.ts` — design tokens
- `apimg1` / `apimg2` — user-provided UI references (in chat history)

---

*End of handoff. Take this as a complete blueprint — the next agent should
not need to ask the user any clarifying questions before starting.*
