# main.py
import asyncio
import logging
import os
import time
import random
import sys

from config import (
    BOT_TOKEN, ADMIN_ID,
    PRICE_SUBSCRIPTION, PRICE_CUSTOM_TOPIC, PRICE_REMOVE_SIGNATURE,
)
from aiogram import Bot, Dispatcher, types, F
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from utils.db import (
    init_db, add_user, log_generation, get_stats,
    can_use_custom_topic, mark_custom_topic_used, get_all_users,
    has_active_subscription, get_user_limits, get_today_usage,
    check_limits, add_usage,
)
from config import BOT_TOKEN, ADMIN_ID
from states.fsm import SubliminalStates
from keyboards.inline import (
    topics_keyboard,
    voices_keyboard,
    categories_keyboard,
    affirmation_keyboard,
    lengths_keyboard,
    publish_keyboard,
    publish_type_keyboard,
    solfeggio_keyboard,
    binaural_keyboard,
    voice_tune_keyboard,
    limit_keyboard,
    subscribe_keyboard,
    back_to_subscribe_keyboard,
)
from services.affirmations import get_affirmation
import services.affirmations
from services.tts import generate_voice
from services.deepseek import generate_affirmation
from services.audio import create_subliminal



# Логи в файл
LOG_FILE = os.path.join(os.getenv("DATA_DIR", "/app/data"), "bot.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

print("=== ЗАПУСК БОТА ===", flush=True)
print(f"BOT_TOKEN: {'есть' if BOT_TOKEN else 'НЕТ'}", flush=True)
print(f"WEBHOOK_URL: {os.getenv('WEBHOOK_URL', 'НЕТ')}", flush=True)
print(f"PORT: {os.getenv('PORT', 'НЕТ')}", flush=True)


FREQ_INFO = {
    "money": "888 Гц (изобилие) + альфа 10 Гц (расслабление)",
    "love": "528 Гц (любовь) + альфа 10 Гц",
    "health": "285 Гц (регенерация) + дельта 2 Гц (восстановление)",
    "career": "741 Гц (интуиция) + бета 15 Гц (фокус)",
    "confidence": "396 Гц (свобода от страха) + альфа 10 Гц",
    "calm": "432 Гц (гармония) + тета 6 Гц (медитация)",
    "weight": "285 Гц (регенерация) + альфа 10 Гц",
    "motivation": "417 Гц (изменения) + бета 15 Гц (драйв)",
    "luck": "888 Гц (изобилие) + альфа 10 Гц",
    "magnetism": "639 Гц (связь с людьми) + альфа 10 Гц",
}


CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

PROXY = os.getenv("PROXY", "")

if PROXY:
    session = AiohttpSession(proxy=PROXY)
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

TOPICS = {
    "topic_money": {"key": "money", "text": "деньги, богатство, изобилие"},
    "topic_love": {"key": "love", "text": "любовь, отношения, притяжение партнёра"},
    "topic_health": {"key": "health", "text": "здоровье, энергия, хорошее самочувствие"},
    "topic_career": {"key": "career", "text": "карьера, успех, реализация в работе"},
    "topic_confidence": {"key": "confidence", "text": "уверенность в себе, сила, харизма"},
    "topic_calm": {"key": "calm", "text": "спокойствие, внутренний баланс, умиротворение"},
    "topic_weight": {"key": "weight", "text": "похудение, стройность, здоровое тело"},
    "topic_motivation": {"key": "motivation", "text": "мотивация, энергия, драйв, действие"},
    "topic_luck": {"key": "luck", "text": "удача, везение, благоприятные возможности"},
    "topic_magnetism": {"key": "magnetism", "text": "магнетизм, притяжение людей, обаяние"},
}

async def main():
    print("=== MAIN STARTED ===", flush=True)
    init_db()
    print("=== DB INITIALIZED ===", flush=True)
    asyncio.create_task(cleanup_output())
    print("=== CLEANUP TASK STARTED ===", flush=True)

    webhook_url = os.getenv("WEBHOOK_URL")
    print(f"=== WEBHOOK_URL: {webhook_url} ===", flush=True)

    if webhook_url:
        print("=== WEBHOOK MODE ===", flush=True)
        webhook_path = "/webhook"
        host = "0.0.0.0"
        port = int(os.getenv("PORT", 3000))
        print(f"=== PORT: {port} ===", flush=True)

        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=webhook_path)
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        print("=== SERVER STARTED ===", flush=True)

        await bot.set_webhook(f"{webhook_url}")
        print("=== WEBHOOK SET ===", flush=True)

        await asyncio.Event().wait()
    else:
        print("=== POLLING MODE ===", flush=True)
        await dp.start_polling(bot)

@dp.message(F.text == "/rs")
async def cmd_broadcast(message: types.Message, state):
    if message.from_user.id != ADMIN_ID:
        return

    await state.clear()

    await message.answer(
        "📢 Напиши текст для рассылки.\n\n"
        "Он уйдёт всем юзерам бота."
    )
    await state.set_state(SubliminalStates.waiting_for_broadcast)


@dp.message(CommandStart())
async def cmd_start(message: types.Message, state):
    data = await state.get_data()

    # Чистим старый саблиминал
    old_path = data.get("subliminal_path")
    if old_path and os.path.exists(old_path):
        try:
            os.remove(old_path)
            print(f"🧹 Удалён старый саблиминал при /start")
        except Exception as e:
            print(f"Ошибка удаления: {e}")

    # Чистим превью
    preview_path = data.get("preview_path")
    if preview_path and os.path.exists(preview_path):
        try:
            os.remove(preview_path)
        except Exception as e:
            print(f"Ошибка удаления превью: {e}")

    # Чистим кэш голоса
    cached_voice = data.get("cached_voice_path")
    if cached_voice and os.path.exists(cached_voice):
        try:
            os.remove(cached_voice)
        except Exception as e:
            print(f"Ошибка удаления кэша: {e}")

    await state.clear()

    is_new = add_user(message.from_user.id, message.from_user.username or "")

    if is_new:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🆕 Новый юзер: @{message.from_user.username or 'без_юзернейма'}\n"
                f"ID: {message.from_user.id}"
            )
        except Exception as e:
            print(f"Не удалось отправить оповещение: {e}")

    await message.answer(
        "Привет! Выбери тему саблиминала:",
        reply_markup=topics_keyboard()
    )
    await state.set_state(SubliminalStates.waiting_for_topic)


@dp.message(F.text == "/stats")
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    stats = get_stats()

    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего юзеров: <b>{stats['total_users']}</b>\n"
        f"🎧 Сгенерировано саблиминалов: <b>{stats['total_generations']}</b>\n\n"
        f"📦 Из пула: <b>{stats['from_pool']}</b>\n"
        f"🔧 Из строк: <b>{stats['from_strings']}</b>\n"
        f"🤖 Из Дипсика: <b>{stats['from_deepseek']}</b>\n"
        f"✍️ Свой текст: <b>{stats['from_custom']}</b>\n"
        f"🎯 Своя тема: <b>{stats['from_custom_topic']}</b>",
        parse_mode="HTML"
    )

@dp.message(F.text == "/subscribe")
async def cmd_subscribe(message: types.Message, state):
    """Показывает тарифы подписки."""
    await state.clear()

    await message.answer(
        f"💎 <b>Подписка — {PRICE_SUBSCRIPTION} руб/мес</b>\n\n"
        f"Что входит:\n"
        f"— 10 своих тем в день\n"
        f"— 180 минут саблиминалов в день\n"
        f"— Без подписи бота\n"
        f"— Приоритетная генерация\n\n"
        f"<b>Разовые покупки:</b>\n"
        f"— 1 своя тема — {PRICE_CUSTOM_TOPIC} руб\n"
        f"— Убрать подпись с 1 саба — {PRICE_REMOVE_SIGNATURE} руб",
        parse_mode="HTML",
        reply_markup=subscribe_keyboard()
    )

@dp.callback_query(F.data == "pay_subscription")
async def handle_pay_subscription(call: types.CallbackQuery, state):
    """Заглушка оплаты подписки (пока ЮKassa не подключена)."""
    await call.message.edit_text(
        f"💎 Подписка — {PRICE_SUBSCRIPTION} руб/мес\n\n"
        f"⏳ Оплата временно недоступна.\n"
        f"Скоро подключим 👌",
        reply_markup=back_to_subscribe_keyboard()
    )
    await call.answer()


@dp.callback_query(F.data == "pay_custom_topic")
async def handle_pay_custom_topic(call: types.CallbackQuery, state):
    """Заглушка оплаты разовой своей темы."""
    await call.message.edit_text(
        f"💳 1 своя тема — {PRICE_CUSTOM_TOPIC} руб\n\n"
        f"⏳ Оплата временно недоступна.\n"
        f"Скоро подключим 👌",
        reply_markup=back_to_subscribe_keyboard()
    )
    await call.answer()


@dp.callback_query(F.data == "pay_remove_signature")
async def handle_pay_remove_signature(call: types.CallbackQuery, state):
    """Заглушка оплаты убрать подпись."""
    await call.message.edit_text(
        f"💳 Убрать подпись с 1 саба — {PRICE_REMOVE_SIGNATURE} руб\n\n"
        f"⏳ Оплата временно недоступна.\n"
        f"Скоро подключим 👌",
        reply_markup=back_to_subscribe_keyboard()
    )
    await call.answer()    


@dp.callback_query(F.data == "subscribe")
async def handle_subscribe(call: types.CallbackQuery, state):
    """Показывает тарифы подписки (из кнопки)."""
    await call.message.edit_text(
        f"💎 <b>Подписка — {PRICE_SUBSCRIPTION} руб/мес</b>\n\n"
        f"Что входит:\n"
        f"— 10 своих тем в день\n"
        f"— 180 минут саблиминалов в день\n"
        f"— Без подписи бота\n"
        f"— Приоритетная генерация\n\n"
        f"<b>Разовые покупки:</b>\n"
        f"— 1 своя тема — {PRICE_CUSTOM_TOPIC} руб\n"
        f"— Убрать подпись с 1 саба — {PRICE_REMOVE_SIGNATURE} руб",
        parse_mode="HTML",
        reply_markup=subscribe_keyboard()
    )
    await call.answer()    


@dp.message(SubliminalStates.waiting_for_broadcast)
async def handle_broadcast(message: types.Message, state):
    if message.from_user.id != ADMIN_ID:
        return

    broadcast_text = message.text
    await state.clear()

    users = get_all_users()

    if not users:
        await message.answer("Нет юзеров для рассылки.")
        return

    status = await message.answer(f"⏳ Рассылаю {len(users)} юзерам...")

    sent = 0
    failed = 0

    for user_id in users:
        try:
            await bot.send_message(user_id, broadcast_text)
            sent += 1
        except Exception as e:
            failed += 1
            print(f"Не отправлено {user_id}: {e}")

        await asyncio.sleep(0.05)

    await status.edit_text(
        f"✅ Рассылка завершена.\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )


@dp.callback_query(SubliminalStates.waiting_for_topic, F.data.in_(TOPICS.keys()))
async def handle_topic(call: types.CallbackQuery, state):
    topic_data = TOPICS[call.data]
    topic_key = topic_data["key"]
    await state.update_data(topic=topic_data["text"], topic_key=topic_key)

    freq_text = FREQ_INFO.get(topic_key, "")

    await call.message.edit_text(
        f"Тема: {topic_data['text']}\n\n"
        f"🎵 Подобрано: {freq_text}"
    )
    await call.answer()
    await ask_affirmation(call.message, state)


@dp.callback_query(SubliminalStates.waiting_for_topic, F.data == "topic_custom")
async def handle_custom(call: types.CallbackQuery, state):
    await call.message.edit_text("Напиши, какой саблиминал ты хочешь:")
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_custom_text)


@dp.callback_query(SubliminalStates.waiting_for_topic, F.data == "topic_custom_topic")
async def handle_custom_topic(call: types.CallbackQuery, state):
    
    if not can_use_custom_topic(call.from_user.id):
         await call.message.edit_text(
             "❌ Лимит на «Свою тему» исчерпан.\n\n"
             "Можно использовать только 1 раз в день.\n"
             "Попробуй завтра или выбери готовую тему."
         )
         await call.answer()
         return

    await call.message.edit_text(
        "🎯 Напиши свою тему — то, чего нет в готовом списке.\n\n"
        "Например:\n"
        "• хочу сдать экзамен\n"
        "• хочу наладить сон\n"
        "• хочу найти своё дело\n\n"
        "Нейронка сгенерирует аффирмации под твой запрос."
    )
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_custom_topic)


@dp.message(SubliminalStates.waiting_for_custom_topic)
async def handle_custom_topic_text(message: types.Message, state):
    # Проверяем лимит
    if not can_use_custom_topic(message.from_user.id):
        await message.answer(
            "❌ Лимит на «Свою тему» исчерпан.\n\n"
            "Можно использовать только 1 раз в день.\n"
            "Попробуй завтра или выбери готовую тему."
        )
        await state.clear()
        return

    if len(message.text) > 500:
        await message.answer(
            f"❌ Слишком длинный запрос ({len(message.text)} символов).\n\n"
            "Максимум — 500 символов. Опиши тему коротко."
        )
        return

    user_topic = message.text
    await state.update_data(topic=user_topic)

    # Отмечаем, что юзер использовал «Свою тему»
    mark_custom_topic_used(message.from_user.id)

    status = await message.answer("⏳ Генерирую аффирмации под твой запрос...")

    affirmation = await asyncio.to_thread(generate_affirmation, user_topic)
    await state.update_data(affirmation=affirmation)

    await state.update_data(source="custom_topic")

    await status.edit_text(
        f"Вот что сгенерировалось:\n\n{affirmation}"
    )

    await message.answer(
        "🎵 Теперь выбери сольфеджио-частоту:",
        reply_markup=solfeggio_keyboard()
    )
    await state.set_state(SubliminalStates.choosing_solfeggio)


@dp.callback_query(SubliminalStates.choosing_solfeggio, F.data.startswith("sol_"))
async def handle_solfeggio(call: types.CallbackQuery, state):
    sol_code = call.data.replace("sol_", "")

    if sol_code == "none":
        await state.update_data(custom_solfeggio=None)
    else:
        await state.update_data(custom_solfeggio=int(sol_code))

    await call.message.edit_text(
        "✅ Частота выбрана.\n\n"
        "🎧 Теперь выбери бинауральный ритм:",
        reply_markup=binaural_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_binaural)


@dp.callback_query(SubliminalStates.choosing_binaural, F.data.startswith("bin_"))
async def handle_binaural(call: types.CallbackQuery, state):
    bin_code = call.data.replace("bin_", "")

    binaural_map = {
        "alpha": (200, 210),
        "theta": (200, 206),
        "delta": (200, 202),
        "beta": (200, 215),
        "none": None,
    }

    await state.update_data(custom_binaural=binaural_map.get(bin_code))

    await call.message.edit_text(
        "✅ Ритм выбран.\n\n"
        "🎙 Теперь выбери голос:",
        reply_markup=voices_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_voice)


@dp.message(SubliminalStates.waiting_for_custom_text)
async def handle_custom_text(message: types.Message, state):
    await state.update_data(affirmation=message.text)
    await state.update_data(source="custom")

    await message.answer(
        "✅ Текст принят.\n\n"
        "🎵 Выбери сольфеджио-частоту:",
        reply_markup=solfeggio_keyboard()
    )
    await state.set_state(SubliminalStates.choosing_solfeggio)


async def ask_affirmation(message: types.Message, state):
    data = await state.get_data()
    topic = data.get("topic", "успех")
    topic_key = data.get("topic_key")

    status = await message.answer("⏳ Генерирую аффирмации...")

    delay = random.uniform(2.0, 4.0)
    await asyncio.sleep(delay)

    affirmation = await asyncio.to_thread(get_affirmation, topic_key, topic)
    await state.update_data(affirmation=affirmation)

    await status.edit_text(
        f"Вот что сгенерировалось:\n\n{affirmation}\n\n"
        f"Подходит или перегенерить?",
        reply_markup=affirmation_keyboard()
    )


@dp.callback_query(F.data == "affirm_regen")
async def handle_regen(call: types.CallbackQuery, state):
    data = await state.get_data()
    topic = data.get("topic", "успех")
    topic_key = data.get("topic_key")

    await call.message.edit_text("⏳ Генерирую новый текст...")
    await call.answer()

    delay = random.uniform(2.0, 4.0)
    await asyncio.sleep(delay)

    affirmation = await asyncio.to_thread(get_affirmation, topic_key, topic)
    await state.update_data(affirmation=affirmation)

    await call.message.edit_text(
        f"Вот что сгенерировалось:\n\n{affirmation}\n\n"
        f"Подходит или перегенерить?",
        reply_markup=affirmation_keyboard()
    )


@dp.callback_query(F.data == "affirm_ok")
async def handle_ok(call: types.CallbackQuery, state):
    await call.message.edit_text(
        "✅ Принято. Теперь выбери голос:",
        reply_markup=voices_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_voice)


@dp.callback_query(SubliminalStates.choosing_voice, F.data.startswith("voice_"))
async def handle_voice(call: types.CallbackQuery, state):
    voice_type = call.data.replace("voice_", "")
    await state.update_data(voice_type=voice_type)

    await call.message.edit_text(
        "✅ Голос выбран. Теперь выбери категорию трека:",
        reply_markup=categories_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_track)


@dp.callback_query(SubliminalStates.choosing_track, F.data.startswith("cat_"))
async def handle_category(call: types.CallbackQuery, state):
    category = call.data.replace("cat_", "")
    await state.update_data(category=category)

    if category == "custom":
        await call.message.edit_text("📁 Отправь свой MP3-файл:")
        await call.answer()
        await state.set_state(SubliminalStates.choosing_track_item)
        return

    category_dir = os.path.join("assets", category)
    preview_dir = os.path.join("assets", "previews", category)

    if not os.path.isdir(category_dir):
        await call.message.edit_text("Нет такой категории.")
        await call.answer()
        return

    tracks = sorted([f for f in os.listdir(category_dir) if f.lower().endswith(".mp3")])

    if not tracks:
        await call.message.edit_text("В этой категории нет треков.")
        await call.answer()
        return

    await call.message.edit_text("🎧 Слушай превью и выбирай:")
    await call.answer()

    tasks = []
    for track in tracks:
        preview_path = os.path.join(preview_dir, track)

        if os.path.exists(preview_path):
            audio_file = FSInputFile(preview_path)
            tasks.append(bot.send_audio(
                chat_id=call.message.chat.id,
                audio=audio_file,
                title=track.replace(".mp3", "")
            ))
        else:
            print(f"Нет превью для {track}")

    if tasks:
        await asyncio.gather(*tasks)

    buttons = [
        [InlineKeyboardButton(
            text=f"🎵 {track.replace('.mp3', '')}",
            callback_data=f"track_{track}"
        )]
        for track in tracks
    ]

    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_category")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.answer(
        "Выбери трек:",
        reply_markup=keyboard
    )
    await state.set_state(SubliminalStates.choosing_track_item)


@dp.callback_query(F.data == "back_to_topic")
async def back_to_topic(call: types.CallbackQuery, state):
    await state.clear()
    await call.message.edit_text(
        "Выбери тему саблиминала:",
        reply_markup=topics_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_topic)


@dp.callback_query(F.data == "back_to_voice")
async def back_to_voice(call: types.CallbackQuery, state):
    await call.message.edit_text(
        "Выбери голос:",
        reply_markup=voices_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_voice)


@dp.callback_query(F.data == "back_to_category")
async def back_to_category(call: types.CallbackQuery, state):
    await call.message.edit_text(
        "Выбери категорию трека:",
        reply_markup=categories_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_track)


@dp.callback_query(SubliminalStates.choosing_track_item, F.data.startswith("track_"))
async def handle_track_choice(call: types.CallbackQuery, state):
    track_name = call.data.replace("track_", "")
    await state.update_data(chosen_track=track_name)

    await call.message.edit_text(
        f"✅ Трек: {track_name}.\n\n"
        f"🕐 Выбери длину саблиминала:",
        reply_markup=lengths_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_length)


@dp.message(SubliminalStates.choosing_track_item, F.audio | F.document)
async def handle_custom_track(message: types.Message, state):
    file = message.audio or message.document

    if not file:
        await message.answer("Пришли MP3-файл.")
        return

    if message.document and not message.document.file_name.lower().endswith(".mp3"):
        await message.answer("Нужен именно MP3-файл.")
        return

    file_info = await bot.get_file(file.file_id)
    os.makedirs("assets/user", exist_ok=True)
    user_track_path = f"assets/user/{message.from_user.id}_{int(time.time())}.mp3"
    await bot.download_file(file_info.file_path, user_track_path)

    await state.update_data(custom_track=user_track_path)
    await message.answer(
        "✅ Трек принят.\n\n"
        "🕐 Выбери длину саблиминала:",
        reply_markup=lengths_keyboard()
    )
    await state.set_state(SubliminalStates.choosing_length)


@dp.callback_query(SubliminalStates.choosing_length, F.data.startswith("len_"))
async def handle_length(call: types.CallbackQuery, state):
    length_code = call.data.replace("len_", "")

    if length_code == "5":
        length_minutes = 5
    elif length_code == "10":
        length_minutes = 10
    elif length_code == "15":
        length_minutes = 15
    else:
        length_minutes = None

    await state.update_data(length_minutes=length_minutes)

    if length_minutes:
        length_text = f"{length_minutes} минут"
    else:
        length_text = "по длине трека"

    await call.message.edit_text(
        f"✅ Длина: {length_text}.\n\n"
        f"✍️ Напиши название для своего саблиминала:"
    )
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_name)


@dp.message(SubliminalStates.waiting_for_name)
async def handle_name(message: types.Message, state):
    if message.text.startswith("/"):
        await message.answer(
            "❌ Название не может начинаться с «/».\n\n"
            "Напиши обычное название для саблиминала."
        )
        return

    data = await state.get_data()
    affirmation = data.get("affirmation")
    voice_type = data.get("voice_type", "male_1")
    length_minutes = data.get("length_minutes")
    source = data.get("source", "")

    # Определяем длину для проверки лимита
    if length_minutes:
        requested_minutes = length_minutes
    else:
        requested_minutes = 10  # по длине трека — примерно

    # Проверяем лимиты
    is_custom_topic = (source == "custom_topic")
    limit_check = check_limits(
        message.from_user.id,
        requested_minutes,
        is_custom_topic=is_custom_topic
    )

    if not limit_check["allowed"]:
        reason = limit_check["reason"]
        message_text = limit_check["message"]

        # Формируем предложение
        if reason == "custom_topic":
            await message.answer(
                f"❌ {message_text}\n\n"
                f"💎 Подписка {PRICE_SUBSCRIPTION} руб/мес — 10 своих тем в день\n"
                f"💳 Разовая покупка — {PRICE_CUSTOM_TOPIC} руб за 1 свою тему",
                reply_markup=limit_keyboard()
            )
        elif reason in ("minutes_per_day", "minutes_per_hour"):
            await message.answer(
                f"❌ {message_text}\n\n"
                f"💎 Подписка {PRICE_SUBSCRIPTION} руб/мес — 180 минут в день",
                reply_markup=limit_keyboard()
            )
        else:
            await message.answer(f"❌ {message_text}")

        await state.clear()
        return

    # Сохраняем лимит для последующей записи
    await state.update_data(
        subliminal_name=message.text,
        voice_offset=0,
        voice_clicks=0,
        requested_minutes=requested_minutes,
        is_custom_topic=is_custom_topic
    )

    # Генерим голос ОДИН РАЗ
    await message.answer("⏳ Готовлю голос...")
    voice_path = await generate_voice(affirmation, voice_type=voice_type)


    if not voice_path:
        await message.answer("❌ Не удалось создать озвучку.")
        await state.clear()
        return

    await state.update_data(
        subliminal_name=message.text,
        voice_offset=0,
        voice_clicks=0,
        cached_voice_path=voice_path
    )

    await message.answer(
        f"✅ Название: «{message.text}».\n\n"
        f"🎧 Генерирую превью (30 секунд)...\n"
        f"Послушай и настрой громкость голоса."
    )

    await generate_preview(message, state)


async def generate_preview(message: types.Message, state):
    """Генерирует короткое превью (30 сек) с текущим voice_offset."""
    data = await state.get_data()
    category = data.get("category", "nature")
    custom_track = data.get("custom_track")
    custom_solfeggio = data.get("custom_solfeggio")
    custom_binaural = data.get("custom_binaural")
    voice_offset = data.get("voice_offset", 0)

    # Берём голос из кэша
    voice_path = data.get("cached_voice_path")

    if not voice_path or not os.path.exists(voice_path):
        await message.answer("❌ Голос потерялся. Начни заново — /start")
        await state.clear()
        return

    chosen_track = data.get("chosen_track")

    if custom_track:
        subliminal_path = await asyncio.to_thread(
            create_subliminal, voice_path, None, custom_track, 0.5,
            custom_solfeggio, custom_binaural, voice_offset
        )
    elif chosen_track:
        track_path = os.path.join("assets", category, chosen_track)
        subliminal_path = await asyncio.to_thread(
            create_subliminal, voice_path, None, track_path, 0.5,
            custom_solfeggio, custom_binaural, voice_offset
        )
    else:
        subliminal_path = await asyncio.to_thread(
            create_subliminal, voice_path, category, None, 0.5,
            custom_solfeggio, custom_binaural, voice_offset
        )

    if not subliminal_path or not os.path.exists(subliminal_path):
        await message.answer("❌ Не удалось создать превью.")
        return

    await state.update_data(preview_path=subliminal_path)

    audio_file = FSInputFile(subliminal_path)
    await message.answer_audio(
        audio=audio_file,
        title="Превью (30 сек)",
        caption=f"🎧 Громкость голоса: {voice_offset:+d} дБ\n"
                f"Кликов: {data.get('voice_clicks', 0)}/5"
    )

    await message.answer(
        "Настрой громкость голоса:",
        reply_markup=voice_tune_keyboard()
    )

@dp.callback_query(F.data == "voice_up")
async def handle_voice_up(call: types.CallbackQuery, state):
    data = await state.get_data()
    voice_clicks = data.get("voice_clicks", 0)

    if voice_clicks >= 5:
        await call.answer("❌ Лимит настройки исчерпан (5 кликов).", show_alert=True)
        return

    voice_offset = data.get("voice_offset", 0)

    if voice_offset >= 20:
        await call.answer("🔊 Громче уже нельзя.", show_alert=True)
        return

    await state.update_data(
        voice_offset=voice_offset + 5,
        voice_clicks=voice_clicks + 1
    )

    preview_path = data.get("preview_path")
    if preview_path and os.path.exists(preview_path):
        os.remove(preview_path)

    await call.message.delete()
    await call.answer()
    await generate_preview(call.message, state)


@dp.callback_query(F.data == "voice_down")
async def handle_voice_down(call: types.CallbackQuery, state):
    data = await state.get_data()
    voice_clicks = data.get("voice_clicks", 0)

    if voice_clicks >= 5:
        await call.answer("❌ Лимит настройки исчерпан (5 кликов).", show_alert=True)
        return

    voice_offset = data.get("voice_offset", 0)

    if voice_offset <= -20:
        await call.answer("🔉 Тише уже нельзя.", show_alert=True)
        return

    await state.update_data(
        voice_offset=voice_offset - 5,
        voice_clicks=voice_clicks + 1
    )

    preview_path = data.get("preview_path")
    if preview_path and os.path.exists(preview_path):
        os.remove(preview_path)

    await call.message.delete()
    await call.answer()
    await generate_preview(call.message, state)


@dp.callback_query(F.data == "voice_done")
async def handle_voice_done(call: types.CallbackQuery, state):
    data = await state.get_data()
    preview_path = data.get("preview_path")

    if preview_path and os.path.exists(preview_path):
        os.remove(preview_path)

    await call.message.delete()
    await call.answer()

    # Сохраняем user_id и chat_id для фоновой задачи
    data["user_id"] = call.from_user.id
    data["chat_id"] = call.message.chat.id

    # Копируем данные (state очистится)
    data_copy = dict(data)

    await call.message.answer(
        "✅ Готово! Генерация идёт в фоне.\n\n"
        "Я пришлю саблиминал, когда он будет готов. "
        "Можешь пока пользоваться ботом."
    )

    # Запускаем в фоне
    asyncio.create_task(generate_subliminal_background(data_copy))

    await state.clear()

async def generate_subliminal_background(data: dict):
    """Генерирует саблиминал в фоне и присылает юзеру."""
    try:
        chat_id = data.get("chat_id")
        user_id = data.get("user_id")
        category = data.get("category", "nature")
        custom_track = data.get("custom_track")
        length_minutes = data.get("length_minutes")
        custom_solfeggio = data.get("custom_solfeggio")
        custom_binaural = data.get("custom_binaural")
        voice_offset = data.get("voice_offset", 0)
        voice_path = data.get("cached_voice_path")
        chosen_track = data.get("chosen_track")
        subliminal_name = data.get("subliminal_name", "Твой саблиминал")

        # Проверяем голос
        if not voice_path or not os.path.exists(voice_path):
            await bot.send_message(chat_id, "❌ Голос потерялся. Начни заново — /start")
            return

        # Собираем саблиминал
        if custom_track:
            subliminal_path = await asyncio.to_thread(
                create_subliminal, voice_path, None, custom_track, length_minutes,
                custom_solfeggio, custom_binaural, voice_offset
            )
        elif chosen_track:
            track_path = os.path.join("assets", category, chosen_track)
            subliminal_path = await asyncio.to_thread(
                create_subliminal, voice_path, None, track_path, length_minutes,
                custom_solfeggio, custom_binaural, voice_offset
            )
        else:
            subliminal_path = await asyncio.to_thread(
                create_subliminal, voice_path, category, None, length_minutes,
                custom_solfeggio, custom_binaural, voice_offset
            )

        # Отправляем
        if subliminal_path and os.path.exists(subliminal_path):
            audio_file = FSInputFile(subliminal_path)
            await bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                title=subliminal_name,
                caption="🎧 Сделано в @SubliminalGenBot"
            )

            # Логируем
            source = data.get("source", "unknown")
            log_generation(user_id, source)

            # Записываем лимит
            requested_minutes = data.get("requested_minutes", 0)
            is_custom_topic = data.get("is_custom_topic", False)
            add_usage(user_id, requested_minutes, is_custom_topic)

            # Чистим файлы
            if os.path.exists(subliminal_path):
                os.remove(subliminal_path)
            if voice_path and os.path.exists(voice_path):
                os.remove(voice_path)
            if custom_track and os.path.exists(custom_track):
                os.remove(custom_track)

            # Кнопка «Хочешь ещё?»
            await bot.send_message(
                chat_id,
                "Хочешь ещё один?",
                reply_markup=topics_keyboard()
            )

        else:
            await bot.send_message(chat_id, "❌ Не удалось собрать саблиминал.")

    except Exception as e:
        logger.error(f"❌ ОШИБКА ФОНОВОЙ ГЕНЕРАЦИИ: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await bot.send_message(chat_id, f"❌ Ошибка: {e}")  


async def generate_subliminal(message: types.Message, state):
    data = await state.get_data()
    category = data.get("category", "nature")
    custom_track = data.get("custom_track")
    length_minutes = data.get("length_minutes")
    custom_solfeggio = data.get("custom_solfeggio")
    custom_binaural = data.get("custom_binaural")
    voice_offset = data.get("voice_offset", 0)

    # Берём голос из кэша
    voice_path = data.get("cached_voice_path")

    if not voice_path or not os.path.exists(voice_path):
        await message.answer("❌ Голос потерялся. Начни заново — /start")
        await state.clear()
        return

    status = await message.answer("⏳ Собираю саблиминал...")

    chosen_track = data.get("chosen_track")

    if custom_track:
        subliminal_path = await asyncio.to_thread(
            create_subliminal, voice_path, None, custom_track, length_minutes,
            custom_solfeggio, custom_binaural, voice_offset
        )
    elif chosen_track:
        track_path = os.path.join("assets", category, chosen_track)
        subliminal_path = await asyncio.to_thread(
            create_subliminal, voice_path, None, track_path, length_minutes,
            custom_solfeggio, custom_binaural, voice_offset
        )
    else:
        subliminal_path = await asyncio.to_thread(
            create_subliminal, voice_path, category, None, length_minutes,
            custom_solfeggio, custom_binaural, voice_offset
        )

    if subliminal_path and os.path.exists(subliminal_path):
        audio_file = FSInputFile(subliminal_path)
        subliminal_name = data.get("subliminal_name", "Твой саблиминал")
        await message.answer_audio(
            audio=audio_file,
            title=subliminal_name,
            caption="🎧 Сделано в @SubliminalGenBot"
        )
        await status.edit_text("✅ Готово!")

        source = data.get("source", services.affirmations.last_source)
        log_generation(message.from_user.id, source)

        # Записываем использование лимита
        requested_minutes = data.get("requested_minutes", 0)
        is_custom_topic = data.get("is_custom_topic", False)
        add_usage(message.from_user.id, requested_minutes, is_custom_topic)

        await state.update_data(subliminal_path=subliminal_path)

        await message.answer(
            "📢 Хочешь опубликовать свой саблиминал в канале?",
            reply_markup=publish_keyboard()
        )
        return
    else:
        await status.edit_text("❌ Не удалось собрать саблиминал.")


@dp.callback_query(F.data == "publish_no")
async def handle_publish_no(call: types.CallbackQuery, state):
    data = await state.get_data()
    subliminal_path = data.get("subliminal_path")
    custom_track = data.get("custom_track")
    cached_voice = data.get("cached_voice_path")

    if subliminal_path and os.path.exists(subliminal_path):
        os.remove(subliminal_path)
    if custom_track and os.path.exists(custom_track):
        os.remove(custom_track)
    if cached_voice and os.path.exists(cached_voice):
        os.remove(cached_voice)

    await call.message.edit_text("Ок, не публикуем. Хочешь ещё один?")
    await call.answer()

    await state.clear()
    await call.message.answer(
        "Выбери тему:",
        reply_markup=topics_keyboard()
    )
    await state.set_state(SubliminalStates.waiting_for_topic)


@dp.callback_query(F.data == "publish_yes")
async def handle_publish_yes(call: types.CallbackQuery, state):
    await call.message.edit_text(
        "Как опубликовать?",
        reply_markup=publish_type_keyboard()
    )
    await call.answer()


@dp.callback_query(F.data == "pub_anon")
async def handle_pub_anon(call: types.CallbackQuery, state):
    await publish_subliminal(call, state, anonymous=True)


@dp.callback_query(F.data == "pub_named")
async def handle_pub_named(call: types.CallbackQuery, state):
    await publish_subliminal(call, state, anonymous=False)


async def publish_subliminal(call: types.CallbackQuery, state, anonymous: bool):
    from config import CHANNEL_ID

    data = await state.get_data()
    subliminal_path = data.get("subliminal_path")
    subliminal_name = data.get("subliminal_name", "Саблиминал")
    custom_track = data.get("custom_track")
    cached_voice = data.get("cached_voice_path")

    if not subliminal_path or not os.path.exists(subliminal_path):
        await call.message.edit_text("❌ Файл потерялся. Начни заново — /start")
        await call.answer()
        await state.clear()
        return

    try:
        if anonymous:
            caption = f"🎧 {subliminal_name}\n\n🕶 Анонимно"
        else:
            username = call.from_user.username
            if username:
                caption = f"🎧 {subliminal_name}\n\n👤 @{username}"
            else:
                caption = f"🎧 {subliminal_name}\n\n👤 {call.from_user.full_name}"

        caption += "\n\n🤖 Сделано в @SubliminalGenBot"

        audio_file = FSInputFile(subliminal_path)
        await bot.send_audio(
            chat_id=CHANNEL_ID,
            audio=audio_file,
            title=subliminal_name,
            caption=caption
        )

        await call.message.edit_text("✅ Опубликовано в канале!")
        await call.answer()

    except Exception as e:
        print(f"Ошибка публикации: {e}")
        await call.message.edit_text("❌ Не удалось опубликовать. Попробуй позже.")
        await call.answer()

    # Чистка
    if subliminal_path and os.path.exists(subliminal_path):
        os.remove(subliminal_path)
    if custom_track and os.path.exists(custom_track):
        os.remove(custom_track)
    if cached_voice and os.path.exists(cached_voice):
        os.remove(cached_voice)

    await state.clear()
    await call.message.answer(
        "Хочешь ещё один?",
        reply_markup=topics_keyboard()
    )
    await state.set_state(SubliminalStates.waiting_for_topic)

@dp.callback_query(F.data == "back_to_publish")
async def back_to_publish(call: types.CallbackQuery, state):
    await call.message.edit_text(
        "📢 Хочешь опубликовать свой саблиминал в канале?",
        reply_markup=publish_keyboard()
    )
    await call.answer()


async def cleanup_output():
    """Удаляет старые файлы из output/ и audio/ раз в час."""
    while True:
        await asyncio.sleep(3600)

        for folder in ["output", "audio"]:
            if not os.path.exists(folder):
                continue

            now = time.time()
            removed = 0

            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    if now - os.path.getmtime(filepath) > 3600:
                        try:
                            os.remove(filepath)
                            removed += 1
                        except Exception as e:
                            print(f"Ошибка удаления {filename}: {e}")

            if removed:
                print(f"🧹 Чистка {folder}: удалено {removed} файлов")

async def main():
    init_db()
    asyncio.create_task(cleanup_output())

    webhook_url = os.getenv("WEBHOOK_URL")

    if webhook_url:
        # Режим webhook
        webhook_path = "/webhook"
        host = "0.0.0.0"
        port = int(os.getenv("PORT", 3000))

        app = web.Application()

        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=webhook_path)

        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        # Регистрируем webhook ПОСЛЕ старта сервера
        await bot.set_webhook(f"{webhook_url}")

        print(f"✅ Бот запущен на webhook: {webhook_url}")
        await asyncio.Event().wait()
    else:
        print("Бот запущен в режиме polling.")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())