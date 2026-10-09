import torch
import os
import re
from services.audio import create_subliminal

# === НАСТРОЙКИ ===
AFFIRMATIONS_FILE = "affirmations.txt"
TRACK_PATH = "assets/user/mytrack.mp3"
VOICE_SPEAKER = "xenia"          # женский мягкий
SAMPLE_RATE = 48000
SOLFEGGIO = 888                  # Гц
BINAURAL = (200, 206)            # тета 6 Гц
LENGTH_MINUTES = None            # None = по длине трека
VOICE_OFFSET = 0                 # громкость голоса


def generate_voice_silero(text: str, speaker: str = "xenia") -> str:
    """Генерирует голос через Silero TTS с очисткой текста и разбивкой на куски."""
    from pydub import AudioSegment

    device = torch.device("cpu")
    torch.set_num_threads(4)

    model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-models",
        model="silero_tts",
        language="ru",
        speaker="v4_ru"
    )
    model.to(device)

    # Чистим текст: убираем спецсимволы
    text = re.sub(r'[*_\[\](){}<>]', '', text)

    # Убираем пустые строки, склеиваем в один поток
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '. '.join(lines)

    # Разбиваем на куски по 500 символов
    chunks = [text[i:i+500] for i in range(0, len(text), 500)]

    os.makedirs("audio", exist_ok=True)
    audio_path = "audio/voice_silero.wav"

    combined = AudioSegment.empty()

    for i, chunk in enumerate(chunks):
        print(f"  Озвучиваю кусок {i+1}/{len(chunks)}...")
        temp_path = f"audio/temp_chunk_{i}.wav"
        model.save_wav(
            text=chunk,
            speaker=speaker,
            sample_rate=SAMPLE_RATE,
            audio_path=temp_path
        )
        chunk_audio = AudioSegment.from_file(temp_path)
        combined += chunk_audio
        os.remove(temp_path)

    combined.export(audio_path, format="wav")
    return audio_path


def main():
    # 1. Читаем текст
    with open(AFFIRMATIONS_FILE, "r", encoding="utf-8") as f:
        text = f.read().strip()

    print("🎙 Генерирую голос через Silero...")
    voice_path = generate_voice_silero(text, speaker=VOICE_SPEAKER)
    print(f"✅ Голос: {voice_path}")

    # 2. Собираем саблиминал
    print("🎧 Собираю саблиминал...")
    subliminal_path = create_subliminal(
        voice_path=voice_path,
        category=None,
        custom_track=TRACK_PATH,
        length_minutes=LENGTH_MINUTES,
        custom_solfeggio=SOLFEGGIO,
        custom_binaural=BINAURAL,
        voice_offset=VOICE_OFFSET
    )
    print(f"✅ Готово: {subliminal_path}")


if __name__ == "__main__":
    main()