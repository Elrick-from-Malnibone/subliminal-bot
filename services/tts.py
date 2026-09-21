# services/tts.py
# Модуль озвучки текста через edge-tts + эффект робота через pedalboard

import os
import time

# ← FFMPEG В PATH (нужен для pydub)
ffmpeg_dir = r"C:\Users\sysin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]

import edge_tts
from pydub import AudioSegment


# Папка для сохранения аудио
AUDIO_DIR = "audio"


# Доступные голоса с параметрами
# rate — скорость, pitch — тон
VOICES = {
    "male_1":   {"voice": "ru-RU-DmitryNeural",   "rate": "+0%",  "pitch": "+0Hz"},
    "male_2":   {"voice": "ru-RU-DmitryNeural",   "rate": "-15%", "pitch": "-20Hz"},
    "female_1": {"voice": "ru-RU-SvetlanaNeural", "rate": "+0%",  "pitch": "+0Hz"},
    "female_2": {"voice": "ru-RU-SvetlanaNeural", "rate": "-10%", "pitch": "-10Hz"},
}



async def generate_voice(text: str, voice_type: str = "male_1") -> str | None:
    """
    Озвучивает текст через edge-tts и сохраняет в MP3.

    :param text: str — текст для озвучки
    :param voice_type: str — ключ из VOICES
    :return: str — путь к MP3-файлу, или None при ошибке
    """

    # Создаём папку для аудио, если её нет
    os.makedirs(AUDIO_DIR, exist_ok=True)

    # Берём параметры голоса
    voice_params = VOICES.get(voice_type, VOICES["male_1"])

    # Уникальное имя файла
    filename = f"{AUDIO_DIR}/voice_{int(time.time() * 1000)}.mp3"

    try:
        # Создаём Communicate с параметрами rate и pitch
        communicate = edge_tts.Communicate(
            text,
            voice_params["voice"],
            rate=voice_params["rate"],
            pitch=voice_params["pitch"],
        )
        await communicate.save(filename)

        return filename

    except Exception as e:
        print(f"Ошибка TTS: {e}")
        return None