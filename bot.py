import os
import json
import time
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
# На Amvera постоянный диск смонтирован в /data — файлы там переживают перезапуск
DATA_DIR = os.getenv("DATA_DIR") or ("/data" if os.path.isdir("/data") else ".")
SEEN_USERS_FILE = os.path.join(DATA_DIR, "seen_users.json")
REPLIES_FILE = os.path.join(DATA_DIR, "replies_map.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending_followups.json")
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
    "analiz":  "Хочешь инструкцию по анализу — сейчас всё будет.",
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
    ("claude", "🤖 Гайд по Claude"),
    ("analiz", "🔍 Инструкция по анализу"),
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
    "analiz":  "Твоя инструкция по анализу",
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
    "analiz":  "анализа",
}

DAY_FOLLOWUP_TEXT = (
    "Привет! Ты вчера забирал(а) у меня гайд 🙂\n\n"
    "Всё понятно? Если остались вопросы — я на связи 👇"
)

DAY_FU_RESPONSES = {
    "ok":     "Круто, рада, что пригодилось 🙌\n\nЕсли не сложно — напиши пару слов или скинь результат прямо сюда, мне будет очень приятно.",
    "ask":    "Напиши свой вопрос прямо сюда, одним сообщением — передам Оксане, ответ придёт в этот чат.",
    "notyet": "Ничего страшного, гайд никуда не денется 🙂\n\nКогда дойдут руки и появятся вопросы — пиши сюда, я на связи.",
}

DAY_FU_LABELS = {
    "ok":     "Всё получилось 🙌",
    "ask":    "Есть вопрос",
    "notyet": "Ещё не успел(а)",
}

SERVICE_KEYWORDS = {
    "oplata": {
        "text": "Лови ссылку на сервис 👇",
        "button_label": "Ловлю",
        "button_url": "https://t.me/zarub_robot?start=ref_NNimMH",
    },
    "platforma": {
        "text": "Лови ссылку на платформу 👇",
        "button_label": "Открыть",
        "button_url": "https://clck.ru/3V4hGJ",
    },
}

KEYWORD_ALIASES = {
    "омни":         "omni",
    "код":          "kod",
    "клод":         "claude",
    "клауд":        "claude",
    "клауде":       "claude",
    "монтаж":       "montaj",
    "автомонтаж":   "montaj",
    "профессии":    "prof",
    "5 профессий":  "prof",
    "промпты":      "promts",
    "промты":       "promts",
    "оплата":       "oplata",
    "платформа":    "platforma",
    "анализ":       "analiz",
}


UNKNOWN_KEYWORD_TEXT = (
    "Не узнала слово. Могу выдать материал — напиши: "
    "омни, код, монтаж, клод, профессии, анализ, оплата или платформа.\n\n"
    "Или напиши что-то своё — передам Оксане."
)


def resolve_keyword(text: str) -> str | None:
    normalized = text.strip().strip(".,!?").lower()
    if not normalized:
        return None
    if normalized in KEYWORDS or normalized in SERVICE_KEYWORDS:
        return normalized
    return KEYWORD_ALIASES.get(normalized)

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


async def send_service(message, keyword: str):
    cfg = SERVICE_KEYWORDS[keyword]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(cfg["button_label"], url=cfg["button_url"])]
    ])
    await message.reply_text(cfg["text"], reply_markup=kb)


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


# Отложенные сообщения хранятся в файле: {"<chat_id>": {"course": ts, "day": ts}}
def load_pending() -> dict:
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    return {}


def save_pending(p: dict):
    with open(PENDING_FILE, "w") as f:
        json.dump(p, f)


pending = load_pending()


def schedule(chat_id: int, kind: str, delay_seconds: int):
    """Ставит отложенное сообщение. Если такое уже ждёт отправки — не дублирует."""
    key = str(chat_id)
    entry = pending.setdefault(key, {})
    if kind in entry:
        return
    entry[kind] = time.time() + delay_seconds
    save_pending(pending)


def schedule_after_content(chat_id: int, with_course: bool):
    schedule(chat_id, "day", DAY_FOLLOWUP_HOURS * 3600)
    if with_course:
        schedule(chat_id, "course", DELAY_MINUTES * 60)


def day_followup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(DAY_FU_LABELS[k], callback_data=f"fu_{k}")]
        for k in ("ok", "ask", "notyet")
    ])


async def send_scheduled(bot, chat_id: int, kind: str):
    if kind == "course":
        await bot.send_message(chat_id=chat_id, text=FOLLOWUP_TEXT, reply_markup=FOLLOWUP_KEYBOARD)
    elif kind == "day":
        await bot.send_message(chat_id=chat_id, text=DAY_FOLLOWUP_TEXT, reply_markup=day_followup_keyboard())


async def followup_loop(bot):
    while True:
        now = time.time()
        changed = False
        for key in list(pending.keys()):
            entry = pending[key]
            for kind in list(entry.keys()):
                if entry[kind] <= now:
                    try:
                        await send_scheduled(bot, int(key), kind)
                    except TelegramError as e:
                        logging.warning("Не удалось отправить %s для %s: %s", kind, key, e)
                    del entry[kind]
                    changed = True
            if not entry:
                del pending[key]
        if changed:
            save_pending(pending)
        await asyncio.sleep(60)


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
        schedule_after_content(message.chat.id, with_course=is_first_visit)
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

    if keyword in SERVICE_KEYWORDS:
        await send_service(update.message, keyword)
        await notify_owner(context.bot, user, keyword, subscribed=True, got_content=True)
        return

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
        schedule_after_content(query.message.chat.id, with_course=True)
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
    schedule_after_content(query.message.chat.id, with_course=False)


async def day_followup_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data.replace("fu_", "")
    response = DAY_FU_RESPONSES.get(action)
    if not response:
        return

    await query.message.reply_text(response)

    user = query.from_user
    if action in ("ok", "ask"):
        # следующее сообщение человека уйдёт Оксане без ответа «не узнала слово»
        context.user_data["awaiting_owner_msg"] = action

    username = f"@{user.username}" if user.username else f"{user.first_name} (id: {user.id})"
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"🔔 {username} ответил(а) на напоминание: «{DAY_FU_LABELS[action]}»"
        )
    except TelegramError:
        pass


async def forward_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Если пишет владелец и это ответ на пересланное сообщение — отправляем ответ пользователю
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

    keyword = resolve_keyword(update.message.text or "")
    if keyword:
        if keyword in SERVICE_KEYWORDS:
            await send_service(update.message, keyword)
            await notify_owner(context.bot, user, keyword, subscribed=True, got_content=True)
            return
        is_first_visit = user.id not in seen_users
        if is_first_visit:
            seen_users.add(user.id)
            save_seen_users(seen_users)
        await deliver_or_prompt(update.message, user, keyword, context.bot, is_first_visit)
        return

    if user.id == OWNER_ID:
        return

    awaiting = context.user_data.pop("awaiting_owner_msg", None)
    if awaiting:
        await update.message.reply_text("Передала Оксане ✅ Ответ придёт сюда.")
        header = "❓ Вопрос" if awaiting == "ask" else "💌 Отзыв"
    else:
        await update.message.reply_text(UNKNOWN_KEYWORD_TEXT)
        header = "💬 Сообщение"

    username = f"@{user.username}" if user.username else f"{user.first_name} (id: {user.id})"
    text = f"{header} от {username}:\n\n{update.message.text}\n\n(Ответь на это сообщение реплаем — ответ уйдёт человеку)"
    try:
        sent = await context.bot.send_message(chat_id=OWNER_ID, text=text)
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
        asyncio.create_task(followup_loop(app.bot))
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
