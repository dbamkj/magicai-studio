// Shared Voice Library for MagiCAi Studio
// All voice IDs are either native edge-tts voice shortnames, or pseudo IDs
// in the form 'effect:baseVoice' (handled in backend /api/generate-tts-audio).

export interface Voice {
  id: string;
  name: string;
  lang: string;
  gender: 'M' | 'F' | 'Baby';
  age?: string;
  category: 'hindi_female' | 'hindi_male' | 'english_female' | 'english_male' | 'baby_boy' | 'baby_girl' | 'sarvam_female' | 'sarvam_male';
  provider?: 'edge-tts' | 'sarvam';
  note?: string;
}

export const VOICE_LIBRARY: Voice[] = [
  // ===== HINDI FEMALE (5) =====
  { id: 'hi-IN-SwaraNeural', name: 'Swara', lang: 'Hindi', gender: 'F', age: 'Adult', category: 'hindi_female' },
  { id: 'young:hi-IN-SwaraNeural', name: 'Priya', lang: 'Hindi', gender: 'F', age: 'Young', category: 'hindi_female' },
  { id: 'sweet:hi-IN-SwaraNeural', name: 'Meera', lang: 'Hindi', gender: 'F', age: 'Sweet', category: 'hindi_female' },
  { id: 'en-IN-NeerjaNeural', name: 'Neerja', lang: 'Indian EN', gender: 'F', age: 'Adult', category: 'hindi_female' },
  { id: 'en-IN-NeerjaExpressiveNeural', name: 'Neerja Exp', lang: 'Indian EN', gender: 'F', age: 'Expressive', category: 'hindi_female' },
  // ===== HINDI MALE (5) =====
  { id: 'hi-IN-MadhurNeural', name: 'Madhur', lang: 'Hindi', gender: 'M', age: 'Adult', category: 'hindi_male' },
  { id: 'young:hi-IN-MadhurNeural', name: 'Arjun', lang: 'Hindi', gender: 'M', age: 'Young', category: 'hindi_male' },
  { id: 'deep:hi-IN-MadhurNeural', name: 'Vikram', lang: 'Hindi', gender: 'M', age: 'Deep', category: 'hindi_male' },
  { id: 'old:hi-IN-MadhurNeural', name: 'Dadaji', lang: 'Hindi', gender: 'M', age: 'Old', category: 'hindi_male' },
  { id: 'en-IN-PrabhatNeural', name: 'Prabhat', lang: 'Indian EN', gender: 'M', age: 'Adult', category: 'hindi_male' },
  // ===== ENGLISH FEMALE (7) =====
  { id: 'en-US-JennyNeural', name: 'Jenny', lang: 'English US', gender: 'F', age: 'Adult', category: 'english_female' },
  { id: 'en-US-AriaNeural', name: 'Aria', lang: 'English US', gender: 'F', age: 'Adult', category: 'english_female' },
  { id: 'en-US-AvaNeural', name: 'Ava', lang: 'English US', gender: 'F', age: 'Adult', category: 'english_female' },
  { id: 'en-US-EmmaNeural', name: 'Emma', lang: 'English US', gender: 'F', age: 'Adult', category: 'english_female' },
  { id: 'en-US-MichelleNeural', name: 'Michelle', lang: 'English US', gender: 'F', age: 'Adult', category: 'english_female' },
  { id: 'en-GB-SoniaNeural', name: 'Sonia', lang: 'English UK', gender: 'F', age: 'Adult', category: 'english_female' },
  { id: 'en-GB-LibbyNeural', name: 'Libby', lang: 'English UK', gender: 'F', age: 'Young', category: 'english_female' },
  // ===== ENGLISH MALE (7) =====
  { id: 'en-US-GuyNeural', name: 'Guy', lang: 'English US', gender: 'M', age: 'Adult', category: 'english_male' },
  { id: 'en-US-AndrewNeural', name: 'Andrew', lang: 'English US', gender: 'M', age: 'Adult', category: 'english_male' },
  { id: 'en-US-BrianNeural', name: 'Brian', lang: 'English US', gender: 'M', age: 'Adult', category: 'english_male' },
  { id: 'en-US-ChristopherNeural', name: 'Chris', lang: 'English US', gender: 'M', age: 'Adult', category: 'english_male' },
  { id: 'en-US-EricNeural', name: 'Eric', lang: 'English US', gender: 'M', age: 'Adult', category: 'english_male' },
  { id: 'en-US-RogerNeural', name: 'Roger', lang: 'English US', gender: 'M', age: 'Adult', category: 'english_male' },
  { id: 'en-GB-RyanNeural', name: 'Ryan', lang: 'English UK', gender: 'M', age: 'Adult', category: 'english_male' },
  // ===== BABY BOY HINDI (3) =====
  { id: 'baby_boy_hi_1:hi-IN-MadhurNeural', name: 'Baby Boy 1', lang: 'Hindi', gender: 'Baby', age: 'Baby Boy', category: 'baby_boy', note: 'Soft pitch' },
  { id: 'baby_boy_hi_2:hi-IN-MadhurNeural', name: 'Baby Boy 2', lang: 'Hindi', gender: 'Baby', age: 'Baby Boy', category: 'baby_boy', note: 'Light pitch' },
  { id: 'baby_boy_hi_3:hi-IN-MadhurNeural', name: 'Baby Boy 3', lang: 'Hindi', gender: 'Baby', age: 'Baby Boy', category: 'baby_boy', note: 'High pitch' },
  // ===== BABY GIRL HINDI (3) =====
  { id: 'baby_girl_hi_1:hi-IN-SwaraNeural', name: 'Baby Girl 1', lang: 'Hindi', gender: 'Baby', age: 'Baby Girl', category: 'baby_girl', note: 'Soft pitch' },
  { id: 'baby_girl_hi_2:hi-IN-SwaraNeural', name: 'Baby Girl 2', lang: 'Hindi', gender: 'Baby', age: 'Baby Girl', category: 'baby_girl', note: 'Light pitch' },
  { id: 'baby_girl_hi_3:hi-IN-SwaraNeural', name: 'Baby Girl 3', lang: 'Hindi', gender: 'Baby', age: 'Baby Girl', category: 'baby_girl', note: 'High pitch' },
  // ===== BABY BOY ENGLISH (3) =====
  { id: 'baby_boy_en_1:en-US-GuyNeural', name: 'Baby Boy EN 1', lang: 'English', gender: 'Baby', age: 'Baby Boy', category: 'baby_boy', note: 'Soft pitch' },
  { id: 'baby_boy_en_2:en-US-AndrewNeural', name: 'Baby Boy EN 2', lang: 'English', gender: 'Baby', age: 'Baby Boy', category: 'baby_boy', note: 'Light pitch' },
  { id: 'baby_boy_en_3:en-US-BrianNeural', name: 'Baby Boy EN 3', lang: 'English', gender: 'Baby', age: 'Baby Boy', category: 'baby_boy', note: 'High pitch' },
  // ===== BABY GIRL ENGLISH (3) — Session 25 round 10: AnaNeural is
  //       Microsoft's real "child" voice; pairs with AriaNeural + EmmaNeural
  //       both with strong upward pitch shift for genuine child timbre.
  { id: 'baby_girl_en_1:en-US-AnaNeural',  name: 'Baby Girl EN 1', lang: 'English', gender: 'Baby', age: 'Baby Girl', category: 'baby_girl', note: 'Real child voice' },
  { id: 'baby_girl_en_2:en-US-AnaNeural',  name: 'Baby Girl EN 2', lang: 'English', gender: 'Baby', age: 'Baby Girl', category: 'baby_girl', note: 'Bright child' },
  { id: 'baby_girl_en_3:en-US-AriaNeural', name: 'Baby Girl EN 3', lang: 'English', gender: 'Baby', age: 'Baby Girl', category: 'baby_girl', note: 'Higher pitch' },
  // ===== SARVAM AI (Indian voices, premium) =====
  { id: 'sarvam:anushka',  name: 'Anushka',  lang: 'Hindi (Sarvam)', gender: 'F', age: 'Premium', category: 'sarvam_female', provider: 'sarvam' },
  { id: 'sarvam:manisha',  name: 'Manisha',  lang: 'Hindi (Sarvam)', gender: 'F', age: 'Premium', category: 'sarvam_female', provider: 'sarvam' },
  { id: 'sarvam:vidya',    name: 'Vidya',    lang: 'Hindi (Sarvam)', gender: 'F', age: 'Premium', category: 'sarvam_female', provider: 'sarvam' },
  { id: 'sarvam:arya',     name: 'Arya',     lang: 'Hindi (Sarvam)', gender: 'F', age: 'Premium', category: 'sarvam_female', provider: 'sarvam' },
  { id: 'sarvam:abhilash', name: 'Abhilash', lang: 'Hindi (Sarvam)', gender: 'M', age: 'Premium', category: 'sarvam_male',   provider: 'sarvam' },
  { id: 'sarvam:karun',    name: 'Karun',    lang: 'Hindi (Sarvam)', gender: 'M', age: 'Premium', category: 'sarvam_male',   provider: 'sarvam' },
  { id: 'sarvam:hitesh',   name: 'Hitesh',   lang: 'Hindi (Sarvam)', gender: 'M', age: 'Premium', category: 'sarvam_male',   provider: 'sarvam' },
];

export const VOICE_CATEGORIES: { id: Voice['category']; label: string; icon: string; color: string; provider?: 'edge-tts' | 'sarvam' }[] = [
  { id: 'hindi_female', label: 'Hindi ♀', icon: 'woman', color: '#EC4899', provider: 'edge-tts' },
  { id: 'hindi_male', label: 'Hindi ♂', icon: 'man', color: '#3B82F6', provider: 'edge-tts' },
  { id: 'english_female', label: 'English ♀', icon: 'woman', color: '#A78BFA', provider: 'edge-tts' },
  { id: 'english_male', label: 'English ♂', icon: 'man', color: '#06B6D4', provider: 'edge-tts' },
  { id: 'baby_girl', label: 'Baby Girl', icon: 'happy', color: '#F472B6', provider: 'edge-tts' },
  { id: 'baby_boy', label: 'Baby Boy', icon: 'happy', color: '#FCD34D', provider: 'edge-tts' },
  { id: 'sarvam_female', label: 'Sarvam ♀', icon: 'star', color: '#F59E0B', provider: 'sarvam' },
  { id: 'sarvam_male', label: 'Sarvam ♂', icon: 'star', color: '#10B981', provider: 'sarvam' },
];

export const findVoice = (id: string) => VOICE_LIBRARY.find(v => v.id === id);

export const getVoicesByCategory = (cat: Voice['category']) =>
  VOICE_LIBRARY.filter(v => v.category === cat);
