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

from apps.utils.discord_client import get_channels, safe_call
from apps.utils.logger import log_job, log_startup
from apps.utils.mention_utils import send_persistent_mention, send_temporary_mention
from apps.utils.poll_message import (
    clear_message_id,
    get_message_id,
    is_channel_disabled,
    schedule_poll_update,
)
from apps.utils.poll_settings import is_paused
from apps.utils.poll_storage import (
    calculate_leading_time,
    load_votes,
    reset_votes,
    reset_votes_scoped,
)

# NL-tijdzone
TZ = pytz.timezone("Europe/Amsterdam")
scheduler = AsyncIOScheduler(timezone=TZ)

CONFIG_PATH = os.getenv("POLL_SETTINGS_FILE", "poll_settings.json")

MIN_NOTIFY_VOTES = 6

# Nieuw: herinneringstijd en resetinstellingen
REMINDER_HOUR = 17  # 17:00 uur - stuur herinnering vóór de deadline
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
    except Exception:
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
        except Exception:
            # Kapotte of lege state? Dan gewoon uitvoeren.
            return True

    # zorg dat last_dt tz-aware is
    if last_dt.tzinfo is None:
        last_dt = TZ.localize(last_dt)

    # gelijk → NIET runnen; alleen draaien als last_dt < occurrence
    return last_dt < occurrence


async def notify_non_voters_thursday(bot) -> None:
    """
    Herinner leden die voor geen enkele dag hebben gestemd (donderdagavond).
    Dit wordt één keer per week verstuurd.
    """
    # DENY_CHANNEL_NAMES en ALLOW_FROM_PER_CHANNEL_ONLY checks
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

            # Check ALLOW_FROM_PER_CHANNEL_ONLY
            if allow_from_per_channel_only:
                try:
                    has_poll = any(
                        get_message_id(cid, key)
                        for key in ("vrijdag", "zaterdag", "zondag", "stemmen")
                    )
                    if not has_poll:
                        continue
                except Exception:
                    continue
            scoped = (
                await load_votes(getattr(guild, "id", "0"), getattr(channel, "id", "0"))
                or {}
            )
            # verzamel IDs die voor één of meer dagen hebben gestemd
            voted_ids: set[str] = set()
            for uid, per_dag in scoped.items():
                for tijden in (per_dag or {}).values():
                    if tijden:
                        actual_uid = (
                            uid.split("_guest::", 1)[0]
                            if "_guest::" in str(uid)
                            else uid
                        )
                        voted_ids.add(str(actual_uid))
            # Alleen leden die toegang hebben tot dit specifieke kanaal
            members = getattr(channel, "members", [])
            non_voters: list[str] = []
            for member in members:
                if getattr(member, "bot", False):
                    continue
                m_id = str(getattr(member, "id", ""))
                if m_id not in voted_ids:
                    mention = getattr(member, "mention", None)
                    if mention:
                        non_voters.append(mention)
            if non_voters:
                # Gebruik tijdelijke mentions (2 seconden zichtbaar)
                mentions_str = ", ".join(non_voters)
                text = "Jullie hebben nog niet gestemd voor dit weekend. Graag stemmen vóór 18:00. Dank!"
                try:
                    await send_temporary_mention(
                        channel, mentions=mentions_str, text=text
                    )
                except Exception:
                    pass


def _read_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
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


async def _run_catch_up(bot) -> None:
    """
    Catch-up na herstart: voer gemiste jobs maximaal één keer uit.
    Reset alleen in het nieuwe venster (dinsdag 20:00 - 20:05).
    """
    now = datetime.now(TZ)
    state = _read_state()
    missed: list[str] = []

    # Dagelijkse update (18:00)
    last_update = state.get("update_all_polls")
    today_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
    last_sched_update = today_18 if now >= today_18 else today_18 - timedelta(days=1)
    if should_run(last_update, last_sched_update):
        await update_all_polls(bot)
        state["update_all_polls"] = now.isoformat()
        missed.append("update_all_polls")
        log_job("update_all_polls", status="executed")
    else:
        log_job("update_all_polls", status="skipped")

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

    # Altijd state schrijven en loggen, ongeacht of Thursday reminder runde
    _write_state(state)
    log_startup(missed)


async def _run_catch_up_with_lock(bot) -> None:
    """Catch-up met file-lock (voorkomt dubbele runs bij snelle herstarts)."""
    try:
        if os.path.exists(LOCK_PATH):
            try:
                mtime = os.path.getmtime(LOCK_PATH)
                if (datetime.now().timestamp() - mtime) < 300:
                    return
                else:
                    os.remove(LOCK_PATH)
            except Exception:
                pass

        with open(LOCK_PATH, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

        await _run_catch_up(bot)
    finally:
        try:
            if os.path.exists(LOCK_PATH):
                os.remove(LOCK_PATH)
        except Exception:
            pass


def setup_scheduler(bot) -> None:
    """
    Plan periodieke jobs en start de scheduler.
    - Pollupdate elke dag om 18:00.
    - Herinnering niet-stemmers op vr/za/zo om 17:00.
    - Notificatie dat een avond doorgaat op vr/za/zo om 18:05.
    - Reset op dinsdag om 20:00.
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
    # Misschien voter notifications (17:05, after regular reminders)
    scheduler.add_job(
        notify_misschien_voters,
        CronTrigger(day_of_week="fri", hour=17, minute=5),
        args=[bot, "vrijdag"],
        name="Misschien notificatie vrijdag",
    )
    scheduler.add_job(
        notify_misschien_voters,
        CronTrigger(day_of_week="sat", hour=17, minute=5),
        args=[bot, "zaterdag"],
        name="Misschien notificatie zaterdag",
    )
    scheduler.add_job(
        notify_misschien_voters,
        CronTrigger(day_of_week="sun", hour=17, minute=5),
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
    scheduler.start()
    asyncio.create_task(_run_catch_up_with_lock(bot))


async def update_all_polls(bot) -> None:
    """
    Update per kanaal de poll-berichten (vrijdag, zaterdag, zondag) als er al polls zijn.
    Deze functie blijft ongewijzigd.
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
            except Exception:
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
            except Exception:
                has_poll = False

            if allow_from_per_channel_only and not has_poll:
                continue

            for dag in ["vrijdag", "zaterdag", "zondag"]:
                tasks.append(schedule_poll_update(channel, dag, delay=0.0))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def notify_non_voters(
    bot,
    dag: Optional[str] = None,
    channel: Optional[discord.TextChannel] = None,
) -> bool:
    """
    Herinner leden die nog niet hebben gestemd.
    - Zonder channel: loop over alle actieve poll-kanalen (zoals voorheen).
    - Met channel: post alleen in dit kanaal (voor het slash-commando).
    - Met dag: alleen niet-stemmers voor die dag; zonder dag: 'ergens dit weekend' telt als gestemd.
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

    # DENY_CHANNEL_NAMES en ALLOW_FROM_PER_CHANNEL_ONLY checks
    deny_names = set(
        n.strip().lower()
        for n in os.getenv("DENY_CHANNEL_NAMES", "").split(",")
        if n.strip()
    )
    allow_from_per_channel_only = os.getenv(
        "ALLOW_FROM_PER_CHANNEL_ONLY", "true"
    ).lower() in {"1", "true", "yes", "y"}

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
            # Filter op ALLOW_FROM_PER_CHANNEL_ONLY
            if allow_from_per_channel_only:
                try:
                    cid = int(getattr(ch, "id", 0))
                    has_poll = any(
                        get_message_id(cid, key)
                        for key in ("vrijdag", "zaterdag", "zondag", "stemmen")
                    )
                    if not has_poll:
                        continue
                except Exception:
                    continue
            filtered.append(ch)
        return filtered

    for guild in guilds_to_process:
        for ch in channels_for_guild(guild):
            # Alleen leden die toegang hebben tot dit specifieke kanaal
            members_src = getattr(ch, "members", [])
            all_members = [m for m in members_src if not getattr(m, "bot", False)]

            gid = getattr(guild, "id", "0")
            cid = getattr(ch, "id", "0") or "0"
            votes = await load_votes(gid, cid) or {}

            # Calculate leading time at 17:00 for vote analysis
            if dag:
                try:
                    leading_time = await calculate_leading_time(gid, cid, dag)
                    if leading_time:
                        print(
                            f"📊 Leading time voor {dag} in channel {cid}: {leading_time}"
                        )
                except Exception:
                    pass  # Silent fail, this is informational only

            # Bepaal stemmers
            voted_ids: set[int] = set()
            if dag:
                # dag-specifiek
                for uid, dagen_map in votes.items():
                    owner_str = (
                        uid.split("_guest::", 1)[0]
                        if isinstance(uid, str)
                        else str(uid)
                    )
                    try:
                        owner = int(owner_str)
                    except Exception:
                        continue
                    if isinstance(dagen_map, dict):
                        tijden = (dagen_map or {}).get(dag, [])
                        if isinstance(tijden, list) and tijden:
                            voted_ids.add(owner)
            else:
                # weekend-breed (oud gedrag)
                for uid, dagen_map in votes.items():
                    owner_str = (
                        uid.split("_guest::", 1)[0]
                        if isinstance(uid, str)
                        else str(uid)
                    )
                    try:
                        owner = int(owner_str)
                    except Exception:
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
            if dag:
                header = (
                    f"📣 DMK-poll – **{dag}**\nJe hebt nog niet gestemd voor **{dag}**."
                )
            else:
                header = "📣 DMK-poll – herinnering\nJe hebt nog niet gestemd voor dit weekend."
            footer = "Stem a.u.b. in deze poll zo snel mogelijk."

            # Gebruik tijdelijke mentions (2 seconden zichtbaar)
            mentions_str = ", ".join(to_mention)
            text = f"{header}\n{footer}"

            try:
                await send_temporary_mention(ch, mentions=mentions_str, text=text)
                sent_any = True
            except Exception:
                pass

    return sent_any


async def notify_voters_if_avond_gaat_door(bot, dag: str) -> None:
    """
    Stuur melding als een tijd >= MIN_NOTIFY_VOTES stemmen heeft (gelijkstand → 20:30).
    De deelnemers worden eerst genoemd, daarna volgt de zin 'de DMK-avond van … gaat door'.
    """
    log_job("notify", dag=dag, status="executed")
    KEY_19 = "om 19:00 uur"
    KEY_2030 = "om 20:30 uur"

    # DENY_CHANNEL_NAMES en ALLOW_FROM_PER_CHANNEL_ONLY checks
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

            # Check ALLOW_FROM_PER_CHANNEL_ONLY
            if allow_from_per_channel_only:
                try:
                    has_poll = any(
                        get_message_id(cid, key)
                        for key in ("vrijdag", "zaterdag", "zondag", "stemmen")
                    )
                    if not has_poll:
                        continue
                except Exception:
                    continue

            scoped = (
                await load_votes(
                    getattr(guild, "id", "0"),
                    getattr(channel, "id", "0"),
                )
                or {}
            )

            voters_19: set[str] = set()
            voters_2030: set[str] = set()
            for uid, per_dag in scoped.items():
                tijden = (per_dag or {}).get(dag, [])
                if not isinstance(tijden, list):
                    continue
                if KEY_19 in tijden:
                    # gasten bevatten "_guest::"; neem eigenaar
                    actual_uid = (
                        uid.split("_guest::", 1)[0]
                        if isinstance(uid, str) and "_guest::" in uid
                        else uid
                    )
                    voters_19.add(str(actual_uid))
                if KEY_2030 in tijden:
                    actual_uid = (
                        uid.split("_guest::", 1)[0]
                        if isinstance(uid, str) and "_guest::" in uid
                        else uid
                    )
                    voters_2030.add(str(actual_uid))

            c19, c2030 = len(voters_19), len(voters_2030)
            if c19 < MIN_NOTIFY_VOTES and c2030 < MIN_NOTIFY_VOTES:
                continue

            # Bepaal winnende tijd
            if c2030 >= c19:
                winnaar_txt = "20:30"
                winner_set = voters_2030
            else:
                winnaar_txt = "19:00"
                winner_set = voters_19

            # Bouw mention-lijst op basis van channel members (alleen wie toegang heeft)
            channel_members = getattr(channel, "members", [])
            channel_member_ids = {str(getattr(m, "id", "")): m for m in channel_members}
            mentions: List[str] = []
            for uid in winner_set:
                try:
                    member = channel_member_ids.get(str(uid))
                    if member and getattr(member, "mention", None):
                        mentions.append(member.mention)
                except Exception:
                    continue

            # Berichttekst - gebruik persistente mentions (blijven tot 23:00)
            if mentions:
                prefix = ", ".join(mentions)
                message = f"{prefix} - de DMK-avond van {dag} om {winnaar_txt} gaat door! Veel plezier!"
            else:
                message = (
                    f"De DMK-avond van {dag} om {winnaar_txt} gaat door! Veel plezier!"
                )

            try:
                await send_persistent_mention(channel, message)
            except Exception:
                # Tests willen dat dit niet crasht
                return


async def reset_polls(bot) -> bool:
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
        except Exception:
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
            except Exception:
                continue

            # Check of dit kanaal actieve poll-berichten heeft
            has_poll = False
            for key in ["vrijdag", "zaterdag", "zondag", "stemmen"]:
                try:
                    if get_message_id(cid, key):
                        has_poll = True
                        break
                except Exception:
                    pass

            if not has_poll:
                continue  # Skip kanalen zonder actieve polls

            # Reset votes voor dit specifieke kanaal
            try:
                await reset_votes_scoped(gid, cid)
                any_reset = True
            except Exception:
                # Fallback naar lege votes voor dit kanaal
                try:
                    from apps.utils.poll_storage import save_votes_scoped

                    await save_votes_scoped(gid, cid, {})
                    any_reset = True
                except Exception:
                    pass

            # Wis bekende message IDs
            for key in ["vrijdag", "zaterdag", "zondag", "stemmen"]:
                try:
                    clear_message_id(cid, key)
                except Exception:
                    pass

            # Stuur resetbericht alleen in dit kanaal
            send_func = getattr(channel, "send", None)
            if send_func:
                try:
                    await safe_call(
                        send_func,
                        "⬆️@everyone De poll is zojuist gereset voor het nieuwe weekend. "
                        "Je kunt weer stemmen. Veel plezier!",
                    )
                except Exception:
                    continue

    # Als geen enkel kanaal gereset werd, val terug op globale reset
    if not any_reset:
        try:
            await reset_votes()
        except Exception:
            pass

    # State bijwerken (nu is er wél gereset)
    try:
        state["reset_polls"] = now.isoformat()
        _write_state(state)
    except Exception:
        pass

    return True


async def notify_for_channel(channel, dag: str) -> bool:
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

        # Alleen in actieve poll-kanalen wanneer ingeschakeld
        allow_from_per_channel_only = os.getenv(
            "ALLOW_FROM_PER_CHANNEL_ONLY", "true"
        ).lower() in {"1", "true", "yes", "y"}
        has_poll = False
        if allow_from_per_channel_only:
            try:
                cid = int(getattr(channel, "id", 0))
            except Exception:
                cid = 0
            if cid:
                for key in ("vrijdag", "zaterdag", "zondag", "stemmen"):
                    try:
                        if get_message_id(cid, key):
                            has_poll = True
                            break
                    except Exception:
                        pass
            if not has_poll:
                return False

        guild = getattr(channel, "guild", None)
        gid = getattr(guild, "id", "0") if guild is not None else "0"
        cid = getattr(channel, "id", "0") or "0"

        votes = await load_votes(gid, cid) or {}

        # Tel stemmen per tijdslot (zoals notify_voters_if_avond_gaat_door)
        counts: dict[str, int] = {}
        for _uid, per_dag in votes.items():
            try:
                tijden = (per_dag or {}).get(dag, [])
                if isinstance(tijden, list):
                    for t in tijden:
                        counts[t] = counts.get(t, 0) + 1
            except Exception:
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
    except Exception:
        # In commands willen we nooit crashen
        return False


# ========================================================================
# Misschien Confirmation Flow (17:00 - 18:00)
# ========================================================================


async def notify_misschien_voters(bot, dag: str) -> None:
    """
    Notify "Misschien" voters at 17:00 with Stem Nu button.

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

    # DENY_CHANNEL_NAMES en ALLOW_FROM_PER_CHANNEL_ONLY checks
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

            # Check ALLOW_FROM_PER_CHANNEL_ONLY
            if allow_from_per_channel_only:
                try:
                    has_poll = any(
                        get_message_id(cid, key)
                        for key in ("vrijdag", "zaterdag", "zondag", "stemmen")
                    )
                    if not has_poll:
                        continue
                except Exception:
                    continue

            gid = getattr(guild, "id", "0")
            votes = await load_votes(gid, cid) or {}

            # Find "misschien" voters for this dag
            misschien_voter_ids: set[str] = set()
            channel_members = getattr(channel, "members", [])
            channel_member_ids = {str(getattr(m, "id", "")): m for m in channel_members}

            for uid, per_dag in votes.items():
                tijden = (per_dag or {}).get(dag, [])
                if not isinstance(tijden, list):
                    continue

                if "misschien" in tijden:
                    # Extract owner ID (handle guests)
                    actual_uid = (
                        uid.split("_guest::", 1)[0]
                        if isinstance(uid, str) and "_guest::" in uid
                        else uid
                    )
                    misschien_voter_ids.add(str(actual_uid))

            # Convert IDs to mentions (deduplicated)
            misschien_voters: list[str] = []
            for uid in misschien_voter_ids:
                try:
                    member = channel_member_ids.get(uid)
                    if member and not getattr(member, "bot", False):
                        mention = getattr(member, "mention", None)
                        if mention:
                            misschien_voters.append(mention)
                except Exception:
                    continue

            if not misschien_voters:
                continue  # No misschien voters in this channel

            # Calculate leading time
            leading_time = None
            try:
                leading_time = await calculate_leading_time(gid, cid, dag)
            except Exception:
                pass

            if not leading_time:
                # No clear winner yet, skip for now
                continue

            # Send temporary mention with button
            mentions_str = ", ".join(misschien_voters)
            text = (
                "Wil je vanavond meedoen?\n"
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
            except Exception:
                # Silent fail
                pass


async def convert_remaining_misschien(bot, dag: str) -> None:
    """
    Convert remaining "Misschien" votes to ❌ at 18:00.

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

    # DENY_CHANNEL_NAMES en ALLOW_FROM_PER_CHANNEL_ONLY checks
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

            # Check ALLOW_FROM_PER_CHANNEL_ONLY
            if allow_from_per_channel_only:
                try:
                    has_poll = any(
                        get_message_id(cid, key)
                        for key in ("vrijdag", "zaterdag", "zondag", "stemmen")
                    )
                    if not has_poll:
                        continue
                except Exception:
                    continue

            gid = getattr(guild, "id", "0")
            votes = await load_votes(gid, cid) or {}

            # Find remaining "misschien" voters and convert them
            converted_any = False
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
                    except Exception:
                        continue

            # Update poll message if we converted anyone
            if converted_any:
                try:
                    await schedule_poll_update(channel, dag, delay=0.0)
                except Exception:
                    pass

            # Clear button from notification (set show_button=False)
            try:
                from apps.utils.poll_message import update_notification_message

                await update_notification_message(
                    channel,
                    mentions="",
                    text="",
                    show_button=False,
                    dag="",
                    leading_time="",
                )
            except Exception:
                pass
