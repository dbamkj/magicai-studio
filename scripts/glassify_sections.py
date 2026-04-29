"""Round-7 — global "card-style sectioned layout" overhaul.

User wants every section on every tool screen to render as its own
rounded glass card (per `lot1.jpeg`). Each screen already groups its
content in `<View style={s.section}>` blocks but the `section` style
is usually just `marginBottom: N` — flat, no border, no card.

Strategy:
  • Find each screen's `section: { ... }` StyleSheet entry.
  • Re-write it with the new glass-card recipe:
        backgroundColor: 'rgba(255,255,255,0.04)',
        borderWidth: 1,
        borderColor: 'rgba(167,139,250,0.18)',
        borderRadius: 18,
        padding: 14,
        marginBottom: 14,
        + light shadow / shadow*-style props for native + boxShadow
          fallback for web.
  • If the screen also has a `sTitle` / `sectionTitle` style, leave it
    alone — the new padding inside the card already gives breathing room.

This keeps the screens self-contained (no need to import a new component)
and the change is tightly scoped: just 3-6 lines per file.

Rerunnable — the script idempotently rewrites the existing key.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path('/app/frontend/app')

# Screens to apply card-sectioning to. We touch the most-visited tool
# screens (the 12 from earlier scope).
SCREENS = [
    'videogen.tsx',
    'imagegen.tsx',
    'avatar.tsx',
    'cartoon-avatar.tsx',
    'lipsync.tsx',
    'redub.tsx',
    'motion-control.tsx',
    'ai-bg-lipsync.tsx',
    'faceswap.tsx',
    'headswap.tsx',
    'multiswap.tsx',
    'divine-transform.tsx',
    'create-wizard.tsx',
]

# The new replacement block (matches RN StyleSheet keys verbatim).
NEW_BODY = """{
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1,
    borderColor: 'rgba(167,139,250,0.20)',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 14,
    marginBottom: 14,
    overflow: 'hidden',
    ...Platform.select({
      web: { boxShadow: '0 6px 22px rgba(15,12,41,0.25)' as any },
      default: { shadowColor: '#0F0C29', shadowOpacity: 0.35, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
    }),
  }"""


# We look for either `section: {` or `sectionCard: {` first balanced
# brace-closed body and re-emit it.
def replace_section(src: str, key: str = 'section') -> tuple[str, bool]:
    pattern = re.compile(rf"\b{key}:\s*\{{")
    m = pattern.search(src)
    if not m:
        return src, False
    # Walk the braces forward to find the closing `}`
    depth = 1
    i = m.end()
    while i < len(src) and depth > 0:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    if depth != 0:
        return src, False
    end_brace = i  # index AFTER the closing '}'
    new = src[: m.start()] + f"{key}: {NEW_BODY}" + src[end_brace:]
    return new, True


def has_platform_import(src: str) -> bool:
    """True if the file already imports `Platform` from react-native."""
    return bool(re.search(
        r"from\s+['\"]react-native['\"];?\s*$",
        src, re.MULTILINE,
    )) and 'Platform' in src


def ensure_platform(src: str) -> str:
    """Ensure `Platform` is imported from react-native."""
    if has_platform_import(src):
        return src
    # find an import { ... } from 'react-native';
    m = re.search(r"import\s+\{([^}]*)\}\s+from\s+['\"]react-native['\"];", src)
    if not m:
        return src  # fallback — leave alone (compile error would surface)
    parts = [p.strip() for p in m.group(1).split(',') if p.strip()]
    if 'Platform' in parts:
        return src
    parts.append('Platform')
    new_import = "import { " + ", ".join(parts) + " } from 'react-native';"
    return src[: m.start()] + new_import + src[m.end():]


def patch(fn: str):
    p = ROOT / fn
    if not p.exists():
        print(f"  ! {fn}  missing")
        return
    src = p.read_text()
    src = ensure_platform(src)
    new, ok = replace_section(src, 'section')
    if not ok:
        # Try alternate keys some files use
        for alt in ('sectionCard', 'card', 'block'):
            new, ok = replace_section(src, alt)
            if ok:
                break
    if ok:
        p.write_text(new)
        print(f"  ✓ {fn}")
    else:
        print(f"  · {fn}  no `section`-style key found")


if __name__ == '__main__':
    print("Applying glass-card section style:")
    for fn in SCREENS:
        patch(fn)
