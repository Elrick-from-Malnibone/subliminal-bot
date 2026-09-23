# services/deepseek.py
# Модуль для генерации аффирмаций через DeepSeek API

import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL


# Системный промпт — задаёт роль и правила для нейронки
SYSTEM_PROMPT = (
    "Ты эксперт по аффирмациям для саблиминалов. "
    "Создай 10-15 коротких аффирмаций от первого лица, в настоящем времени. "
    "Каждая — одно предложение, максимум 10 слов. Без 'я хочу'. "
    "\n\nВАЖНО про разнообразие: "
    "аффирмации должны затрагивать РАЗНЫЕ стороны темы, а не повторять одну мысль. "
    "Например, для денег: благодарность, уверенность, действия, возможности, "
    "отношение к себе, будущее, спокойствие, изобилие. "
    "\nТолько текст, каждая фраза с новой строки, без нумерации, без пояснений, без кавычек."
)


def generate_affirmation(user_text):
    """
    Принимает текст от юзера и возвращает аффирмации через DeepSeek API.

    :param user_text: str — запрос юзера (например, "хочу денег")
    :return: str — готовые аффирмации или сообщение об ошибке
    """

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        "temperature": 1.0,
        "max_tokens": 1500,
        "thinking": {"type": "disabled"}
    }

    # Заголовки с ключом авторизации
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # Отправляем POST-запрос к DeepSeek API
        response = requests.post(
            DEEPSEEK_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )

        # Если статус не 200 — что-то пошло не так
        if response.status_code != 200:
            return f"Ошибка API DeepSeek: {response.status_code}. Попробуй позже."

        # Достаём текст ответа из структуры JSON
        data = response.json()
        affirmation = data["choices"][0]["message"]["content"].strip()

        # Логируем расход токенов
        usage = data.get("usage", {})
        print(f"📊 ТОКЕНЫ: prompt={usage.get('prompt_tokens')}, "
              f"completion={usage.get('completion_tokens')}, "
              f"total={usage.get('total_tokens')}")

        # На всякий случай — если нейронка вернула пустоту
        if not affirmation:
            return "Нейронка вернула пустой ответ. Попробуй переформулировать запрос."

        return affirmation

    except requests.exceptions.Timeout:
        return "DeepSeek не отвечает. Попробуй ещё раз через минуту."

    except requests.exceptions.RequestException as e:
        return f"Ошибка соединения: {e}"

    except (KeyError, IndexError):
        return "Не удалось разобрать ответ от DeepSeek."