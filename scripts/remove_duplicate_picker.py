"""Remove the duplicate ModelPickerBlock from screens that already
ship the older QualityPicker (Quick/Studio/Cinematic). Keep it only on
screens that have NO model UI at all."""
import re
from pathlib import Path

ROOT = Path('/app/frontend/app')

# Screens that already have QualityPicker → remove our new block.
DUPLICATES = [
    'videogen.tsx',
    'redub.tsx',
    'avatar.tsx',
    'lipsync.tsx',
    'imagegen.tsx',
]

# Block we inserted earlier — match flexibly.
BLOCK_PATTERN = re.compile(
    r"\n\s*\{\/\* MH-style Image Model picker.*?\*\/\}\s*\n\s*<ModelPickerBlock[^/]*?/>\n*"
    r"|\n\s*\{\/\*[^*]*?Image model picker.*?\*\/\}[\s\S]*?<ModelPickerBlock[^/]*?/>\s*\n\s*</View>\n*"
    r"|\n\s*<View style=\{\{ paddingHorizontal: 16 \}\}>\s*\n\s*<ModelPickerBlock[^/]*?/>\s*\n\s*</View>\s*\n",
    re.MULTILINE,
)

IMPORT_LINE_RE = re.compile(
    r"\nimport ModelPickerBlock from '[^']+';\n",
)

for fn in DUPLICATES:
    p = ROOT / fn
    src = p.read_text()
    new_src = BLOCK_PATTERN.sub("\n", src, count=1)
    new_src = IMPORT_LINE_RE.sub("\n", new_src, count=1)
    if new_src != src:
        p.write_text(new_src)
        print(f"  ✓ {fn}  removed duplicate block")
    else:
        print(f"  · {fn}  no match")

# Verify the keepers still import the picker
KEEPERS = [
    'motion-control.tsx',
    'ai-bg-lipsync.tsx',
    'faceswap.tsx',
    'headswap.tsx',
    'multiswap.tsx',
    'divine-transform.tsx',
]
print("\nKept on:")
for fn in KEEPERS:
    p = ROOT / fn
    if p.exists() and 'ModelPickerBlock' in p.read_text():
        print(f"  ✓ {fn}")
    else:
        print(f"  ! {fn}  MISSING picker — will need manual review")
