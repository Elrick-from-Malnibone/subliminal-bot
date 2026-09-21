# services/affirmations.py
# Диспетчер: решает откуда брать текст — пул, строки или Дипсик

import os
import random

from services.strings import build_from_strings
from services.deepseek import generate_affirmation


# Папка с пулом целых текстов
POOL_DIR = os.path.join("assets", "affirmations")

# Разделитель текстов в файлах
SEPARATOR = "===ТЕКСТ==="

# Вероятности (в сумме = 1.0)
CHANCE_POOL = 0.70      # 70% — готовый текст из пула
CHANCE_STRINGS = 0.25   # 25% — сборка из строк
# Остаток 5% — Дипсик

# Последний источник (pool / strings / deepseek)
last_source = None


def get_from_pool(topic_key: str) -> str | None:
    """Берёт случайный текст из пула."""
    file_path = os.path.join(POOL_DIR, f"{topic_key}.txt")

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    texts = [t.strip() for t in content.split(SEPARATOR) if t.strip()]

    if not texts:
        return None

    return random.choice(texts)


def get_affirmation(topic_key: str, topic_text: str) -> str:
    """
    Главная функция — решает откуда взять текст.

    :param topic_key: ключ темы для файлов (money, love, health...)
    :param topic_text: текст темы для Дипсика ("деньги, богатство, изобилие")
    :return: текст аффирмаций
    """
    global last_source

    roll = random.random()

    # 70% — готовый текст из пула
    if roll < CHANCE_POOL:
        text = get_from_pool(topic_key)
        if text:
            print(f"[ПУЛ] {topic_key}")
            last_source = "pool"
            return text

    # 25% — сборка из строк
    if roll < CHANCE_POOL + CHANCE_STRINGS:
        text = build_from_strings(topic_key)
        if text:
            print(f"[СТРОКИ] {topic_key}")
            last_source = "strings"
            return text

    # 5% (или fallback) — Дипсик
    print(f"[ДИПСИК] {topic_text}")
    last_source = "deepseek"
    return generate_affirmation(topic_text)