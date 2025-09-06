# apps/utils/poll_message.py

import json
import os
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import discord

from apps.logic.decision import build_decision_line
from apps.utils.discord_client import safe_call
from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_settings import should_hide_counts

POLL_MESSAGE_FILE = os.getenv("POLL_MESSAGE_FILE", "poll_message.json")


def is_channel_disabled(channel_id: int) -> bool:
    """Controleer of dit kanaal uitgeschakeld is voor polls.

    We gebruiken strings als keys, net zoals bij per_channel.
    Als het kanaal in de lijst staat, worden polls niet opnieuw aangemaakt.

    Args:
        channel_id: Het numerieke ID van het kanaal.

    Returns:
        True als het kanaal uitgeschakeld is, anders False.
    """
    data = _load()
    disabled = data.get("disabled_channels", [])
    # Ondersteun zowel string- als int-representaties in de lijst
    cid_str = str(channel_id)
    return cid_str in disabled or channel_id in disabled


def set_channel_disabled(channel_id: int, disabled: bool) -> None:
    """Zet of verwijder de uitgeschakelde status voor een kanaal.

    Wanneer `disabled` True is, voegen we het kanaal toe aan de lijst.
    Wanneer `disabled` False is, verwijderen we het kanaal uit de lijst.
    De lijst wordt opgeslagen in hetzelfde JSON-bestand als de berichten-IDs.

    Args:
        channel_id: Het numerieke ID van het kanaal.
        disabled: True om uit te schakelen, False om weer in te schakelen.
    """
    data = _load()
    disabled_channels = data.get("disabled_channels", [])
    cid_str = str(channel_id)
    # Normaliseer naar strings voor opslag
    if disabled:
        if cid_str not in disabled_channels:
            disabled_channels.append(cid_str)
    else:
        # Verwijder zowel string- als int-representaties als ze bestaan
        disabled_channels = [
            c for c in disabled_channels if c != cid_str and c != channel_id
        ]
    data["disabled_channels"] = disabled_channels
    _save(data)


def _load() -> dict[str, Any]:
    if os.path.exists(POLL_MESSAGE_FILE):
        try:
            with open(POLL_MESSAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def _save(data: dict[str, Any]) -> None:
    with open(POLL_MESSAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_message_id(channel_id: int, key: str, message_id: int) -> None:
    data = _load()
    data.setdefault("per_channel", {}).setdefault(str(channel_id), {})[key] = message_id
    _save(data)


def get_message_id(channel_id: int, key: str) -> Optional[int]:
    data = _load()
    return data.get("per_channel", {}).get(str(channel_id), {}).get(key)


def clear_message_id(channel_id: int, key: str) -> None:
    data = _load()
    per = data.setdefault("per_channel", {}).setdefault(str(channel_id), {})
    per.pop(key, None)
    _save(data)


async def update_poll_message(channel: Any, dag: str | None = None) -> None:
    """
    Update (of maak aan) de dag-berichten.
    Toont/verbergt aantallen per dag via should_hide_counts(...).
    Als er geen message_id is of het bericht bestaat niet meer,
    wordt het bericht opnieuw aangemaakt en opgeslagen.
    """
    keys = [dag] if dag else ["vrijdag", "zaterdag", "zondag"]
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    guild_obj = getattr(channel, "guild", None)
    gid_val: int | str = int(getattr(guild_obj, "id", 0))
    cid_val: int | str = int(getattr(channel, "id", 0))

    # Als dit kanaal uitgeschakeld is (via /dmk-poll-verwijderen), niets doen.
    if is_channel_disabled(cid_val):
        return

    for d in keys:
        mid = get_message_id(cid_val, d)

        # Bepaal content (zowel voor edit als create)
        hide = should_hide_counts(cid_val, d, now)
        content = await build_poll_message_for_day_async(
            d,
            guild_id=gid_val,
            channel_id=cid_val,
            hide_counts=hide,
            guild=getattr(channel, "guild", None),  # voor namen
        )

        decision = await build_decision_line(gid_val, cid_val, d, now)
        if decision:
            content = content.rstrip() + "\n\n" + decision

        if mid:
            try:
                # Probeer te editen als het bericht bestaat
                fetch = getattr(channel, "fetch_message", None)
                msg = await safe_call(fetch, mid) if fetch else None
                if msg is not None:
                    await safe_call(msg.edit, content=content, view=None)
                    continue  # klaar voor deze dag
                else:
                    # Bestond niet meer of niet op te halen → id opruimen en daarna aanmaken
                    clear_message_id(cid_val, d)
            except discord.NotFound:
                # Bestond niet meer → id opruimen en hierna aanmaken
                clear_message_id(cid_val, d)
            except discord.HTTPException as e:
                if getattr(e, "code", None) == 30046:
                    # Maximum edits voor oud bericht → niets doen (stil negeren)
                    continue
                else:
                    print(f"❌ Fout bij updaten voor {d}: {e}")
                    continue  # geen create proberen in dit pad

        # Create-pad: geen mid óf net opgeschoond na NotFound → nieuw sturen
        try:
            send = getattr(channel, "send", None)
            new_msg = (
                await safe_call(send, content=content, view=None) if send else None
            )
            if new_msg is not None:
                save_message_id(cid_val, d, new_msg.id)
        except Exception as e:  # pragma: no cover
            print(f"❌ Fout bij aanmaken bericht voor {d}: {e}")
