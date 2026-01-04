# apps/scheduler.py

import asyncio
import json
import os
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import List, Optional, Union

import discord
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.utils.discord_client import fetch_message_or_none, get_channels, safe_call
from apps.utils.logger import log_job, log_startup
from apps.utils.mention_utils import (
    send_non_voter_notification,
    send_persistent_mention,
    send_temporary_mention,
)
from apps.utils.message_builder import build_doorgaan_participant_list
from apps.utils.poll_message import (
    clear_message_id,
    create_notification_message,
    get_message_id,
    is_channel_disabled,
    save_message_id,
    schedule_poll_update,
    set_channel_disabled,
)
from apps.utils.poll_settings import (
    get_enabled_poll_days,
    get_setting,
    is_notification_enabled,
    is_paused,
)
from apps.utils.poll_storage import (
    calculate_leading_time,
    load_votes,
    reset_votes,
    reset_votes_scoped,
)
from apps.utils.tenor_sync import needs_sync, sync_tenor_links

# NL-tijdzone
TZ = pytz.timezone("Europe/Amsterdam")
scheduler = AsyncIOScheduler(timezone=TZ)

CONFIG_PATH = os.getenv("POLL_SETTINGS_FILE", "poll_settings.json")

MIN_NOTIFY_VOTES = 6

# Nieuw: herinneringstijd en resetinstellingen
REMINDER_HOUR = 16  # 16:00 uur - stuur herinnering vóór de deadline
RESET_DAY_OF_WEEK = 1  # 0=ma, 1=di … reset op dinsdag
RESET_HOUR = 20  # 20:00 uur - resetmoment
REMINDER_DAYS = {"vrijdag": 4, "zaterdag": 5, "zondag": 6}
EARLY_REMINDER_DAY = "donderdag"
EARLY_REMINDER_HOUR = 20  # 20:00 uur

LOCK_PATH = ".scheduler.lock"
STATE_PATH = ".scheduler_state.json"


def _load_poll_config() -> None:
    global REMINDER_HOUR, RESET_DAY_OF_WEEK, RESET_HOUR
    global MIN_NOTIFY_VOTES, REMINDER_DAYS, EARLY_REMINDER_DAY
    global EARLY_REMINDER_HOUR
    if not CONFIG_PATH or not os.path.exists(CONFIG_PATH):
        return
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # pragma: no cover
        return
    # overschrijf waarden als ze bestaan in het JSON-bestand
    REMINDER_HOUR = int(data.get("reminder_hour", REMINDER_HOUR))
    EARLY_REMINDER_HOUR = int(data.get("early_reminder_hour", EARLY_REMINDER_HOUR))
    RESET_DAY_OF_WEEK = int(data.get("reset_day_of_week", RESET_DAY_OF_WEEK))
    RESET_HOUR = int(data.get("reset_hour", RESET_HOUR))
    MIN_NOTIFY_VOTES = int(data.get("min_notify_votes", MIN_NOTIFY_VOTES))
    # reminder_days is een mapping dag → weekday-index
    if isinstance(data.get("reminder_days"), dict):
        REMINDER_DAYS.update(
            {str(dag): int(idx) for dag, idx in data["reminder_days"].items()}
        )
    EARLY_REMINDER_DAY = data.get("early_reminder_day", EARLY_REMINDER_DAY)


def _weekly_reset_threshold(now: datetime) -> datetime:
    """
    Drempel voor 'nieuwe week' t.b.v. reset-skip:
    - Zondag 20:30 Europe/Amsterdam.
    Als nu vóór die tijd ligt, pak de vorige week.
    """
    if now.tzinfo is None:
        now = TZ.localize(now)

    # 6 = zondag
    days_since_sun = (now.weekday() - 6) % 7
    last_sunday = (now - timedelta(days=days_since_sun)).replace(
        hour=20, minute=30, second=0, microsecond=0
    )
    if now < last_sunday:
        last_sunday -= timedelta(days=7)
    return last_sunday


# laad configuratie zodra het bestand wordt geïmporteerd
_load_poll_config()


def should_run(last_run: Union[str, datetime, None], occurrence: datetime) -> bool:
    """
    Bepaal of een job moet draaien t.o.v. de laatst uitgevoerde timestamp.
    - occurrence is de geplande occurrence in Europe/Amsterdam.
    - last_run mag een ISO-string, datetime of None zijn.
    """
    # zorg dat occurrence tz-aware is
    if occurrence.tzinfo is None:
        occurrence = TZ.localize(occurrence)

    if last_run is None:
        return True

    # parse last_run → datetime
    if isinstance(last_run, datetime):
        last_dt = last_run
    else:
        try:
            last_dt = datetime.fromisoformat(str(last_run))
        except Exception:  # pragma: no cover
            # Kapotte of lege state? Dan gewoon uitvoeren.
            return True

    # zorg dat last_dt tz-aware is
    if last_dt.tzinfo is None:
        last_dt = TZ.localize(last_dt)

    # gelijk → NIET runnen; alleen draaien als last_dt < occurrence
    return last_dt < occurrence


def _is_deadline_mode(channel_id: int, dag: str) -> bool:
    """
    Controleer of een kanaal 'deadline' modus gebruikt voor een specifieke dag.

    Retourneert True als:
    - Geen expliciete setting (standaard is 'deadline')
    - Expliciete setting met modus='deadline'

    Retourneert False als:
    - Expliciete setting met modus='altijd'
    """
    try:
        setting = get_setting(channel_id, dag)
        if not setting or not isinstance(setting, dict):
            return True  # Standaard is 'deadline' modus
        return setting.get("modus", "deadline") == "deadline"
    except Exception:  # pragma: no cover
        return True  # Bij fout, standaard 'deadline' modus aannemen


# ============================================================================
# Helper functies om code-duplicatie te verminderen (DRY principe)
# ============================================================================


def _get_deny_channel_names() -> set[str]:
    """Load en parse DENY_CHANNEL_NAMES environment variable."""
    return set(
        n.strip().lower()
        for n in os.getenv("DENY_CHANNEL_NAMES", "").split(",")
        if n.strip()
    )


def _extract_owner_id(uid: Union[str, int]) -> str:
    """Extraheer owner ID, handelt gaststemmen af (format: "owner_id_guest::guest_name")."""
    uid_str = str(uid)
    if "_guest::" in uid_str:
        return uid_str.split("_guest::", 1)[0]
    return uid_str


async def _load_channel_votes(guild, channel) -> dict:
    """Laad stemmen voor een specifiek guild/kanaal met veilige defaults."""
    gid = getattr(guild, "id", "0")
    cid = getattr(channel, "id", "0")
    return await load_votes(gid, cid) or {}


async def _get_voted_ids(
    votes: dict, dag: Optional[str] = None, vote_type: str = "any"
) -> set[int]:
    """Extraheer user IDs die hebben gestemd voor specifieke dag/type."""
    voted_ids: set[int] = set()

    for uid, dagen_map in votes.items():
        if not isinstance(dagen_map, dict):
            continue

        owner_id_str = _extract_owner_id(uid)
        try:
            owner_id = int(owner_id_str)
        except (ValueError, TypeError):
            continue

        if dag:
            # Dag-specifieke check
            tijden = (dagen_map or {}).get(dag, [])
            if isinstance(tijden, list):
                if vote_type == "any":
                    if tijden:
                        voted_ids.add(owner_id)
                elif vote_type in tijden:
                    voted_ids.add(owner_id)
        else:
            # Weekend-brede check
            for tijden in dagen_map.values():
                if isinstance(tijden, list) and tijden:
                    voted_ids.add(owner_id)
                    break

    return voted_ids


def _get_non_voter_mentions(channel, voted_ids: set[int]) -> List[str]:
    """Haal mentions op voor kanaalleden die niet hebben gestemd."""
    mentions = []
    members = getattr(channel, "members", [])

    for member in members:
        if getattr(member, "bot", False):
            continue

        mid = getattr(member, "id", None)
        if mid and mid not in voted_ids:
            mention = getattr(member, "mention", f"<@{mid}>")
            if mention:
                mentions.append(mention)

    return mentions


async def _delete_poll_message(
    channel, cid: int, key: str, fallback_text: str = "📴 Dit bericht is gesloten."
) -> None:
    """Verwijder poll-bericht op key, met fallback naar bewerken."""
    msg_id = get_message_id(cid, key)
    if not msg_id:
        return

    msg = await fetch_message_or_none(channel, msg_id)
    if msg is not None:
        try:
            await safe_call(msg.delete)
        except Exception:  # pragma: no cover
            await safe_call(msg.edit, content=fallback_text, view=None)

    clear_message_id(cid, key)


async def _clear_notification_messages(channel, cid: int) -> None:
    """Wis alle notificatieberichten (temp, persistent, en legacy)."""
    notification_keys = [
        "notification_temp",
        "notification_persistent",
        "notification",  # Legacy key
    ]

    for key in notification_keys:
        await _delete_poll_message(
            channel, cid, key, fallback_text="📴 Notificaties gesloten."
        )


async def _update_or_create_message(
    channel, cid: int, key: str, content: str, view=None
) -> Optional[discord.Message]:
    """Update bestaand bericht of maak nieuw bericht aan."""
    send = getattr(channel, "send", None)
    if not send:
        return None

    msg_id = get_message_id(cid, key)

    if msg_id:
        msg = await fetch_message_or_none(channel, msg_id)
        if msg is not None:
            await safe_call(msg.edit, content=content, view=view)
            return msg

    # Maak nieuw bericht
    msg = await safe_call(send, content=content, view=view)
    if msg is not None:
        save_message_id(cid, key, msg.id)

    return msg


# ============================================================================
# Scheduler functies
# ============================================================================


async def notify_non_voters_thursday(bot) -> None:  # pragma: no cover
    """Herinner donderdagavond leden die nog niet hebben gestemd (alleen deadline modus)."""
    # DENY_CHANNEL_NAMES check
    deny_names = _get_deny_channel_names()

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            cid = getattr(channel, "id", 0)
            if is_channel_disabled(cid):
                continue

            # Skip if channel is paused
            if is_paused(cid):
                continue

            # Check notification settings: skip als thursday_reminder disabled is
            if not is_notification_enabled(cid, "thursday_reminder"):
                continue

            # Skip als GEEN van de dagen in 'deadline' modus staat
            # (donderdag-notificatie is alleen relevant voor deadline-scenario)
            if not any(_is_deadline_mode(cid, dag) for dag in get_enabled_poll_days(cid)):
                continue

            # Check DENY_CHANNEL_NAMES
            ch_name = (getattr(channel, "name", "") or "").lower()
            if ch_name in deny_names:
                continue

            # ALLOW_FROM_PER_CHANNEL_ONLY check verwijderd:
            # Notificaties werken op data-niveau (votes), niet afhankelijk van berichten
            # Laad stemmen en vind niet-stemmers
            votes = await _load_channel_votes(guild, channel)
            voted_ids = await _get_voted_ids(votes)
            non_voters = _get_non_voter_mentions(channel, voted_ids)
            if non_voters:
                # Gebruik tijdelijke mentions (5 seconden zichtbaar, auto-delete na 1 uur)
                mentions_str = ", ".join(non_voters)
                count = len(non_voters)
                text = f"**{count} {'lid' if count == 1 else 'leden'}** {'heeft' if count == 1 else 'hebben'} nog niet gestemd voor dit weekend. Als je nog niet gestemd hebt: graag stemmen vóór 18:00. Dank!"
                try:
                    await send_temporary_mention(
                        channel, mentions=mentions_str, text=text
                    )
                except Exception:  # pragma: no cover
                    pass


async def sync_tenor_links_weekly(bot=None) -> None:  # pragma: no cover
    """
    Sync tenor GIF lijst wekelijks (maandag 00:00).
    Controleert eerst of sync nodig is (nieuwe/verwijderde GIFs).
    Voert alleen sync uit als er daadwerkelijk verschillen zijn (niet alleen counts).
    """
    log_job("tenor_sync", status="checking")

    # Check of sync nodig is (nieuwe/verwijderde GIFs, niet alleen count wijzigingen)
    if not needs_sync():
        log_job("tenor_sync", status="skipped_no_changes")
        return

    # Voer sync uit
    try:
        sync_tenor_links()
        log_job("tenor_sync", status="executed")
    except Exception as e:  # pragma: no cover
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Fout bij tenor sync: {e}")
        log_job("tenor_sync", status="failed")


def _read_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # pragma: no cover
        return {}


def _write_state(state: dict) -> None:
    tmp = f"{STATE_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_PATH)


def _within_reset_window(now: datetime, minutes: int = 5) -> bool:
    """
    Controleer of we in het resetvenster zitten.
    Reset vindt voortaan plaats op dinsdag tussen 20:00 en 20:05.
    """
    if now.tzinfo is None:
        now = TZ.localize(now)
    return (
        now.weekday() == RESET_DAY_OF_WEEK
        and now.hour == RESET_HOUR
        and now.minute < minutes
    )


async def _cleanup_outdated_poll_messages(bot) -> None:  # pragma: no cover
    """
    Verwijder ALLE poll-berichten en clear message IDs bij startup.

    Dit zorgt ervoor dat na herstart alle berichten opnieuw worden aangemaakt
    met correcte datums uit de huidige rolling window. Voorkomt situaties waarbij
    oude berichten (bijv. "Zondag 7 december") naast nieuwe berichten ("Zondag 14
    december") blijven staan na langdurige offline periode.
    """
    from apps.utils.constants import DAG_NAMEN
    from apps.utils.discord_client import fetch_message_or_none, safe_call

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            try:
                cid = int(getattr(channel, "id", 0))
            except Exception:  # pragma: no cover
                continue

            if is_channel_disabled(cid):
                continue

            # Verwijder alle dag-berichten en clear hun IDs
            for dag_naam in DAG_NAMEN:
                mid = get_message_id(cid, dag_naam)
                if mid:
                    msg = await fetch_message_or_none(channel, mid)
                    if msg is not None:
                        await safe_call(msg.delete)
                    clear_message_id(cid, dag_naam)

            # Clear ook het "stemmen" button bericht
            stem_mid = get_message_id(cid, "stemmen")
            if stem_mid:
                msg = await fetch_message_or_none(channel, stem_mid)
                if msg is not None:
                    await safe_call(msg.delete)
                clear_message_id(cid, "stemmen")


async def _run_catch_up(bot) -> None:  # pragma: no cover
    """
    Catch-up na herstart: voer gemiste jobs maximaal één keer uit.
    Reset alleen in het nieuwe venster (dinsdag 20:00 - 20:05).

    BELANGRIJK: cleanup_outdated_poll_messages wordt EERST uitgevoerd om oude
    berichten te verwijderen. Daarna wordt update_all_polls ALTIJD uitgevoerd
    om nieuwe berichten aan te maken met correcte datums uit rolling window.
    """
    # STAP 1: Verwijder oude berichten en clear alle message IDs
    await _cleanup_outdated_poll_messages(bot)

    # STAP 2: Voer normale catch-up logica uit
    now = datetime.now(TZ)
    state = _read_state()
    missed: list[str] = []

    # Dagelijkse update (18:00)
    # ALTIJD uitvoeren bij startup om oude berichten op te ruimen
    last_update = state.get("update_all_polls")
    today_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
    last_sched_update = today_18 if now >= today_18 else today_18 - timedelta(days=1)

    # Altijd update_all_polls uitvoeren bij startup (niet alleen bij gemiste deadline)
    await update_all_polls(bot)
    state["update_all_polls"] = now.isoformat()
    if should_run(last_update, last_sched_update):
        missed.append("update_all_polls")
        log_job("update_all_polls", status="executed")
    else:
        log_job("update_all_polls", status="executed_startup_cleanup")

    # Wekelijkse reset (dinsdag 20:00)
    last_reset = state.get("reset_polls")
    days_since = (now.weekday() - RESET_DAY_OF_WEEK) % 7
    reset_date = (now - timedelta(days=days_since)).replace(
        hour=RESET_HOUR, minute=0, second=0, microsecond=0
    )
    last_sched_reset = (
        reset_date if now >= reset_date else reset_date - timedelta(days=7)
    )
    if should_run(last_reset, last_sched_reset):
        executed = await reset_polls(bot)
        if executed:
            state["reset_polls"] = now.isoformat()
            missed.append("reset_polls")
        else:
            # al geskipte reset (buiten venster of al handmatig gedaan)
            log_job("reset_polls", status="skipped_in_catchup")
    else:
        log_job("reset_polls", status="skipped")

    # Notificaties (vr/za/zo - om 18:05)
    weekday_map = {"vrijdag": 4, "zaterdag": 5, "zondag": 6}
    for dag, target_wd in weekday_map.items():
        key = f"notify_{dag}"
        last_notify = state.get(key)
        days_since = (now.weekday() - target_wd) % 7
        last_date = (now - timedelta(days=days_since)).date()
        # 18:05 i.p.v. precies 18:00 om pollupdates af te ronden
        last_occurrence = TZ.localize(datetime.combine(last_date, dt_time(18, 5)))
        if now < last_occurrence:
            last_occurrence -= timedelta(days=7)
        if should_run(last_notify, last_occurrence):
            await notify_voters_if_avond_gaat_door(bot, dag)
            state[key] = now.isoformat()
            missed.append(f"notify_{dag}")
            log_job("notify", dag=dag, status="executed")
        else:
            log_job("notify", dag=dag, status="skipped")

    # Herinneringen naar niet-stemmers (17:00)
    for dag, target_wd in REMINDER_DAYS.items():
        key = f"reminder_{dag}"
        last_rem = state.get(key)
        days_since = (now.weekday() - target_wd) % 7
        last_date = (now - timedelta(days=days_since)).date()
        rem_occurrence = TZ.localize(
            datetime.combine(last_date, dt_time(REMINDER_HOUR, 0))
        )
        if now < rem_occurrence:
            rem_occurrence -= timedelta(days=7)
        if should_run(last_rem, rem_occurrence):
            await notify_non_voters(bot, dag)
            state[key] = now.isoformat()
            missed.append(f"reminder_{dag}")
            log_job("reminder", dag=dag, status="executed")
        else:
            log_job("reminder", dag=dag, status="skipped")

    # Donderdag-herinnering naar niet-stemmers (20:00)
    last_thu = state.get("reminder_thursday")
    days_since_thu = (now.weekday() - 3) % 7  # 3 = donderdag
    last_date_thu = (now - timedelta(days=days_since_thu)).date()
    last_occurrence_thu = TZ.localize(
        datetime.combine(last_date_thu, dt_time(EARLY_REMINDER_HOUR, 0))
    )
    if now < last_occurrence_thu:
        last_occurrence_thu -= timedelta(days=7)
    if should_run(last_thu, last_occurrence_thu):
        await notify_non_voters_thursday(bot)
        state["reminder_thursday"] = now.isoformat()
        missed.append("reminder_thursday")

    # Wekelijkse tenor GIF sync (maandag 00:00)
    last_tenor_sync = state.get("tenor_sync")
    days_since_mon = (now.weekday() - 0) % 7  # 0 = maandag
    last_date_mon = (now - timedelta(days=days_since_mon)).date()
    last_occurrence_mon = TZ.localize(
        datetime.combine(last_date_mon, dt_time(0, 0))
    )
    if now < last_occurrence_mon:
        last_occurrence_mon -= timedelta(days=7)
    if should_run(last_tenor_sync, last_occurrence_mon):
        await sync_tenor_links_weekly(bot)
        state["tenor_sync"] = now.isoformat()
        missed.append("tenor_sync")
        log_job("tenor_sync", status="executed")
    else:
        log_job("tenor_sync", status="skipped")

    # Altijd state schrijven en loggen, ongeacht of Thursday reminder runde
    _write_state(state)
    log_startup(missed)


async def _run_catch_up_with_lock(bot) -> None:  # pragma: no cover
    """Catch-up met file-lock (voorkomt dubbele runs bij snelle herstarts)."""
    try:
        if os.path.exists(LOCK_PATH):
            try:
                mtime = os.path.getmtime(LOCK_PATH)
                if (datetime.now().timestamp() - mtime) < 300:
                    return
                else:
                    os.remove(LOCK_PATH)
            except Exception:  # pragma: no cover
                pass

        with open(LOCK_PATH, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

        await _run_catch_up(bot)
    finally:
        try:
            if os.path.exists(LOCK_PATH):
                os.remove(LOCK_PATH)
        except Exception:  # pragma: no cover
            pass


async def retry_failed_operations(bot):
    """
    Probeer mislukte misschien conversies en vote resets opnieuw.

    - Runs every minute
    - Retries pending operations (binnen 2 uur)
    - Sends error messages for expired operations (>2 uur)
    """
    log_job("retry_operations", status="started")

    from apps.utils.retry_queue import (
        get_expired_conversions,
        get_pending_conversions,
        increment_retry_count,
        remove_from_queue,
    )
    from apps.utils.poll_storage import add_vote, remove_vote, reset_votes_scoped

    # 1. Probeer pending operations opnieuw
    pending = get_pending_conversions()
    for item in pending:
        operation_type = item.get("type", "conversion")
        gid = item["guild_id"]
        cid = item["channel_id"]
        key = item["key"]

        try:
            if operation_type == "conversion":
                # Misschien conversie
                uid = item["user_id"]
                dag = item["dag"]
                await remove_vote(uid, dag, "misschien", gid, cid)
                await add_vote(uid, dag, "niet meedoen", gid, cid)

                # Success - verwijder uit queue
                remove_from_queue(key)
                log_job("retry_operations", status=f"conversion_success: user={uid}, dag={dag}")

                # Update poll message
                try:
                    all_channels = get_channels(bot)
                    channel = next((ch for ch in all_channels if str(getattr(ch, "id", "")) == cid), None)
                    if channel:
                        await schedule_poll_update(channel, dag, delay=0.0)
                except Exception:  # pragma: no cover
                    pass

            elif operation_type == "reset":
                # Vote reset
                await reset_votes_scoped(gid, cid)

                # Success - verwijder uit queue
                remove_from_queue(key)
                log_job("retry_operations", status=f"reset_success: guild={gid}, channel={cid}")

        except Exception:  # pragma: no cover
            # Nog steeds gefaald - verhoog retry count
            increment_retry_count(key)
            log_job("retry_operations", status=f"retry_failed: type={operation_type}")

    # 2. Stuur error messages voor expired operations (>2 uur)
    expired = get_expired_conversions()
    for item in expired:
        operation_type = item.get("type", "conversion")
        gid = item["guild_id"]
        cid = item["channel_id"]
        key = item["key"]
        retry_count = item.get("retry_count", 0)

        try:
            # Haal channel op
            all_channels = get_channels(bot)
            channel = next((ch for ch in all_channels if str(getattr(ch, "id", "")) == cid), None)

            if channel:
                send = getattr(channel, "send", None)
                if send:
                    if operation_type == "conversion":
                        uid = item["user_id"]
                        dag = item["dag"]
                        await send(
                            f"⚠️ **Fout bij misschien conversie:**\n"
                            f"Kan stem van <@{uid}> voor **{dag}** niet converteren naar 'niet meedoen'.\n"
                            f"Geprobeerd {retry_count + 1}x over 2 uur. Neem contact op met de beheerder.",
                            delete_after=None
                        )
                    elif operation_type == "reset":
                        await send(
                            f"⚠️ **Fout bij vote reset:**\n"
                            f"Kan stemmen niet resetten voor dit kanaal na poll sluiting.\n"
                            f"Geprobeerd {retry_count + 1}x over 2 uur. Oude stemmen blijven mogelijk zichtbaar.\n"
                            f"Neem contact op met de beheerder.",
                            delete_after=None
                        )
                    log_job("retry_operations", status=f"timeout_error_sent: type={operation_type}")
        except Exception:  # pragma: no cover
            log_job("retry_operations", status=f"error_send_failed: type={operation_type}")

        # Verwijder uit queue (ook als error message faalt)
        remove_from_queue(key)

    log_job("retry_operations", status=f"completed (pending={len(pending)}, expired={len(expired)})")


def setup_scheduler(bot) -> None:  # pragma: no cover
    """
    Plan periodieke jobs en start de scheduler.
    - Pollupdate elke dag om 18:00.
    - Herinnering niet-stemmers op vr/za/zo om 17:00.
    - Notificatie dat een avond doorgaat op vr/za/zo om 18:05.
    - Reset op dinsdag om 20:00.
    - Tenor GIF sync op maandag om 00:00.
    """
    # Dagelijkse pollupdates
    scheduler.add_job(
        update_all_polls,
        CronTrigger(hour=18, minute=0),
        args=[bot],
        name="Dagelijkse pollupdate om 18:00",
    )
    # Wekelijkse reset (dinsdag 20:00)
    scheduler.add_job(
        reset_polls,
        CronTrigger(day_of_week="tue", hour=RESET_HOUR, minute=0),
        args=[bot],
        name="Wekelijkse reset dinsdag 20:00",
    )
    # Wekelijkse tenor GIF sync (maandag 00:00)
    scheduler.add_job(
        sync_tenor_links_weekly,
        CronTrigger(day_of_week="mon", hour=0, minute=0),
        args=[bot],
        name="Wekelijkse tenor sync maandag 00:00",
    )
    # Herinneringen (vrijdag, zaterdag, zondag)
    scheduler.add_job(
        notify_non_voters,
        CronTrigger(day_of_week="fri", hour=REMINDER_HOUR, minute=0),
        args=[bot, "vrijdag"],
        name="Herinnering vrijdag",
    )
    scheduler.add_job(
        notify_non_voters,
        CronTrigger(day_of_week="sat", hour=REMINDER_HOUR, minute=0),
        args=[bot, "zaterdag"],
        name="Herinnering zaterdag",
    )
    scheduler.add_job(
        notify_non_voters,
        CronTrigger(day_of_week="sun", hour=REMINDER_HOUR, minute=0),
        args=[bot, "zondag"],
        name="Herinnering zondag",
    )
    # Notificaties als een avond doorgaat (18:05 om race-condities te voorkomen)
    scheduler.add_job(
        notify_voters_if_avond_gaat_door,
        CronTrigger(day_of_week="fri", hour=18, minute=5),
        args=[bot, "vrijdag"],
        name="Notificatie vrijdag",
    )
    scheduler.add_job(
        notify_voters_if_avond_gaat_door,
        CronTrigger(day_of_week="sat", hour=18, minute=5),
        args=[bot, "zaterdag"],
        name="Notificatie zaterdag",
    )
    scheduler.add_job(
        notify_voters_if_avond_gaat_door,
        CronTrigger(day_of_week="sun", hour=18, minute=5),
        args=[bot, "zondag"],
        name="Notificatie zondag",
    )
    scheduler.add_job(
        notify_non_voters_thursday,
        CronTrigger(day_of_week="thu", hour=EARLY_REMINDER_HOUR, minute=0),
        args=[bot],
        name="Herinnering donderdag",
    )
    # Misschien voter notifications (17:00, after regular reminders at 16:00)
    scheduler.add_job(
        notify_misschien_voters,
        CronTrigger(day_of_week="fri", hour=17, minute=0),
        args=[bot, "vrijdag"],
        name="Misschien notificatie vrijdag",
    )
    scheduler.add_job(
        notify_misschien_voters,
        CronTrigger(day_of_week="sat", hour=17, minute=0),
        args=[bot, "zaterdag"],
        name="Misschien notificatie zaterdag",
    )
    scheduler.add_job(
        notify_misschien_voters,
        CronTrigger(day_of_week="sun", hour=17, minute=0),
        args=[bot, "zondag"],
        name="Misschien notificatie zondag",
    )
    # Convert remaining Misschien votes to ❌ at 18:00
    scheduler.add_job(
        convert_remaining_misschien,
        CronTrigger(day_of_week="fri", hour=18, minute=0),
        args=[bot, "vrijdag"],
        name="Convert Misschien vrijdag",
    )
    scheduler.add_job(
        convert_remaining_misschien,
        CronTrigger(day_of_week="sat", hour=18, minute=0),
        args=[bot, "zaterdag"],
        name="Convert Misschien zaterdag",
    )
    scheduler.add_job(
        convert_remaining_misschien,
        CronTrigger(day_of_week="sun", hour=18, minute=0),
        args=[bot, "zondag"],
        name="Convert Misschien zondag",
    )
    # Scheduled poll activation check (every minute)
    scheduler.add_job(
        activate_scheduled_polls,
        CronTrigger(minute="*"),
        args=[bot],
        name="Scheduled poll activation check",
    )
    # Scheduled poll deactivation check (every minute)
    scheduler.add_job(
        deactivate_scheduled_polls,
        CronTrigger(minute="*"),
        args=[bot],
        name="Scheduled poll deactivation check",
    )
    # Retry failed operations (conversions + resets, every minute)
    scheduler.add_job(
        retry_failed_operations,
        CronTrigger(minute="*"),
        args=[bot],
        name="Retry failed operations",
    )
    scheduler.start()
    asyncio.create_task(_run_catch_up_with_lock(bot))


async def update_all_polls(bot) -> None:  # pragma: no cover
    """
    Update per kanaal de poll-berichten binnen rolling window en verwijder oude berichten.
    """
    log_job("update_all_polls", status="executed")
    tasks: List[asyncio.Task] = []

    deny_names = set(
        n.strip().lower()
        for n in os.getenv("DENY_CHANNEL_NAMES", "").split(",")
        if n.strip()
    )
    allow_from_per_channel_only = os.getenv(
        "ALLOW_FROM_PER_CHANNEL_ONLY", "true"
    ).lower() in {"1", "true", "yes", "y"}

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            try:
                cid = int(getattr(channel, "id", 0))
            except Exception:  # pragma: no cover
                cid = 0

            if is_channel_disabled(cid):
                continue

            # Skip if channel is paused
            if is_paused(cid):
                continue

            ch_name = (getattr(channel, "name", "") or "").lower()
            if ch_name in deny_names:
                continue

            has_poll = False
            try:
                for key in ("vrijdag", "zaterdag", "zondag", "stemmen"):
                    if get_message_id(cid, key):
                        has_poll = True
                        break
            except Exception:  # pragma: no cover
                has_poll = False

            if allow_from_per_channel_only and not has_poll:
                continue

            # Gebruik rolling window logica (altijd huidige dag)
            from apps.utils.poll_settings import get_enabled_rolling_window_days

            dagen_info = get_enabled_rolling_window_days(cid, dag_als_vandaag=None)

            # Verwijder oude dag-berichten die niet meer in de rolling window zitten
            from apps.utils.constants import DAG_NAMEN
            from apps.utils.discord_client import fetch_message_or_none, safe_call

            enabled_dagen_set = {day_info["dag"] for day_info in dagen_info}
            for dag_naam in DAG_NAMEN:
                if dag_naam not in enabled_dagen_set:
                    mid = get_message_id(cid, dag_naam)
                    if mid:
                        msg = await fetch_message_or_none(channel, mid)
                        if msg is not None:
                            await safe_call(msg.delete)
                        clear_message_id(cid, dag_naam)

            # Update poll-berichten voor dagen in rolling window
            for day_info in dagen_info:
                dag = day_info["dag"]
                tasks.append(schedule_poll_update(channel, dag, delay=0.0))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def notify_non_voters(  # pragma: no cover
    bot,
    dag: Optional[str] = None,
    channel: Optional[discord.TextChannel] = None,
) -> bool:
    """
    Herinner leden die nog niet hebben gestemd.
    - Zonder channel: loop over alle actieve poll-kanalen (zoals voorheen).
    - Met channel: post alleen in dit kanaal (voor het slash-commando).
    - Met dag: alleen niet-stemmers voor die dag; zonder dag: 'ergens dit weekend' telt als gestemd.
    Alleen voor kanalen in 'deadline' modus (scheduler-oproepen).
    Voor commando-oproepen (met channel parameter) wordt de check overgeslagen.
    Retourneert True als er ergens iets is verstuurd.
    """
    sent_any = False
    log_job("reminder", dag=dag or "(any)", status="executed")

    # Als een specifiek kanaal is opgegeven (via commando), alleen dat kanaal gebruiken
    if channel:
        target_guild = getattr(channel, "guild", None)
        if not target_guild:
            return False
        guilds_to_process = [target_guild]
    else:
        # Scheduler-modus: alle guilds
        guilds_to_process = getattr(bot, "guilds", []) or []

    # DENY_CHANNEL_NAMES check
    deny_names = _get_deny_channel_names()

    def channels_for_guild(guild):
        if channel:
            # Commando-modus: alleen het opgegeven kanaal
            return [channel] if getattr(channel, "guild", None) == guild else []
        # Scheduler-modus: alle actieve poll-kanalen
        candidates = [
            ch
            for ch in (get_channels(guild) or [])
            if not is_channel_disabled(getattr(ch, "id", 0))
            and not is_paused(getattr(ch, "id", 0))
        ]
        # Filter op DENY_CHANNEL_NAMES
        filtered = []
        for ch in candidates:
            ch_name = (getattr(ch, "name", "") or "").lower()
            if ch_name in deny_names:
                continue
            # ALLOW_FROM_PER_CHANNEL_ONLY check verwijderd:
            # Notificaties werken op data-niveau, niet afhankelijk van berichten
            filtered.append(ch)
        return filtered

    for guild in guilds_to_process:
        for ch in channels_for_guild(guild):
            cid = getattr(ch, "id", "0") or "0"

            # Check notification settings: skip als reminders disabled zijn (alleen voor scheduler)
            if not channel:  # Scheduler-modus
                if not is_notification_enabled(int(cid) if cid != "0" else 0, "reminders"):
                    continue

            # Skip kanalen die niet in 'deadline' modus staan (alleen voor scheduler, niet voor commando)
            if not channel and dag:  # Scheduler-modus met specifieke dag
                if not _is_deadline_mode(int(cid) if cid != "0" else 0, dag):
                    continue
                # Check of de dag enabled is voor dit kanaal
                enabled_days = get_enabled_poll_days(int(cid) if cid != "0" else 0)
                if dag not in enabled_days:
                    continue

            # Alleen leden die toegang hebben tot dit specifieke kanaal
            members_src = getattr(ch, "members", [])
            all_members = [m for m in members_src if not getattr(m, "bot", False)]

            gid = getattr(guild, "id", "0")
            votes = await load_votes(gid, cid) or {}

            # Calculate leading time at 17:00 for vote analysis
            if dag:
                try:
                    leading_time = await calculate_leading_time(gid, cid, dag)
                    if leading_time:
                        print(
                            f"📊 Leading time voor {dag} in channel {cid}: {leading_time}"
                        )
                except Exception:  # pragma: no cover
                    pass  # Silent fail, this is informational only

            # Bepaal stemmers
            voted_ids: set[int] = set()
            if dag:
                # dag-specifiek
                for uid, dagen_map in votes.items():
                    owner_str = _extract_owner_id(uid)
                    try:
                        owner = int(owner_str)
                    except Exception:  # pragma: no cover
                        continue
                    if isinstance(dagen_map, dict):
                        tijden = (dagen_map or {}).get(dag, [])
                        if isinstance(tijden, list) and tijden:
                            voted_ids.add(owner)
            else:
                # weekend-breed (oud gedrag)
                for uid, dagen_map in votes.items():
                    owner_str = _extract_owner_id(uid)
                    try:
                        owner = int(owner_str)
                    except Exception:  # pragma: no cover
                        continue
                    if isinstance(dagen_map, dict):
                        for tijden in dagen_map.values():
                            if isinstance(tijden, list) and tijden:
                                voted_ids.add(owner)
                                break

            # Non-stemmers
            to_mention = []
            for m in all_members:
                mid = getattr(m, "id", None)
                if mid and mid not in voted_ids:
                    to_mention.append(getattr(m, "mention", f"<@{mid}>"))

            if not to_mention:
                continue

            # Tekst
            count = len(to_mention)
            count_text = f"**{count} {'lid' if count == 1 else 'leden'}** {'heeft' if count == 1 else 'hebben'} nog niet gestemd. "
            if dag:
                header = (
                    f"📣 DMK-poll – **{dag}**\n{count_text}Als je nog niet gestemd hebt voor **{dag}**, doe dat dan a.u.b. zo snel mogelijk."
                )
            else:
                header = f"📣 DMK-poll – herinnering\n{count_text}Als je nog niet gestemd hebt voor dit weekend, doe dat dan a.u.b. zo snel mogelijk."
            footer = ""

            mentions_str = ", ".join(to_mention)
            text = f"{header}\n{footer}"

            try:
                # Als dag-specifiek: gebruik dynamische non-voter notification met deadline awareness
                if dag:
                    from apps.utils.poll_settings import get_setting

                    # Haal deadline tijd op voor deze dag
                    channel_id_int = int(cid) if cid != "0" else 0
                    setting = get_setting(channel_id_int, dag)
                    deadline_time = setting.get("tijd", "18:00")

                    await send_non_voter_notification(
                        ch,
                        dag=dag,
                        mentions_str=mentions_str,
                        text=header,
                        deadline_time_str=deadline_time,
                    )
                else:
                    # Weekend-breed (legacy): gebruik tijdelijke mentions (5 seconden zichtbaar)
                    await send_temporary_mention(ch, mentions=mentions_str, text=text)

                sent_any = True
            except Exception:  # pragma: no cover
                pass

    return sent_any


async def notify_voters_if_avond_gaat_door(bot, dag: str) -> None:  # pragma: no cover
    """
    Stuur melding als een tijd >= MIN_NOTIFY_VOTES stemmen heeft (gelijkstand → 20:30).
    De deelnemers worden eerst genoemd, daarna volgt de zin 'de DMK-avond van … gaat door'.
    """
    log_job("notify", dag=dag, status="executed")
    KEY_19 = "om 19:00 uur"
    KEY_2030 = "om 20:30 uur"

    # Import TimeZoneHelper voor Hammertime conversie
    from apps.utils.time_zone_helper import TimeZoneHelper

    # DENY_CHANNEL_NAMES check
    deny_names = _get_deny_channel_names()

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            cid = getattr(channel, "id", 0)
            if is_channel_disabled(cid):
                continue

            # Skip if channel is paused
            if is_paused(cid):
                continue

            # Check DENY_CHANNEL_NAMES
            ch_name = (getattr(channel, "name", "") or "").lower()
            if ch_name in deny_names:
                continue

            # ALLOW_FROM_PER_CHANNEL_ONLY check verwijderd:
            # Notificaties werken op data-niveau (votes), niet afhankelijk van berichten

            scoped = (
                await load_votes(
                    getattr(guild, "id", "0"),
                    getattr(channel, "id", "0"),
                )
                or {}
            )

            # Tel totale stemmen (inclusief gasten), niet alleen unieke eigenaren
            c19 = 0
            c2030 = 0
            for uid, per_dag in scoped.items():
                tijden = (per_dag or {}).get(dag, [])
                if not isinstance(tijden, list):
                    continue
                if KEY_19 in tijden:
                    c19 += 1  # Tel elke stem (inclusief gasten)
                if KEY_2030 in tijden:
                    c2030 += 1  # Tel elke stem (inclusief gasten)
            if c19 < MIN_NOTIFY_VOTES and c2030 < MIN_NOTIFY_VOTES:
                continue

            # Bepaal winnende tijd
            if c2030 >= c19:
                winnaar_tijd_str = "20:30"
                winnaar_key = KEY_2030
            else:
                winnaar_tijd_str = "19:00"
                winnaar_key = KEY_19

            # Bereken datum en converteer naar Hammertime
            # Gebruik rolling window om correcte datum te krijgen
            from apps.utils.poll_settings import get_enabled_rolling_window_days
            dagen_info = get_enabled_rolling_window_days(cid, dag_als_vandaag=None)
            datum_iso = None
            for day_info in dagen_info:
                if day_info["dag"] == dag.lower():
                    datum_iso = day_info["datum_iso"]
                    break
            # Dag moet altijd in rolling window zitten - als niet, dan is er een bug
            if datum_iso is None:
                # Stuur foutmelding naar kanaal (zichtbaar voor gebruikers)
                try:
                    await channel.send(
                        f"⚠️ **Fout bij beslissing aankondiging:** Dag '{dag}' niet gevonden in rolling window. "
                        f"Dit zou niet moeten gebeuren. Neem contact op met de beheerder.",
                        delete_after=300
                    )
                except Exception:  # pragma: no cover
                    pass
                continue  # Skip deze dag, ga door met andere enabled dagen

            winnaar_hammertime = TimeZoneHelper.nl_tijd_naar_hammertime(
                datum_iso, winnaar_tijd_str, style="t"
            )

            # Bouw deelnemerslijst met gasten
            channel_members = getattr(channel, "members", [])
            channel_member_ids = {str(getattr(m, "id", "")): m for m in channel_members}

            totaal, mentions_str, participant_list = await build_doorgaan_participant_list(
                dag,
                winnaar_key,
                guild,
                scoped,
                channel_member_ids,
            )

            # Berichttekst - gebruik unified notification layout (5 uur lifetime) met Hammertime
            if participant_list:
                text = f"Totaal {totaal} deelnemers: {participant_list}\nDe DMK-avond van {dag} om {winnaar_hammertime} gaat door! Veel plezier!"
            else:
                text = f"De DMK-avond van {dag} om {winnaar_hammertime} gaat door! Veel plezier!"

            try:
                await send_persistent_mention(channel, mentions_str, text)
            except Exception:  # pragma: no cover
                # Tests willen dat dit niet crasht
                return


async def reset_polls(bot) -> bool:  # pragma: no cover
    """
    Maak stemmen leeg + verwijder bericht-IDs en stuur een resetmelding.
    Reset wordt alleen uitgevoerd in het resetvenster (dinsdag 20:00 - 20:05),
    en alleen als er niet al handmatig gereset is sinds de drempel (zondag 20:30).
    Retourneert True als er echt is gereset, anders False.
    """
    now = datetime.now(TZ)

    # Buiten venster? Sla over.
    if not _within_reset_window(now):
        log_job("reset_polls", status="skipped_outside_window")
        return False

    # Nieuw: skip als er al handmatig (of eerder) is gereset sinds zondag 20:30.
    state = _read_state()
    last_reset_str = state.get("reset_polls")
    threshold = _weekly_reset_threshold(now)
    if last_reset_str:
        try:
            last_dt = datetime.fromisoformat(str(last_reset_str))
            if last_dt.tzinfo is None:
                last_dt = TZ.localize(last_dt)
        except Exception:  # pragma: no cover
            last_dt = None
        if last_dt and last_dt >= threshold:
            # Al gereset deze week → niets doen
            log_job("reset_polls", status="skipped_already_reset")
            return False

    # Uitvoeren: reset alleen kanalen met actieve polls
    log_job("reset_polls", status="executed")
    any_reset = False

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            try:
                cid = int(getattr(channel, "id"))
                gid = int(getattr(guild, "id"))
            except Exception:  # pragma: no cover
                continue

            # Skip als kanaal uitgeschakeld is
            if is_channel_disabled(cid):
                continue

            # Skip als kanaal gepauzeerd is
            if is_paused(cid):
                continue

            # Reset votes voor dit specifieke kanaal
            try:
                await reset_votes_scoped(gid, cid)
                any_reset = True
            except Exception:  # pragma: no cover
                # Fallback naar lege votes voor dit kanaal
                try:
                    from apps.utils.poll_storage import save_votes_scoped

                    await save_votes_scoped(gid, cid, {})
                    any_reset = True
                except Exception:  # pragma: no cover
                    # Beide pogingen gefaald - voeg toe aan retry queue
                    from apps.utils.retry_queue import add_failed_reset
                    add_failed_reset(str(gid), str(cid))
                    pass

            # NIET: dag_als_vandaag opslaan in state
            # We gebruiken altijd de huidige dag bij updates (berekend on-the-fly)

            # Wis celebration message
            try:
                from apps.utils.poll_message import remove_celebration_message

                await remove_celebration_message(channel, cid)
            except Exception:  # pragma: no cover
                pass

            # Wis bekende message IDs (alle weekdagen + stemmen)
            from apps.utils.constants import DAG_NAMEN
            for key in [*DAG_NAMEN, "stemmen"]:
                try:
                    clear_message_id(cid, key)
                except Exception:  # pragma: no cover
                    pass

            # Stuur resetbericht alleen in dit kanaal via notificatiebericht
            try:
                await send_temporary_mention(
                    channel,
                    mentions="@everyone",
                    text="De poll is zojuist gereset voor het nieuwe weekend. Je kunt weer stemmen. Veel plezier!",
                )
            except Exception:  # pragma: no cover
                continue

    # Als geen enkel kanaal gereset werd, val terug op globale reset
    if not any_reset:
        try:
            await reset_votes()
        except Exception:  # pragma: no cover
            pass

    # State bijwerken (nu is er wél gereset)
    try:
        state["reset_polls"] = now.isoformat()
        _write_state(state)
    except Exception:  # pragma: no cover
        pass

    return True


async def notify_for_channel(channel, dag: str) -> bool:  # pragma: no cover
    """
    Stuur dezelfde notificatie die de scheduler normaal zou plaatsen,
    maar dan alleen in het opgegeven kanaal. Geeft True terug als er iets
    is verstuurd, anders False.
    Respecteert uitgeschakelde kanalen, DENY_CHANNEL_NAMES en
    (optioneel) 'alleen in actieve poll-kanalen'.
    """
    try:
        if is_channel_disabled(getattr(channel, "id", 0)):
            return False

        # DENY-lijst
        deny_names = set(
            n.strip().lower()
            for n in os.getenv("DENY_CHANNEL_NAMES", "").split(",")
            if n.strip()
        )
        ch_name = (getattr(channel, "name", "") or "").lower()
        if ch_name in deny_names:
            return False

        # ALLOW_FROM_PER_CHANNEL_ONLY check verwijderd:
        # Notificaties werken op data-niveau, niet afhankelijk van berichten

        guild = getattr(channel, "guild", None)
        gid = getattr(guild, "id", "0") if guild is not None else "0"
        cid = getattr(channel, "id", "0") or "0"

        votes = await load_votes(gid, cid) or {}

        # Tel stemmen per tijdslot (zoals notify_voters_if_avond_gaat_door)
        counts: dict[str, int] = {}
        for per_dag in votes.values():
            try:
                tijden = (per_dag or {}).get(dag, [])
                if isinstance(tijden, list):
                    for t in tijden:
                        counts[t] = counts.get(t, 0) + 1
            except Exception:  # pragma: no cover
                continue

        if not counts:
            return False

        winner = None
        max_count = -1
        for slot, cnt in counts.items():
            if cnt > max_count:
                winner, max_count = slot, cnt
            elif cnt == max_count:
                if "20:30" in slot and "20:30" not in (winner or ""):
                    winner = slot

        if max_count < MIN_NOTIFY_VOTES:
            return False

        tekst = f"📣 Er zijn **{max_count}** stemmen voor **{dag} {winner}**. Zien we je daar?"
        await safe_call(channel.send, tekst)
        log_job("notify", dag=dag, status="executed")
        return True
    except Exception:  # pragma: no cover
        # In commands willen we nooit crashen
        return False


# ========================================================================
# Misschien Confirmation Flow (17:00 - 18:00)
# ========================================================================


async def notify_misschien_voters(bot, dag: str) -> None:  # pragma: no cover
    """
    Notify "Misschien" voters at 17:00 with Stem Nu button.
    Alleen voor kanalen in 'deadline' modus.

    Flow:
    1. Find all users with "misschien" vote for this dag
    2. Calculate leading time (19:00 or 20:30)
    3. Send temporary mention with "Stem nu" button
    4. Button persists until 18:00

    Args:
        bot: Discord bot instance
        dag: Day to notify for (vrijdag, zaterdag, zondag)
    """
    log_job("misschien_notify", dag=dag, status="executed")

    # DENY_CHANNEL_NAMES check
    deny_names = _get_deny_channel_names()

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            cid = getattr(channel, "id", 0)
            if is_channel_disabled(cid):
                continue

            # Skip if channel is paused
            if is_paused(cid):
                continue

            # Check notification settings: skip als misschien notifications disabled zijn
            if not is_notification_enabled(cid, "misschien"):
                continue

            # Skip kanalen die niet in 'deadline' modus staan
            # (misschien-notificaties zijn alleen relevant voor deadline-scenario)
            if not _is_deadline_mode(cid, dag):
                continue

            # Check DENY_CHANNEL_NAMES
            ch_name = (getattr(channel, "name", "") or "").lower()
            if ch_name in deny_names:
                continue

            # ALLOW_FROM_PER_CHANNEL_ONLY check verwijderd:
            # Notificaties werken op data-niveau (votes), niet afhankelijk van berichten

            gid = getattr(guild, "id", "0")
            votes = await load_votes(gid, cid) or {}

            # Vind "misschien" stemmers voor deze dag
            misschien_voter_ids = await _get_voted_ids(votes, dag=dag, vote_type="misschien")
            misschien_voters = _get_non_voter_mentions(channel, set())

            # Filter alleen voor mensen die "misschien" hebben gestemd
            misschien_voters = []
            for member in getattr(channel, "members", []):
                if getattr(member, "bot", False):
                    continue
                mid = getattr(member, "id", None)
                if mid and mid in misschien_voter_ids:
                    mention = getattr(member, "mention", f"<@{mid}>")
                    if mention:
                        misschien_voters.append(mention)

            if not misschien_voters:
                continue  # No misschien voters in this channel

            # Calculate leading time
            leading_time = None
            try:
                leading_time = await calculate_leading_time(gid, cid, dag)
            except Exception:  # pragma: no cover
                pass

            if not leading_time:
                # No clear winner yet, skip for now
                continue

            # Send temporary mention with button
            mentions_str = ", ".join(misschien_voters)
            count = len(misschien_voters)
            text = (
                f"**{count} {'lid' if count == 1 else 'leden'}** {'heeft' if count == 1 else 'hebben'} op :m: **Misschien** gestemd. "
                f"Als je op **Misschien** hebt gestemd: wil je vanavond meedoen?\n"
                "Klik op **Stem nu** om je stem te bevestigen."
            )

            try:
                await send_temporary_mention(
                    channel,
                    mentions=mentions_str,
                    text=text,
                    show_button=True,
                    dag=dag,
                    leading_time=leading_time,
                )
            except Exception:  # pragma: no cover
                # Silent fail
                pass


async def deactivate_scheduled_polls(bot) -> None:  # pragma: no cover
    """
    Deactiveer polls die volgens het schema gedeactiveerd moeten worden.
    Dit wordt elke minuut uitgevoerd en controleert:
    1. Datum-gebaseerde schedules (eenmalig)
    2. Wekelijkse schedules

    Dit is de tegenhanger van activate_scheduled_polls voor /dmk-poll-off.
    """
    from apps.utils.poll_settings import (
        clear_scheduled_deactivation,
        get_effective_activation,
        get_effective_deactivation,
    )

    now = datetime.now(TZ)
    current_date = now.date().isoformat()  # YYYY-MM-DD
    current_time = now.strftime("%H:%M")
    current_weekday = now.weekday()
    weekday_names = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    current_dag = weekday_names[current_weekday]

    log_job("deactivate_scheduled_polls", status="executed")

    # Doorloop alle guilds en kanalen
    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            cid = getattr(channel, "id", 0)

            # Skip disabled channels (al uitgeschakeld)
            if is_channel_disabled(cid):
                continue

            # KRITIEK: Skip channels die nooit geactiveerd zijn geweest
            # Een channel is alleen "actief" als het minimaal 1 poll message heeft
            # Dit voorkomt dat de scheduler leaked naar kanalen waar de bot nooit is aangezet
            dagen = get_enabled_poll_days(cid)
            has_any_poll_message = any(get_message_id(cid, dag) for dag in dagen)
            if not has_any_poll_message:
                # Channel heeft geen poll messages, dus is nooit geactiveerd
                continue

            # Haal effective deactivation schedule op (met fallback naar default)
            schedule, _is_default = get_effective_deactivation(cid)
            if not schedule:
                continue

            activation_type = schedule.get("type")
            scheduled_time = schedule.get("tijd", "00:00")

            # Check of het tijd is om te deactiveren
            should_deactivate = False

            if activation_type == "datum":
                # Eenmalige deactivatie op specifieke datum
                scheduled_date = schedule.get("datum")
                if scheduled_date == current_date and scheduled_time == current_time:
                    should_deactivate = True
                    # Na deactivatie: wis de eenmalige schedule
                    try:
                        clear_scheduled_deactivation(cid)
                    except Exception:  # pragma: no cover
                        pass

            elif activation_type == "wekelijks":
                # Wekelijkse deactivatie op specifieke dag
                scheduled_dag = schedule.get("dag")
                if scheduled_dag == current_dag and scheduled_time == current_time:
                    should_deactivate = True

            if should_deactivate:
                # Deactiveer de polls: kanaal leegmaken + scheduler uitschakelen
                try:
                    dagen = get_enabled_poll_days(cid)

                    # 0) Opening bericht verwijderen
                    opening_mid = get_message_id(cid, "opening")
                    if opening_mid:
                        opening_msg = await fetch_message_or_none(channel, opening_mid)
                        if opening_msg is not None:
                            try:
                                await safe_call(opening_msg.delete)
                            except Exception:  # pragma: no cover
                                await safe_call(
                                    opening_msg.edit, content="📴 Poll gesloten.", view=None
                                )
                        clear_message_id(cid, "opening")

                    # 1) Dag-berichten verwijderen
                    for dag in dagen:
                        mid = get_message_id(cid, dag)
                        if not mid:
                            continue
                        msg = await fetch_message_or_none(channel, mid)
                        if msg is not None:
                            try:
                                await safe_call(msg.delete)
                            except Exception:  # pragma: no cover
                                afsluit_tekst = "📴 Deze poll is gesloten. Dank voor je deelname."
                                await safe_call(msg.edit, content=afsluit_tekst, view=None)
                        clear_message_id(cid, dag)

                    # 2) Stemmen-bericht verwijderen
                    s_mid = get_message_id(cid, "stemmen")
                    if s_mid:
                        s_msg = await fetch_message_or_none(channel, s_mid)
                        if s_msg is not None:
                            try:
                                await safe_call(s_msg.delete)
                            except Exception:  # pragma: no cover
                                await safe_call(
                                    s_msg.edit, content="📴 Stemmen gesloten.", view=None
                                )
                        clear_message_id(cid, "stemmen")

                    # 3) Notificatieberichten verwijderen (temp, persistent en legacy)
                    await _clear_notification_messages(channel, cid)

                    # 3b) Celebration berichten verwijderen (embed + GIF)
                    try:
                        from apps.utils.poll_message import remove_celebration_message
                        await remove_celebration_message(channel, cid)
                    except Exception:  # pragma: no cover
                        pass

                    # 4) Archiveer huidige week's data voordat we deactiveren
                    try:
                        from apps.utils.archive import append_week_snapshot_scoped
                        gid = getattr(guild, "id", 0)
                        await append_week_snapshot_scoped(gid, cid, channel=channel)
                    except Exception as e:  # pragma: no cover
                        print(f"⚠️ Archiveren bij deactivatie mislukt: {e}")

                    # 5) Post sluitingsbericht met heropening tijd
                    try:
                        from apps.utils.notification_texts import (
                            format_opening_time_from_schedule,
                            get_text_poll_gesloten,
                        )

                        act_schedule, _ = get_effective_activation(cid)
                        opening_time = format_opening_time_from_schedule(act_schedule)
                        sluitingsbericht = get_text_poll_gesloten(opening_time)

                        send = getattr(channel, "send", None)
                        if send:
                            await safe_call(send, content=sluitingsbericht)
                    except Exception as e:  # pragma: no cover
                        print(f"⚠️ Sluitingsbericht versturen mislukt: {e}")

                    # BELANGRIJK: Kanaal NIET disablen bij automatische deactivatie!
                    # Het kanaal moet automatisch weer geopend kunnen worden op de geplande tijd.
                    # Alleen handmatige /dmk-poll-stopzetten mag het kanaal permanent disablen.

                    print(f"✅ Automatisch gedeactiveerd: kanaal {cid} volgens schedule")

                except Exception as e:  # pragma: no cover
                    print(f"❌ Fout bij automatische deactivatie voor kanaal {cid}: {e}")


async def activate_scheduled_polls(bot) -> None:  # pragma: no cover
    """
    Activeer polls die volgens het schema geactiveerd moeten worden.
    Dit wordt elke minuut uitgevoerd en controleert:
    1. Datum-gebaseerde schedules (eenmalig)
    2. Wekelijkse schedules

    Prioriteit: handmatig > datum > wekelijks
    (Handmatige activatie wordt afgehandeld door /dmk-poll-on zelf)
    """
    from apps.utils.poll_settings import clear_scheduled_activation, get_effective_activation

    now = datetime.now(TZ)
    current_date = now.date().isoformat()  # YYYY-MM-DD
    current_time = now.strftime("%H:%M")
    current_weekday = now.weekday()
    weekday_names = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    current_dag = weekday_names[current_weekday]

    log_job("activate_scheduled_polls", status="executed")

    # Doorloop alle guilds en kanalen
    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            cid = getattr(channel, "id", 0)

            # Skip disabled channels (handmatig uitgeschakeld met /dmk-poll-off)
            # Automatische deactivatie disabled het kanaal NIET, dus dit is veilig
            if is_channel_disabled(cid):
                continue

            # KRITIEK: Skip channels die nooit geactiveerd zijn geweest
            # Een channel is alleen "actief" als het minimaal 1 poll message heeft
            # Dit voorkomt dat de scheduler leaked naar kanalen waar de bot nooit is aangezet
            dagen = get_enabled_poll_days(cid)
            has_any_poll_message = any(get_message_id(cid, dag) for dag in dagen)
            if not has_any_poll_message:
                # Channel heeft geen poll messages, dus is nooit geactiveerd
                continue

            # Haal effective schedule op (met fallback naar default)
            schedule, _is_default = get_effective_activation(cid)
            if not schedule:
                continue

            activation_type = schedule.get("type")
            scheduled_time = schedule.get("tijd", "20:00")

            # Check of het tijd is om te activeren
            should_activate = False

            if activation_type == "datum":
                # Eenmalige activatie op specifieke datum
                scheduled_date = schedule.get("datum")
                if scheduled_date == current_date and scheduled_time == current_time:
                    should_activate = True
                    # Na activatie: wis de eenmalige schedule
                    try:
                        clear_scheduled_activation(cid)
                    except Exception:  # pragma: no cover
                        pass

            elif activation_type == "wekelijks":
                # Wekelijkse activatie op specifieke dag
                scheduled_dag = schedule.get("dag")
                if scheduled_dag == current_dag and scheduled_time == current_time:
                    should_activate = True

            if should_activate:
                # Activeer de polls via een mock interaction
                # We kunnen niet de normale _plaats_polls gebruiken zonder interaction,
                # dus we moeten de activatie-logica hier dupliceren of een helper maken
                try:
                    # Import hier om circular dependency te voorkomen
                    from apps.utils.poll_message import update_poll_message
                    from apps.ui.poll_buttons import OneStemButtonView

                    # Kanaal activeren
                    set_channel_disabled(cid, False)

                    # Unpause
                    try:
                        from apps.utils.poll_settings import set_paused
                        set_paused(cid, False)
                    except Exception:  # pragma: no cover
                        pass

                    # Reset votes voor schone start (Bug #3 fix)
                    # Dit zorgt ervoor dat de poll altijd met 0 stemmen start,
                    # ongeacht wanneer de activatie plaatsvindt (bijv. dinsdag 13:33)
                    try:
                        gid = getattr(guild, "id", 0)
                        await reset_votes_scoped(gid, cid)
                    except Exception:  # pragma: no cover
                        pass

                    send = getattr(channel, "send", None)

                    # STAP 1: Verwijder ALLE bestaande bot-berichten (opschonen)
                    # Dit zorgt voor een schone start zoals /dmk-poll-on doet
                    try:
                        bot_user = getattr(bot, "user", None)
                        if bot_user:
                            bot_user_id = getattr(bot_user, "id", None)
                            if bot_user_id and hasattr(channel, "history"):
                                # channel.history returns AsyncIterator[discord.Message]
                                async for bericht in channel.history(limit=100):  # type: ignore[attr-defined]
                                    author = getattr(bericht, "author", None)
                                    if author:
                                        author_id = getattr(author, "id", None)
                                        if author_id == bot_user_id:
                                            try:
                                                await bericht.delete()
                                            except Exception:  # pragma: no cover
                                                pass
                    except Exception as e:  # pragma: no cover
                        print(f"⚠️ Kon bot-berichten niet verwijderen: {e}")

                    # Wis alle message IDs na cleanup
                    for key in ["opening", "vrijdag", "zaterdag", "zondag", "maandag", "dinsdag", "woensdag", "donderdag", "stemmen", "notification", "notification_persistent"]:
                        try:
                            clear_message_id(cid, key)
                        except Exception:  # pragma: no cover
                            pass

                    # STAP 2: Opening bericht (nu nieuw aanmaken met dynamisch gegenereerde tekst)
                    from apps.commands.poll_lifecycle import _load_opening_message
                    opening_text = _load_opening_message(channel_id=cid)
                    if send:
                        opening_msg = await safe_call(send, content=opening_text)
                        if opening_msg is not None:
                            save_message_id(cid, "opening", opening_msg.id)

                    # STAP 3: Dag-berichten creëren (nieuw)
                    for dag in get_enabled_poll_days(cid):
                        await update_poll_message(channel, dag)

                    # STAP 4: Stemmen-knop bericht (nieuw aanmaken)
                    key = "stemmen"
                    tekst = "Klik op **🗳️ Stemmen** om je keuzes te maken."
                    paused = is_paused(cid)
                    view = OneStemButtonView(paused=paused)

                    if send:
                        s_msg = await safe_call(send, content=tekst, view=view)
                        if s_msg is not None:
                            save_message_id(cid, key, s_msg.id)

                    # STAP 5: Bereken HammerTime voor de activatietijd (voor notificatie en mention)
                    from apps.utils.time_zone_helper import TimeZoneHelper
                    from zoneinfo import ZoneInfo

                    hammertime_str = ""
                    if activation_type == "datum":
                        scheduled_date = schedule.get("datum")
                        if scheduled_date:
                            hammertime_str = TimeZoneHelper.nl_tijd_naar_hammertime(
                                scheduled_date, scheduled_time, style="t"
                            )
                    elif activation_type == "wekelijks":
                        # Voor wekelijkse activatie: gebruik vandaag als datum
                        now = datetime.now(ZoneInfo("Europe/Amsterdam"))
                        current_date_obj = now.date()
                        hammertime_str = TimeZoneHelper.nl_tijd_naar_hammertime(
                            current_date_obj.strftime("%Y-%m-%d"), scheduled_time, style="t"
                        )

                    # STAP 6: Notificatiebericht met HammerTime (altijd nieuw aanmaken na cleanup)
                    # Dit voorkomt dubbele notificatieberichten (Bug 4)
                    await create_notification_message(
                        channel, activation_hammertime=hammertime_str if hammertime_str else None
                    )

                    # STAP 7: Openingsmentions versturen met HammerTime
                    try:
                        from apps.utils.mention_utils import send_temporary_mention

                        if hammertime_str:
                            opening_notification = f"De DMK-poll-bot is zojuist aangezet om {hammertime_str}. Veel plezier met de stemmen! 🎮"
                        else:
                            opening_notification = "De DMK-poll-bot is zojuist aangezet. Veel plezier met de stemmen! 🎮"

                        await send_temporary_mention(
                            channel, mentions="@everyone", text=opening_notification
                        )
                    except Exception as e:  # pragma: no cover
                        print(f"⚠️ Openingsbericht versturen mislukt: {e}")

                    print(f"✅ Automatisch geactiveerd: kanaal {cid} volgens schedule")

                except Exception as e:  # pragma: no cover
                    print(f"❌ Fout bij automatische activatie voor kanaal {cid}: {e}")


async def convert_remaining_misschien(bot, dag: str) -> None:  # pragma: no cover
    """
    Convert remaining "Misschien" votes to ❌ at 18:00.
    Alleen voor kanalen in 'deadline' modus.

    Flow:
    1. Find all users still with "misschien" vote for this dag
    2. Convert their votes to "niet meedoen"
    3. Update poll messages
    4. Clear button from notification message

    Args:
        bot: Discord bot instance
        dag: Day to convert for (vrijdag, zaterdag, zondag)
    """
    log_job("convert_misschien", dag=dag, status="executed")

    # DENY_CHANNEL_NAMES check
    deny_names = _get_deny_channel_names()

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            cid = getattr(channel, "id", 0)
            if is_channel_disabled(cid):
                continue

            # Skip if channel is paused
            if is_paused(cid):
                continue

            # Skip kanalen die niet in 'deadline' modus staan
            # (misschien-conversie is alleen relevant voor deadline-scenario)
            if not _is_deadline_mode(cid, dag):
                continue

            # Check DENY_CHANNEL_NAMES
            ch_name = (getattr(channel, "name", "") or "").lower()
            if ch_name in deny_names:
                continue

            # ALLOW_FROM_PER_CHANNEL_ONLY check verwijderd:
            # Notificaties werken op data-niveau (votes), niet afhankelijk van berichten

            gid = getattr(guild, "id", "0")
            votes = await load_votes(gid, cid) or {}

            # Find remaining "misschien" voters and convert them
            converted_any = False
            misschien_count = 0
            for uid, per_dag in votes.items():
                tijden = (per_dag or {}).get(dag, [])
                if not isinstance(tijden, list):
                    continue

                if "misschien" in tijden:
                    # Convert to "niet meedoen"
                    try:
                        from apps.utils.poll_storage import add_vote, remove_vote

                        await remove_vote(str(uid), dag, "misschien", gid, cid)
                        await add_vote(str(uid), dag, "niet meedoen", gid, cid)
                        converted_any = True
                        misschien_count += 1
                    except Exception:  # pragma: no cover
                        # Voeg toe aan retry queue voor 2 uur retry window
                        from apps.utils.retry_queue import add_failed_conversion
                        add_failed_conversion(str(gid), str(cid), str(uid), dag)
                        continue

            # Store the count of converted misschien votes
            if misschien_count > 0:
                try:
                    from apps.utils.poll_storage import set_was_misschien_count

                    await set_was_misschien_count(dag, misschien_count, gid, cid)
                except Exception:  # pragma: no cover
                    pass

            # Update poll message if we converted anyone
            if converted_any:
                try:
                    await schedule_poll_update(channel, dag, delay=0.0)
                except Exception:  # pragma: no cover
                    pass

            # Delete notification messages if they still exist (should auto-delete anyway)
            # Since misschien notification is at 17:00 and conversion is at 18:00,
            # the notification will be auto-deleted. This is a safety cleanup.
            # Wis alle notificatieberichten (temp, persistent en legacy)
            try:
                await _clear_notification_messages(channel, cid)
            except Exception:  # pragma: no cover
                pass
