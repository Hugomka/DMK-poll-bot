# apps/utils/mention_utils.py
#
# Helpers voor privacy-vriendelijke mentions in notificaties.
# - Tijdelijke mentions (5 seconden zichtbaar, dan auto-delete na 1 uur)
# - Persistente mentions (auto-delete na 5 uur)

import asyncio
from typing import Any, Optional

from apps.utils.discord_client import safe_call
from apps.utils.poll_message import get_message_id, save_message_id


async def send_temporary_mention(
    channel: Any,
    mentions: str,
    text: str,
    delay: float = 5.0,
    show_button: bool = False,
    dag: str = "",
    leading_time: str = "",
    delete_after_hours: float = 1.0,
) -> None:
    """
    Stuur een nieuwe notificatie met mentions die gebruikers pingt.

    Flow:
    1. Verwijder vorige notificatiebericht (indien aanwezig)
    2. Stuur nieuw bericht met mentions en optionele knop
    3. Na 5 seconden: verwijder mentions (privacy)
    4. Na delete_after_hours: verwijder het hele bericht

    Args:
        channel: Het Discord kanaal object
        mentions: Mentions string, bijv. "@user1, @user2"
        text: De tekst die onder de mentions verschijnt
        delay: Hoeveel seconden de mentions zichtbaar blijven (standaard 5.0)
        show_button: Of de "Stem nu" knop getoond moet worden
        dag: De dag voor de Stem Nu knop
        leading_time: De leidende tijd voor de Stem Nu knop
        delete_after_hours: Na hoeveel uur het bericht verwijderd wordt (standaard 1.0)
    """
    # Stap 1: Verwijder vorig notificatiebericht
    cid = getattr(channel, "id", 0)
    old_msg_id = get_message_id(cid, "notification")
    if old_msg_id:
        try:
            from apps.utils.discord_client import fetch_message_or_none

            old_msg = await fetch_message_or_none(channel, old_msg_id)
            if old_msg is not None:
                await safe_call(old_msg.delete)
        except Exception:
            pass  # Bericht bestaat niet meer

    # Stap 2: Stuur nieuw bericht
    send_func = getattr(channel, "send", None)
    if send_func is None:
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
        msg = await safe_call(send_func, content=content, view=view)
        if msg is None:
            return

        # Sla nieuwe message ID op
        save_message_id(cid, "notification", msg.id)

        # Stap 3: Plan privacy removal (na 5 seconden)
        asyncio.create_task(
            _remove_mentions_after_delay(msg, delay, text, view, show_button)
        )

        # Stap 4: Plan auto-delete (na delete_after_hours)
        delete_seconds = delete_after_hours * 3600
        asyncio.create_task(_delete_message_after_delay(msg, delete_seconds, cid))

    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij versturen temporary mention: {e}")


async def _remove_mentions_after_delay(
    message: Any, delay: float, text: str, view: Any, show_button: bool
) -> None:
    """
    Interne helper: verwijder mentions na delay seconden, behoud tekst en knop.

    Args:
        message: Het Discord message object
        delay: Hoeveel seconden te wachten
        text: De tekst om te behouden
        view: De view om te behouden (bijv. Stem Nu knop)
        show_button: Of de knop getoond moet blijven
    """
    try:
        await asyncio.sleep(delay)

        # Build content zonder mentions
        content = ":mega: Notificatie:\n\n"
        content += f"{text}" if text else ""

        # Edit het bericht: verwijder mentions, behoud tekst en knop
        if hasattr(message, "edit"):
            await safe_call(message.edit, content=content, view=view if show_button else None)
    except Exception:  # pragma: no cover
        # Stil falen (bericht kan verwijderd zijn, bot heeft geen rechten, etc.)
        pass


async def _delete_message_after_delay(message: Any, delay_seconds: float, channel_id: int) -> None:
    """
    Interne helper: verwijder een bericht na delay_seconds en clear de message ID.

    Args:
        message: Het Discord message object
        delay_seconds: Hoeveel seconden te wachten
        channel_id: Het kanaal ID (voor het opschonen van de message ID)
    """
    try:
        await asyncio.sleep(delay_seconds)

        # Verwijder het bericht
        if hasattr(message, "delete"):
            await safe_call(message.delete)

        # Clear de opgeslagen message ID
        from apps.utils.poll_message import clear_message_id

        clear_message_id(channel_id, "notification")
    except Exception:  # pragma: no cover
        # Stil falen (bericht kan al verwijderd zijn, bot heeft geen rechten, etc.)
        pass


async def send_persistent_mention(channel: Any, message: str) -> Optional[Any]:
    """
    Stuur een "doorgaan" notificatie met mentions die na 5 uur verwijderd wordt.

    Flow:
    1. Verwijder vorige notificatiebericht
    2. Stuur nieuw bericht met mentions
    3. Na 5 seconden: verwijder mentions (privacy)
    4. Na 5 uur: verwijder het hele bericht

    Args:
        channel: Het Discord kanaal object
        message: Het volledige bericht inclusief mentions

    Returns:
        Het verzonden bericht object, of None bij fout
    """
    # Stap 1: Verwijder vorig notificatiebericht
    cid = getattr(channel, "id", 0)
    old_msg_id = get_message_id(cid, "notification")
    if old_msg_id:
        try:
            from apps.utils.discord_client import fetch_message_or_none

            old_msg = await fetch_message_or_none(channel, old_msg_id)
            if old_msg is not None:
                await safe_call(old_msg.delete)
        except Exception:
            pass  # Bericht bestaat niet meer

    # Stap 2: Stuur nieuw bericht
    send_func = getattr(channel, "send", None)
    if send_func is None:
        return None

    try:
        msg = await safe_call(send_func, message)

        if msg is not None:
            # Sla nieuwe message ID op
            save_message_id(cid, "notification", msg.id)

            # Stap 3: Plan privacy removal (na 5 seconden)
            asyncio.create_task(_remove_persistent_mentions_after_delay(msg, 5.0))

            # Stap 4: Plan auto-delete (na 5 uur)
            delete_seconds = 5 * 3600
            asyncio.create_task(_delete_message_after_delay(msg, delete_seconds, cid))

        return msg
    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij versturen persistent mention: {e}")
        return None


async def _remove_persistent_mentions_after_delay(message: Any, delay: float) -> None:
    """
    Interne helper: verwijder mentions uit een persistent bericht na delay seconden.

    Args:
        message: Het Discord message object
        delay: Hoeveel seconden te wachten
    """
    try:
        await asyncio.sleep(delay)

        # Edit het bericht: verwijder alle mentions
        content = getattr(message, "content", "")
        if not content:
            return

        # Verwijder alle Discord mentions (<@123>, <@&456>, @everyone, @here)
        import re

        cleaned = re.sub(r"<@!?\d+>|<@&\d+>|@everyone|@here", "", content)

        # Probeer te editen
        if hasattr(message, "edit"):
            await safe_call(message.edit, content=cleaned.strip())
    except Exception:  # pragma: no cover
        # Stil falen (bericht kan verwijderd zijn, bot heeft geen rechten, etc.)
        pass
