"""Batch insert ModelPickerBlock into 10 tool screens."""
import re
from pathlib import Path

ROOT = Path('/app/frontend/app')

# (filename, kind: 'video'|'image')
SCREENS = [
    ('videogen.tsx',         'video'),
    ('motion-control.tsx',   'video'),
    ('lipsync.tsx',          'video'),
    ('ai-bg-lipsync.tsx',    'video'),
    ('redub.tsx',            'video'),
    ('avatar.tsx',           'video'),
    ('faceswap.tsx',         'image'),
    ('headswap.tsx',         'image'),
    ('multiswap.tsx',        'image'),
    ('divine-transform.tsx', 'image'),
]

IMPORT_LINE = "import ModelPickerBlock from '../src/components/ModelPickerBlock';\n"

# Two patterns:
#  (a) screens with GlassHeader → insert after </GlassHeader>
#  (b) screens with classic Text title in s.header view → insert after the
#      header </View>

GLASS_HEADER_PATTERN = re.compile(
    r"(<GlassHeader\b[\s\S]*?/>|<GlassHeader\b[\s\S]*?</GlassHeader>)",
    re.MULTILINE,
)
HEADER_TITLE_PATTERN = re.compile(
    r"(<Text style=\{s\.title\}>[^<]+</Text>\s*<TouchableOpacity[\s\S]*?</TouchableOpacity>\s*</View>)",
    re.DOTALL,
)
# Simpler fallback: look for `<Text style={s.title}>...</Text>` then end of header `</View>`
SIMPLE_HEADER_PATTERN = re.compile(
    r"(<Text style=\{s\.title\}>[\s\S]+?</Text>\s*</View>)",
    re.MULTILINE,
)


def patch(file_name: str, kind: str):
    p = ROOT / file_name
    if not p.exists():
        print(f"  - {file_name}  MISSING")
        return
    src = p.read_text()
    if "ModelPickerBlock" in src:
        print(f"  · {file_name}  already wired")
        return

    # add import — after the LAST import statement
    last_import = list(re.finditer(r"^import .+;\n", src, re.MULTILINE))
    if not last_import:
        print(f"  ! {file_name}  no imports found")
        return
    pos = last_import[-1].end()
    src = src[:pos] + IMPORT_LINE + src[pos:]

    block = (
        f"\n          <View style={{{{ paddingHorizontal: 16 }}}}>\n"
        f"            <ModelPickerBlock kind=\"{kind}\" />\n"
        f"          </View>\n"
    )

    # Try GlassHeader first
    if GLASS_HEADER_PATTERN.search(src):
        src = GLASS_HEADER_PATTERN.sub(r"\1" + block, src, count=1)
        print(f"  ✓ {file_name}  inserted after GlassHeader (kind={kind})")
    else:
        # Try header title patterns
        m = HEADER_TITLE_PATTERN.search(src)
        if not m:
            m = SIMPLE_HEADER_PATTERN.search(src)
        if m:
            src = src[: m.end()] + block + src[m.end():]
            print(f"  ✓ {file_name}  inserted after title row (kind={kind})")
        else:
            print(f"  ! {file_name}  no insertion point found")
            return
    p.write_text(src)


if __name__ == '__main__':
    print("Wiring ModelPickerBlock into tool screens:")
    for fn, kind in SCREENS:
        patch(fn, kind)
