# utils/db.py
# Работа с SQLite: юзеры, генерации, лимиты, статистика

import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.getenv("DATA_DIR", "."), "data.db")


def init_db():
    """Создаёт таблицы, если их нет."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Юзеры
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TIMESTAMP
            )
        """)

        # Генерации
        c.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                source TEXT,
                created_at TIMESTAMP
            )
        """)

        # Лимиты юзера
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_limits (
                user_id INTEGER,
                date DATE,
                custom_topic_used INTEGER DEFAULT 0,
                minutes_today INTEGER DEFAULT 0,
                minutes_this_hour INTEGER DEFAULT 0,
                hour_start TIMESTAMP,
                last_request_time TIMESTAMP,
                PRIMARY KEY (user_id, date)
            )
        """)

        # Подписки
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                active INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                created_at TIMESTAMP
            )
        """)

        conn.commit()


def add_user(user_id: int, username: str) -> bool:
    """
    Добавляет юзера, если его нет.
    Возвращает True, если юзер новый.
    """
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = c.fetchone()

        if exists:
            return False

        c.execute(
            "INSERT INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
            (user_id, username, datetime.now())
        )
        conn.commit()
        return True


def log_generation(user_id: int, source: str):
    """Записывает факт генерации саблиминала."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO generations (user_id, source, created_at) VALUES (?, ?, ?)",
            (user_id, source, datetime.now())
        )
        conn.commit()


def get_stats() -> dict:
    """Возвращает статистику по боту."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations")
        total_generations = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations WHERE source = 'pool'")
        from_pool = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations WHERE source = 'strings'")
        from_strings = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations WHERE source = 'deepseek'")
        from_deepseek = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations WHERE source = 'custom'")
        from_custom = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations WHERE source = 'custom_topic'")
        from_custom_topic = c.fetchone()[0]

        return {
            "total_users": total_users,
            "total_generations": total_generations,
            "from_pool": from_pool,
            "from_strings": from_strings,
            "from_deepseek": from_deepseek,
            "from_custom": from_custom,
            "from_custom_topic": from_custom_topic,
        }


def can_use_custom_topic(user_id: int) -> bool:
    """Проверяет, может ли юзер сегодня использовать Свою тему."""
    today = datetime.now().date().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT custom_topic_used FROM user_limits WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        row = c.fetchone()

        if not row:
            return True

        return row[0] == 0


def mark_custom_topic_used(user_id: int):
    """Отмечает, что юзер использовал Свою тему сегодня."""
    today = datetime.now().date().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute(
            "SELECT 1 FROM user_limits WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        exists = c.fetchone()

        if exists:
            c.execute(
                "UPDATE user_limits SET custom_topic_used = 1 WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
        else:
            c.execute(
                "INSERT INTO user_limits (user_id, date, custom_topic_used) VALUES (?, ?, 1)",
                (user_id, today)
            )

        conn.commit()


def get_all_users() -> list[int]:
    """Возвращает список ID всех юзеров."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        return [row[0] for row in c.fetchall()]

def has_active_subscription(user_id: int) -> bool:
    """Проверяет, есть ли у юзера активная подписка."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT active, expires_at FROM subscriptions WHERE user_id = ?",
            (user_id,)
        )
        row = c.fetchone()

        if not row:
            return False

        active, expires_at = row

        if not active:
            return False

        # Проверяем, не истекла ли
        if expires_at:
            expires = datetime.fromisoformat(expires_at)
            if expires < datetime.now():
                return False

        return True


def get_user_limits(user_id: int) -> dict:
    """Возвращает лимиты юзера — бесплатные или платные."""
    from config import (
        FREE_CUSTOM_TOPICS, FREE_MINUTES_PER_DAY, FREE_MINUTES_PER_HOUR, FREE_ANTISPAM,
        SUB_CUSTOM_TOPICS, SUB_MINUTES_PER_DAY, SUB_MINUTES_PER_HOUR, SUB_ANTISPAM,
    )

    if has_active_subscription(user_id):
        return {
            "custom_topics": SUB_CUSTOM_TOPICS,
            "minutes_per_day": SUB_MINUTES_PER_DAY,
            "minutes_per_hour": SUB_MINUTES_PER_HOUR,
            "antispam": SUB_ANTISPAM,
            "is_subscriber": True,
        }
    else:
        return {
            "custom_topics": FREE_CUSTOM_TOPICS,
            "minutes_per_day": FREE_MINUTES_PER_DAY,
            "minutes_per_hour": FREE_MINUTES_PER_HOUR,
            "antispam": FREE_ANTISPAM,
            "is_subscriber": False,
        }


def get_today_usage(user_id: int) -> dict:
    """Возвращает текущее использование лимитов за сегодня."""
    today = datetime.now().date().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT custom_topic_used, minutes_today, minutes_this_hour, hour_start, last_request_time "
            "FROM user_limits WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        row = c.fetchone()

        if not row:
            return {
                "custom_topic_used": 0,
                "minutes_today": 0,
                "minutes_this_hour": 0,
                "hour_start": None,
                "last_request_time": None,
            }

        return {
            "custom_topic_used": row[0],
            "minutes_today": row[1],
            "minutes_this_hour": row[2],
            "hour_start": row[3],
            "last_request_time": row[4],
        }


def check_limits(user_id: int, requested_minutes: int, is_custom_topic: bool = False) -> dict:
    """
    Проверяет, может ли юзер сгенерировать саблиминал.

    :param user_id: ID юзера
    :param requested_minutes: сколько минут запрашивает
    :param is_custom_topic: используется ли «Своя тема»
    :return: {"allowed": bool, "reason": str или None}
    """
    limits = get_user_limits(user_id)
    usage = get_today_usage(user_id)
    now = datetime.now()

    # 1. Проверка лимита «Своя тема»
    if is_custom_topic:
        if usage["custom_topic_used"] >= limits["custom_topics"]:
            return {
                "allowed": False,
                "reason": "custom_topic",
                "message": f"Лимит на «Свою тему» исчерпан ({limits['custom_topics']} в день)."
            }

    # 2. Проверка антиспама
    if usage["last_request_time"]:
        last = datetime.fromisoformat(usage["last_request_time"])
        diff = (now - last).total_seconds()
        if diff < limits["antispam"]:
            wait = int(limits["antispam"] - diff)
            return {
                "allowed": False,
                "reason": "antispam",
                "message": f"Подожди {wait} секунд перед новой генерацией."
            }

    # 3. Проверка часового лимита
    hour_start = usage["hour_start"]
    if hour_start:
        hour_start_dt = datetime.fromisoformat(hour_start)
        # Если час прошёл — сбрасываем часовой счётчик
        if (now - hour_start_dt).total_seconds() >= 3600:
            usage["minutes_this_hour"] = 0

    if usage["minutes_this_hour"] + requested_minutes > limits["minutes_per_hour"]:
        return {
            "allowed": False,
            "reason": "minutes_per_hour",
            "message": f"Лимит на час исчерпан ({limits['minutes_per_hour']} минут)."
        }

    # 4. Проверка дневного лимита
    if usage["minutes_today"] + requested_minutes > limits["minutes_per_day"]:
        remaining = limits["minutes_per_day"] - usage["minutes_today"]
        return {
            "allowed": False,
            "reason": "minutes_per_day",
            "message": f"Лимит на день исчерпан. Осталось: {remaining} минут."
        }

    # Всё ок
    return {"allowed": True, "reason": None, "message": None}


def add_usage(user_id: int, minutes: int, is_custom_topic: bool = False):
    """Записывает использование лимитов."""
    today = datetime.now().date().isoformat()
    now = datetime.now()

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Проверяем, есть ли запись
        c.execute(
            "SELECT minutes_today, minutes_this_hour, hour_start FROM user_limits "
            "WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        row = c.fetchone()

        if row:
            minutes_today, minutes_this_hour, hour_start = row

            # Проверяем, прошёл ли час
            if hour_start:
                hour_start_dt = datetime.fromisoformat(hour_start)
                if (now - hour_start_dt).total_seconds() >= 3600:
                    # Час прошёл — сбрасываем
                    minutes_this_hour = 0
                    hour_start = now.isoformat()

            # Обновляем
            c.execute(
                "UPDATE user_limits SET "
                "custom_topic_used = custom_topic_used + ?, "
                "minutes_today = ?, "
                "minutes_this_hour = ?, "
                "hour_start = ?, "
                "last_request_time = ? "
                "WHERE user_id = ? AND date = ?",
                (
                    1 if is_custom_topic else 0,
                    minutes_today + minutes,
                    minutes_this_hour + minutes,
                    hour_start if hour_start else now.isoformat(),
                    now.isoformat(),
                    user_id,
                    today,
                )
            )
        else:
            # Создаём новую запись
            c.execute(
                "INSERT INTO user_limits "
                "(user_id, date, custom_topic_used, minutes_today, minutes_this_hour, hour_start, last_request_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    today,
                    1 if is_custom_topic else 0,
                    minutes,
                    minutes,
                    now.isoformat(),
                    now.isoformat(),
                )
            )

        conn.commit()    