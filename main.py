# main.py
import asyncio
import logging
import os
import time
import random
import sys


# Хранилище путей к саблиминалам для публикации
PENDING_PUBLICATIONS = {}

# Логи в файл — ДО всех импортов
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


from aiogram.exceptions import TelegramBadRequest
from config import (
    BOT_TOKEN, ADMIN_ID,
    PRICE_SUBLIMINAL, PRICE_FIRST_CLONE, PRICE_CLONE,
    FEEDBACK_CHAT_ID,
)
from aiogram import Bot, Dispatcher, types, F
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from utils.db import (
    init_db, add_user, log_generation, get_stats,
    can_use_custom_topic, mark_custom_topic_used, get_all_users,
    has_active_subscription, get_user_limits, get_today_usage,
    check_limits, add_usage,
    activate_subscription,
    add_extra_custom_topics, use_extra_custom_topic,
    save_voice_id, get_voice_id, 
)
from services.payments import create_payment, check_payment
from aiogram_sqlite_storage.sqlitestore import SQLStorage
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
    donate_keyboard,
    voices_keyboard_has_clone,
    feedback_keyboard,
)
from services.affirmations import get_affirmation
import services.affirmations
from services.tts import generate_voice, clone_voice
from services.deepseek import generate_affirmation
from services.audio import create_subliminal





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

storage = SQLStorage("/app/data/fsm.db")
dp = Dispatcher(storage=storage)

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



@dp.message(CommandStart())
async def cmd_start(message: types.Message, state):
    # 1. Получаем данные
    data = await state.get_data() or {}
    
    # 2. Сразу очищаем состояние
    await state.clear()

    # 3. Чистим старый саблиминал
    old_path = data.get("subliminal_path")
    if old_path and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except Exception:
            pass

    # 4. Чистим превью
    preview_path = data.get("preview_path")
    if preview_path and os.path.exists(preview_path):
        try:
            os.remove(preview_path)
        except Exception:
            pass

    # 5. Чистим кэш голоса
    cached_voice = data.get("cached_voice_path")
    if cached_voice and os.path.exists(cached_voice):
        try:
            os.remove(cached_voice)
        except Exception:
            pass

    # 6. Регистрация юзера
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

    # 7. СРАЗУ ПОКАЗЫВАЕМ ВЫБОР ГОЛОСА
    user_id = message.from_user.id
    voice_id = get_voice_id(user_id)

    if voice_id:
        await message.answer(
            "Привет! С чего начнем? Выбери голос:",
            reply_markup=voices_keyboard_has_clone()
        )
    else:
        await message.answer(
            "Привет! С чего начнем? Выбери голос:",
            reply_markup=voices_keyboard()
        )

        
    await state.set_state(SubliminalStates.choosing_voice)

@dp.message(F.text.in_(["/help", "/хэлп", "/помощь"]))
async def cmd_help(message: types.Message, state):
    await message.answer(
        "🤖 <b>Что умеет бот</b>\n\n"
        "🎧 Генерирует персональные саблиминалы\n"
        "✨ 10 готовых тем + свой текст + своя тема\n"
        "🎙 4 голоса, 6 частот, 5 бинауральных ритмов\n"
        "📢 Публикация в канал\n\n"
        "<b>Команды:</b>\n"
        "/start — начать / выбрать тему\n"
        "/feedback — отзывы и предложения\n"
        "/help — эта справка",
        parse_mode="HTML"
    )

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

@dp.message(Command("post"))
async def cmd_post(message: types.Message, state):
    if message.from_user.id != ADMIN_ID:
        return

    await state.clear()
    await message.answer(
        "📢 Перешли мне любой пост из любого чата.\n\n"
        "Я разошлю его всем юзерам бота."
    )
    await state.set_state(SubliminalStates.waiting_for_broadcast)


@dp.message(SubliminalStates.waiting_for_broadcast)
async def handle_broadcast(message: types.Message, state):
    if message.from_user.id != ADMIN_ID:
        return

    # Сохраняем ID чата и ID сообщения, чтобы скопировать его
    from_chat_id = message.chat.id
    message_id = message.message_id

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
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=from_chat_id,
                message_id=message_id
            )
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


@dp.message(F.text.in_(["/donate", "/донат", "/поддержать"]))
async def cmd_donate(message: types.Message, state):
    """Показывает меню доната."""
    await message.answer(
        "💝 <b>Поддержать проект</b>\n\n"
        "Бот развивается, и любая поддержка помогает делать его лучше: "
        "новые темы, фичи, улучшения звука.\n\n"
        "Выбери сумму:",
        parse_mode="HTML",
        reply_markup=donate_keyboard()
    )    

@dp.callback_query(F.data == "pay_sub")
async def handle_pay_sub(call: types.CallbackQuery, state):
    """Создаёт платёж на разовый саб."""
    user_id = call.from_user.id

    payment = await asyncio.to_thread(
        create_payment,
        PRICE_SUBLIMINAL,
        "Оплата саблиминала",
        user_id,
        "subliminal"
    )

    if not payment:
        await call.message.edit_text(
            "❌ Не удалось создать платёж. Попробуй позже.",
            
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"💳 Оплата саблиминала — {PRICE_SUBLIMINAL} ₽\n\n"
        f"Перейди по ссылке для оплаты:\n"
        f"{payment['confirmation_url']}\n\n"
        f"После оплаты бот пришлёт доступ.",
        
    )
    await call.answer()



@dp.callback_query(F.data == "donate_menu")
async def handle_donate_menu(call: types.CallbackQuery, state):
    """Открывает меню доната из кнопки."""
    await call.message.edit_text(
        "💝 <b>Поддержать проект</b>\n\n"
        "Бот развивается, и любая поддержка помогает делать его лучше.\n\n"
        "Выбери сумму:",
        parse_mode="HTML",
        reply_markup=donate_keyboard()
    )
    await call.answer()


@dp.callback_query(F.data.startswith("donate_") & ~F.data.in_(["donate_menu"]))
async def handle_donate(call: types.CallbackQuery, state):
    """Создаёт платёж на донат."""
    amount = int(call.data.replace("donate_", ""))
    user_id = call.from_user.id

    logger.info(f"💝 Донат: user_id={user_id}, amount={amount}")

    payment = await asyncio.to_thread(
        create_payment,
        amount,
        f"Поддержка проекта ({amount} ₽)",
        user_id,
        "donation"
    )

    if not payment:
        await call.message.edit_text(
            "❌ Не удалось создать платёж. Попробуй позже.",
            
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"💝 Спасибо за поддержку!\n\n"
        f"Сумма: {amount} ₽\n\n"
        f"Перейди по ссылке для оплаты:\n"
        f"{payment['confirmation_url']}",
        
    )
    await call.answer()    




@dp.callback_query(F.data.in_(TOPICS.keys()))
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


@dp.callback_query(F.data == "topic_custom")
async def handle_custom(call: types.CallbackQuery, state):
    await call.message.edit_text("Напиши, какой саблиминал ты хочешь:")
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_custom_text)


@dp.callback_query(F.data == "topic_custom_topic")
async def handle_custom_topic(call: types.CallbackQuery, state):
    await state.set_state(SubliminalStates.waiting_for_custom_topic)

    await call.message.edit_text(
        "🎯 Напиши свою тему — то, чего нет в готовом списке.\n\n"
        "Например:\n"
        "• хочу сдать экзамен\n"
        "• хочу наладить сон\n"
        "• хочу найти своё дело\n\n"
        "Нейронка сгенерирует аффирмации под твой запрос."
    )
    await call.answer()

@dp.message(SubliminalStates.waiting_for_custom_topic)
async def handle_custom_topic_text(message: types.Message, state):
    if len(message.text) > 500:
        await message.answer(
            f"❌ Слишком длинный запрос ({len(message.text)} символов).\n\n"
            "Максимум — 500 символов. Опиши тему коротко."
        )
        return

    user_topic = message.text
    await state.update_data(topic=user_topic)

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
        "🎧 Теперь выбери категорию трека:",
        reply_markup=categories_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_track)


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
    data = await state.get_data() or {}
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
        "✅ Принято. Теперь выбери категорию трека:",
        reply_markup=categories_keyboard()
    )
    await call.answer()
    await state.set_state(SubliminalStates.choosing_track)

 

@dp.callback_query(SubliminalStates.choosing_voice, F.data.startswith("voice_"))
async def handle_voice(call: types.CallbackQuery, state):
    voice_type = call.data.replace("voice_", "")
    user_id = call.from_user.id

    # Сохраняем голос
    await state.update_data(voice_type=voice_type, reference_id=None)

    # Проверяем, первый ли это саб
    from utils.db import get_today_usage, set_pending_payment, mark_custom_topic_used
    usage = get_today_usage(user_id)
    free_used = usage["custom_topic_used"] >= 1

    if not free_used:
        # Это первый бесплатный саб — пускаем
        mark_custom_topic_used(user_id)
        await call.message.edit_text(
            "✅ Голос выбран. Теперь выбери тему саблиминала:",
            reply_markup=topics_keyboard()
        )
        await call.answer()
        await state.set_state(SubliminalStates.waiting_for_topic)
        return

    # Это не первый саб — просим оплату
    await state.update_data(pending_payment_type="subliminal")
    set_pending_payment(user_id, "subliminal")
    
    price = PRICE_SUBLIMINAL
    payment = await asyncio.to_thread(
        create_payment,
        price,
        "Оплата саблиминала",
        user_id,
        "subliminal"
    )

    if not payment:
        await call.message.edit_text(
            "❌ Не удалось создать платёж. Попробуй позже."
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"💳 Для создания саблиминала нужно оплатить {price} ₽.\n\n"
        f"Перейди по ссылке для оплаты:\n"
        f"{payment['confirmation_url']}\n\n"
        f"После оплаты бот продолжит автоматически.",
        reply_markup=None
    )
    await call.answer()  

@dp.callback_query(F.data == "use_my_voice")
async def handle_use_my_voice(call: types.CallbackQuery, state):
    user_id = call.from_user.id
    voice_id = get_voice_id(user_id)

    if not voice_id:
        await call.message.edit_text("❌ У тебя ещё нет клона. Запиши голос сначала.")
        await call.answer()
        return

    await state.update_data(voice_type="clone", reference_id=voice_id)

    # Оплата за саб клоном
    from utils.db import set_pending_payment
    set_pending_payment(user_id, "subliminal")
    
    price = PRICE_CLONE
    payment = await asyncio.to_thread(
        create_payment,
        price,
        "Оплата саблиминала своим голосом",
        user_id,
        "subliminal"
    )

    if not payment:
        await call.message.edit_text(
            "❌ Не удалось создать платёж. Попробуй позже."
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"💳 Для создания саблиминала своим голосом нужно оплатить {price} ₽.\n\n"
        f"Перейди по ссылке для оплаты:\n"
        f"{payment['confirmation_url']}\n\n"
        f"После оплаты бот продолжит автоматически.",
        reply_markup=None
    )
    await call.answer()    

@dp.callback_query(F.data == "clone_voice")
async def handle_clone_voice(call: types.CallbackQuery, state):
    user_id = call.from_user.id

    # Сохраняем в БД, что ждём оплату за клон
    from utils.db import set_pending_payment
    set_pending_payment(user_id, "clone")
    
    price = PRICE_FIRST_CLONE
    payment = await asyncio.to_thread(
        create_payment,
        price,
        "Создание клона голоса",
        user_id,
        "subliminal"
    )

    if not payment:
        await call.message.edit_text("❌ Не удалось создать платёж. Попробуй позже.")
        await call.answer()
        return

    await call.message.edit_text(
        f"💳 Для создания клона голоса нужно оплатить {price} ₽.\n\n"
        f"Перейди по ссылке для оплаты:\n"
        f"{payment['confirmation_url']}\n\n"
        f"После оплаты я пришлю текст для чтения.",
        reply_markup=None
    )
    await call.answer()


@dp.message(F.voice)
async def handle_voice_sample(message: types.Message, state):
    user_id = message.from_user.id

    # Проверяем, ждёт ли бот голосовое (через состояние)
    current_state = await state.get_state()
    if current_state != SubliminalStates.waiting_for_voice_sample:
        await message.answer("Чтобы записать голос для клонирования, нажми /start и выбери «✨ Мой голос (клонировать)».")
        return

    status = await message.answer("⏳ Обрабатываю запись...")

    try:
        file = message.voice
        logger.info(f"🎙 Получено голосовое от {user_id}, размер: {file.file_size}")
        
        file_info = await bot.get_file(file.file_id)
        logger.info(f"📥 File info получен: {file_info.file_path}")
        
        os.makedirs("/app/data/samples", exist_ok=True)
        ogg_path = f"/app/data/samples/{user_id}_{int(time.time())}.ogg"
        await bot.download_file(file_info.file_path, ogg_path)
        logger.info(f"💾 Голосовое скачано: {ogg_path}, размер на диске: {os.path.getsize(ogg_path)}")

        from pydub import AudioSegment
        logger.info("🎛 Конвертирую в wav...")
        
        audio = AudioSegment.from_file(ogg_path)
        wav_path = ogg_path.replace(".ogg", ".wav")
        audio.export(wav_path, format="wav")
        logger.info(f"✅ Конвертировано в wav: {wav_path}, размер: {os.path.getsize(wav_path)}")

    except Exception as e:
        logger.error(f"❌ Ошибка на этапе скачивания/конвертации: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await status.edit_text(f"❌ Ошибка обработки: {e}")
        return

    try:
        await status.edit_text("⏳ Создаю клон голоса...")
        logger.info(f"🚀 Отправляю на клонирование: {wav_path}")
        
        voice_id = await asyncio.to_thread(clone_voice, wav_path)
        logger.info(f"📦 Результат клонирования: {voice_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка клонирования: {e}")
        import traceback
        logger.error(traceback.format_exc())
        voice_id = None

    # Чистим файлы
    if os.path.exists(ogg_path):
        os.remove(ogg_path)
    if os.path.exists(wav_path):
        os.remove(wav_path)

    if not voice_id:
        await status.edit_text("❌ Не удалось создать клон. Попробуй позже.")
        await state.clear()
        return

    save_voice_id(user_id, voice_id)

    await status.edit_text(
        "✅ <b>Клон готов!</b>\n\n"
        "Сейчас пришлю тестовую озвучку твоим голосом.",
        parse_mode="HTML"
    )

    # Тестовая фраза для демонстрации
    test_text = "Привет! Это мой клонированный голос. Теперь я могу озвучивать саблиминалы так."
    
    test_audio_path = await generate_voice(test_text, reference_id=voice_id)
    
    if test_audio_path and os.path.exists(test_audio_path):
        audio_file = FSInputFile(test_audio_path)
        await message.answer_audio(
            audio=audio_file,
            title="Тест клонированного голоса",
            caption="🎧 Послушай, как звучит твой клон."
        )
        if os.path.exists(test_audio_path):
            os.remove(test_audio_path)
    else:
        await message.answer("⚠️ Не удалось сгенерировать тестовую озвучку, но клон сохранён.")

    # Чистим флаг ожидания оплаты/клонирования
    from utils.db import clear_pending_payment
    clear_pending_payment(user_id)

    # СРАЗУ ПЕРЕХОДИМ К ВЫБОРУ ТЕМЫ (без показа голосов)
    await message.answer(
        "✅ Клон готов! Теперь выбери тему саблиминала:",
        reply_markup=topics_keyboard()
    )
    
    await state.set_state(SubliminalStates.waiting_for_topic)


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

    # Проверка размера — Telegram не даёт боту скачивать >20 МБ
    if file.file_size and file.file_size > 20 * 1024 * 1024:
        await message.answer(
            "❌ Файл больше 20 МБ — Telegram не даёт боту такие скачивать.\n\n"
            "Сожми трек или возьми файл до 20 МБ."
        )
        return

    try:
        file_info = await bot.get_file(file.file_id)
    except TelegramBadRequest:
        await message.answer(
            "❌ Не удалось скачать файл. Скорее всего, он слишком большой.\n\n"
            "Попробуй файл до 20 МБ."
        )
        return

    os.makedirs("assets/user", exist_ok=True)
    user_track_path = f"assets/user/{message.from_user.id}_{int(time.time())}.mp3"
    await bot.download_file(file_info.file_path, user_track_path)

    await state.update_data(custom_track=user_track_path, category="custom")
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
    source = data.get("source", "")


    # Сохраняем название
    await state.update_data(
        subliminal_name=message.text,
        voice_offset=0,
        voice_clicks=0
    )

    # Генерим голос ОДИН РАЗ
    await message.answer("⏳ Готовлю голос...")
    reference_id = data.get("reference_id")
    voice_path = await generate_voice(affirmation, voice_type=voice_type, reference_id=reference_id)

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

        # Устанавливаем источник, если не установлен
    if "source" not in data or not data["source"]:
        import services.affirmations
        data["source"] = services.affirmations.last_source or "unknown"

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

        logger.info(f"🎬 СТАРТ ГЕНЕРАЦИИ: {subliminal_name}, {length_minutes} мин")

        # Проверяем голос
        if not voice_path or not os.path.exists(voice_path):
            logger.error(f"❌ Голос потерялся: {voice_path}")
            await bot.send_message(chat_id, "❌ Голос потерялся. Начни заново — /start")
            return

        # Собираем саблиминал
        start_gen = time.time()

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

        gen_time = time.time() - start_gen
        logger.info(f"🎬 ГЕНЕРАЦИЯ ЗАВЕРШЕНА за {gen_time:.1f} сек")

        # Отправляем
        if subliminal_path and os.path.exists(subliminal_path):
            size_mb = os.path.getsize(subliminal_path) / 1024 / 1024
            logger.info(f"📤 ФАЙЛ: {subliminal_path}, размер {size_mb:.1f} МБ")

                        # Всегда ставим подпись
            caption = f"🎧 {subliminal_name}\n\n🤖 Сделано в @SubliminalGenBot"

            audio_file = FSInputFile(subliminal_path)

            start_send = time.time()
            try:
                await bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title=subliminal_name,
                    caption=caption
                )
                send_time = time.time() - start_send
                logger.info(f"✅ ОТПРАВЛЕНО за {send_time:.1f} сек")

            except Exception as e:
                send_time = time.time() - start_send
                logger.error(f"❌ ОШИБКА ОТПРАВКИ через {send_time:.1f} сек: {e}")
                raise

            # Логируем
            source = data.get("source", "unknown")
            log_generation(user_id, source)

            # Записываем лимит
            requested_minutes = data.get("requested_minutes", 0)
            is_custom_topic = data.get("is_custom_topic", False)
            add_usage(user_id, requested_minutes, is_custom_topic)

            # Чистим только голос и свой трек
            if voice_path and os.path.exists(voice_path):
                os.remove(voice_path)
            if custom_track and os.path.exists(custom_track):
                os.remove(custom_track)

            # Сохраняем путь для публикации
            PENDING_PUBLICATIONS[user_id] = {
                "path": subliminal_path,
                "name": subliminal_name
            }

                        # Спрашиваем про публикацию
            await bot.send_message(
                chat_id,
                "📢 <b>Хочешь опубликовать свой саблиминал в канале?</b>\n\n"
                "Он появится здесь: https://t.me/SubliminalBot_Channel",
                parse_mode="HTML",
                reply_markup=publish_keyboard()
            )
        else:
            logger.error(f"❌ Саблиминал не создан: {subliminal_path}")
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
    user_id = call.from_user.id
    pending = PENDING_PUBLICATIONS.get(user_id)

    if pending:
        subliminal_path = pending["path"]
        if subliminal_path and os.path.exists(subliminal_path):
            os.remove(subliminal_path)
        PENDING_PUBLICATIONS.pop(user_id, None)

    await call.message.edit_text("Ок, не публикуем. Хочешь ещё один?")
    await call.answer()

    await state.clear()
    
    user_id = call.from_user.id
    voice_id = get_voice_id(user_id)
    
    if voice_id:
        await call.message.answer(
            "Хочешь ещё один? Выбери голос:",
            reply_markup=voices_keyboard_has_clone()
        )
    else:
        await call.message.answer(
            "Хочешь ещё один? Выбери голос:",
            reply_markup=voices_keyboard()
        )
        
    await state.set_state(SubliminalStates.choosing_voice)


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

    user_id = call.from_user.id

    # Берём путь из словаря
    pending = PENDING_PUBLICATIONS.get(user_id)

    if not pending:
        await call.message.edit_text("❌ Файл не найден. Попробуй заново.")
        await call.answer()
        return

    subliminal_path = pending["path"]
    subliminal_name = pending["name"]

    if not subliminal_path or not os.path.exists(subliminal_path):
        await call.message.edit_text("❌ Файл потерялся. Попробуй заново.")
        await call.answer()
        PENDING_PUBLICATIONS.pop(user_id, None)
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

    # Убираем из словаря
    PENDING_PUBLICATIONS.pop(user_id, None)

    await call.message.answer(
        "Хочешь ещё один?",
        reply_markup=topics_keyboard()
    )
    await state.set_state(SubliminalStates.waiting_for_topic)


async def handle_yookassa_event(event: dict):
    """Обрабатывает уведомление от ЮKassa об оплате."""
    try:
        event_type = event.get("event")
        payment_obj = event.get("object", {})

        # Обрабатываем только успешные платежи
        if event_type != "payment.succeeded":
            return

        # Достаём метаданные
        metadata = payment_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        payment_type = metadata.get("payment_type")

        if not user_id or not payment_type:
            logger.error(f"Нет user_id или payment_type в metadata: {metadata}")
            return

        user_id = int(user_id)

        logger.info(f"💰 ОПЛАТА: user_id={user_id}, type={payment_type}")

        # Донат
        if payment_type == "donation":
            logger.info(f"💝 Донат получен: user_id={user_id}")
            await bot.send_message(
                user_id,
                "💝 Спасибо за поддержку! Ты делаешь проект лучше."
            )
            await bot.send_message(
                ADMIN_ID,
                f"💝 Донат: user_id={user_id}"
            )

        elif payment_type == "subliminal":
            logger.info(f"✅ Оплачен саб для {user_id}")
            
            from utils.db import get_pending_payment, clear_pending_payment
            pending = get_pending_payment(user_id)
            
            # Получаем нормальный контекст состояния (FSM) по юзеру
            state = dp.fsm.get_context(bot=bot, chat_id=user_id, user_id=user_id)

            if pending == "clone":
                # Юзер оплатил клон — присылаем текст и переводим в состояние записи
                await bot.send_message(
                    user_id,
                    "✅ <b>Оплата за клонирование прошла!</b>\n\n"
                    "Теперь запиши голосовое сообщение (около 1 минуты), читая этот текст:\n\n"
                    "<i>Привет. Меня зовут [имя]. Я записываю свой голос для создания персонального саблиминала. Я говорю спокойно и чётко.\n\n"
                    "Сегодня хороший день. Я читаю этот текст, чтобы мой голос был узнаваемым. Один, два, три, четыре, пять, шесть, семь, восемь, девять, десять.\n\n"
                    "Я люблю утро, когда солнце только встаёт. Я люблю вечер, когда становится тихо. Я люблю дождь, который стучит по крыше. Я люблю ветер, который шумит в листьях.\n\n"
                    "Моя речь ровная и естественная. Я не тороплюсь. Я дышу спокойно. Я чувствую себя комфортно.\n\n"
                    "Этот голос — мой. Он звучит так, как я говорю каждый день. Я читаю этот текст, чтобы мой голос был узнаваемым.\n\n"
                    "Спасибо. Это был мой голос.</i>\n\n"
                    "⚠️ Читай чётко, с выражением, не торопись.",
                    parse_mode="HTML"
                )
                
                # Нормально ставим состояние
                await state.set_state(SubliminalStates.waiting_for_voice_sample)
                await state.update_data(voice_type="clone")
                
            else:
                # Юзер оплатил обычный саб
                await bot.send_message(
                    user_id,
                    "✅ Оплата прошла! Теперь выбери тему саблиминала:",
                    reply_markup=topics_keyboard()
                )
                
                # Нормально ставим состояние
                await state.set_state(SubliminalStates.waiting_for_topic)
            
            clear_pending_payment(user_id)

        elif payment_type == "custom_topic":
            add_extra_custom_topics(user_id, count=1)
            logger.info(f"✅ Разовая тема начислена для {user_id}")
            await bot.send_message(
                user_id,
                "✅ Разовая тема оплачена!\n\n"
                "Можешь использовать её в боте."
            )

        

    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")
        import traceback
        logger.error(traceback.format_exc())

@dp.callback_query(F.data == "back_to_publish")
async def back_to_publish(call: types.CallbackQuery, state):
    await call.message.edit_text(
        "📢 Хочешь опубликовать свой саблиминал в канале?",
        reply_markup=publish_keyboard()
    )
    await call.answer()


async def cleanup_output():
    """Удаляет старые файлы из output/, audio/ и assets/user/ раз в 15 минут."""
    while True:
        await asyncio.sleep(900)

        for folder in ["/app/data/output", "/app/data/audio", "assets/user"]:
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

@dp.message(F.text.in_(["/feedback", "/отзыв", "/фидбек"]))
async def cmd_feedback(message: types.Message, state):
    await message.answer(
        "💬 Отзыв, жалобы, предложения сюда -> @SubliminalReviews",
        parse_mode="HTML"
    )

async def main():
    init_db()
    asyncio.create_task(cleanup_output())

    # Меню команд в Telegram
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Начать"),
        types.BotCommand(command="feedback", description="Отзывы и предложения"),
        types.BotCommand(command="donate", description="Поддержать проект"),
        types.BotCommand(command="help", description="Помощь"),
    ])

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

        # Обработчик вебхука ЮKassa
        async def yookassa_webhook(request):
            try:
                event = await request.json()
                await handle_yookassa_event(event)
            except Exception as e:
                print(f"Ошибка обработки вебхука ЮKassa: {e}")
            return web.Response(status=200)

        app.router.add_post("/yookassa_webhook", yookassa_webhook)

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