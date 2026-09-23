# services/audio.py
# Модуль наложения голоса на фоновый трек + бинауральные ритмы

import os
import time
import numpy as np
import random

# Маппинг тем → сольфеджио-частотам
SOLFEGGIO_MAP = {
    "money": 888,       # изобилие
    "love": 528,        # любовь и исцеление
    "health": 285,      # регенерация
    "career": 741,      # интуиция и решения
    "confidence": 396,  # свобода от страха
    "calm": 432,        # гармония
    "weight": 285,      # регенерация
    "motivation": 417,  # изменения
    "luck": 888,        # изобилие
    "magnetism": 639,   # связь с людьми
}

# Маппинг тем → бинауральным ритмам
# Дельта (2-3 Гц) — глубокий сон, восстановление
# Тета (6 Гц) — медитация, расслабление
# Альфа (10 Гц) — спокойная бодрость, творчество
# Бета (15 Гц) — фокус, драйв, действие

BINAURAL_MAP = {
    "money": (200, 210),       # альфа 10 Гц
    "love": (200, 210),        # альфа 10 Гц
    "health": (200, 202),      # ДЕЛЬТА 2 Гц — восстановление
    "career": (200, 215),      # бета 15 Гц — драйв
    "confidence": (200, 210),  # альфа 10 Гц
    "calm": (200, 206),        # тета 6 Гц — медитация
    "weight": (200, 210),      # альфа 10 Гц
    "motivation": (200, 215),  # бета 15 Гц — драйв
    "luck": (200, 210),        # альфа 10 Гц
    "magnetism": (200, 210),   # альфа 10 Гц
}

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
def generate_solfeggio(duration_ms: int, freq: float = 528.0) -> AudioSegment:
    """
    Генерирует сольфеджио-частоту (один тон в оба канала).
    
    :param duration_ms: длительность в миллисекундах
    :param freq: частота в Гц (528, 432, 888 и т.д.)
    :return: AudioSegment со стерео-звуком
    """
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    
    t = np.linspace(0, duration_ms / 1000, n_samples, False)
    
    # Один тон для обоих каналов
    tone = np.sin(freq * 2 * np.pi * t)
    
    # Дублируем в стерео
    stereo = np.column_stack((tone, tone))
    
    # Конвертируем в 16-битный PCM
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


def create_subliminal(voice_path: str, category: str = "nature", custom_track: str = None, length_minutes: int = None, custom_solfeggio: int = None, custom_binaural: tuple = None) -> str | None:
    """
    Накладывает голос на трек + бинаурал + сольфеджио.
    
    :param voice_path: путь к MP3 с озвучкой
    :param category: название папки в assets/ (тема для выбора частот)
    :param custom_track: путь к своему треку юзера (если есть)
    :param length_minutes: длина в минутах (None = по длине трека)
    :return: путь к готовому саблиминалу, или None при ошибке
    """

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Если юзер загрузил свой трек — используем его
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
        # Загружаем голос и фон
        voice = AudioSegment.from_file(voice_path)
        background = AudioSegment.from_file(background_path)

        # Фон чуть тише
        background = background - 6

        # Накладываем реверберацию на голос
        voice = apply_reverb(voice)

        # Привязываем громкость голоса к громкости фона
        bg_volume = background.dBFS
        voice_volume = voice.dBFS
        target_voice_volume = bg_volume - 27
        voice = voice.apply_gain(target_voice_volume - voice_volume)

        # Определяем итоговую длину
        if length_minutes:
            target_length_ms = length_minutes * 60 * 1000
        else:
            target_length_ms = len(background)

        # Зацикливаем фон с кроссфейдом, если он короче нужного
        if len(background) < target_length_ms:
            loops_needed = (target_length_ms // len(background)) + 1
            looped = background
            for _ in range(loops_needed - 1):
                looped = looped.append(background, crossfade=1000)
            background = looped

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

                # Берём бинаурал — кастомный от юзера или из маппинга
        if custom_binaural is None and custom_solfeggio is None:
            # Для готовых тем — из маппинга
            freq_left, freq_right = BINAURAL_MAP.get(category, (200, 210))
        elif custom_binaural:
            # Юзер выбрал свой ритм
            freq_left, freq_right = custom_binaural
        else:
            # Юзер выбрал «без бинаурала»
            freq_left, freq_right = None, None

                # Накладываем бинаурал, если он есть
        if freq_left is not None and freq_right is not None:
            binaural = generate_binaural(len(mixed), freq_left=freq_left, freq_right=freq_right)
            binaural = binaural - 30
            final = mixed.overlay(binaural)
        else:
            final = mixed

                # Берём сольфеджио — кастомный от юзера или из маппинга
        if custom_solfeggio is None and custom_binaural is None:
            # Для готовых тем — из маппинга
            solfeggio_freq = SOLFEGGIO_MAP.get(category, 528)
        else:
            # Юзер выбрал сам (или «без частоты»)
            solfeggio_freq = custom_solfeggio

                # Накладываем сольфеджио, если оно есть
        if solfeggio_freq:
            solfeggio = generate_solfeggio(len(mixed), freq=solfeggio_freq)
            solfeggio = solfeggio - 35
            final = final.overlay(solfeggio)

        # Плавное затухание в конце — на всём финале
        final = final.fade_out(5000)

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
