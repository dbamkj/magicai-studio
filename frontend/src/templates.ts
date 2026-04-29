// Shared trends templates with authentic Indian imagery.
// URLs use Pixabay's CDN (free, no API key, direct hotlink) with reliable mythological/cultural imagery.

export interface Template {
  id: string;
  title: string;
  label: string;     // Tool/category label
  color: string;     // Badge color
  route: string;     // Destination tool
  img: string;       // Cover image
  description: string;
  prompts: string[]; // 2-4 sample prompts user can tap to pre-fill
  settings?: { duration?: number; aspectRatio?: string; voiceId?: string };
}

export const TEMPLATES: Template[] = [
  {
    id: 'krishna_bhajan',
    title: 'Krishna Bhajan',
    label: 'AI Video',
    color: '#F97316',
    route: '/videogen',
    img: 'https://images.pexels.com/photos/32601772/pexels-photo-32601772.jpeg?w=300&h=400&fit=crop',
    description: 'Divine Krishna reel with flute, Vrindavan garden, and devotional atmosphere.',
    prompts: [
      'Lord Krishna playing flute in Vrindavan garden, peacock feather crown, golden divine glow, cinematic slow motion, warm sunset lighting, close-up angle',
      'Young Krishna dancing among cows in Vrindavan, monsoon clouds, joyful devotional mood, cinematic aerial shot',
      'Krishna and Radha in garden, romantic divine glow, flowers blooming, golden hour, soft wind',
    ],
    settings: { duration: 10, aspectRatio: '9:16', voiceId: 'sarvam:vidya' },
  },
  {
    id: 'shiv_tandav',
    title: 'Shiv Tandav',
    label: 'AI Video',
    color: '#F97316',
    route: '/videogen',
    img: 'https://images.pexels.com/photos/18364244/pexels-photo-18364244.jpeg?w=300&h=400&fit=crop',
    description: 'Majestic Shiva performing cosmic dance Tandav on Mount Kailash.',
    prompts: [
      'Lord Shiva performing cosmic dance Tandav on Mount Kailash, third eye glowing, trishul in hand, snow storm, dramatic blue and gold cinematic wide shot',
      'Shiva meditating under full moon, snow covered mountains, sacred aura, cold blue tones, epic cinematography',
      'Nataraja pose of Shiva surrounded by cosmic fire ring, divine energy, slow motion, dramatic lighting',
    ],
    settings: { duration: 10, aspectRatio: '9:16', voiceId: 'sarvam:hitesh' },
  },
  {
    id: 'wedding_lehenga',
    title: 'Bridal Lehenga',
    label: 'Outfit Swap',
    color: '#06B6D4',
    route: '/multiswap',
    img: 'https://images.pexels.com/photos/30276936/pexels-photo-30276936.jpeg?w=300&h=400&fit=crop',
    description: 'Transform any photo into a stunning Indian bridal look.',
    prompts: [
      'Full body portrait in elegant red Indian wedding lehenga with heavy gold embroidery, bridal jewelry, decorated mandap background',
      'Full body in royal blue wedding lehenga with silver embroidery, traditional bridal pose, palace background',
      'Full body in pastel pink lehenga with floral embroidery, garden mehendi ceremony setting',
    ],
  },
  {
    id: 'face_swap_classic',
    title: 'Face Swap',
    label: 'Video',
    color: '#EC4899',
    route: '/faceswap',
    img: 'https://images.unsplash.com/photo-1626275696293-c92316956d78?w=300&h=400&fit=crop',
    description: 'Swap your face into any movie clip or video.',
    prompts: [
      'Upload a clear front-facing portrait and any target video',
      'Best results with well-lit, unobstructed face photos',
    ],
  },
  {
    id: 'diwali_scene',
    title: 'Diwali Scene',
    label: 'AI Image',
    color: '#EC4899',
    route: '/imagegen',
    img: 'https://images.pexels.com/photos/31104752/pexels-photo-31104752.jpeg?w=300&h=400&fit=crop',
    description: 'Generate stunning Diwali festival scenes with diyas and fireworks.',
    prompts: [
      'Indian family celebrating Diwali, lighting diyas on rangoli, fireworks in night sky, warm orange glow, joyful festive mood',
      'Traditional Indian home decorated with diyas and marigold flowers, Lakshmi puja setup, warm devotional lighting',
      'Children bursting crackers on Diwali night, sparklers lighting up faces, festive streetscape, cinematic warm tones',
    ],
    settings: { aspectRatio: '9:16' },
  },
  {
    id: 'ai_bg_new',
    title: 'AI Background Lip Sync',
    label: 'NEW',
    color: '#EC4899',
    route: '/ai-bg-lipsync',
    img: 'https://images.unsplash.com/photo-1695229347633-75607054f21f?w=300&h=400&fit=crop',
    description: 'Place your character in a brand-new AI-generated scene with fresh background and sound.',
    prompts: [
      'Lord Ganesha blessing devotees during aarti, golden temple, warm candlelight',
      'Lord Hanuman in heroic flight carrying Sanjeevani mountain, sunrise sky',
      'Royal procession in Ayodhya, elephants, musicians, palace, golden hour',
    ],
    settings: { duration: 10, aspectRatio: '9:16', voiceId: 'sarvam:vidya' },
  },
];

export const HERO_SLIDES = [
  {
    id: 'hero_alltools',
    title: 'Explore All Tools',
    subtitle: 'AI Video • Face Swap • Lip Sync • Multi-Swap & more',
    cta: '9 PRO AI TOOLS',
    bg: 'https://images.pexels.com/photos/32601772/pexels-photo-32601772.jpeg?w=800&h=400&fit=crop',
    tint: 'rgba(139,92,246,0.72)',
    route: '/explore-tools',
  },
  {
    id: 'hero_ai_video',
    title: 'Text → AI Video',
    subtitle: 'Describe a scene, get a reel in seconds',
    cta: 'MAGICAI POWERED',
    bg: 'https://images.pexels.com/photos/18364244/pexels-photo-18364244.jpeg?w=800&h=400&fit=crop',
    tint: 'rgba(249,115,22,0.72)',
    route: '/videogen',
  },
  {
    id: 'hero_image_video',
    title: 'Image → Video',
    subtitle: 'Animate any photo with 4× multi-shot variations',
    cta: 'NEW • MULTI-SHOT',
    bg: 'https://images.unsplash.com/photo-1695229347633-75607054f21f?w=800&h=400&fit=crop',
    tint: 'rgba(236,72,153,0.72)',
    route: '/videogen',
  },
  {
    id: 'hero_bg_lipsync',
    title: 'AI Background Lip Sync',
    subtitle: 'Place any character in a brand-new AI scene',
    cta: 'BRAND NEW FEATURE',
    bg: 'https://images.pexels.com/photos/30276936/pexels-photo-30276936.jpeg?w=800&h=400&fit=crop',
    tint: 'rgba(6,182,212,0.72)',
    route: '/ai-bg-lipsync',
  },
  {
    id: 'hero_voice_sarvam',
    title: 'Sarvam AI Premium Voices',
    subtitle: '7 natural Indian voices — Anushka, Arya, Karun & more',
    cta: 'NOW INTEGRATED',
    bg: 'https://images.pexels.com/photos/31104752/pexels-photo-31104752.jpeg?w=800&h=400&fit=crop',
    tint: 'rgba(245,158,11,0.72)',
    route: '/lipsync',
  },
  {
    id: 'hero_multiswap',
    title: 'Multi-Character Swap',
    subtitle: 'Swap faces & outfits of multiple characters at once',
    cta: 'BATCH POWER',
    bg: 'https://images.unsplash.com/photo-1626275696293-c92316956d78?w=800&h=400&fit=crop',
    tint: 'rgba(16,185,129,0.72)',
    route: '/multiswap',
  },
];

export const findTemplate = (id: string) => TEMPLATES.find(t => t.id === id);

