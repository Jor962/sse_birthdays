"""
Run this locally to load the birthdays defined in birthdays_local.py into the bot's database.

Usage:
    python seed_db.py

Safe to run multiple times — existing entries (matched by name, within the same
chat) get updated rather than duplicated.
"""

import storage
from birthdays_local import GROUP_CHAT_ID, LANGUAGE, BIRTHDAYS


def main():
    storage.init_db()
    storage.set_language(GROUP_CHAT_ID, LANGUAGE)

    for b in BIRTHDAYS:
        storage.add_birthday(
            chat_id=GROUP_CHAT_ID,
            name=b["name"],
            day=b["day"],
            month=b["month"],
            year=b.get("year"),
            username=b.get("username"),
        )

    print(f"Loaded {len(BIRTHDAYS)} birthday(s) into chat {GROUP_CHAT_ID} (language: {LANGUAGE}).")
    print("Current list:")
    for row in storage.list_birthdays(GROUP_CHAT_ID):
        print(" -", row)


if __name__ == "__main__":
    main()
