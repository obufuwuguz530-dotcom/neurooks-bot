import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

from keywords import KEYWORDS

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@neirogide"
OWNER_ID = 415652620
SEEN_USERS_FILE = "seen_users.json"
REPLIES_FILE = "replies_map.json"
DELAY_MINUTES = 40

WELCOME_INTRO = "Привет! Я Смартик — заведую канцелярией ИИ и выдаю полезные материалы."

WELCOME_LINES = {
    "omni":    "Хочешь инструкцию по Omni — отлично.",
    "kod":     "Хочешь инструкцию по установке Claude Code — то самое место.",
    "gaid":    "Хочешь инструкцию по установке Claude Code — то самое место.",
    "start":   "Хочешь инструкцию по установке Claude Code — то самое место.",
    "code":    "Хочешь инструкцию по установке Claude Code — то самое место.",
    "promts":  "Забираешь 7 промптов для бизнеса — держи.",
    "prof":    "Разбор 5 профессий 2027 — забирай.",
    "5":       "Разбор 5 профессий 2027 — забирай.",
    "montaj":  "Хочешь инструкцию по автомонтажу — сейчас всё будет.",
    "montage": "Хочешь инструкцию по автомонтажу — сейчас всё будет.",
    "claude":  "Хочешь гайд по Claude — держи.",
}

WELCOME_OUTRO = (
    "Материал лежит в моём канале — там я выкладываю все инструкции и разборы, "
    "чтобы они не терялись.\n\n"
    "Подпишись и жми кнопку ниже — открою доступ."
)


def build_welcome_text(keyword: str) -> str:
    parts = [WELCOME_INTRO]
    line = WELCOME_LINES.get(keyword)
    if line:
        parts.append(line)
    parts.append(WELCOME_OUTRO)
    return "\n\n".join(parts)

FOLLOWUP_TEXT = (
    "Кстати, пока ты тут 👀\n\n"
    "Гайд ты забрал. Но настроить доступ это только полдела. Дальше начинается вопрос: а что постить?\n\n"
    "Я собрала себе ИИ-сотрудника, который сам заходит к моим конкурентам в Instagram, Threads, YouTube и Telegram, "
    "смотрит, что у них залетает, и на основе этого пишет мне посты, хуки и сценарии Reels. Под каждую площадку отдельно.\n\n"
    "Я его не придумывала для курса. Я им работаю сама.\n\n"
    "За 3 дня соберём такого же тебе. Без кода, даже если ты не технарь."
)

FOLLOWUP_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Собрать ИИ-сотрудника", url="https://aiworkercont.vercel.app/")]
])

COURSE_URL = "https://aiworkercont.vercel.app/"

GUIDE_MENU_ITEMS = [
    ("kod",    "⚙️ Установка Claude Code с нуля"),
    ("montaj", "🎬 Автомонтаж: субтитры и биролы"),
    ("omni",   "🪄 Omni: меняю фон и одежду в видео"),
    ("prof",   "📈 5 профессий 2027 года"),
]

MATERIAL_INTROS = {
    "kod":     "Твоя инструкция по установке Claude Code",
    "gaid":    "Твоя инструкция по установке Claude Code",
    "start":   "Твоя инструкция по установке Claude Code",
    "code":    "Твоя инструкция по установке Claude Code",
    "montaj":  "Твоя инструкция по автомонтажу",
    "montage": "Твоя инструкция по автомонтажу",
    "omni":    "Твоя инструкция по Omni",
    "claude":  "Твой гайд по Claude",
    "prof":    "Твой разбор 5 профессий 2027",
    "5":       "Твой разбор 5 профессий 2027",
    "promts":  "Твои 7 промптов для бизнеса",
}

NO_PARAM_WELCOME = (
    "Привет! Я бот Оксаны Прохоровой.\n\n"
    "Оксана — экономист, не программист. Собирает ИИ-агентов и сервисы без кода "
    "и учит тому же. Спикер Сколково.\n\n"
    "Здесь лежат её бесплатные гайды. Выбирай, что тебе ближе:"
)

MORE_GUIDES_TEXT = "У меня есть ещё. Всё бесплатно, забирай что нужно:"

NOT_SUBSCRIBED_TEXT = (
    "Пока не вижу тебя в канале. Загляни туда, нажми «Присоединиться» "
    "и возвращайся — кнопка на месте."
)

CONTENT_TAIL = (
    "Сохрани пост в закладки, чтобы не искать. И попробуй на своём видео сегодня — "
    "пока горячо, иначе отложится на «потом» и не вернётся."
)

DAY_FOLLOWUP_HOURS = 24

MATERIAL_SHORT = {
    "kod":     "Claude Code",
    "gaid":    "Claude Code",
    "start":   "Claude Code",
    "code":    "Claude Code",
    "montaj":  "автомонтажа",
    "montage": "автомонтажа",
    "omni":    "Omni",
    "claude":  "Claude",
    "prof":    "разбора 5 профессий 2027",
    "5":       "разбора 5 профессий 2027",
    "promts":  "7 промптов",
}

DAY_FU_RESPONSES = {
    "ok":     "Круто! Скинь результат в личку @milakhweb — это ваши будущие отзывы 🙌",
    "stuck":  "Напиши мне лично @milakhweb — разберёмся, я через это сама прошла.",
    "notyet": "Оставь себе 15 минут вечером. Реально столько и нужно.",
}

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def load_seen_users() -> set:
    if os.path.exists(SEEN_USERS_FILE):
        with open(SEEN_USERS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_users(users: set):
    with open(SEEN_USERS_FILE, "w") as f:
        json.dump(list(users), f)


seen_users = load_seen_users()

# message_id сообщения владельцу → chat_id пользователя
def load_replies_map() -> dict:
    if os.path.exists(REPLIES_FILE):
        with open(REPLIES_FILE, "r") as f:
            return {int(k): int(v) for k, v in json.load(f).items()}
    return {}

def save_replies_map(m: dict):
    with open(REPLIES_FILE, "w") as f:
        json.dump(m, f)

replies_map = load_replies_map()


async def is_subscribed(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError:
        return False


async def notify_owner(bot, user, keyword: str, subscribed: bool, got_content: bool):
    username = f"@{user.username}" if user.username else f"{user.first_name} (id: {user.id})"
    now = datetime.now().strftime("%d %b, %H:%M")
    sub_icon = "✅" if subscribed else "❌"
    content_icon = "📎" if got_content else "⏳"

    text = (
        f"👤 {username}\n"
        f"📅 {now}\n"
        f"🔑 Кодовое слово: {keyword}\n"
        f"{sub_icon} Подписан на канал\n"
        f"{content_icon} Материал получил"
    )
    try:
        await bot.send_message(chat_id=OWNER_ID, text=text)
    except TelegramError:
        pass


def guides_menu_keyboard(callback_prefix: str, include_course: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{callback_prefix}_{k}")]
        for k, label in GUIDE_MENU_ITEMS
    ]
    if include_course:
        rows.append([InlineKeyboardButton("Мне интересен мини-курс", url=COURSE_URL)])
    return InlineKeyboardMarkup(rows)


def after_content_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Забрать ещё гайды", callback_data="more_guides")],
        [InlineKeyboardButton("Что за мини-курс?", url=COURSE_URL)],
    ])


async def send_content(message, keyword: str):
    link = KEYWORDS.get(keyword)
    if not link:
        await message.reply_text("Не знаю такого кодового слова.")
        return

    intro = MATERIAL_INTROS.get(keyword, "Твой материал")
    text = (
        f"Готово, доступ открыт 🔓\n\n"
        f"{intro}: {link}\n\n"
        f"{CONTENT_TAIL}"
    )
    await message.reply_text(text, reply_markup=after_content_keyboard())


async def send_followup(bot, chat_id: int):
    await asyncio.sleep(DELAY_MINUTES * 60)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=FOLLOWUP_TEXT,
            reply_markup=FOLLOWUP_KEYBOARD
        )
    except TelegramError:
        pass


def day_followup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Получилось", callback_data="fu_ok")],
        [InlineKeyboardButton("Застряла на установке", callback_data="fu_stuck")],
        [InlineKeyboardButton("Ещё не пробовала", callback_data="fu_notyet")],
    ])


async def send_day_followup(bot, chat_id: int, keyword: str):
    await asyncio.sleep(DAY_FOLLOWUP_HOURS * 3600)
    short = MATERIAL_SHORT.get(keyword, "материала")
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=f"Ну как, дошли руки до {short}? 🙂",
            reply_markup=day_followup_keyboard()
        )
    except TelegramError:
        pass


def subscription_keyboard(keyword: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Подписаться на канал 👇", url="https://t.me/neirogide")],
        [InlineKeyboardButton("Я подписался ✅", callback_data=f"check_{keyword}")],
    ])


def retry_check_keyboard(keyword: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Подписаться на канал 👇", url="https://t.me/neirogide")],
        [InlineKeyboardButton("Проверить снова", callback_data=f"check_{keyword}")],
    ])


async def deliver_or_prompt(message, user, keyword: str, bot, is_first_visit: bool):
    subscribed = await is_subscribed(user.id, bot)

    if subscribed:
        await send_content(message, keyword)
        await notify_owner(bot, user, keyword, subscribed=True, got_content=True)
        asyncio.create_task(send_day_followup(bot, message.chat.id, keyword))
        if is_first_visit:
            asyncio.create_task(send_followup(bot, message.chat.id))
    else:
        await message.reply_text(
            build_welcome_text(keyword),
            reply_markup=subscription_keyboard(keyword)
        )
        await notify_owner(bot, user, keyword, subscribed=False, got_content=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user = update.effective_user

    if not args:
        await update.message.reply_text(
            NO_PARAM_WELCOME,
            reply_markup=guides_menu_keyboard(callback_prefix="pick")
        )
        return

    keyword = args[0].lower()

    if keyword not in KEYWORDS:
        await update.message.reply_text("Не знаю такого кодового слова.")
        return

    is_first_visit = user.id not in seen_users
    if is_first_visit:
        seen_users.add(user.id)
        save_seen_users(seen_users)

    await deliver_or_prompt(update.message, user, keyword, context.bot, is_first_visit)


async def pick_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyword = query.data.replace("pick_", "")
    if keyword not in KEYWORDS:
        return

    user = query.from_user
    is_first_visit = user.id not in seen_users
    if is_first_visit:
        seen_users.add(user.id)
        save_seen_users(seen_users)

    await deliver_or_prompt(query.message, user, keyword, context.bot, is_first_visit)


async def check_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyword = query.data.replace("check_", "")
    user = query.from_user

    if await is_subscribed(user.id, context.bot):
        try:
            await query.message.delete()
        except TelegramError:
            pass
        await send_content(query.message, keyword)
        await notify_owner(context.bot, user, keyword, subscribed=True, got_content=True)
        asyncio.create_task(send_day_followup(context.bot, query.message.chat.id, keyword))
        asyncio.create_task(send_followup(context.bot, query.message.chat.id))
    else:
        try:
            await query.edit_message_text(
                NOT_SUBSCRIBED_TEXT,
                reply_markup=retry_check_keyboard(keyword)
            )
        except TelegramError:
            await query.message.reply_text(
                NOT_SUBSCRIBED_TEXT,
                reply_markup=retry_check_keyboard(keyword)
            )


async def more_guides_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        MORE_GUIDES_TEXT,
        reply_markup=guides_menu_keyboard(callback_prefix="guide", include_course=True)
    )


async def guide_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyword = query.data.replace("guide_", "")
    link = KEYWORDS.get(keyword)
    if not link:
        return

    await query.message.reply_text(
        f"Держи: {link}\n\nЗабирай ещё, если что-то приглянулось 👆"
    )
    await notify_owner(context.bot, query.from_user, keyword, subscribed=True, got_content=True)
    asyncio.create_task(send_day_followup(context.bot, query.message.chat.id, keyword))


async def day_followup_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data.replace("fu_", "")
    response = DAY_FU_RESPONSES.get(action)
    if not response:
        return

    await query.message.reply_text(response)


async def forward_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Если пишет владелец — проверяем, не ответ ли это на чужое сообщение
    if user.id == OWNER_ID:
        reply = update.message.reply_to_message
        if reply and reply.message_id in replies_map:
            user_chat_id = replies_map[reply.message_id]
            try:
                await context.bot.send_message(chat_id=user_chat_id, text=update.message.text)
                await update.message.reply_text("✅ Ответ отправлен")
            except TelegramError:
                await update.message.reply_text("❌ Не удалось отправить ответ")
        return

    username = f"@{user.username}" if user.username else f"{user.first_name} (id: {user.id})"
    text = f"💬 Сообщение от {username}:\n\n{update.message.text}\n\n_(Ответь на это сообщение, чтобы написать пользователю)_"
    try:
        sent = await context.bot.send_message(chat_id=OWNER_ID, text=text, parse_mode="Markdown")
        replies_map[sent.message_id] = update.effective_chat.id
        save_replies_map(replies_map)
    except TelegramError:
        pass


async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не задан в файле .env")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_button, pattern=r"^check_"))
    app.add_handler(CallbackQueryHandler(pick_button, pattern=r"^pick_"))
    app.add_handler(CallbackQueryHandler(more_guides_button, pattern=r"^more_guides$"))
    app.add_handler(CallbackQueryHandler(guide_button, pattern=r"^guide_"))
    app.add_handler(CallbackQueryHandler(day_followup_button, pattern=r"^fu_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_owner))

    print("Бот запущен...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
