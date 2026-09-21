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