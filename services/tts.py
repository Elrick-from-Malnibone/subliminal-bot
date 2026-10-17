# services/tts.py
import os
import time
import requests
from config import FISH_API_KEY

AUDIO_DIR = "/app/data/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICES = {
    "male_1":   "0a690dbeb3984a9f88cd39353880775f",
    "male_2":   "0a690dbeb3984a9f88cd39353880775f",
    "female_1": "2a1036d645634680b3cc69aeeb60375b",
    "female_2": "2a1036d645634680b3cc69aeeb60375b",
}

async def generate_voice(text: str, voice_type: str = "male_1", reference_id: str = None) -> str | None:
    filename = f"{AUDIO_DIR}/voice_{int(time.time() * 1000)}.mp3"

    url = "https://api.fish.audio/v1/tts"
    headers = {
        "Authorization": f"Bearer {FISH_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "format": "mp3",
        "mp3_bitrate": 128,
        "chunk_length": 200,
        "normalize": True,
        "reference_id": reference_id or VOICES.get(voice_type, VOICES["male_1"])
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            print(f"Ошибка Fish Audio: {response.status_code} — {response.text}")
            return None

        with open(filename, "wb") as f:
            f.write(response.content)

        return filename

    except Exception as e:
        print(f"Ошибка TTS: {e}")
        return None

def clone_voice(audio_path: str) -> str | None:
    """Создаёт клон голоса через Fish Audio. Возвращает reference_id."""
    import requests

    url = "https://api.fish.audio/v1/model"
    headers = {
        "Authorization": f"Bearer {FISH_API_KEY}",
    }

    try:
        with open(audio_path, "rb") as f:
            files = {
                "voices": (os.path.basename(audio_path), f, "audio/wav"),
            }
            data = {
                "title": "My Voice",
                "description": "Cloned from user sample",
                "visibility": "private",
            }

            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)

        if response.status_code not in (200, 201):
            print(f"Ошибка клонирования: {response.status_code} — {response.text}")
            return None

        result = response.json()
        return result.get("id")

    except Exception as e:
        print(f"Ошибка клонирования: {e}")
        return None    