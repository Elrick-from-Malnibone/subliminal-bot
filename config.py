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

# === ЛИМИТЫ ===

# Бесплатный тариф
FREE_CUSTOM_TOPICS = 1      # своих тем в день
FREE_MINUTES_PER_DAY = 30   # минут в день
FREE_MINUTES_PER_HOUR = 30  # минут в час
FREE_ANTISPAM = 30          # секунд между генерациями

# Подписка
SUB_CUSTOM_TOPICS = 10       # своих тем в день
SUB_MINUTES_PER_DAY = 180    # минут в день
SUB_MINUTES_PER_HOUR = 90    # минут в час
SUB_ANTISPAM = 10            # секунд между генерациями

# === ЦЕНЫ  ===
PRICE_SUBSCRIPTION = 30      # подписка
PRICE_CUSTOM_TOPIC = 50      # разовая своя тема
PRICE_REMOVE_SIGNATURE = 30   # убрать подпись с 1 саба

# ЮKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")