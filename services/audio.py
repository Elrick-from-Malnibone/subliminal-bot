# services/audio.py
# Модуль наложения голоса на фоновый трек + бинауральные ритмы

import os
import time
import numpy as np
import random

# ← ДОБАВЛЯЕМ FFMPEG В PATH ПЕРЕД ИМПОРТОМ PYDUB
ffmpeg_dir = r"C:\Users\sysin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin"
os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]

from pydub import AudioSegment
from pedalboard import Pedalboard, Reverb, LowpassFilter, HighpassFilter

# Папка с фоновыми треками
ASSETS_DIR = "assets"

# Папка для готовых саблиминалов
OUTPUT_DIR = "output"


def generate_binaural(duration_ms: int, freq_left: float = 200.0, freq_right: float = 210.0) -> AudioSegment:
    """
    Генерирует бинауральный ритм через numpy.
    """
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)

    t = np.linspace(0, duration_ms / 1000, n_samples, False)

    left = np.sin(freq_left * 2 * np.pi * t)
    right = np.sin(freq_right * 2 * np.pi * t)

    stereo = np.column_stack((left, right))
    stereo_int16 = (stereo * 32767).astype(np.int16)

    audio = AudioSegment(
        stereo_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=2
    )

    return audio


def apply_reverb(audio: AudioSegment) -> AudioSegment:
    """
    Накладывает реверберацию через pedalboard.
    """
    # Конвертируем AudioSegment → numpy массив
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

    # Нормализуем в диапазон [-1, 1]
    samples = samples / 32768.0

    # Ресемплим в стерео, если моно
    if audio.channels == 1:
        samples = np.column_stack((samples, samples))
    else:
        samples = samples.reshape((-1, 2))

    # Создаём цепочку эффектов
    board = Pedalboard([
        LowpassFilter(cutoff_frequency_hz=2000),   # глушим высокие
        HighpassFilter(cutoff_frequency_hz=300),   # глушим низкие
        Reverb(
            room_size=0.75,        # большое пространство
            damping=0.7,           # мягкое затухание
            wet_level=0.6,         # 50% реверба
            dry_level=0.4,         # 50% оригинала
            width=1.0,             # стерео-ширина
        ),
    ])

    # Прогоняем через эффекты
    processed = board(samples, audio.frame_rate)

    # Конвертируем обратно в 16-бит PCM
    processed_int16 = (processed * 32767).astype(np.int16)

    # Создаём AudioSegment
    result = AudioSegment(
        processed_int16.tobytes(),
        frame_rate=audio.frame_rate,
        sample_width=2,
        channels=2
    )

    return result


def create_subliminal(voice_path: str, category: str = "nature", custom_track: str = None, length_minutes: int = None) -> str | None:
    """
    Накладывает голос на трек.

    :param voice_path: путь к MP3 с озвучкой
    :param category: название папки в assets/ (ambient, deephouse, lofi, nature)
    :param custom_track: путь к своему треку юзера (если есть)
    :return: путь к готовому саблиминалу, или None при ошибке
    """

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Если юзер загрузил свой трек — используем его
    if custom_track:
        background_path = custom_track
        print(f"Использую свой трек: {custom_track}")
    else:
        # Иначе — случайный из категории
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

    # Проверяем, что голос существует
    if not os.path.exists(voice_path):
        print(f"Нет файла с голосом: {voice_path}")
        return None

    try:
        # Загружаем голос и фон
        voice = AudioSegment.from_file(voice_path)
        background = AudioSegment.from_file(background_path)

        # Голос тише на 20 дБ (реверб сделает остальное)
        voice = voice - 25

        # Накладываем реверберацию
        voice = apply_reverb(voice)

        # Фон чуть тише
        background = background - 1

        # Растягиваем фон, если он короче голоса
        if len(background) < len(voice):
            loops_needed = (len(voice) // len(background)) + 1
            background = background * loops_needed

                # Определяем итоговую длину
        if length_minutes:
            target_length_ms = length_minutes * 60 * 1000
        else:
            # По длине трека
            target_length_ms = len(background)

        # Зацикливаем фон, если он короче нужного
        if len(background) < target_length_ms:
            loops_needed = (target_length_ms // len(background)) + 1
            background = background * loops_needed

        # Обрезаем фон под нужную длину
        background = background[:target_length_ms]

        # Зацикливаем голос под длину фона
        if len(voice) < len(background):
            voice_loops = (len(background) // len(voice)) + 1
            voice = voice * voice_loops

        # Обрезаем голос под длину фона
        voice = voice[:len(background)]

        # Накладываем голос на фон
        mixed = background.overlay(voice)

        # Плавное затухание в конце
        mixed = mixed.fade_out(5000)

        # Генерируем бинауральный ритм
        binaural = generate_binaural(len(mixed), freq_left=200, freq_right=210)
        binaural = binaural - 18

        # Накладываем бинауральные ритмы
        final = mixed.overlay(binaural)

        # Сохраняем
        filename = f"{OUTPUT_DIR}/subliminal_{int(time.time() * 1000)}.mp3"
        final.export(filename, format="mp3")

        return filename

    

    except Exception as e:
        print(f"Ошибка обработки аудио: {e}")
        return None

def make_preview(track_path: str, seconds: int = 15) -> str | None:
    """Режет первые N секунд трека для превью."""
    from pydub import AudioSegment
    try:
        audio = AudioSegment.from_file(track_path)
        preview = audio[:seconds * 1000]
        preview_path = track_path.replace(".mp3", "_preview.mp3")
        preview.export(preview_path, format="mp3")
        return preview_path
    except Exception as e:
        print(f"Ошибка превью: {e}")
        return None
