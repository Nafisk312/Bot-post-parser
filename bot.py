"""
Telegram Channel Parser (Userbot)
Собирает последние 20 постов с канала и сохраняет в JSON.

Запуск:
    python bot.py                        # спросит канал интерактивно
    python bot.py @durov                 # один канал
    python bot.py @durov t.me/python     # несколько каналов сразу

При первом запуске Telethon попросит номер телефона и код из SMS/приложения.
Сессия сохраняется в user_session.session — повторная авторизация не нужна.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

API_ID      = int(os.getenv("API_ID", "0"))
API_HASH    = os.getenv("API_HASH", "")
OUTPUT_DIR  = os.getenv("OUTPUT_DIR", "output")
POSTS_LIMIT = int(os.getenv("POSTS_LIMIT", "20"))

os.makedirs(OUTPUT_DIR, exist_ok=True)


def serialize_message(msg) -> dict:
    """Преобразует объект Message в сериализуемый словарь."""
    media_type = None
    if msg.media:
        if isinstance(msg.media, MessageMediaPhoto):
            media_type = "photo"
        elif isinstance(msg.media, MessageMediaDocument):
            mime = getattr(msg.media.document, "mime_type", "")
            if mime.startswith("video"):
                media_type = "video"
            elif mime.startswith("audio"):
                media_type = "audio"
            else:
                media_type = "document"

    return {
        "id":         msg.id,
        "date":       msg.date.isoformat() if msg.date else None,
        "text":       msg.text or "",
        "views":      msg.views,
        "forwards":   msg.forwards,
        "replies":    msg.replies.replies if msg.replies else 0,
        "media_type": media_type,
        "edit_date":  msg.edit_date.isoformat() if msg.edit_date else None,
        "grouped_id": msg.grouped_id,
    }


async def fetch_channel(client: TelegramClient, channel: str) -> str:
    """
    Загружает POSTS_LIMIT последних постов и сохраняет в JSON.
    Возвращает путь к сохранённому файлу.
    """
    logger.info(f"Получаю данные канала: {channel}")
    entity   = await client.get_entity(channel)
    messages = await client.get_messages(entity, limit=POSTS_LIMIT)

    posts = [serialize_message(m) for m in messages if m.text or m.media]

    channel_name = getattr(entity, "username", None) or getattr(entity, "title", channel)
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name    = channel_name.lstrip("@").replace("/", "_")
    filepath     = os.path.join(OUTPUT_DIR, f"{safe_name}_{timestamp}.json")

    payload = {
        "channel":     channel_name,
        "channel_id":  entity.id,
        "fetched_at":  datetime.now().isoformat(),
        "total_posts": len(posts),
        "posts":       posts,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info(f"Сохранено {len(posts)} постов → {filepath}")
    return filepath


async def main():
    if not API_ID or not API_HASH:
        print("Заполни .env: API_ID и API_HASH")
        print("Получи их на https://my.telegram.org -> API development tools")
        sys.exit(1)

    channels = sys.argv[1:]

    # Клиент от имени пользователя (не бота) — только так работает GetHistory
    async with TelegramClient("user_session", API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"Авторизован как: {me.first_name} (@{me.username})\n")

        if not channels:
            raw = input(
                f"Введи каналы через пробел (будут сохранены последние {POSTS_LIMIT} постов)\n"
                "Например: @durov t.me/python\n> "
            ).strip()
            channels = raw.split()

        if not channels:
            print("Не указан ни один канал.")
            return

        results = []
        for ch in channels:
            try:
                filepath = await fetch_channel(client, ch)
                print(f"OK  {ch}  ->  {filepath}")
                results.append({"channel": ch, "file": filepath, "ok": True})
            except ValueError as e:
                print(f"ERR {ch}  ->  канал не найден: {e}")
                results.append({"channel": ch, "error": str(e), "ok": False})
            except Exception as e:
                print(f"ERR {ch}  ->  ошибка: {e}")
                logger.exception(e)
                results.append({"channel": ch, "error": str(e), "ok": False})

        ok  = sum(1 for r in results if r["ok"])
        err = len(results) - ok
        print(f"\nИтого: {ok} успешно, {err} ошибок.")


if __name__ == "__main__":
    asyncio.run(main())