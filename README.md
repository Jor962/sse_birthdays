# 🎂 Telegram Birthday Bot

A small Telegram bot that tracks birthdays per chat, lets you look them up
on demand, and posts an automatic reminder when one is coming up (and on the day).

## Features

- `/addbirthday Name DD-MM [@username]` — add or update a birthday (year optional: `DD-MM-YYYY`); adding their `@username` lets the bot tag them directly in messages
- `/list` — show all saved birthdays, soonest first
- `/next` — show just the next upcoming birthday
- `/remove Name` — delete a saved birthday
- `/setlanguage en|ru` — switch this chat's birthday messages between English and Russian
- `/chatid` — show the current chat's ID (needed once, for admin setup below)
- A daily background check that:
  - Posts a warm birthday message (🎉 tagging @username if you saved one, several message variants so it's not always the same wording)
  - Posts a heads-up N days before (default 3, configurable)

## Admin workflow: load birthdays locally, skip in-chat entry

If you'd rather manage the birthday list yourself instead of having people
add their own via `/addbirthday`, you can load everything straight into the
database from a local file:

1. **Add the bot to your group** as normal (no need to configure anything first)
2. **Get the group's chat ID**: in the group, send `/chatid` — the bot replies
   with a number (often negative, e.g. `-1001234567890`)
3. **Edit `birthdays_local.py`**: paste that chat ID into `GROUP_CHAT_ID`, set
   your preferred `LANGUAGE` (`"en"` or `"ru"`), and fill in the `BIRTHDAYS` list
4. **Run it**: `python seed_db.py` — this loads everything straight into
   `birthdays.db`

Run `seed_db.py` again any time you edit the list — it updates existing
entries by name instead of duplicating them. Group members can still use
`/list`, `/next`, etc. — this just gives you a faster way to bulk-manage
the list yourself instead of typing `/addbirthday` for everyone one at a time.


Works in group chats or 1:1 DMs — birthdays are stored per chat.

## 1. Get a bot token

1. Open Telegram, message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the token it gives you

## 2. Run it locally

```bash
cd birthday-bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your BOT_TOKEN
python main.py
```

Then open Telegram, find your bot, and send `/start`.

## 3. Deploy to Railway (or similar)

1. Push this folder to a GitHub repo
2. On [railway.app](https://railway.app), create a new project → "Deploy from GitHub repo"
3. Add an environment variable `BOT_TOKEN` (and optionally `REMINDER_DAYS_BEFORE`,
   `DAILY_CHECK_HOUR_UTC`) in Railway's Variables tab
4. Railway will detect the `Procfile` and run `python main.py` as a worker

This uses polling (not webhooks), so no public URL or extra webhook config is needed —
it just needs to stay running, which Railway's worker process handles.

**Note on storage:** birthdays are saved in a local SQLite file (`birthdays.db`).
On most free hosts this resets on redeploy. If you want birthdays to persist
long-term on a platform like Railway, attach a persistent volume mounted at the
project folder, or swap `storage.py` to use Railway's Postgres addon instead —
happy to help with that swap when you're ready.

## Files

- `main.py` — bot commands + daily reminder job
- `storage.py` — SQLite persistence layer
- `birthdays_local.py` — edit this to define your group's chat ID and birthday list
- `seed_db.py` — run this to load `birthdays_local.py` into the database
- `requirements.txt` — dependencies
- `Procfile` — tells Railway/Heroku how to run the worker
- `.env.example` — copy to `.env` and fill in your token
