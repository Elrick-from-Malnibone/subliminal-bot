from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def topics_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Деньги", callback_data="topic_money"),
         InlineKeyboardButton(text="❤️ Любовь", callback_data="topic_love")],
        [InlineKeyboardButton(text="💪 Здоровье", callback_data="topic_health"),
         InlineKeyboardButton(text="💼 Карьера", callback_data="topic_career")],
        [InlineKeyboardButton(text="🦁 Уверенность", callback_data="topic_confidence"),
         InlineKeyboardButton(text="🧘 Спокойствие", callback_data="topic_calm")],
        [InlineKeyboardButton(text="🍏 Похудение", callback_data="topic_weight"),
         InlineKeyboardButton(text="🔥 Мотивация", callback_data="topic_motivation")],
        [InlineKeyboardButton(text="🍀 Удача", callback_data="topic_luck"),
         InlineKeyboardButton(text="🧲 Магнетизм", callback_data="topic_magnetism")],
        [InlineKeyboardButton(text="✍️ Свой текст", callback_data="topic_custom")],
        [InlineKeyboardButton(text="🎯 Своя тема", callback_data="topic_custom_topic")],
    ])


def voices_keyboard():
    """Клавиатура выбора голоса."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎙 Мужской обычный", callback_data="voice_male_1"),
            InlineKeyboardButton(text="🎙 Мужской глубокий", callback_data="voice_male_2"),
        ],
        [
            InlineKeyboardButton(text="🎤 Женский обычный", callback_data="voice_female_1"),
            InlineKeyboardButton(text="🎤 Женский мягкий", callback_data="voice_female_2"),
        ],
        
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_topic"),
        ],
    ])


def categories_keyboard():
    """Клавиатура выбора категории трека."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌌 Эмбиент", callback_data="cat_Эмбиент"),
            InlineKeyboardButton(text="🎵 Дипхаус", callback_data="cat_Дипхаус"),
        ],
        [
            InlineKeyboardButton(text="🎧 Лоуфай", callback_data="cat_Лоуфай"),
            InlineKeyboardButton(text="🌿 Природа", callback_data="cat_Природа"),
        ],
        [
            InlineKeyboardButton(text="🎹 Классика", callback_data="cat_Классика"),
            InlineKeyboardButton(text="🌊 Шум", callback_data="cat_Шум"),
        ],
        [
            InlineKeyboardButton(text="📁 Свой трек", callback_data="cat_custom"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_voice"),
        ],
    ])

def affirmation_keyboard():
    """Клавиатура после генерации текста."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Перегенерить", callback_data="affirm_regen"),
            InlineKeyboardButton(text="✅ Подходит", callback_data="affirm_ok"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_topic"),
        ],
    ])

def lengths_keyboard():
    """Клавиатура выбора длины саблиминала."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="5 минут", callback_data="len_5"),
            InlineKeyboardButton(text="10 минут", callback_data="len_10"),
        ],
        [
            InlineKeyboardButton(text="30 минут", callback_data="len_30"),
            InlineKeyboardButton(text="По длине трека", callback_data="len_track"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_category"),
        ],
    ])

def publish_keyboard():
    """Клавиатура после генерации саблиминала — предложение опубликовать."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Опубликовать в канал", callback_data="publish_yes"),
        ],
        [
            InlineKeyboardButton(text="❌ Не надо", callback_data="publish_no"),
        ],
    ])


def publish_type_keyboard():
    """Клавиатура выбора типа публикации."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕶 Анонимно", callback_data="pub_anon"),
        ],
        [
            InlineKeyboardButton(text="👤 От своего имени", callback_data="pub_named"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_publish"),
        ],
    ])

def solfeggio_keyboard():
    """Клавиатура выбора сольфеджио-частоты."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="528 Гц — любовь и исцеление", callback_data="sol_528")],
        [InlineKeyboardButton(text="432 Гц — гармония и баланс", callback_data="sol_432")],
        [InlineKeyboardButton(text="888 Гц — изобилие и деньги", callback_data="sol_888")],
        [InlineKeyboardButton(text="396 Гц — свобода от страха", callback_data="sol_396")],
        [InlineKeyboardButton(text="174 Гц — безопасность и покой", callback_data="sol_174")],
        [InlineKeyboardButton(text="Без частоты", callback_data="sol_none")],
    ])


def binaural_keyboard():
    """Клавиатура выбора бинаурального ритма."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Альфа 10 Гц — расслабление и творчество", callback_data="bin_alpha")],
        [InlineKeyboardButton(text="Тета 6 Гц — медитация и сон", callback_data="bin_theta")],
        [InlineKeyboardButton(text="Дельта 2 Гц — глубокий сон", callback_data="bin_delta")],
        [InlineKeyboardButton(text="Бета 15 Гц — фокус и драйв", callback_data="bin_beta")],
        [InlineKeyboardButton(text="Без бинаурала", callback_data="bin_none")],
    ])

def voice_tune_keyboard():
    """Клавиатура настройки громкости голоса."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔉 Тише", callback_data="voice_down"),
            InlineKeyboardButton(text="🔊 Громче", callback_data="voice_up"),
        ],
        [
            InlineKeyboardButton(text="✅ Готово", callback_data="voice_done"),
        ],
    ])
