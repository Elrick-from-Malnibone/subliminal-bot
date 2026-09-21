# utils/db.py
# Работа с SQLite: юзеры, генерации, лимиты, статистика

import os
import sqlite3
from datetime import datetime

DB_PATH = "bot.db"


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
                PRIMARY KEY (user_id, date)
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

        return {
            "total_users": total_users,
            "total_generations": total_generations,
            "from_pool": from_pool,
            "from_strings": from_strings,
            "from_deepseek": from_deepseek,
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