"""Catalog of TTS voices shown to the user.

Session 27d: Extracted from server.py for routes/catalog.py consumption.
"""

VOICE_LIBRARY = [
    # ===== HINDI FEMALE (5+) =====
    {"id": "hi-IN-SwaraNeural", "name": "Swara", "language": "Hindi", "gender": "Female", "age": "Adult", "preview_text": "Namaste, main Swara hoon. Aap kaise hain?"},
    {"id": "young:hi-IN-SwaraNeural", "name": "Priya", "language": "Hindi", "gender": "Female", "age": "Young", "preview_text": "Hi, main Priya hoon. Kaise ho aap?"},
    {"id": "sweet:hi-IN-SwaraNeural", "name": "Meera", "language": "Hindi", "gender": "Female", "age": "Sweet", "preview_text": "Namaste, main Meera. Aapka swagat hai."},
    {"id": "en-IN-NeerjaNeural", "name": "Neerja", "language": "Indian English", "gender": "Female", "age": "Adult", "preview_text": "Hello, I am Neerja. How can I help you today?"},
    {"id": "en-IN-NeerjaExpressiveNeural", "name": "Neerja Expressive", "language": "Indian English", "gender": "Female", "age": "Expressive", "preview_text": "Hello! I am Neerja, nice to meet you!"},
    # ===== HINDI MALE (5+) =====
    {"id": "hi-IN-MadhurNeural", "name": "Madhur", "language": "Hindi", "gender": "Male", "age": "Adult", "preview_text": "Namaste, main Madhur hoon. Kaise hain aap?"},
    {"id": "young:hi-IN-MadhurNeural", "name": "Arjun", "language": "Hindi", "gender": "Male", "age": "Young", "preview_text": "Hi, main Arjun. Sab theek hai?"},
    {"id": "deep:hi-IN-MadhurNeural", "name": "Vikram", "language": "Hindi", "gender": "Male", "age": "Deep", "preview_text": "Namaskar, main Vikram. Dhanyavaad."},
    {"id": "old:hi-IN-MadhurNeural", "name": "Dadaji", "language": "Hindi", "gender": "Male", "age": "Old", "preview_text": "Beta, main Dadaji hoon. Aao baith jao."},
    {"id": "en-IN-PrabhatNeural", "name": "Prabhat", "language": "Indian English", "gender": "Male", "age": "Adult", "preview_text": "Hello, I am Prabhat. Welcome to MagiCAi Studio."},
    # ===== ENGLISH FEMALE (5+) =====
    {"id": "en-US-JennyNeural", "name": "Jenny", "language": "English US", "gender": "Female", "age": "Adult", "preview_text": "Hi there, I'm Jenny. Nice to meet you!"},
    {"id": "en-US-AriaNeural", "name": "Aria", "language": "English US", "gender": "Female", "age": "Adult", "preview_text": "Hello, I'm Aria. How can I help?"},
    {"id": "en-US-AvaNeural", "name": "Ava", "language": "English US", "gender": "Female", "age": "Adult", "preview_text": "Hi, I'm Ava. Great to see you!"},
    {"id": "en-US-EmmaNeural", "name": "Emma", "language": "English US", "gender": "Female", "age": "Adult", "preview_text": "Hey, I'm Emma. Let's get started!"},
    {"id": "en-US-MichelleNeural", "name": "Michelle", "language": "English US", "gender": "Female", "age": "Adult", "preview_text": "Hi, this is Michelle speaking."},
    {"id": "en-GB-SoniaNeural", "name": "Sonia", "language": "English UK", "gender": "Female", "age": "Adult", "preview_text": "Hello, I'm Sonia from the UK."},
    {"id": "en-GB-LibbyNeural", "name": "Libby", "language": "English UK", "gender": "Female", "age": "Young", "preview_text": "Hi, I'm Libby. How are you?"},
    # ===== ENGLISH MALE (5+) =====
    {"id": "en-US-GuyNeural", "name": "Guy", "language": "English US", "gender": "Male", "age": "Adult", "preview_text": "Hey, I'm Guy. Nice to meet you!"},
    {"id": "en-US-AndrewNeural", "name": "Andrew", "language": "English US", "gender": "Male", "age": "Adult", "preview_text": "Hello, I'm Andrew. How can I help?"},
    {"id": "en-US-BrianNeural", "name": "Brian", "language": "English US", "gender": "Male", "age": "Adult", "preview_text": "Hi, this is Brian speaking."},
    {"id": "en-US-ChristopherNeural", "name": "Chris", "language": "English US", "gender": "Male", "age": "Adult", "preview_text": "Hey, I'm Chris. Let's roll!"},
    {"id": "en-US-EricNeural", "name": "Eric", "language": "English US", "gender": "Male", "age": "Adult", "preview_text": "Hello, I'm Eric. Good to see you."},
    {"id": "en-US-RogerNeural", "name": "Roger", "language": "English US", "gender": "Male", "age": "Adult", "preview_text": "Hi, I'm Roger. How's it going?"},
    {"id": "en-GB-RyanNeural", "name": "Ryan", "language": "English UK", "gender": "Male", "age": "Adult", "preview_text": "Hello, I'm Ryan from the UK."},
    # ===== BABY BOY HINDI =====
    {"id": "baby_boy_hi_1:hi-IN-MadhurNeural", "name": "Baby Boy 1", "language": "Hindi", "gender": "Baby", "age": "Baby Boy", "preview_text": "Mummy mummy, main aa gaya!"},
    {"id": "baby_boy_hi_2:hi-IN-MadhurNeural", "name": "Baby Boy 2", "language": "Hindi", "gender": "Baby", "age": "Baby Boy", "preview_text": "Papa, mujhe chocolate do na!"},
    {"id": "baby_boy_hi_3:hi-IN-MadhurNeural", "name": "Baby Boy 3", "language": "Hindi", "gender": "Baby", "age": "Baby Boy", "preview_text": "Namaste! Main chota bacha hoon."},
    # ===== BABY GIRL HINDI =====
    {"id": "baby_girl_hi_1:hi-IN-SwaraNeural", "name": "Baby Girl 1", "language": "Hindi", "gender": "Baby", "age": "Baby Girl", "preview_text": "Mummy mummy, meri guria lao!"},
    {"id": "baby_girl_hi_2:hi-IN-SwaraNeural", "name": "Baby Girl 2", "language": "Hindi", "gender": "Baby", "age": "Baby Girl", "preview_text": "Papa papa, mujhe ghumane le chalo!"},
    {"id": "baby_girl_hi_3:hi-IN-SwaraNeural", "name": "Baby Girl 3", "language": "Hindi", "gender": "Baby", "age": "Baby Girl", "preview_text": "Namaste! Main pyaari gudiya hoon."},
    # ===== BABY BOY ENGLISH =====
    {"id": "baby_boy_en_1:en-US-GuyNeural", "name": "Baby Boy EN 1", "language": "English", "gender": "Baby", "age": "Baby Boy", "preview_text": "Mommy mommy, look at me!"},
    {"id": "baby_boy_en_2:en-US-AndrewNeural", "name": "Baby Boy EN 2", "language": "English", "gender": "Baby", "age": "Baby Boy", "preview_text": "Daddy, can I have a cookie?"},
    {"id": "baby_boy_en_3:en-US-BrianNeural", "name": "Baby Boy EN 3", "language": "English", "gender": "Baby", "age": "Baby Boy", "preview_text": "Hi, I'm a little boy!"},
    # ===== BABY GIRL ENGLISH =====
    {"id": "baby_girl_en_1:en-US-JennyNeural", "name": "Baby Girl EN 1", "language": "English", "gender": "Baby", "age": "Baby Girl", "preview_text": "Mommy, I want my dolly!"},
    {"id": "baby_girl_en_2:en-US-AriaNeural", "name": "Baby Girl EN 2", "language": "English", "gender": "Baby", "age": "Baby Girl", "preview_text": "Daddy, take me to the park!"},
    {"id": "baby_girl_en_3:en-US-EmmaNeural", "name": "Baby Girl EN 3", "language": "English", "gender": "Baby", "age": "Baby Girl", "preview_text": "Hi, I'm a little girl!"},
    # ===== SARVAM AI (Indian voices, premium) =====
    {"id": "sarvam:anushka", "name": "Anushka (Sarvam)", "language": "Hindi", "gender": "Female", "age": "Sarvam", "provider": "sarvam", "preview_text": "Namaste, main Anushka hoon. Sarvam AI ki awaz."},
    {"id": "sarvam:manisha", "name": "Manisha (Sarvam)", "language": "Hindi", "gender": "Female", "age": "Sarvam", "provider": "sarvam", "preview_text": "Namaste, main Manisha. Aapka swagat hai."},
    {"id": "sarvam:vidya",   "name": "Vidya (Sarvam)",   "language": "Hindi", "gender": "Female", "age": "Sarvam", "provider": "sarvam", "preview_text": "Namaste, main Vidya bol rahi hoon."},
    {"id": "sarvam:arya",    "name": "Arya (Sarvam)",    "language": "Hindi", "gender": "Female", "age": "Sarvam", "provider": "sarvam", "preview_text": "Namaste, main Arya hoon. Kaise hain aap?"},
    {"id": "sarvam:abhilash", "name": "Abhilash (Sarvam)", "language": "Hindi", "gender": "Male", "age": "Sarvam", "provider": "sarvam", "preview_text": "Namaste, main Abhilash. Bolne mein khushi hogi."},
    {"id": "sarvam:karun",    "name": "Karun (Sarvam)",    "language": "Hindi", "gender": "Male", "age": "Sarvam", "provider": "sarvam", "preview_text": "Namaste, main Karun hoon. Swagat hai aapka."},
    {"id": "sarvam:hitesh",   "name": "Hitesh (Sarvam)",   "language": "Hindi", "gender": "Male", "age": "Sarvam", "provider": "sarvam", "preview_text": "Namaste, main Hitesh. Aap kaise hain?"},
]

