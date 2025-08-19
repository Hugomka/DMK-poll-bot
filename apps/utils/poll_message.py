#apps\utils\poll_message.py

import json
import os
import discord
from datetime import datetime
from zoneinfo import ZoneInfo
from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_settings import should_hide_counts

POLL_MESSAGE_FILE = os.getenv("POLL_MESSAGE_FILE", "poll_message.json")

def _load():
    if os.path.exists(POLL_MESSAGE_FILE):
        try:
            with open(POLL_MESSAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}

def _save(data):
    with open(POLL_MESSAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_message_id(channel_id, key, message_id):
    data = _load()
    data.setdefault("per_channel", {}).setdefault(str(channel_id), {})[key] = message_id
    _save(data)

def get_message_id(channel_id, key):
    data = _load()
    return data.get("per_channel", {}).get(str(channel_id), {}).get(key)

def clear_message_id(channel_id, key):
    data = _load()
    per = data.setdefault("per_channel", {}).setdefault(str(channel_id), {})
    per.pop(key, None)
    _save(data)

async def update_poll_message(channel, dag: str | None = None):
    """
    Update de 3 dag-berichten. Toont of verbergt aantallen per dag
    op basis van poll_settings.should_hide_counts(...).
    """
    keys = [dag] if dag else ["vrijdag", "zaterdag", "zondag"]
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))

    for d in keys:
        mid = get_message_id(channel.id, d)
        if not mid:
            continue
        try:
            msg = await channel.fetch_message(mid)

            # bepaal of aantallen verborgen moeten worden
            hide = should_hide_counts(channel.id, d, now)

            # ✨ Geef guild mee voor naamvermelding (indien actief)
            content = await build_poll_message_for_day_async(
                d,
                hide_counts=hide,
                guild=channel.guild
            )

            # publieke dag-berichten blijven knop-vrij
            await msg.edit(content=content, view=None)

        except discord.NotFound:
            clear_message_id(channel.id, d)
        except discord.HTTPException as e:
            if e.code == 30046:
                # "Too Many Requests (error code: 30046): Maximum number of edits to messages older than 1 hour reached."
                pass  # Stil negeren
            else:
                print(f"❌ Fout bij updaten voor {d}: {e}")
