# services/strings.py
# Сборка уникального текста из пула строк

import os
import random

# Папка со строками
STRINGS_DIR = os.path.join("assets", "affirmations", "strings")

# Сколько строк брать для одного текста
LINES_PER_TEXT = 14


def build_from_strings(topic_key: str) -> str | None:
    """
    Собирает уникальный текст из случайных строк пула.

    :param topic_key: имя файла без .txt (money, love, health...)
    :return: текст из 14 случайных строк, или None при ошибке
    """
    file_path = os.path.join(STRINGS_DIR, f"{topic_key}.txt")

    if not os.path.exists(file_path):
        print(f"Нет файла строк: {file_path}")
        return None

    # Читаем все строки
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < LINES_PER_TEXT:
        print(f"Мало строк в {file_path}: {len(lines)}")
        return None

    # Берём 14 случайных строк
    chosen = random.sample(lines, LINES_PER_TEXT)

    # Склеиваем в текст
    return "\n".join(chosen)