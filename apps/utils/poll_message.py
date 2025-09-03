#apps\utils\poll_message.py

import json
import os
import discord
from datetime import datetime
from zoneinfo import ZoneInfo
from apps.logic.decision import build_decision_line
from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_settings import should_hide_counts
from apps.utils.discord_client import safe_call

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
    Update (of maak aan) de dag-berichten.
    Toont/verbergt aantallen per dag via should_hide_counts(...).
    Als er geen message_id is of het bericht bestaat niet meer,
    wordt het bericht opnieuw aangemaakt en opgeslagen.
    """
    keys = [dag] if dag else ["vrijdag", "zaterdag", "zondag"]
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))

    for d in keys:
        mid = get_message_id(channel.id, d)

        # Bepaal content (zowel voor edit als create)
        hide = should_hide_counts(channel.id, d, now)
        content = await build_poll_message_for_day_async(
            d,
            hide_counts=hide,
            guild=channel.guild,  # voor namen
        )

        decision = await build_decision_line(channel.id, d, now)
        if decision:
            content = content.rstrip() + "\n\n" + decision

        if mid:
            try:
                # Probeer te editen als het bericht bestaat
                msg = await safe_call(channel.fetch_message, mid)
                await safe_call(msg.edit, content=content, view=None)
                continue  # klaar voor deze dag
            except discord.NotFound:
                # Bestond niet meer → id opruimen en hierna aanmaken
                clear_message_id(channel.id, d)
            except discord.HTTPException as e:
                if getattr(e, "code", None) == 30046:
                    # Maximum edits voor oud bericht → niets doen (stil negeren)
                    continue
                else:
                    print(f"❌ Fout bij updaten voor {d}: {e}")
                    continue  # geen create proberen in dit pad

        # Create-pad: geen mid óf net opgeschoond na NotFound → nieuw sturen
        try:
            new_msg = await safe_call(channel.send, content=content, view=None)
            save_message_id(channel.id, d, new_msg.id)
        except Exception as e:
            print(f"❌ Fout bij aanmaken bericht voor {d}: {e}")
