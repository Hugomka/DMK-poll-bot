# apps/utils/mention_utils.py
#
# Helpers voor privacy-vriendelijke mentions in notificaties.
# - Tijdelijke mentions (5 seconden zichtbaar, dan auto-delete na 1 uur)
# - Persistente mentions (auto-delete na 5 uur)

import asyncio
from typing import Any, Optional

from apps.utils.discord_client import safe_call
from apps.utils.poll_message import clear_message_id, get_message_id, save_message_id


def render_notification_content(
    heading: str = ":mega: Notificatie:",
    mentions: Optional[str] = None,
    text: Optional[str] = None,
    footer: Optional[str] = None,
) -> str:
    """
    Render notification content with clean layout (no empty lines or comma artifacts).

    Args:
        heading: Header text (default: ":mega: Notificatie:")
        mentions: Mention string (e.g. "@user1 @user2") - omitted if None/empty
        text: Main body text - omitted if None/empty
        footer: Footer text - omitted if None/empty

    Returns:
        Clean notification content with no empty lines
    """
    lines = [heading]
    if mentions and mentions.strip():
        lines.append(mentions.strip())
    if text and text.strip():
        lines.append(text.strip())
    if footer and footer.strip():
        lines.append(footer.strip())
    return "\n".join(lines)


async def send_temporary_mention(
    channel: Any,
    mentions: Optional[str],
    text: str,
    delay: float = 5.0,
    show_button: bool = False,
    dag: str = "",
    leading_time: str = "",
    delete_after_hours: float = 1.0,
    message_key: str = "notification_temp",
) -> None:
    """
    Stuur een nieuwe notificatie met mentions die gebruikers pingt.

    Flow:
    1. Verwijder ALLE bestaande notificatieberichten (om duplicaten te voorkomen)
    2. Stuur nieuw bericht met mentions en optionele knop
    3. Na 5 seconden: verwijder mentions (privacy)
    4. Na delete_after_hours: verwijder het hele bericht

    Args:
        channel: Het Discord kanaal object
        mentions: Mentions string, bijv. "@user1, @user2", of None voor geen mentions
        text: De tekst die onder de mentions verschijnt
        delay: Hoeveel seconden de mentions zichtbaar blijven (standaard 5.0)
        show_button: Of de "Stem nu" knop getoond moet worden
        dag: De dag voor de Stem Nu knop
        leading_time: De leidende tijd voor de Stem Nu knop
        delete_after_hours: Na hoeveel uur het bericht verwijderd wordt (standaard 1.0)
        message_key: De storage key voor dit bericht (standaard 'notification_temp')
    """
    # Stap 1: Verwijder ALLE bestaande notificatieberichten (temp, persistent, legacy)
    # om ervoor te zorgen dat er altijd maar één notificatiebericht is
    cid = getattr(channel, "id", 0)
    notification_keys = ["notification_temp", "notification_persistent", "notification"]
    for key in notification_keys:
        old_msg_id = get_message_id(cid, key)
        if old_msg_id:
            try:
                from apps.utils.discord_client import fetch_message_or_none

                old_msg = await fetch_message_or_none(channel, old_msg_id)
                if old_msg is not None:
                    await safe_call(old_msg.delete)
            except Exception:
                pass  # Bericht bestaat niet meer
            clear_message_id(cid, key)

    # Stap 2: Stuur nieuw bericht
    send_func = getattr(channel, "send", None)
    if send_func is None:
        return

    # Build content using renderer (no comma artifacts, clean layout)
    content = render_notification_content(
        heading=":mega: Notificatie:",
        mentions=mentions,
        text=text,
        footer=None,
    )

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
        save_message_id(cid, message_key, msg.id)

        # Stap 3: Plan privacy removal (na 5 seconden)
        asyncio.create_task(
            _remove_mentions_after_delay(msg, delay, text, view, show_button)
        )

        # Stap 4: Plan auto-delete (na delete_after_hours)
        delete_seconds = delete_after_hours * 3600
        asyncio.create_task(_delete_message_after_delay(msg, delete_seconds, cid, message_key))

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

        # Build content zonder mentions using renderer (no comma artifacts)
        content = render_notification_content(
            heading=":mega: Notificatie:",
            mentions=None,  # Remove mentions for privacy
            text=text,
            footer=None,
        )

        # Edit het bericht: verwijder mentions, behoud tekst en knop
        if hasattr(message, "edit"):
            await safe_call(message.edit, content=content, view=view if show_button else None)
    except Exception:  # pragma: no cover
        # Stil falen (bericht kan verwijderd zijn, bot heeft geen rechten, etc.)
        pass


async def _delete_message_after_delay(message: Any, delay_seconds: float, channel_id: int, message_key: str = "notification_temp") -> None:
    """
    Interne helper: verwijder een bericht na delay_seconds en clear de message ID.

    Args:
        message: Het Discord message object
        delay_seconds: Hoeveel seconden te wachten
        channel_id: Het kanaal ID (voor het opschonen van de message ID)
        message_key: De storage key voor dit bericht (standaard 'notification_temp')
    """
    try:
        await asyncio.sleep(delay_seconds)

        # Verwijder het bericht
        if hasattr(message, "delete"):
            await safe_call(message.delete)

        # Clear de opgeslagen message ID
        from apps.utils.poll_message import clear_message_id

        clear_message_id(channel_id, message_key)
    except Exception:  # pragma: no cover
        # Stil falen (bericht kan al verwijderd zijn, bot heeft geen rechten, etc.)
        pass


async def send_persistent_mention(
    channel: Any,
    mentions: str,
    text: str,
    message_key: str = "notification_persistent",
) -> Optional[Any]:
    """
    Stuur een "doorgaan" notificatie met unified layout (5 uur lifetime).

    Flow:
    1. Verwijder ALLE bestaande notificatieberichten (om duplicaten te voorkomen)
    2. Stuur nieuw bericht met mentions
    3. Behoud mentions in het bericht (geen privacy removal voor persistent)
    4. Na 5 uur: verwijder het hele bericht

    Args:
        channel: Het Discord kanaal object
        mentions: Mention string (e.g. "@user1 @user2")
        text: Body text voor de notificatie
        message_key: De storage key voor dit bericht (standaard 'notification_persistent')

    Returns:
        Het verzonden bericht object, of None bij fout
    """
    # Stap 1: Verwijder ALLE bestaande notificatieberichten (temp, persistent, legacy)
    # om ervoor te zorgen dat er altijd maar één notificatiebericht is
    cid = getattr(channel, "id", 0)
    notification_keys = ["notification_temp", "notification_persistent", "notification"]
    for key in notification_keys:
        old_msg_id = get_message_id(cid, key)
        if old_msg_id:
            try:
                from apps.utils.discord_client import fetch_message_or_none

                old_msg = await fetch_message_or_none(channel, old_msg_id)
                if old_msg is not None:
                    await safe_call(old_msg.delete)
            except Exception:
                pass  # Bericht bestaat niet meer
            clear_message_id(cid, key)

    # Stap 2: Stuur nieuw bericht using unified renderer
    send_func = getattr(channel, "send", None)
    if send_func is None:
        return None

    # Build content using renderer (unified layout, no comma artifacts)
    content = render_notification_content(
        heading=":mega: Notificatie:",
        mentions=mentions,
        text=text,
        footer=None,
    )

    try:
        msg = await safe_call(send_func, content)

        if msg is not None:
            # Sla nieuwe message ID op
            save_message_id(cid, message_key, msg.id)

            # Stap 3: SKIP privacy removal voor persistent mentions
            # Mentions blijven zichtbaar tot het bericht verwijderd wordt

            # Stap 4: Plan auto-delete (na 5 uur)
            delete_seconds = 5 * 3600
            asyncio.create_task(_delete_message_after_delay(msg, delete_seconds, cid, message_key))

        return msg
    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij versturen persistent mention: {e}")
        return None


