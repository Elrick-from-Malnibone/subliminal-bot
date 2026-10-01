# services/audio.py
# Модуль наложения голоса на фоновый трек + бинауральные ритмы

import os
import time
import numpy as np
import random

# Маппинг тем → сольфеджио-частотам
SOLFEGGIO_MAP = {
    "money": 888,
    "love": 528,
    "health": 285,
    "career": 741,
    "confidence": 396,
    "calm": 432,
    "weight": 285,
    "motivation": 417,
    "luck": 888,
    "magnetism": 639,
}

# Маппинг тем → бинауральным ритмам
BINAURAL_MAP = {
    "money": (200, 210),
    "love": (200, 210),
    "health": (200, 202),
    "career": (200, 215),
    "confidence": (200, 210),
    "calm": (200, 206),
    "weight": (200, 210),
    "motivation": (200, 215),
    "luck": (200, 210),
    "magnetism": (200, 210),
}

# ← ДОБАВЛЯЕМ FFMPEG В PATH ПЕРЕД ИМПОРТОМ PYDUB
ffmpeg_dir = r"C:\Users\sysin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]

from pydub import AudioSegment


# Папка с фоновыми треками
ASSETS_DIR = "assets"

# Папка для готовых саблиминалов
OUTPUT_DIR = "output"


def generate_binaural(duration_ms: int, freq_left: float = 200.0, freq_right: float = 210.0) -> AudioSegment:
    """Генерирует бинауральный ритм через numpy. 1 секунда + зацикливание."""
    sample_rate = 44100

    # Генерим только 1 секунду
    n_samples = sample_rate
    t = np.linspace(0, 1, n_samples, False)

    left = np.sin(freq_left * 2 * np.pi * t)
    right = np.sin(freq_right * 2 * np.pi * t)

    stereo = np.column_stack((left, right))
    stereo_int16 = (stereo * 32767).astype(np.int16)

    one_sec = AudioSegment(
        stereo_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=2
    )

    # Зацикливаем до нужной длины
    loops = (duration_ms // 1000) + 1
    return one_sec * loops


def generate_solfeggio(duration_ms: int, freq: float = 528.0) -> AudioSegment:
    """Генерирует сольфеджио-частоту. 1 секунда + зацикливание."""
    sample_rate = 44100

    # Генерим только 1 секунду
    n_samples = sample_rate
    t = np.linspace(0, 1, n_samples, False)

    tone = np.sin(freq * 2 * np.pi * t)
    stereo = np.column_stack((tone, tone))
    stereo_int16 = (stereo * 32767).astype(np.int16)

    one_sec = AudioSegment(
        stereo_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=2
    )

    # Зацикливаем до нужной длины
    loops = (duration_ms // 1000) + 1
    return one_sec * loops


def apply_reverb(audio: AudioSegment) -> AudioSegment:
    """Заглушка — реверб убран."""
    return audio

def create_subliminal(voice_path: str, category: str = "nature", custom_track: str = None, length_minutes: int = None, custom_solfeggio: int = None, custom_binaural: tuple = None, voice_offset: int = 0) -> str | None:
    """Накладывает голос на трек + бинаурал + сольфеджио."""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if custom_track:
        background_path = custom_track
        print(f"Использую свой трек: {custom_track}")
    else:
        category_dir = os.path.join(ASSETS_DIR, category)

        if not os.path.isdir(category_dir):
            print(f"Нет папки категории: {category_dir}")
            return None

        tracks = [f for f in os.listdir(category_dir) if f.lower().endswith(".mp3")]

        if not tracks:
            print(f"В папке {category_dir} нет MP3-файлов")
            return None

        chosen_track = random.choice(tracks)
        background_path = os.path.join(category_dir, chosen_track)
        print(f"Выбран трек: {chosen_track}")

    if not os.path.exists(voice_path):
        print(f"Нет файла с голосом: {voice_path}")
        return None

    try:
        # === 1. ЗАГРУЗКА ===
        voice = AudioSegment.from_file(voice_path)
        background = AudioSegment.from_file(background_path)

        # === 2. ОБРАБОТКА ФОНА ===
        background = background - 6

        # === 3. ОБРАБОТКА ГОЛОСА ===
        #voice = apply_reverb(voice)

        # === 4. ОПРЕДЕЛЯЕМ ДЛИНУ ===
        if length_minutes:
            target_length_ms = length_minutes * 60 * 1000
        else:
            target_length_ms = len(background)

        # === 5. ЗАЦИКЛИВАЕМ ФОН ===
        if len(background) < target_length_ms:
            loops_needed = (target_length_ms // len(background)) + 1
            looped = background
            for _ in range(loops_needed - 1):
                looped = looped.append(background, crossfade=1000)
            background = looped

        background = background[:target_length_ms]

                # === 6. ПРИВЯЗКА ГОЛОСА К ФОНУ ===
        bg_volume = background.dBFS
        voice_volume = voice.dBFS
        target_voice_volume = bg_volume - 25 + voice_offset

        

        voice = voice.apply_gain(target_voice_volume - voice_volume)

        # === 7. ЗАЦИКЛИВАЕМ ГОЛОС ===
        if len(voice) < len(background):
            voice_loops = (len(background) // len(voice)) + 1
            voice = voice * voice_loops

        voice = voice[:len(background)]

        # === 8. НАКЛАДЫВАЕМ ГОЛОС НА ФОН ===
        mixed = background.overlay(voice)

        # === 9. БИНАУРАЛ ===
        if custom_binaural is None and custom_solfeggio is None:
            freq_left, freq_right = BINAURAL_MAP.get(category, (200, 210))
        elif custom_binaural:
            freq_left, freq_right = custom_binaural
        else:
            freq_left, freq_right = None, None

        if freq_left is not None and freq_right is not None:
            binaural = generate_binaural(len(mixed), freq_left=freq_left, freq_right=freq_right)

            bg_vol = background.dBFS
            bin_vol = binaural.dBFS
            target_bin_vol = bg_vol - 32

            if target_bin_vol < -55:
                target_bin_vol = -55

            binaural = binaural.apply_gain(target_bin_vol - bin_vol)

            final = mixed.overlay(binaural)
        else:
            final = mixed

        # === 10. СОЛЬФЕДЖИО ===
        if custom_solfeggio is None and custom_binaural is None:
            solfeggio_freq = SOLFEGGIO_MAP.get(category, 528)
        else:
            solfeggio_freq = custom_solfeggio

        if solfeggio_freq:
            solfeggio = generate_solfeggio(len(mixed), freq=solfeggio_freq)

            bg_vol = background.dBFS
            sol_vol = solfeggio.dBFS
            target_sol_vol = bg_vol - 45

            if target_sol_vol < -60:
                target_sol_vol = -60

            solfeggio = solfeggio.apply_gain(target_sol_vol - sol_vol)

            final = final.overlay(solfeggio)

        # === 11. FADE OUT — только к последним 5 секундам ===
        if len(final) > 5000:
            main_part = final[:-5000]
            fade_part = final[-5000:]
            fade_part = fade_part.fade_out(5000)
            final = main_part + fade_part
        else:
            final = final.fade_out(5000)

        # === 12. ЭКСПОРТ ===
        original_name = os.path.splitext(os.path.basename(background_path))[0]
        filename = f"{OUTPUT_DIR}/subliminal_{original_name}.mp3"
        final.export(filename, format="mp3")

        return filename

    except Exception as e:
        print(f"Ошибка обработки аудио: {e}")
        return None