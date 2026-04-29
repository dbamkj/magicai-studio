"""Generate v1.0 contest assets via Gemini Nano Banana (gemini-3.1-flash-image-preview)."""
import asyncio
import base64
import os
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from emergentintegrations.llm.chat import LlmChat, UserMessage

OUT_DIR = '/app/contest_assets'
os.makedirs(OUT_DIR, exist_ok=True)

ASSETS = [
    {
        'name': 'app_icon_1024',
        'prompt': (
            "A premium mobile app icon, 1024x1024, square with subtle rounded "
            "corners. Bold stylised wordmark 'M' as the centerpiece, painted "
            "with a smooth aurora gradient flowing from violet (#7B5CFF) to "
            "magenta (#FF007F) to coral (#FF6B08) to gold (#FBBF24). The "
            "letter has a thin frosted-glass inner highlight and a soft glow. "
            "Background: deep space-indigo (#0F0C29) with faint sparkle stars "
            "and a hint of cosmic nebula. NO text other than the M. NO border. "
            "Modern, minimal, AI-creator vibe — feels like a 2026 flagship app. "
            "Clean enough to read at 60x60 pixels."
        ),
    },
    {
        'name': 'hero_banner_1080',
        'prompt': (
            "A premium contest hero banner for an AI video creator app called "
            "'MagiCAi Studio', portrait 9:16 mobile-style poster. Top: bold "
            "wordmark 'MagiCAi Studio' in aurora gradient (violet → magenta → "
            "coral → gold). Below the title in slimmer text: 'Cinematic AI "
            "Reels in Seconds'. Center: a stylised mobile phone tilted at "
            "-8deg, screen glowing with a colorful neon-glass video reel "
            "preview. Around the phone: floating glass orbs containing "
            "miniature icons of a film reel, a microphone, a sparkle, a music "
            "note. Background: dark aurora gradient with cosmic glow. Modern, "
            "frosted-glass aesthetic. Must look like a flagship 2026 AI app "
            "marketing poster."
        ),
    },
]


async def gen_image(spec):
    api_key = os.getenv('EMERGENT_LLM_KEY')
    chat = LlmChat(
        api_key=api_key,
        session_id=f"contest-asset-{spec['name']}",
        system_message="You are an expert app/poster designer. Output a single high-resolution image.",
    )
    chat.with_model('gemini', 'gemini-3.1-flash-image-preview').with_params(modalities=['image', 'text'])
    msg = UserMessage(text=spec['prompt'])
    text, images = await chat.send_message_multimodal_response(msg)
    if not images:
        print(f"  ! {spec['name']}: no image returned")
        return None
    img = images[0]
    out_path = os.path.join(OUT_DIR, f"{spec['name']}.png")
    with open(out_path, 'wb') as f:
        f.write(base64.b64decode(img['data']))
    print(f"  ✓ {spec['name']:<20} → {out_path}  ({os.path.getsize(out_path):,} bytes)")
    return out_path


async def main():
    print(f"Generating contest assets to {OUT_DIR}")
    for spec in ASSETS:
        try:
            await gen_image(spec)
        except Exception as e:
            print(f"  ! {spec['name']} FAILED: {e}")


if __name__ == '__main__':
    asyncio.run(main())
