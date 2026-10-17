# services/tts.py
import os
import time
from fishaudio import FishAudio
from config import FISH_API_KEY

AUDIO_DIR = "audio"
client = FishAudio(api_key=FISH_API_KEY)

# Маппинг твоих кнопок на ID голосов Fish Audio
VOICES = {
    "male_1":   "0a690dbeb3984a9f88cd39353880775f",  # Меллстрой (мужской)
    "male_2":   "0a690dbeb3984a9f88cd39353880775f",  # Пока тот же
    "female_1": "2a1036d645634680b3cc69aeeb60375b",  # Спокойный женский
    "female_2": "2a1036d645634680b3cc69aeeb60375b",  # Пока тот же
}

async def generate_voice(text: str, voice_type: str = "male_1", reference_id: str = None) -> str | None:
    """Озвучивает текст. Если reference_id — клоном, иначе — выбранным голосом."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    filename = f"{AUDIO_DIR}/voice_{int(time.time() * 1000)}.mp3"

    try:
        if reference_id:
            # Клон юзера
            audio = client.tts.convert(text=text, reference_id=reference_id)
        else:
            # Обычный голос из списка
            voice_id = VOICES.get(voice_type, VOICES["male_1"])
            audio = client.tts.convert(text=text, reference_id=voice_id)

        with open(filename, "wb") as f:
            f.write(audio)

        return filename

    except Exception as e:
        print(f"Ошибка TTS: {e}")
        return None