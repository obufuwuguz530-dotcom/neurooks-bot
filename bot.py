import os
import json
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

from keywords import KEYWORDS

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = "@neirogide"
SEEN_USERS_FILE = "seen_users.json"
DELAY_MINUTES = 40

WELCOME_TEXT = (
    "Привет! Я Клодик — заведую канцелярией ИИ и выдаю полезные материалы. "
    "Лови свой подарок 🎁"
)

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


async def is_subscribed(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError:
        return False


async def send_content(message, keyword: str):
    link = KEYWORDS.get(keyword)
    if link:
        await message.reply_text(f"Держи материал 👉 {link}")
    else:
        await message.reply_text("Не знаю такого кодового слова.")


async def send_followup(bot, chat_id: int):
    await asyncio.sleep(DELAY_MINUTES * 60)
    await bot.send_message(
        chat_id=chat_id,
        text=FOLLOWUP_TEXT,
        reply_markup=FOLLOWUP_KEYBOARD
    )


def subscription_keyboard(keyword: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Подписаться на канал 👇", url="https://t.me/neirogide")],
        [InlineKeyboardButton("Я подписался ✅", callback_data=f"check_{keyword}")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user = update.effective_user

    if not args:
        await update.message.reply_text("Привет! Перейди по ссылке из Instagram, чтобы получить материал.")
        return

    keyword = args[0].lower()

    if keyword not in KEYWORDS:
        await update.message.reply_text("Не знаю такого кодового слова.")
        return

    is_first_visit = user.id not in seen_users

    if is_first_visit:
        await update.message.reply_text(WELCOME_TEXT)
        seen_users.add(user.id)
        save_seen_users(seen_users)

    if await is_subscribed(user.id, context.bot):
        await send_content(update.message, keyword)
        if is_first_visit:
            asyncio.create_task(send_followup(context.bot, update.effective_chat.id))
    else:
        await update.message.reply_text(
            "Чтобы получить материал — подпишись на канал и нажми кнопку ниже 👇",
            reply_markup=subscription_keyboard(keyword)
        )


async def check_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyword = query.data.replace("check_", "")
    user = query.from_user

    if await is_subscribed(user.id, context.bot):
        await query.message.delete()
        await send_content(query.message, keyword)
        asyncio.create_task(send_followup(context.bot, query.message.chat.id))
    else:
        await query.answer("Ты ещё не подписался на канал 😔", show_alert=True)


async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не задан в файле .env")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_button, pattern=r"^check_"))

    print("Бот запущен...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
