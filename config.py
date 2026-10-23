import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Токен бота (из .env)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Ключ DeepSeek (из .env)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# URL API DeepSeek (не меняется)
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Модель
DEEPSEEK_MODEL = "deepseek-v4-flash"

# ID админа (для статистики и оповещений)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHANNEL_ID = os.getenv("CHANNEL_ID")

# === ЦЕНЫ ===
PRICE_SUBLIMINAL = 100        # обычный саб (после бесплатного)
PRICE_FIRST_CLONE = 200       # первый саб с клоном голоса
PRICE_CLONE = 1           # последующие сабы с клоном

# === АНТИСПАМ ===
FREE_ANTISPAM = 30           # секунд между генерациями

# ЮKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

# Fish Audio
FISH_API_KEY = os.getenv("FISH_API_KEY")

FEEDBACK_CHAT_ID = -1004426924647