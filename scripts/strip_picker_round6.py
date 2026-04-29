"""Round-6 — strip ModelPickerBlock from screens the user no longer wants
it on, per Apr-29 feedback:

  Remove from: motion-control, ai-bg-lipsync, faceswap, headswap, multiswap.
  Keep on:    divine-transform.
  Replace QualityPicker with new picker on: videogen (video), imagegen (image).
"""
import re
from pathlib import Path

ROOT = Path('/app/frontend/app')

REMOVE_FROM = [
    'motion-control.tsx',
    'ai-bg-lipsync.tsx',
    'faceswap.tsx',
    'headswap.tsx',
    'multiswap.tsx',
]

# Match the inserted picker — there are 3 different shapes used by the
# earlier wiring scripts.
BLOCK_PATTERNS = [
    re.compile(r"\n\s*\{\/\* MH-style.*?picker.*?\*\/\}\s*\n\s*<ModelPickerBlock[^/]*?/>\n", re.DOTALL),
    re.compile(r"\n\s*<View style=\{\{ paddingHorizontal: 16 \}\}>\s*\n\s*<ModelPickerBlock[^/]*?/>\s*\n\s*</View>\s*\n", re.MULTILINE),
    re.compile(r"\n\s*\{\/\*[^*]*?model picker.*?\*\/\}[\s\S]*?<ModelPickerBlock[^/]*?/>\s*\n", re.IGNORECASE),
    re.compile(r"\n\s*<ModelPickerBlock[^/]*?/>\s*\n", re.MULTILINE),
]
IMPORT_RE = re.compile(r"\nimport ModelPickerBlock from '[^']+';\n")

for fn in REMOVE_FROM:
    p = ROOT / fn
    if not p.exists():
        print(f"  ! {fn}  missing"); continue
    src = p.read_text()
    orig = src
    for pat in BLOCK_PATTERNS:
        new = pat.sub("\n", src, count=1)
        if new != src:
            src = new
            break
    src = IMPORT_RE.sub("\n", src, count=1)
    if src != orig:
        p.write_text(src)
        print(f"  ✓ {fn}  cleaned")
    else:
        print(f"  · {fn}  no match")

# Sanity check
print("\nFinal state:")
for fn in REMOVE_FROM + ['divine-transform.tsx']:
    p = ROOT / fn
    if p.exists():
        has = 'ModelPickerBlock' in p.read_text()
        print(f"  {fn:<25}  has block: {has}")
