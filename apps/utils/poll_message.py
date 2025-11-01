# apps/utils/poll_message.py

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from apps.logic.decision import build_decision_line
from apps.utils.discord_client import fetch_message_or_none, safe_call
from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_settings import is_paused, should_hide_counts
from apps.utils.poll_storage import update_non_voters

POLL_MESSAGE_FILE = os.getenv("POLL_MESSAGE_FILE", "poll_message.json")

# Interne locks & pending-taken om dubbele updates te voorkomen
_update_locks: dict[tuple[int, str], asyncio.Lock] = {}
_pending_tasks: dict[tuple[int, str], asyncio.Task] = {}


def is_channel_disabled(channel_id: int) -> bool:
    """
    Controleer of dit kanaal uitgeschakeld is voor polls.

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
    """
    Zet of verwijder de uitgeschakelde status voor een kanaal.

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
        except json.JSONDecodeError:  # pragma: no cover
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


async def create_notification_message(channel: Any) -> Optional[Any]:
    """
    Creëer een vriendelijk notificatiebericht wanneer de bot wordt aangezet.

    Note: This is a persistent notification that should remain visible.
    Uses 'notification_persistent' key to avoid conflicts with temporary notifications.

    Returns:
        Het aangemaakte bericht, of None bij fout.
    """
    content = ":mega: Notificatie:\nDe DMK-poll-bot is zojuist aangezet. Veel plezier met de stemmen! 🎮"
    send = getattr(channel, "send", None)
    if send is None:
        return None
    try:
        msg = await safe_call(send, content=content, view=None)
        if msg is not None:
            cid = int(getattr(channel, "id", 0))
            # Use persistent key since this is a bot activation message that should stay
            save_message_id(cid, "notification_persistent", msg.id)
        return msg
    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij aanmaken notificatiebericht: {e}")
        return None


async def update_notification_message(
    channel: Any,
    mentions: str = "",
    text: str = "",
    show_button: bool = False,
    dag: str = "",
    leading_time: str = "",
) -> None:
    """
    Update het notificatiebericht met mentions, text, en optioneel een knop.

    Args:
        channel: Het Discord kanaal object
        mentions: Mentions (lijn 2), bijv. "@user1 @user2"
        text: De tekst (lijn 3+)
        show_button: Of de "Stem nu" knop getoond moet worden
        dag: De dag voor de Stem Nu knop (vereis als show_button=True)
        leading_time: De leidende tijd (19:00 of 20:30) voor de knop
    """
    cid = int(getattr(channel, "id", 0))
    mid = get_message_id(cid, "notification")

    if not mid:
        return

    msg = await fetch_message_or_none(channel, mid)
    if msg is None:
        return

    # Build content
    content = ":mega: Notificatie:\n"
    content += f"{mentions}\n" if mentions else "\n"
    content += f"{text}" if text else ""

    # Add Stem Nu button if requested
    view = None
    if show_button and dag and leading_time:
        from apps.ui.stem_nu_button import create_stem_nu_view

        view = create_stem_nu_view(dag, leading_time)

    try:
        await safe_call(msg.edit, content=content, view=view)
    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij updaten notificatiebericht: {e}")


async def clear_notification_mentions(channel: Any) -> None:
    """
    Verwijder mentions uit het notificatiebericht (lijn 2 leegmaken).
    """
    await update_notification_message(channel, mentions="", text="", show_button=False)


def schedule_poll_update(channel: Any, dag: str, delay: float = 0.3) -> asyncio.Task:
    """
    Plan een update voor (kanaal, dag) op de achtergrond met kleine debounce.

    - Als er al een pending taak bestaat voor dezelfde key, vervangen we die (reset de debounce).
    - Retourneert de asyncio.Task, zodat een aanroeper eventueel kan awaiten in batch (scheduler).
    """
    cid = int(getattr(channel, "id", 0))
    key = (cid, dag)

    # Als er al een pending taak is, annuleer die (debounce)
    old = _pending_tasks.get(key)
    if old is not None and not old.done():
        old.cancel()

    async def _runner():
        try:
            if delay and delay > 0:
                await asyncio.sleep(delay)
            await update_poll_message(channel, dag)
        except asyncio.CancelledError:  # pragma: no cover
            # Debounced; niets aan de hand
            return

    task = asyncio.create_task(_runner())
    _pending_tasks[key] = task
    return task


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
        # Per (kanaal, dag) lock om overlap te voorkomen
        lock_key = (int(cid_val), d)
        lock = _update_locks.get(lock_key)
        if lock is None:
            lock = _update_locks[lock_key] = asyncio.Lock()

        async with lock:
            mid = get_message_id(cid_val, d)

            # Update non-voters in storage before building the message
            await update_non_voters(gid_val, cid_val, channel)

            # Bepaal content (zowel voor edit als create)
            hide = should_hide_counts(cid_val, d, now)
            paused = is_paused(cid_val)
            content = await build_poll_message_for_day_async(
                d,
                guild_id=gid_val,
                channel_id=cid_val,
                hide_counts=hide,
                pauze=paused,
                guild=getattr(channel, "guild", None),  # Voor namen
                channel=channel,  # Voor niet-stemmers tracking
            )

            decision = await build_decision_line(gid_val, cid_val, d, now)
            if decision:
                content = content.rstrip() + ":arrow_up: " + decision + "\n\u200b"

            if mid:
                msg = await fetch_message_or_none(channel, mid)
                if msg is not None:
                    await safe_call(msg.edit, content=content, view=None)
                    continue
                else:
                    # Bestond niet meer of niet op te halen → id opruimen en daarna aanmaken
                    clear_message_id(cid_val, d)

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
