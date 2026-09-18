"""
Telegram Birthday Bot
----------------------
Commands:
  /start                              - welcome message
  /help                               - list commands
  /addbirthday Name DD-MM [@username] - add/update a birthday (year optional: DD-MM-YYYY)
  /list                               - show all birthdays in this chat, soonest first
  /next                               - show just the next upcoming birthday
  /remove Name                        - remove a birthday
  /setlanguage en|ru                  - set the language for this chat's birthday messages

Daily job (runs once every 24h):
  - Posts a message for anyone whose birthday is TODAY
  - Posts a heads-up for anyone whose birthday is in REMINDER_DAYS_BEFORE days
"""

import logging
import os
import random
from datetime import time as dtime, date

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import storage

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
REMINDER_DAYS_BEFORE = int(os.getenv("REMINDER_DAYS_BEFORE", "0"))
DAILY_CHECK_HOUR_UTC = int(os.getenv("DAILY_CHECK_HOUR_UTC", "5"))  # 9am UTC default
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")  # "en" or "ru"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ---------- message templates ----------

TODAY_TEMPLATES = {
    "en": [
        "🎉 Happy Birthday, {mention}! Wishing you a fantastic year ahead full of success and joy!",
        "🎂 It's {mention}'s birthday today! Wishing you health, happiness, and big wins ahead!",
        "🥳 Happy Birthday, {mention}! May this year bring you closer to all your goals!",
    ],
    "ru": [
        "🎉 С днём рождения, {mention}! Пусть ваш напор и целеустремлённость всегда ведут вас к победам!",
        "🎂 Сегодня день рождения у {mention}! Желаем крепкого здоровья, семейного уюта и больших успехов!",
        "🥳 Поздравляем с днём рождения, {mention}! Пусть этот год принесёт много ярких побед и приятных сюрпризов!",
    ],
}

REMINDER_TEMPLATES = {
    "en": [
        "📅 Heads up — {mention}'s birthday is in {days} days!",
        "📅 Don't forget: {mention}'s birthday is coming up in {days} days!",
    ],
    "ru": [
        "📅 Напоминание: день рождения {mention} через {days} дн.!",
        "📅 Не забудьте: скоро день рождения у {mention} — через {days} дн.!",
    ],
}


def mention_for(name: str, username: str | None) -> str:
    return f"@{username}" if username else name


# ---------- helpers ----------

def parse_add_args(args: list[str]):
    """
    Parse args for /addbirthday. Accepts, in any order among the trailing tokens:
      Name [Name...] DD-MM[-YYYY] [@username]
    Returns (name, day, month, year, username)
    """
    args = list(args)
    username = None
    for i, tok in enumerate(args):
        if tok.startswith("@"):
            username = args.pop(i).lstrip("@")
            break

    if len(args) < 2:
        raise ValueError("Need at least a name and a date")

    *name_parts, date_str = args
    name = " ".join(name_parts)

    parts = date_str.replace("/", "-").split("-")
    if len(parts) == 2:
        day, month = int(parts[0]), int(parts[1])
        year = None
    elif len(parts) == 3:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError("Date must be DD-MM or DD-MM-YYYY")

    date(2000 if not (month == 2 and day == 29) else 2000, month, day)  # validate
    return name, day, month, year, username


def format_birthday_line(name, day, month, year, username, today=None):
    days_left = storage.days_until_next_birthday(day, month, today)
    when = "🎉 TODAY!" if days_left == 0 else f"in {days_left} day{'s' if days_left != 1 else ''}"
    age_str = ""
    if year:
        next_year = date.today().year + (1 if days_left > 0 and (date.today().month, date.today().day) > (month, day) else 0)
        age_str = f" (turning {next_year - year})"
    return f"• {name} — {day:02d}/{month:02d}{age_str} — {when}"


# ---------- command handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎂 Hi! I'm your Birthday Bot.\n\n"
        "Add a birthday with:\n"
        "/addbirthday Alice 25-12\n"
        "Add a year and/or their @username too if you want:\n"
        "/addbirthday Alice 25-12-1990 @alice_tg\n\n"
        "Then try /list or /next.\n"
        "Use /setlanguage ru to switch birthday messages to Russian.\n"
        "Send /help to see everything I can do."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/addbirthday Name DD-MM(-YYYY) [@username] — add or update a birthday\n"
        "/list — show all birthdays, soonest first\n"
        "/next — show the next upcoming birthday\n"
        "/remove Name — delete a birthday\n"
        "/setlanguage en|ru — set the language for this chat's birthday messages\n"
        "/chatid — show this chat's ID (useful for admin setup)\n"
        f"\nI'll also post automatically here when it's someone's birthday, "
        f"and give a heads-up {REMINDER_DAYS_BEFORE} days before."
    )


async def add_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        name, day, month, year, username = parse_add_args(context.args)
    except ValueError:
        await update.message.reply_text(
            "Usage: /addbirthday Name DD-MM [@username]\n"
            "Examples:\n"
            "/addbirthday Alice 25-12\n"
            "/addbirthday Alice 25-12-1990 @alice_tg"
        )
        return

    storage.add_birthday(chat_id, name, day, month, year, username)
    handle = f" (@{username})" if username else ""
    await update.message.reply_text(
        f"Got it! 🎂 Saved {name}{handle}'s birthday as {day:02d}/{month:02d}"
        + (f"/{year}" if year else "") + "."
    )


TELEGRAM_MAX_MESSAGE_LEN = 4096


def chunk_lines(header: str, lines: list[str], limit: int = TELEGRAM_MAX_MESSAGE_LEN) -> list[str]:
    """Group lines into messages that each stay under Telegram's length limit."""
    chunks = []
    current = header
    for line in lines:
        candidate = current + "\n" + line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    chunks.append(current)
    return chunks


async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = storage.list_birthdays(chat_id)
    if not rows:
        await update.message.reply_text("No birthdays saved yet. Add one with /addbirthday.")
        return
    today = date.today()
    rows_sorted = sorted(rows, key=lambda r: storage.days_until_next_birthday(r[1], r[2], today))
    lines = [format_birthday_line(*r, today=today) for r in rows_sorted]
    for chunk in chunk_lines("🎂 Birthdays:", lines):
        await update.message.reply_text(chunk)


async def next_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = storage.list_birthdays(chat_id)
    if not rows:
        await update.message.reply_text("No birthdays saved yet. Add one with /addbirthday.")
        return
    today = date.today()
    row = min(rows, key=lambda r: storage.days_until_next_birthday(r[1], r[2], today))
    await update.message.reply_text(format_birthday_line(*row, today=today))


async def remove_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: /remove Name")
        return
    name = " ".join(context.args)
    removed = storage.remove_birthday(chat_id, name)
    if removed:
        await update.message.reply_text(f"Removed {name}'s birthday.")
    else:
        await update.message.reply_text(f"Couldn't find a birthday saved for '{name}'.")


async def chat_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"This chat's ID is: {update.effective_chat.id}")


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or context.args[0].lower() not in ("en", "ru"):
        await update.message.reply_text("Usage: /setlanguage en  or  /setlanguage ru")
        return
    lang = context.args[0].lower()
    storage.set_language(chat_id, lang)
    confirm = "Language set to English 🇬🇧" if lang == "en" else "Язык переключён на русский 🇷🇺"
    await update.message.reply_text(confirm)


# ---------- daily job ----------

async def daily_check(context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    for chat_id in storage.all_chat_ids():
        lang = storage.get_language(chat_id)
        if lang not in TODAY_TEMPLATES:
            lang = DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in TODAY_TEMPLATES else "en"
        for name, day, month, year, username in storage.list_birthdays(chat_id):
            days_left = storage.days_until_next_birthday(day, month, today)
            mention = mention_for(name, username)
            if days_left == 0:
                msg = random.choice(TODAY_TEMPLATES[lang]).format(mention=mention)
                await context.bot.send_message(chat_id=chat_id, text=msg)
            elif days_left == REMINDER_DAYS_BEFORE:
                msg = random.choice(REMINDER_TEMPLATES[lang]).format(mention=mention, days=days_left)
                await context.bot.send_message(chat_id=chat_id, text=msg)


# ---------- app setup ----------

def main():
    if not BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in your .env file (get one from @BotFather on Telegram).")

    storage.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("addbirthday", add_birthday))
    app.add_handler(CommandHandler("list", list_birthdays))
    app.add_handler(CommandHandler("next", next_birthday))
    app.add_handler(CommandHandler("remove", remove_birthday))
    app.add_handler(CommandHandler("setlanguage", set_language))
    app.add_handler(CommandHandler("chatid", chat_id_cmd))

    app.job_queue.run_daily(daily_check, time=dtime(hour=DAILY_CHECK_HOUR_UTC, minute=0))

    logger.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
