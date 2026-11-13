# main.py
import asyncio
import logging
import os
import time
import random

PENDING_PUBLICATIONS = {}

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
    PRICE_SUBLIMINAL,
    FEEDBACK_CHAT_ID,
)
from aiogram import Bot, Dispatcher, types, F
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from utils.db import (
    init_db, add_user, log_generation, get_stats, get_all_users,
    add_usage, save_voice_id, get_voice_id,
    has_used_free_subliminal, mark_free_subliminal_used,
)
from services.payments import create_payment
from aiogram_sqlite_storage.sqlitestore import SQLStorage
from states.fsm import SubliminalStates
from keyboards.inline import (
    topics_keyboard, voices_keyboard, categories_keyboard,
    affirmation_keyboard, lengths_keyboard, publish_keyboard,
    publish_type_keyboard, solfeggio_keyboard, binaural_keyboard,
    voice_tune_keyboard, limit_keyboard, donate_keyboard,
    voices_keyboard_has_clone, feedback_keyboard,
)
from services.affirmations import get_affirmation
import services.affirmations
from services.tts import generate_voice
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

async def cleanup_output():
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

async def main():
    init_db()
    asyncio.create_task(cleanup_output())

    await bot.set_my_commands([
        types.BotCommand(command="start", description="Начать"),
        types.BotCommand(command="feedback", description="Отзывы и предложения"),
        types.BotCommand(command="donate", description="Поддержать проект"),
        types.BotCommand(command="help", description="Помощь"),
    ])

    webhook_url = os.getenv("WEBHOOK_URL")

    if webhook_url:
        webhook_path = "/webhook"
        host = "0.0.0.0"
        port = int(os.getenv("PORT", 3000))

        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_requests_handler.register(app, path=webhook_path)
        setup_application(app, dp, bot=bot)

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

        await bot.set_webhook(f"{webhook_url}")
        print(f"✅ Бот запущен на webhook: {webhook_url}")
        await asyncio.Event().wait()
    else:
        print("Бот запущен в режиме polling.")
        await dp.start_polling(bot)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state):
    data = await state.get_data() or {}
    await state.clear()

    old_path = data.get("subliminal_path")
    if old_path and os.path.exists(old_path):
        try: os.remove(old_path)
        except: pass

    preview_path = data.get("preview_path")
    if preview_path and os.path.exists(preview_path):
        try: os.remove(preview_path)
        except: pass

    cached_voice = data.get("cached_voice_path")
    if cached_voice and os.path.exists(cached_voice):
        try: os.remove(cached_voice)
        except: pass

    is_new = add_user(message.from_user.id, message.from_user.username or "")
    if is_new:
        try:
            await bot.send_message(ADMIN_ID, f"🆕 Новый юзер: @{message.from_user.username or 'без_юзернейма'}\nID: {message.from_user.id}")
        except Exception: pass

    user_id = message.from_user.id
    voice_id = get_voice_id(user_id)

    if voice_id:
        await message.answer("Привет! С чего начнем? Выбери голос:", reply_markup=voices_keyboard_has_clone())
    else:
        await message.answer("Привет! С чего начнем? Выбери голос:", reply_markup=voices_keyboard())
        
    await state.set_state(SubliminalStates.choosing_voice)

@dp.message(F.text.in_(["/help", "/хэлп", "/помощь"]))
async def cmd_help(message: types.Message, state):
    await message.answer(
        "🤖 <b>Что умеет бот</b>\n\n"
        "🎧 Генерирует персональные саблиминалы\n"
        "✨ 10 готовых тем + свой текст + своя тема\n"
        "🎙 4 голоса, 6 частот, 5 бинауральных ритмов\n"
        "📢 Публикация в канал\n\n"
        "<b>Команды:</b>\n/start — начать\n/feedback — отзывы\n/help — справка",
        parse_mode="HTML"
    )

@dp.message(F.text == "/stats")
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    stats = get_stats()
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего юзеров: <b>{stats['total_users']}</b>\n"
        f"🎧 Сгенерировано: <b>{stats['total_generations']}</b>\n\n"
        f"📦 Из пула: <b>{stats['from_pool']}</b>\n"
        f"🔧 Из строк: <b>{stats['from_strings']}</b>\n"
        f"🤖 Из Дипсика: <b>{stats['from_deepseek']}</b>\n"
        f"✍️ Свой текст: <b>{stats['from_custom']}</b>\n"
        f"🎯 Своя тема: <b>{stats['from_custom_topic']}</b>",
        parse_mode="HTML"
    )

@dp.message(Command("post"))
async def cmd_post(message: types.Message, state):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("📢 Перешли мне пост для рассылки.")
    await state.set_state(SubliminalStates.waiting_for_broadcast)

@dp.message(SubliminalStates.waiting_for_broadcast)
async def handle_broadcast(message: types.Message, state):
    if message.from_user.id != ADMIN_ID: return
    from_chat_id = message.chat.id
    message_id = message.message_id
    await state.clear()
    users = get_all_users()
    if not users:
        await message.answer("Нет юзеров.")
        return
    status = await message.answer(f"⏳ Рассылаю {len(users)}...")
    sent, failed = 0, 0
    for user_id in users:
        try:
            await bot.copy_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ Рассылка завершена.\n📤 Отправлено: {sent}\n❌ Ошибок: {failed}")

@dp.message(F.text.in_(["/donate", "/донат"]))
async def cmd_donate(message: types.Message, state):
    await message.answer("💝 <b>Поддержать проект</b>\n\nВыбери сумму:", parse_mode="HTML", reply_markup=donate_keyboard())

@dp.callback_query(F.data == "donate_menu")
async def handle_donate_menu(call: types.CallbackQuery, state):
    await call.message.edit_text("💝 <b>Поддержать проект</b>\n\nВыбери сумму:", parse_mode="HTML", reply_markup=donate_keyboard())
    await call.answer()

@dp.callback_query(F.data.in_(TOPICS.keys()))
async def handle_topic(call: types.CallbackQuery, state):
    topic_data = TOPICS[call.data]
    await state.update_data(topic=topic_data["text"], topic_key=topic_data["key"])
    freq_text = FREQ_INFO.get(topic_data["key"], "")
    await call.message.edit_text(f"Тема: {topic_data['text']}\n\n🎵 Подобрано: {freq_text}")
    await call.answer()
    await ask_affirmation(call.message, state)

@dp.callback_query(F.data == "topic_custom")
async def handle_custom(call: types.CallbackQuery, state):
    user_id = call.from_user.id
    from utils.db import set_pending_payment
    set_pending_payment(user_id, "custom_text")
    price = 150
    payment = await asyncio.to_thread(create_payment, price, "Оплата своего текста", user_id, "subliminal")
    if not payment:
        await call.message.edit_text("❌ Не удалось создать платёж. Попробуй позже.")
        await call.answer()
        return
    await call.message.edit_text(f"💳 Свой текст — {price} ₽.\n\nПерейди по ссылке для оплаты:\n{payment['confirmation_url']}\n\nПосле оплаты бот продолжит автоматически.", reply_markup=None)
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_custom_text)

@dp.callback_query(F.data == "topic_custom_topic")
async def handle_custom_topic(call: types.CallbackQuery, state):
    user_id = call.from_user.id
    from utils.db import set_pending_payment
    set_pending_payment(user_id, "custom_topic_payment")
    price = 150
    payment = await asyncio.to_thread(create_payment, price, "Оплата своей темы", user_id, "subliminal")
    if not payment:
        await call.message.edit_text("❌ Не удалось создать платёж. Попробуй позже.")
        await call.answer()
        return
    await call.message.edit_text(f"💳 Своя тема — {price} ₽.\n\nПерейди по ссылке для оплаты:\n{payment['confirmation_url']}\n\nПосле оплаты бот продолжит автоматически.", reply_markup=None)
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_custom_topic)

@dp.message(SubliminalStates.waiting_for_custom_topic)
async def handle_custom_topic_text(message: types.Message, state):
    if len(message.text) > 500:
        await message.answer("❌ Максимум 500 символов.")
        return
    user_topic = message.text
    await state.update_data(topic=user_topic)
    status = await message.answer("⏳ Генерирую аффирмации...")
    affirmation = await asyncio.to_thread(generate_affirmation, user_topic)
    await state.update_data(affirmation=affirmation, source="custom_topic")
    await status.edit_text(f"Вот что сгенерировалось:\n\n{affirmation}")
    await message.answer("🎵 Теперь выбери сольфеджио-частоту:", reply_markup=solfeggio_keyboard())
    await state.set_state(SubliminalStates.choosing_solfeggio)

@dp.callback_query(SubliminalStates.choosing_solfeggio, F.data.startswith("sol_"))
async def handle_solfeggio(call: types.CallbackQuery, state):
    sol_code = call.data.replace("sol_", "")
    if sol_code == "none":
        await state.update_data(custom_solfeggio=None)
    else:
        await state.update_data(custom_solfeggio=int(sol_code))
    await call.message.edit_text("✅ Частота выбрана.\n\n🎧 Теперь выбери бинауральный ритм:", reply_markup=binaural_keyboard())
    await call.answer()
    await state.set_state(SubliminalStates.choosing_binaural)

@dp.callback_query(SubliminalStates.choosing_binaural, F.data.startswith("bin_"))
async def handle_binaural(call: types.CallbackQuery, state):
    bin_code = call.data.replace("bin_", "")
    binaural_map = {"alpha": (200, 210), "theta": (200, 206), "delta": (200, 202), "beta": (200, 215), "none": None}
    await state.update_data(custom_binaural=binaural_map.get(bin_code))
    await call.message.edit_text("✅ Ритм выбран.\n\n🎧 Теперь выбери категорию трека:", reply_markup=categories_keyboard())
    await call.answer()
    await state.set_state(SubliminalStates.choosing_track)

@dp.message(SubliminalStates.waiting_for_custom_text)
async def handle_custom_text(message: types.Message, state):
    await state.update_data(affirmation=message.text, source="custom")
    await message.answer("✅ Текст принят.\n\n🎵 Выбери сольфеджио-частоту:", reply_markup=solfeggio_keyboard())
    await state.set_state(SubliminalStates.choosing_solfeggio)

async def ask_affirmation(message: types.Message, state):
    data = await state.get_data() or {}
    status = await message.answer("⏳ Генерирую аффирмации...")
    await asyncio.sleep(random.uniform(2.0, 4.0))
    affirmation = await asyncio.to_thread(get_affirmation, data.get("topic_key"), data.get("topic", "успех"))
    await state.update_data(affirmation=affirmation)
    await status.edit_text(f"Вот что сгенерировалось:\n\n{affirmation}\n\nПодходит или перегенерить?", reply_markup=affirmation_keyboard())

@dp.callback_query(F.data == "affirm_regen")
async def handle_regen(call: types.CallbackQuery, state):
    data = await state.get_data()
    await call.message.edit_text("⏳ Генерирую новый текст...")
    await call.answer()
    await asyncio.sleep(random.uniform(2.0, 4.0))
    affirmation = await asyncio.to_thread(get_affirmation, data.get("topic_key"), data.get("topic", "успех"))
    await state.update_data(affirmation=affirmation)
    await call.message.edit_text(f"Вот что сгенерировалось:\n\n{affirmation}\n\nПодходит или перегенерить?", reply_markup=affirmation_keyboard())

@dp.callback_query(F.data == "affirm_ok")
async def handle_ok(call: types.CallbackQuery, state):
    await call.message.edit_text("✅ Принято. Теперь выбери категорию трека:", reply_markup=categories_keyboard())
    await call.answer()
    await state.set_state(SubliminalStates.choosing_track)

@dp.callback_query(SubliminalStates.choosing_voice, F.data.startswith("voice_"))
async def handle_voice(call: types.CallbackQuery, state):
    voice_type = call.data.replace("voice_", "")
    user_id = call.from_user.id
    await state.update_data(voice_type=voice_type, reference_id=None)
    from utils.db import set_pending_payment

    if not has_used_free_subliminal(user_id):
        await state.update_data(is_free_subliminal=True)
        await call.message.edit_text("✅ Голос выбран. Это твой первый саб — он бесплатный!\n\nТеперь выбери тему саблиминала:", reply_markup=topics_keyboard())
        await call.answer()
        await state.set_state(SubliminalStates.waiting_for_topic)
        return

    await state.update_data(pending_payment_type="subliminal")
    set_pending_payment(user_id, "subliminal")
    price = PRICE_SUBLIMINAL
    payment = await asyncio.to_thread(create_payment, price, "Оплата саблиминала", user_id, "subliminal")
    if not payment:
        await call.message.edit_text("❌ Не удалось создать платёж. Попробуй позже.")
        await call.answer()
        return
    await call.message.edit_text(f"💳 Твой бесплатный саб уже использован.\n\nСледующий саб (любая тема на выбор) — {price} ₽.\nПерейди по ссылке для оплаты:\n{payment['confirmation_url']}\n\nПосле оплаты бот продолжит автоматически.", reply_markup=None)
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
    from utils.db import set_pending_payment
    set_pending_payment(user_id, "subliminal")
    price = PRICE_SUBLIMINAL
    payment = await asyncio.to_thread(create_payment, price, "Оплата саблиминала", user_id, "subliminal")
    if not payment:
        await call.message.edit_text("❌ Не удалось создать платёж. Попробуй позже.")
        await call.answer()
        return
    await call.message.edit_text(f"💳 Для создания саблиминала нужно оплатить {price} ₽.\n\nПерейди по ссылке для оплаты:\n{payment['confirmation_url']}\n\nПосле оплаты бот продолжит автоматически.", reply_markup=None)
    await call.answer()    

@dp.callback_query(F.data == "clone_voice")
async def handle_clone_voice(call: types.CallbackQuery, state):
    user_id = call.from_user.id
    from utils.db import set_pending_payment
    set_pending_payment(user_id, "clone")
    price = 1
    payment = await asyncio.to_thread(create_payment, price, "Создание клона голоса", user_id, "subliminal")
    if not payment:
        await call.message.edit_text("❌ Не удалось создать платёж. Попробуй позже.")
        await call.answer()
        return
    await call.message.edit_text(f"💳 Для создания клона голоса нужно оплатить {price} ₽.\n\nПерейди по ссылке для оплаты:\n{payment['confirmation_url']}\n\nПосле оплаты я пришлю текст для чтения.", reply_markup=None)
    await call.answer()

@dp.message(F.voice)
async def handle_voice_sample(message: types.Message, state):
    user_id = message.from_user.id
    current_state = await state.get_state()
    if current_state != SubliminalStates.waiting_for_voice_sample:
        await message.answer("Чтобы записать голос, нажми /start и выбери «✨ Мой голос».")
        return
    status = await message.answer("⏳ Обрабатываю запись...")
    try:
        file = message.voice
        file_info = await bot.get_file(file.file_id)
        os.makedirs("/app/data/samples", exist_ok=True)
        ogg_path = f"/app/data/samples/{user_id}_{int(time.time())}.ogg"
        await bot.download_file(file_info.file_path, ogg_path)
        from pydub import AudioSegment
        audio = AudioSegment.from_file(ogg_path)
        wav_path = ogg_path.replace(".ogg", ".wav")
        audio.export(wav_path, format="wav")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка обработки: {e}")
        return
    try:
        await status.edit_text("⏳ Создаю клон голоса...")
        voice_id = await asyncio.to_thread(clone_voice, wav_path)
    except Exception as e:
        voice_id = None
    if os.path.exists(ogg_path): os.remove(ogg_path)
    if os.path.exists(wav_path): os.remove(wav_path)
    if not voice_id:
        await status.edit_text("❌ Не удалось создать клон. Попробуй позже.")
        await state.clear()
        return
    save_voice_id(user_id, voice_id)
    await status.edit_text("✅ <b>Клон готов!</b>\n\nСейчас пришлю тестовую озвучку.", parse_mode="HTML")
    test_audio_path = await generate_voice("Привет! Это мой клонированный голос. Теперь я могу озвучивать саблиминалы так.", reference_id=voice_id)
    if test_audio_path and os.path.exists(test_audio_path):
        await message.answer_audio(FSInputFile(test_audio_path), title="Тест клона", caption="🎧 Послушай, как звучит твой клон.")
        os.remove(test_audio_path)
    else:
        await message.answer("⚠️ Не удалось сгенерировать тестовую озвучку, но клон сохранён.")
    from utils.db import clear_pending_payment
    clear_pending_payment(user_id)
    await message.answer("✅ Клон готов! Теперь выбери тему саблиминала:", reply_markup=topics_keyboard())
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
        preview_path = os.path.join("assets", "previews", category, track)
        if os.path.exists(preview_path):
            tasks.append(bot.send_audio(chat_id=call.message.chat.id, audio=FSInputFile(preview_path), title=track.replace(".mp3", "")))
    if tasks: await asyncio.gather(*tasks)
    buttons = [[InlineKeyboardButton(text=f"🎵 {track.replace('.mp3', '')}", callback_data=f"track_{track}")] for track in tracks]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_category")])
    await call.message.answer("Выбери трек:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(SubliminalStates.choosing_track_item)

@dp.callback_query(F.data == "back_to_topic")
async def back_to_topic(call: types.CallbackQuery, state):
    await state.clear()
    await call.message.edit_text("Выбери тему саблиминала:", reply_markup=topics_keyboard())
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_topic)

@dp.callback_query(F.data == "back_to_voice")
async def back_to_voice(call: types.CallbackQuery, state):
    await call.message.edit_text("Выбери голос:", reply_markup=voices_keyboard())
    await call.answer()
    await state.set_state(SubliminalStates.choosing_voice)

@dp.callback_query(F.data == "back_to_category")
async def back_to_category(call: types.CallbackQuery, state):
    await call.message.edit_text("Выбери категорию трека:", reply_markup=categories_keyboard())
    await call.answer()
    await state.set_state(SubliminalStates.choosing_track)

@dp.callback_query(SubliminalStates.choosing_track_item, F.data.startswith("track_"))
async def handle_track_choice(call: types.CallbackQuery, state):
    await state.update_data(chosen_track=call.data.replace("track_", ""))
    await call.message.edit_text("✅ Трек выбран.\n\n🕐 Выбери длину саблиминала:", reply_markup=lengths_keyboard())
    await call.answer()
    await state.set_state(SubliminalStates.choosing_length)

@dp.message(SubliminalStates.choosing_track_item, F.audio | F.document)
async def handle_custom_track(message: types.Message, state):
    file = message.audio or message.document
    if not file or (message.document and not message.document.file_name.lower().endswith(".mp3")):
        await message.answer("Нужен MP3-файл.")
        return
    if file.file_size and file.file_size > 20 * 1024 * 1024:
        await message.answer("❌ Файл больше 20 МБ.")
        return
    try:
        file_info = await bot.get_file(file.file_id)
    except TelegramBadRequest:
        await message.answer("❌ Не удалось скачать файл (больше 20 МБ).")
        return
    os.makedirs("assets/user", exist_ok=True)
    user_track_path = f"assets/user/{message.from_user.id}_{int(time.time())}.mp3"
    await bot.download_file(file_info.file_path, user_track_path)
    await state.update_data(custom_track=user_track_path, category="custom")
    await message.answer("✅ Трек принят.\n\n🕐 Выбери длину:", reply_markup=lengths_keyboard())
    await state.set_state(SubliminalStates.choosing_length)

@dp.callback_query(SubliminalStates.choosing_length, F.data.startswith("len_"))
async def handle_length(call: types.CallbackQuery, state):
    length_code = call.data.replace("len_", "")
    length_minutes = int(length_code) if length_code in ["5", "10", "15"] else None
    await state.update_data(length_minutes=length_minutes)
    await call.message.edit_text(f"✅ Длина: {length_minutes if length_minutes else 'по треку'}.\n\n✍️ Напиши название для саблиминала:")
    await call.answer()
    await state.set_state(SubliminalStates.waiting_for_name)

@dp.message(SubliminalStates.waiting_for_name)
async def handle_name(message: types.Message, state):
    if message.text.startswith("/"):
        await message.answer("❌ Название не может начинаться с «/».")
        return
    data = await state.get_data()
    await state.update_data(subliminal_name=message.text, voice_offset=0, voice_clicks=0)
    await message.answer("⏳ Готовлю голос...")
    voice_path = await generate_voice(data.get("affirmation"), voice_type=data.get("voice_type", "male_1"), reference_id=data.get("reference_id"))
    if not voice_path:
        await message.answer("❌ Не удалось создать озвучку.")
        await state.clear()
        return
    await state.update_data(subliminal_name=message.text, voice_offset=0, voice_clicks=0, cached_voice_path=voice_path)
    await message.answer(f"✅ Название: «{message.text}».\n\n🎧 Генерирую превью...")
    await generate_preview(message, state)

async def generate_preview(message: types.Message, state):
    data = await state.get_data()
    voice_path = data.get("cached_voice_path")
    if not voice_path or not os.path.exists(voice_path):
        await message.answer("❌ Голос потерялся.")
        await state.clear()
        return
    if data.get("custom_track"):
        subliminal_path = await asyncio.to_thread(create_subliminal, voice_path, None, data.get("custom_track"), 0.5, data.get("custom_solfeggio"), data.get("custom_binaural"), data.get("voice_offset", 0))
    elif data.get("chosen_track"):
        subliminal_path = await asyncio.to_thread(create_subliminal, voice_path, None, os.path.join("assets", data.get("category"), data.get("chosen_track")), 0.5, data.get("custom_solfeggio"), data.get("custom_binaural"), data.get("voice_offset", 0))
    else:
        subliminal_path = await asyncio.to_thread(create_subliminal, voice_path, data.get("category"), None, 0.5, data.get("custom_solfeggio"), data.get("custom_binaural"), data.get("voice_offset", 0))
    if not subliminal_path or not os.path.exists(subliminal_path):
        await message.answer("❌ Не удалось создать превью.")
        return
    await state.update_data(preview_path=subliminal_path)
    await message.answer_audio(FSInputFile(subliminal_path), title="Превью (30 сек)", caption=f"🎧 Громкость: {data.get('voice_offset', 0):+d} дБ\nКликов: {data.get('voice_clicks', 0)}/5")
    await message.answer("Настрой громкость:", reply_markup=voice_tune_keyboard())

@dp.callback_query(F.data == "voice_up")
async def handle_voice_up(call: types.CallbackQuery, state):
    data = await state.get_data()
    if data.get("voice_clicks", 0) >= 5:
        await call.answer("❌ Лимит кликов.", show_alert=True); return
    if data.get("voice_offset", 0) >= 20:
        await call.answer("🔊 Громче нельзя.", show_alert=True); return
    await state.update_data(voice_offset=data.get("voice_offset", 0) + 5, voice_clicks=data.get("voice_clicks", 0) + 1)
    if data.get("preview_path") and os.path.exists(data.get("preview_path")): os.remove(data.get("preview_path"))
    await call.message.delete()
    await call.answer()
    await generate_preview(call.message, state)

@dp.callback_query(F.data == "voice_down")
async def handle_voice_down(call: types.CallbackQuery, state):
    data = await state.get_data()
    if data.get("voice_clicks", 0) >= 5:
        await call.answer("❌ Лимит кликов.", show_alert=True); return
    if data.get("voice_offset", 0) <= -20:
        await call.answer("🔉 Тише нельзя.", show_alert=True); return
    await state.update_data(voice_offset=data.get("voice_offset", 0) - 5, voice_clicks=data.get("voice_clicks", 0) + 1)
    if data.get("preview_path") and os.path.exists(data.get("preview_path")): os.remove(data.get("preview_path"))
    await call.message.delete()
    await call.answer()
    await generate_preview(call.message, state)

@dp.callback_query(F.data == "voice_done")
async def handle_voice_done(call: types.CallbackQuery, state):
    data = await state.get_data()
    if data.get("preview_path") and os.path.exists(data.get("preview_path")): os.remove(data.get("preview_path"))
    await call.message.delete()
    await call.answer()
    if "source" not in data or not data["source"]:
        import services.affirmations
        data["source"] = services.affirmations.last_source or "unknown"
    data["user_id"] = call.from_user.id
    data["chat_id"] = call.message.chat.id
    data_copy = dict(data)
    await call.message.answer("✅ Готово! Генерация идёт в фоне.\n\nЯ пришлю саблиминал, когда он будет готов.")
    asyncio.create_task(generate_subliminal_background(data_copy))
    await state.clear()

async def generate_subliminal_background(data: dict):
    try:
        chat_id, user_id = data.get("chat_id"), data.get("user_id")
        voice_path, custom_track = data.get("cached_voice_path"), data.get("custom_track")
        if not voice_path or not os.path.exists(voice_path):
            await bot.send_message(chat_id, "❌ Голос потерялся."); return
        if custom_track:
            subliminal_path = await asyncio.to_thread(create_subliminal, voice_path, None, custom_track, data.get("length_minutes"), data.get("custom_solfeggio"), data.get("custom_binaural"), data.get("voice_offset", 0))
        elif data.get("chosen_track"):
            subliminal_path = await asyncio.to_thread(create_subliminal, voice_path, None, os.path.join("assets", data.get("category"), data.get("chosen_track")), data.get("length_minutes"), data.get("custom_solfeggio"), data.get("custom_binaural"), data.get("voice_offset", 0))
        else:
            subliminal_path = await asyncio.to_thread(create_subliminal, voice_path, data.get("category"), None, data.get("length_minutes"), data.get("custom_solfeggio"), data.get("custom_binaural"), data.get("voice_offset", 0))
        
        if subliminal_path and os.path.exists(subliminal_path):
            await bot.send_audio(chat_id=chat_id, audio=FSInputFile(subliminal_path), title=data.get("subliminal_name", "Твой саблиминал"), caption="🎧 Сделано в @SubliminalGenBot")
            log_generation(user_id, data.get("source", "unknown"))
            add_usage(user_id, data.get("requested_minutes", 0), data.get("is_custom_topic", False))
            if voice_path and os.path.exists(voice_path): os.remove(voice_path)
            if custom_track and os.path.exists(custom_track): os.remove(custom_track)
            
            # Сжигаем флаг бесплатного саба, если он был
            if data.get("is_free_subliminal"):
                mark_free_subliminal_used(user_id)
                logger.info(f"🎁 Бесплатный саб использован: user_id={user_id}")

            PENDING_PUBLICATIONS[user_id] = {"path": subliminal_path, "name": data.get("subliminal_name", "Твой саблиминал")}
            await bot.send_message(chat_id, "📢 <b>Хочешь опубликовать свой саблиминал в канале?</b>", parse_mode="HTML", reply_markup=publish_keyboard())
        else:
            await bot.send_message(chat_id, "❌ Не удалось собрать саблиминал.")
    except Exception as e:
        logger.error(f"❌ ОШИБКА ФОНОВОЙ ГЕНЕРАЦИИ: {e}")
        await bot.send_message(chat_id, f"❌ Ошибка: {e}")

@dp.callback_query(F.data == "publish_no")
async def handle_publish_no(call: types.CallbackQuery, state):
    pending = PENDING_PUBLICATIONS.pop(call.from_user.id, None)
    if pending and pending.get("path") and os.path.exists(pending["path"]): os.remove(pending["path"])
    await call.message.edit_text("Ок, не публикуем. Хочешь ещё один?")
    await call.answer()
    await state.clear()
    voice_id = get_voice_id(call.from_user.id)
    await call.message.answer("Хочешь ещё один? Выбери голос:", reply_markup=voices_keyboard_has_clone() if voice_id else voices_keyboard())
    await state.set_state(SubliminalStates.choosing_voice)

@dp.callback_query(F.data == "publish_yes")
async def handle_publish_yes(call: types.CallbackQuery, state):
    await call.message.edit_text("Как опубликовать?", reply_markup=publish_type_keyboard())
    await call.answer()

@dp.callback_query(F.data == "pub_anon")
async def handle_pub_anon(call: types.CallbackQuery, state):
    await publish_subliminal(call, state, anonymous=True)

@dp.callback_query(F.data == "pub_named")
async def handle_pub_named(call: types.CallbackQuery, state):
    await publish_subliminal(call, state, anonymous=False)

async def publish_subliminal(call: types.CallbackQuery, state, anonymous: bool):
    from config import CHANNEL_ID
    pending = PENDING_PUBLICATIONS.get(call.from_user.id)
    if not pending:
        await call.message.edit_text("❌ Файл не найден."); await call.answer(); return
    subliminal_path, subliminal_name = pending["path"], pending["name"]
    if not subliminal_path or not os.path.exists(subliminal_path):
        await call.message.edit_text("❌ Файл потерялся."); await call.answer(); PENDING_PUBLICATIONS.pop(call.from_user.id, None); return
    try:
        caption = f"🎧 {subliminal_name}\n\n🕶 Анонимно" if anonymous else (f"🎧 {subliminal_name}\n\n👤 @{call.from_user.username}" if call.from_user.username else f"🎧 {subliminal_name}\n\n👤 {call.from_user.full_name}")
        caption += "\n\n🤖 Сделано в @SubliminalGenBot"
        await bot.send_audio(chat_id=CHANNEL_ID, audio=FSInputFile(subliminal_path), title=subliminal_name, caption=caption)
        await call.message.edit_text("✅ Опубликовано в канале!")
        await call.answer()
    except Exception as e:
        print(f"Ошибка публикации: {e}")
        await call.message.edit_text("❌ Не удалось опубликовать.")
        await call.answer()
    if subliminal_path and os.path.exists(subliminal_path): os.remove(subliminal_path)
    PENDING_PUBLICATIONS.pop(call.from_user.id, None)
    await call.message.answer("Хочешь ещё один?", reply_markup=topics_keyboard())
    await state.set_state(SubliminalStates.waiting_for_topic)

@dp.callback_query(F.data == "back_to_publish")
async def back_to_publish(call: types.CallbackQuery, state):
    await call.message.edit_text("📢 Хочешь опубликовать свой саблиминал в канале?", reply_markup=publish_keyboard())
    await call.answer()

@dp.message(F.text.in_(["/feedback", "/отзыв", "/фидбек"]))
async def cmd_feedback(message: types.Message, state):
    await message.answer("💬 Отзыв, жалобы, предложения сюда -> @SubliminalReviews", parse_mode="HTML")

async def handle_yookassa_event(event: dict):
    try:
        event_type = event.get("event")
        payment_obj = event.get("object", {})
        if event_type != "payment.succeeded": return

        metadata = payment_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        payment_type = metadata.get("payment_type")
        if not user_id or not payment_type: return
        user_id = int(user_id)

        if payment_type == "donation":
            await bot.send_message(user_id, "💝 Спасибо за поддержку! Ты делаешь проект лучше.")
            await bot.send_message(ADMIN_ID, f"💝 Донат: user_id={user_id}")
        elif payment_type == "subliminal":
            from utils.db import get_pending_payment, clear_pending_payment
            pending = get_pending_payment(user_id)
            state = dp.fsm.get_context(bot=bot, chat_id=user_id, user_id=user_id)

            if pending == "custom_text":
                await bot.send_message(user_id, "✅ Оплата прошла! Теперь напиши свой текст для саблиминала:")
                await state.set_state(SubliminalStates.waiting_for_custom_text)
            elif pending == "custom_topic_payment":
                await bot.send_message(user_id, "✅ Оплата прошла! Теперь напиши свою тему:")
                await state.set_state(SubliminalStates.waiting_for_custom_topic)
            else:
                await bot.send_message(user_id, "✅ Оплата прошла! Теперь выбери тему саблиминала:", reply_markup=topics_keyboard())
                await state.set_state(SubliminalStates.waiting_for_topic)
            clear_pending_payment(user_id)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}")

if __name__ == "__main__":
    asyncio.run(main())