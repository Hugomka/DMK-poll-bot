# apps/utils/poll_message.py

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import discord

from apps.logic.decision import build_decision_line
from apps.utils.celebration_gif import get_celebration_gif_url
from apps.utils.discord_client import fetch_message_or_none, safe_call
from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_settings import (
    is_paused,
    should_hide_counts,
    should_hide_ghosts,
)
from apps.utils.poll_storage import (
    get_non_voters_for_day,
    update_non_voters,
)

POLL_MESSAGE_FILE = os.getenv("POLL_MESSAGE_FILE", "poll_message.json")
# Lokale fallback afbeelding als Tenor niet werkt
LOCAL_CELEBRATION_IMAGE = "resources/bedankt-puppies-kitties.jpg"

# Interne locks & pending-taken om dubbele updates te voorkomen
_update_locks: dict[tuple[int, str], asyncio.Lock] = {}
_pending_tasks: dict[tuple[int, str], asyncio.Task] = {}


def is_channel_disabled(channel_id: int) -> bool:
    """
    Controleer of dit kanaal permanent uitgeschakeld is voor polls.

    Dit wordt ALLEEN gebruikt voor /dmk-poll-stopzetten (permanent shutdown).
    /dmk-poll-off (tijdelijk sluiten) gebruikt deze functie NIET.

    Args:
        channel_id: Het numerieke ID van het kanaal.

    Returns:
        True als het kanaal permanent uitgeschakeld is, anders False.
    """
    data = _load()
    # Backwards compatibility: check beide oude en nieuwe key
    shutdown_channels = data.get("permanently_shutdown_channels", [])
    if not shutdown_channels:
        shutdown_channels = data.get("disabled_channels", [])
    # Ondersteun zowel string- als int-representaties in de lijst
    cid_str = str(channel_id)
    return cid_str in shutdown_channels or channel_id in shutdown_channels


def set_channel_disabled(channel_id: int, disabled: bool) -> None:
    """
    Zet of verwijder de permanent uitgeschakelde status voor een kanaal.

    Dit wordt ALLEEN gebruikt voor /dmk-poll-stopzetten (permanent shutdown).
    /dmk-poll-off (tijdelijk sluiten) gebruikt deze functie NIET.

    Args:
        channel_id: Het numerieke ID van het kanaal.
        disabled: True om permanent uit te schakelen, False om weer in te schakelen.
    """
    data = _load()
    shutdown_channels = data.get("permanently_shutdown_channels", [])
    cid_str = str(channel_id)
    # Normaliseer naar strings voor opslag
    if disabled:
        if cid_str not in shutdown_channels:
            shutdown_channels.append(cid_str)
    else:
        # Verwijder zowel string- als int-representaties als ze bestaan
        shutdown_channels = [
            c for c in shutdown_channels if c != cid_str and c != channel_id
        ]
    data["permanently_shutdown_channels"] = shutdown_channels
    _save(data)


def get_dag_als_vandaag(channel_id: int) -> str | None:
    """
    Haal de opgeslagen dag_als_vandaag waarde op voor een kanaal.

    Args:
        channel_id: Het numerieke ID van het kanaal.

    Returns:
        De dag naam (bijv. "dinsdag") of None als niet ingesteld.
    """
    data = _load()
    dag_als_vandaag_map = data.get("dag_als_vandaag", {})
    cid_str = str(channel_id)
    return dag_als_vandaag_map.get(cid_str)


def set_dag_als_vandaag(channel_id: int, dag: str | None) -> None:
    """
    Sla de dag_als_vandaag waarde op voor een kanaal.

    Als dag None is, wordt de waarde verwijderd (terug naar normale modus).

    Args:
        channel_id: Het numerieke ID van het kanaal.
        dag: De dag naam (bijv. "dinsdag") of None om te wissen.
    """
    data = _load()
    dag_als_vandaag_map = data.get("dag_als_vandaag", {})
    cid_str = str(channel_id)

    if dag is None:
        # Verwijder de waarde
        dag_als_vandaag_map.pop(cid_str, None)
    else:
        # Sla de waarde op
        dag_als_vandaag_map[cid_str] = dag

    data["dag_als_vandaag"] = dag_als_vandaag_map
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


async def create_notification_message(
    channel: Any, activation_hammertime: str | None = None
) -> Optional[Any]:
    """
    Creëer een vriendelijk notificatiebericht wanneer de bot wordt aangezet.

    Note: This is a persistent notification that should remain visible.
    Uses 'notification_persistent' key to avoid conflicts with temporary notifications.
    Deletes any existing notification messages before creating the new one to ensure
    there's always only ONE notification message in the channel.

    Args:
        channel: Het Discord kanaal
        activation_hammertime: Optionele HammerTime string voor activatietijd (bijv. "<t:1234567890:t>")

    Returns:
        Het aangemaakte bericht, of None bij fout.
    """
    cid = int(getattr(channel, "id", 0))

    # STAP 1: Verwijder ALLE bestaande notificatieberichten (temp, persistent, legacy)
    # om ervoor te zorgen dat er altijd maar één notificatiebericht is
    notification_keys = ["notification_temp", "notification_persistent", "notification"]
    for key in notification_keys:
        old_msg_id = get_message_id(cid, key)
        if old_msg_id:
            try:
                old_msg = await fetch_message_or_none(channel, old_msg_id)
                if old_msg is not None:
                    await safe_call(old_msg.delete)
            except Exception:  # pragma: no cover
                pass  # Bericht bestaat niet meer
            clear_message_id(cid, key)

    # STAP 2: Maak nieuw notificatiebericht aan
    from apps.utils.i18n import t

    heading = t(cid, "NOTIFICATIONS.notification_heading")
    if activation_hammertime:
        body = t(cid, "NOTIFICATIONS.poll_opened_at", tijd=activation_hammertime)
    else:
        body = t(cid, "NOTIFICATIONS.poll_opened")
    content = f"{heading}\n{body}"

    send = getattr(channel, "send", None)
    if send is None:
        return None
    try:
        msg = await safe_call(send, content=content, view=None)
        if msg is not None:
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
    from apps.utils.i18n import t

    heading = t(cid, "NOTIFICATIONS.notification_heading")
    content = f"{heading}\n"
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


async def update_poll_messages_for_category(channel: Any, dag: str) -> None:
    """
    Update poll messages in all channels that share votes with this channel.

    This function is used for category-based dual language support. When a vote
    changes in one channel, all channels in the same category (that have active
    polls) need to be updated to reflect the shared vote count.

    For standalone channels (no category or single channel in category),
    this behaves the same as update_poll_message().

    Args:
        channel: Discord TextChannel object
        dag: The day to update (vrijdag, zaterdag, zondag, etc.)
    """
    from apps.utils.poll_settings import get_vote_scope_channels

    scope_ids = get_vote_scope_channels(channel)

    if len(scope_ids) == 1:
        # Single channel, use existing flow
        await update_poll_message(channel, dag)
        return

    # Multiple channels - update all in parallel
    tasks: list[asyncio.Task] = []
    guild = getattr(channel, "guild", None)
    if not guild:
        await update_poll_message(channel, dag)
        return

    for cid in scope_ids:
        ch = guild.get_channel(cid)
        if ch:
            tasks.append(schedule_poll_update(ch, dag, delay=0.0))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


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
    cid_val_temp = int(getattr(channel, "id", 0))

    # Gebruik period-based system om correcte datums te krijgen
    from apps.utils.poll_settings import get_enabled_period_days
    dagen_info = get_enabled_period_days(cid_val_temp, reference_date=None)

    # Maak een mapping van dag naar datum
    dag_naar_datum = {day_info["dag"]: day_info["datum_iso"] for day_info in dagen_info}

    if dag:
        # Filter alleen de gevraagde dag (als die in de enabled periods zit)
        if dag not in dag_naar_datum:
            # Dag zit niet in enabled periods, negeer
            return
        keys = [dag]
    else:
        # Alle enabled dagen uit periods
        keys = [day_info["dag"] for day_info in dagen_info]

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

            # Haal datum op uit rolling window
            datum_iso = dag_naar_datum.get(d)

            # Bepaal content (zowel voor edit als create)
            hide = should_hide_counts(cid_val, d, now)
            hide_ghosts_val = should_hide_ghosts(cid_val, d, now)
            paused = is_paused(cid_val)
            content = await build_poll_message_for_day_async(
                d,
                guild_id=gid_val,
                channel_id=cid_val,
                hide_counts=hide,
                hide_ghosts=hide_ghosts_val,
                pauze=paused,
                guild=getattr(channel, "guild", None),  # Voor namen
                channel=channel,  # Voor niet-stemmers tracking
                datum_iso=datum_iso,  # Correcte datum uit rolling window
            )

            decision = await build_decision_line(gid_val, cid_val, d, now, channel=channel)
            if decision:
                content = content.rstrip() + ":arrow_up: " + decision + "\n\u200b"

            if mid:
                # Bericht ID bestaat - probeer te updaten
                msg = await fetch_message_or_none(channel, mid)
                if msg is not None:
                    await safe_call(msg.edit, content=content, view=None)
                # Als msg is None (fetch failed), NIET opnieuw aanmaken (Bug #4 fix)
                # Vertrouw op message ID - tijdelijke Discord API fout is geen reden om te recreëren
                continue

            # Create-pad: alleen als er GEEN mid is (eerste keer)
            try:
                send = getattr(channel, "send", None)
                new_msg = (
                    await safe_call(send, content=content, view=None) if send else None
                )
                if new_msg is not None:
                    save_message_id(cid_val, d, new_msg.id)
            except Exception as e:  # pragma: no cover
                print(f"❌ Fout bij aanmaken bericht voor {d}: {e}")


def create_celebration_embed() -> discord.Embed:
    """Maak celebration embed (zonder GIF - die wordt apart gestuurd)."""
    embed = discord.Embed(
        title="🎉 Geweldig! Iedereen heeft gestemd!",
        description="Bedankt voor jullie inzet dit weekend!",
        color=discord.Color.gold(),
    )
    return embed


async def check_all_voted_celebration(
    channel: Any, guild_id: int, channel_id: int
) -> None:
    """Check of iedereen heeft gestemd en stuur/verwijder celebration message."""
    try:
        # Check alleen huidige-periode-dagen voor niet-stemmers
        from apps.utils.poll_settings import get_enabled_period_days
        dagen = [d["dag"] for d in get_enabled_period_days(channel_id, reference_date=None)]

        all_voted = True
        for dag in dagen:
            count, _ = await get_non_voters_for_day(dag, guild_id, channel_id)
            if count > 0:
                all_voted = False
                break

        # Bug #2 fix: Check of er daadwerkelijk stemmen zijn (niet alleen "geen niet-stemmers")
        # Dit voorkomt celebration op verse polls met slechts 1 stem
        has_any_votes = False
        if all_voted:
            from apps.utils.poll_storage import load_votes, _is_non_voter_id
            votes = await load_votes(str(guild_id), str(channel_id))
            # Filter non-voter IDs eruit - alleen echte stemmen tellen
            real_voter_ids = [uid for uid in votes.keys() if not _is_non_voter_id(uid)]
            has_any_votes = len(real_voter_ids) > 0

        celebration_id = get_message_id(channel_id, "celebration")
        celebration_gif_id = get_message_id(channel_id, "celebration_gif")

        # Alleen celebration als iedereen heeft gestemd ÉN er daadwerkelijk stemmen zijn
        if all_voted and has_any_votes:
            # Iedereen heeft gestemd! Stuur celebration als die nog niet bestaat
            if not celebration_id:
                embed = create_celebration_embed()

                send = getattr(channel, "send", None)
                if send:
                    # Stuur eerst embed met tekst
                    new_msg = await safe_call(send, embed=embed)
                    if new_msg:
                        save_message_id(channel_id, "celebration", new_msg.id)

                    # Selecteer random Tenor URL met gewogen selectie
                    tenor_url = get_celebration_gif_url()

                    # Probeer eerst Tenor URL, fallback naar lokale afbeelding
                    gif_msg = None
                    if tenor_url:
                        gif_msg = await safe_call(send, content=tenor_url)

                    # Sla GIF message ID op (Tenor of fallback)
                    if gif_msg:
                        save_message_id(channel_id, "celebration_gif", gif_msg.id)
                    elif os.path.exists(LOCAL_CELEBRATION_IMAGE):
                        # Als Tenor niet werkt, stuur lokale afbeelding
                        with open(LOCAL_CELEBRATION_IMAGE, "rb") as f:
                            file = discord.File(f, filename="bedankt.jpg")
                            fallback_msg = await safe_call(send, file=file)
                            if fallback_msg:
                                save_message_id(
                                    channel_id, "celebration_gif", fallback_msg.id
                                )
        else:
            # Niet iedereen heeft gestemd, verwijder BEIDE celebration messages
            if celebration_id:
                msg = await fetch_message_or_none(channel, celebration_id)
                if msg:
                    await safe_call(msg.delete)
                clear_message_id(channel_id, "celebration")

            if celebration_gif_id:
                gif_msg = await fetch_message_or_none(channel, celebration_gif_id)
                if gif_msg:
                    await safe_call(gif_msg.delete)
                clear_message_id(channel_id, "celebration_gif")

    except Exception:  # pragma: no cover
        pass


async def remove_celebration_message(channel: Any, channel_id: int) -> None:
    """Verwijder celebration messages (embed + GIF, gebruikt bij reset)."""
    try:
        # Verwijder celebration embed
        celebration_id = get_message_id(channel_id, "celebration")
        if celebration_id:
            msg = await fetch_message_or_none(channel, celebration_id)
            if msg:
                await safe_call(msg.delete)
            clear_message_id(channel_id, "celebration")

        # Verwijder celebration GIF
        celebration_gif_id = get_message_id(channel_id, "celebration_gif")
        if celebration_gif_id:
            gif_msg = await fetch_message_or_none(channel, celebration_gif_id)
            if gif_msg:
                await safe_call(gif_msg.delete)
            clear_message_id(channel_id, "celebration_gif")
    except Exception:  # pragma: no cover
        pass
