"""Stitch 12 contest screenshots into a 30-sec mobile demo MP4 with
crossfade transitions and a 9:16 background. 1080x1920 @ 30fps."""
import subprocess, os
from pathlib import Path

ROOT = Path('/app/contest_assets')
SHOTS = sorted((ROOT / 'screenshots').glob('*.png'))
assert len(SHOTS) == 12, f"expected 12 shots, got {len(SHOTS)}"

# 30s / 12 shots ≈ 2.5s per shot
PER = 2.5
FADE = 0.4
OUT_W, OUT_H, FPS = 1080, 1920, 30

# ── 1. Render each frame as a 2.5s padded clip on a dark aurora bg ──
clips = []
for i, p in enumerate(SHOTS):
    out = ROOT / f'_clip_{i:02d}.mp4'
    # scale to fit (preserve aspect, max 1080w / 1740h leaving room for chrome)
    # Then pad to 1080x1920 with a dark bg, add a subtle violet-cyan vignette
    cmd = [
        'ffmpeg', '-y', '-loop', '1', '-t', f'{PER}', '-i', str(p),
        '-f', 'lavfi', '-t', f'{PER}',
        '-i', f'color=c=0x0F0C29:s={OUT_W}x{OUT_H}:r={FPS}',
        '-filter_complex',
        # Scale image, place on top of dark bg, fade in/out
        f'[0:v]scale={OUT_W-100}:-1:flags=lanczos,format=yuv420p[scaled];'
        f'[1:v][scaled]overlay=(W-w)/2:(H-h)/2,'
        f'fade=in:st=0:d={FADE},fade=out:st={PER-FADE}:d={FADE}',
        '-r', str(FPS), '-pix_fmt', 'yuv420p', '-an', str(out)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    clips.append(out)
    print(f'  ✓ clip {i+1:02d}/{len(SHOTS)}  {p.name}')

# ── 2. Concatenate ──
concat_list = ROOT / '_concat.txt'
concat_list.write_text(''.join(f"file '{c}'\n" for c in clips))
silent_video = ROOT / '_silent.mp4'
subprocess.run([
    'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_list),
    '-c', 'copy', str(silent_video)
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f'\n  ✓ concatenated → {silent_video}')

# ── 3. Add a soft cinematic background music track if available ──
bgm_candidates = list(Path('/app/backend/static/bgm').glob('*.mp3')) if Path('/app/backend/static/bgm').exists() else []
if not bgm_candidates:
    bgm_candidates = list(Path('/app/backend/storage/bgm').glob('*.mp3'))
if not bgm_candidates:
    bgm_candidates = list(Path('/app/backend/storage').rglob('*.mp3'))[:5]
bgm = bgm_candidates[0] if bgm_candidates else None

final = ROOT / 'magicai_demo_30s.mp4'
if bgm:
    print(f'  ↪ using BGM: {bgm.name}')
    subprocess.run([
        'ffmpeg', '-y', '-i', str(silent_video), '-i', str(bgm),
        '-filter_complex',
        f'[1:a]aloop=loop=-1:size=2e+09,atrim=0:30,afade=in:st=0:d=1,'
        f'afade=out:st=29:d=1,volume=0.55[a]',
        '-map', '0:v', '-map', '[a]', '-shortest',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-c:a', 'aac', '-b:a', '128k',
        str(final)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
else:
    print('  ↪ no BGM found, exporting silent')
    subprocess.run([
        'ffmpeg', '-y', '-i', str(silent_video),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-an',
        str(final)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Clean up tmp clips
for c in clips: c.unlink(missing_ok=True)
silent_video.unlink(missing_ok=True)
concat_list.unlink(missing_ok=True)

size_mb = final.stat().st_size / 1024 / 1024
print(f'\n🎬 Demo video → {final}  ({size_mb:.1f} MB)')
