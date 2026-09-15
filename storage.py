"""
Simple SQLite storage for the Birthday Bot.
Each Telegram chat (group or DM) has its own independent list of birthdays.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date

DB_PATH = "birthdays.db"


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                day INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER,           -- optional, used to show age
                username TEXT,          -- optional, without the leading @
                UNIQUE(chat_id, name)
            )
            """
        )
        # migration for dbs created before the username column existed
        cols = [row[1] for row in conn.execute("PRAGMA table_info(birthdays)").fetchall()]
        if "username" not in cols:
            conn.execute("ALTER TABLE birthdays ADD COLUMN username TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'en'
            )
            """
        )


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_birthday(chat_id: int, name: str, day: int, month: int, year: int | None = None,
                  username: str | None = None):
    if username:
        username = username.lstrip("@")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO birthdays (chat_id, name, day, month, year, username)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, name) DO UPDATE SET
                day=excluded.day, month=excluded.month, year=excluded.year,
                username=excluded.username
            """,
            (chat_id, name, day, month, year, username),
        )


def get_language(chat_id: int) -> str:
    with _connect() as conn:
        row = conn.execute(
            "SELECT language FROM chat_settings WHERE chat_id=?", (chat_id,)
        ).fetchone()
    return row[0] if row else "en"


def set_language(chat_id: int, language: str):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_settings (chat_id, language) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET language=excluded.language
            """,
            (chat_id, language),
        )


def remove_birthday(chat_id: int, name: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM birthdays WHERE chat_id=? AND lower(name)=lower(?)",
            (chat_id, name),
        )
        return cur.rowcount > 0


def list_birthdays(chat_id: int):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT name, day, month, year, username FROM birthdays WHERE chat_id=?",
            (chat_id,),
        ).fetchall()
    return rows


def all_chat_ids():
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT chat_id FROM birthdays").fetchall()
    return [r[0] for r in rows]


def days_until_next_birthday(day: int, month: int, today: date | None = None) -> int:
    """Return number of days from today until the next occurrence of day/month."""
    today = today or date.today()
    year = today.year
    try:
        next_date = date(year, month, day)
    except ValueError:
        # handle Feb 29 on non-leap years by celebrating on Feb 28
        next_date = date(year, month, 28)
    if next_date < today:
        try:
            next_date = date(year + 1, month, day)
        except ValueError:
            next_date = date(year + 1, month, 28)
    return (next_date - today).days
