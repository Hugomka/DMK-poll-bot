# apps/utils/mention_utils.py
#
# Helpers voor privacy-vriendelijke mentions in notificaties.
# - Tijdelijke mentions (5 seconden zichtbaar, dan auto-delete na 1 uur)
# - Persistente mentions (auto-delete na 5 uur)
# - Dynamische non-voter mentions (real-time updates wanneer iemand stemt)

import asyncio
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from apps.utils.discord_client import safe_call
from apps.utils.i18n import t
from apps.utils.poll_message import clear_message_id, get_message_id, save_message_id


def _get_notification_heading(channel_id: int) -> str:
    """Get localized notification heading for a channel."""
    return t(channel_id, "NOTIFICATIONS.notification_heading")

# Storage voor non-voter notification metadata (per kanaal)
# Format: {channel_id: {"dag": str, "deadline_time": str, "message_id": int}}
_NON_VOTER_NOTIFICATION_META: dict[int, dict] = {}


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
            except Exception:  # pragma: no cover
                pass  # Bericht bestaat niet meer
            clear_message_id(cid, key)

    # Stap 2: Stuur nieuw bericht
    send_func = getattr(channel, "send", None)
    if send_func is None:
        return

    # Build content using renderer (no comma artifacts, clean layout)
    content = render_notification_content(
        heading=_get_notification_heading(cid),
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
            _remove_mentions_after_delay(msg, delay, text, view, show_button, cid)
        )

        # Stap 4: Plan auto-delete (na delete_after_hours)
        delete_seconds = delete_after_hours * 3600
        asyncio.create_task(
            _delete_message_after_delay(msg, delete_seconds, cid, message_key)
        )

    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij versturen temporary mention: {e}")


async def _remove_mentions_after_delay(
    message: Any, delay: float, text: str, view: Any, show_button: bool, channel_id: int
) -> None:
    """
    Interne helper: verwijder mentions na delay seconden, behoud tekst en knop.

    Args:
        message: Het Discord message object
        delay: Hoeveel seconden te wachten
        text: De tekst om te behouden
        view: De view om te behouden (bijv. Stem Nu knop)
        show_button: Of de knop getoond moet blijven
        channel_id: Het kanaal ID voor i18n
    """
    try:
        await asyncio.sleep(delay)

        # Build content zonder mentions using renderer (no comma artifacts)
        content = render_notification_content(
            heading=_get_notification_heading(channel_id),
            mentions=None,  # Remove mentions for privacy
            text=text,
            footer=None,
        )

        # Edit het bericht: verwijder mentions, behoud tekst en knop
        if hasattr(message, "edit"):
            await safe_call(
                message.edit, content=content, view=view if show_button else None
            )
    except Exception:  # pragma: no cover
        # Stil falen (bericht kan verwijderd zijn, bot heeft geen rechten, etc.)
        pass


async def _delete_message_after_delay(
    message: Any,
    delay_seconds: float,
    channel_id: int,
    message_key: str = "notification_temp",
) -> None:
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
            except Exception:  # pragma: no cover
                pass  # Bericht bestaat niet meer
            clear_message_id(cid, key)

    # Stap 2: Stuur nieuw bericht using unified renderer
    send_func = getattr(channel, "send", None)
    if send_func is None:
        return None

    # Build content using renderer (unified layout, no comma artifacts)
    content = render_notification_content(
        heading=_get_notification_heading(cid),
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
            asyncio.create_task(
                _delete_message_after_delay(msg, delete_seconds, cid, message_key)
            )

        return msg
    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij versturen persistent mention: {e}")
        return None


# ========================================================================
# Dynamische Non-Voter Notifications (Real-time Mention Updates)
# ========================================================================


async def send_non_voter_notification(
    channel: Any,
    dag: str,
    mentions_str: str,
    text: str,
    deadline_time_str: str,
) -> None:
    """
    Stuur een non-voter notification met dynamische mention updates.

    Flow:
    1. Stuur notificatie met mentions
    2. Mentions blijven zichtbaar (NIET verwijderd na 5 seconden!)
    3. Wanneer iemand stemt: update mentions real-time (zie update_non_voter_notification)
    4. 5 minuten voor deadline: verwijder ALLE mentions (maar behoud namen zonder @)
    5. Na 1 uur: verwijder het hele bericht

    Args:
        channel: Het Discord kanaal object
        dag: De dag waarvoor deze notificatie is (bijv. 'vrijdag')
        mentions_str: Mentions string (bijv. "@user1, @user2")
        text: De body tekst (bijv. "2 leden hebben nog niet gestemd...")
        deadline_time_str: Deadline tijd voor deze dag (bijv. "18:00")
    """
    cid = getattr(channel, "id", 0)

    # Stap 1: Verwijder oude non-voter notification (als die bestaat)
    notification_keys = [
        "notification_nonvoter",
        "notification_temp",
        "notification_persistent",
        "notification",
    ]
    for key in notification_keys:
        old_msg_id = get_message_id(cid, key)
        if old_msg_id:
            try:
                from apps.utils.discord_client import fetch_message_or_none

                old_msg = await fetch_message_or_none(channel, old_msg_id)
                if old_msg is not None:
                    await safe_call(old_msg.delete)
            except Exception:
                pass
            clear_message_id(cid, key)

    # Stap 2: Stuur nieuw bericht
    send_func = getattr(channel, "send", None)
    if send_func is None:
        return

    content = render_notification_content(
        heading=_get_notification_heading(cid),
        mentions=mentions_str,
        text=text,
        footer=None,
    )

    try:
        msg = await safe_call(send_func, content=content)
        if msg is None:
            return

        # Sla message ID op
        save_message_id(cid, "notification_nonvoter", msg.id)

        # Stap 3: Sla metadata op voor real-time updates
        _NON_VOTER_NOTIFICATION_META[cid] = {
            "dag": dag,
            "deadline_time": deadline_time_str,
            "message_id": msg.id,
        }

        # Stap 4: Plan mention removal 5 minuten voor deadline
        now = datetime.now(ZoneInfo("Europe/Amsterdam"))
        try:
            uur, minuut = map(int, deadline_time_str.split(":"))
            deadline_datetime = now.replace(
                hour=uur, minute=minuut, second=0, microsecond=0
            )

            # Als deadline al voorbij is vandaag, skip (zou niet moeten gebeuren)
            if deadline_datetime <= now:
                print(
                    f"⚠️ Deadline {deadline_time_str} is al voorbij, skip mention removal scheduling"
                )
            else:
                # Bereken delay tot 5 minuten voor deadline
                removal_time = deadline_datetime.replace(minute=max(0, minuut - 5))
                delay_seconds = (removal_time - now).total_seconds()

                if delay_seconds > 0:
                    asyncio.create_task(
                        _remove_all_mentions_before_deadline(
                            msg, delay_seconds, text, cid
                        )
                    )
                else:
                    # Minder dan 5 minuten tot deadline, verwijder meteen
                    asyncio.create_task(
                        _remove_all_mentions_before_deadline(msg, 0, text, cid)
                    )

        except Exception as e:  # pragma: no cover
            print(f"⚠️ Kon deadline parsing niet doen voor {deadline_time_str}: {e}")

        # Stap 5: Plan auto-delete na 1 uur
        delete_seconds = 1 * 3600
        asyncio.create_task(
            _delete_message_after_delay(
                msg, delete_seconds, cid, "notification_nonvoter"
            )
        )

    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij versturen non-voter notification: {e}")


async def _remove_all_mentions_before_deadline(
    message: Any, delay_seconds: float, text: str, channel_id: int
) -> None:
    """
    Verwijder ALLE mentions 5 minuten voor deadline (behoud namen zonder @).

    Args:
        message: Het Discord message object
        delay_seconds: Hoeveel seconden te wachten
        text: De tekst om te behouden (zonder mentions)
        channel_id: Het kanaal ID
    """
    try:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        # Build content zonder mentions
        content = render_notification_content(
            heading=_get_notification_heading(channel_id),
            mentions=None,  # Verwijder mentions
            text=text,
            footer=None,
        )

        # Edit het bericht
        if hasattr(message, "edit"):
            await safe_call(message.edit, content=content)

        # Clear metadata (notificatie is niet meer dynamisch updatable)
        if channel_id in _NON_VOTER_NOTIFICATION_META:
            del _NON_VOTER_NOTIFICATION_META[channel_id]

    except Exception:  # pragma: no cover
        pass


async def update_non_voter_notification(channel: Any, dag: str, guild_id: int) -> None:
    """
    Update de non-voter notification real-time wanneer iemand stemt.

    Deze functie wordt aangeroepen vanuit de vote callback (poll_buttons.py).
    Het haalt de huidige niet-stemmers op en update de notificatie message.

    Args:
        channel: Het Discord kanaal object
        dag: De dag waarvoor de stem was (bijv. 'vrijdag')
        guild_id: Het guild ID
    """
    cid = getattr(channel, "id", 0)

    # Check of er een actieve non-voter notification is voor deze dag
    if cid not in _NON_VOTER_NOTIFICATION_META:
        return

    meta = _NON_VOTER_NOTIFICATION_META[cid]
    if meta["dag"] != dag:
        # Notificatie is voor een andere dag, skip
        return

    try:
        # Haal bericht op
        from apps.utils.discord_client import fetch_message_or_none

        message = await fetch_message_or_none(channel, meta["message_id"])
        if message is None:
            # Bericht bestaat niet meer, cleanup metadata
            del _NON_VOTER_NOTIFICATION_META[cid]
            return

        # Haal huidige niet-stemmers op
        from apps.utils.poll_storage import get_non_voters_for_day

        count, non_voter_ids = await get_non_voters_for_day(dag, guild_id, cid)

        if count == 0:
            # Iedereen heeft gestemd! Delete deze notificatie (celebration neemt over)
            await safe_call(message.delete)
            clear_message_id(cid, "notification_nonvoter")
            del _NON_VOTER_NOTIFICATION_META[cid]
            return

        # Build nieuwe mentions lijst
        guild = getattr(channel, "guild", None)
        if guild is None:
            return

        mentions_list = []
        for uid in non_voter_ids:
            try:
                user_id_int = int(uid)
                member = guild.get_member(user_id_int)
                if member:
                    mentions_list.append(
                        getattr(member, "mention", f"<@{user_id_int}>")
                    )
                else:
                    mentions_list.append(f"<@{user_id_int}>")
            except Exception:  # pragma: no cover
                continue

        if not mentions_list:
            # Geen mentions meer, delete notificatie
            await safe_call(message.delete)
            clear_message_id(cid, "notification_nonvoter")
            del _NON_VOTER_NOTIFICATION_META[cid]
            return

        # Build tekst met correcte Nederlandse grammatica
        mentions_str = ", ".join(mentions_list)
        count_text = f"**{count} {'lid' if count == 1 else 'leden'}** {'heeft' if count == 1 else 'hebben'} nog niet gestemd. "
        header = f"📣 DMK-poll – **{dag}**\n{count_text}Als je nog niet gestemd hebt voor **{dag}**, doe dat dan a.u.b. zo snel mogelijk."

        # Update bericht
        content = render_notification_content(
            heading=_get_notification_heading(cid),
            mentions=mentions_str,
            text=header,
            footer=None,
        )

        await safe_call(message.edit, content=content)

    except Exception as e:  # pragma: no cover
        print(f"⚠️ Fout bij updaten non-voter notification: {e}")
