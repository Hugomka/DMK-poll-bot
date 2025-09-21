# apps/scheduler.py

import asyncio
import json
import os
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import List, Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.utils.discord_client import get_channels, safe_call
from apps.utils.logger import log_job, log_startup
from apps.utils.poll_message import (
    clear_message_id,
    get_message_id,
    is_channel_disabled,
    schedule_poll_update,
)
from apps.utils.poll_storage import load_votes, reset_votes

# NL-tijdzone
TZ = pytz.timezone("Europe/Amsterdam")
scheduler = AsyncIOScheduler(timezone=TZ)

MIN_NOTIFY_VOTES = 6

# Nieuw: herinneringstijd en resetinstellingen
REMINDER_HOUR = 17  # 17:00 uur - stuur herinnering vóór de deadline
RESET_DAY_OF_WEEK = 1  # 0=ma, 1=di … reset op dinsdag
RESET_HOUR = 20  # 20:00 uur - resetmoment
REMINDER_DAYS = {"vrijdag": 4, "zaterdag": 5, "zondag": 6}

LOCK_PATH = ".scheduler.lock"
STATE_PATH = ".scheduler_state.json"


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

    def should_run(last_str: Optional[str], scheduled_dt: datetime) -> bool:
        if last_str is None:
            return True
        try:
            last = datetime.fromisoformat(last_str)
        except Exception:
            return True
        return last < scheduled_dt

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
        await reset_polls(bot)
        state["reset_polls"] = now.isoformat()
        missed.append("reset_polls")
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


async def notify_non_voters(bot, dag: str) -> None:
    """
    Herinner leden die nog niet hebben gestemd voor een bepaalde dag.
    Vermeld alle niet-stemmers als mention en vraag ze vóór 18:00 uur te stemmen.
    """
    log_job("reminder", dag=dag, status="executed")
    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            if is_channel_disabled(getattr(channel, "id", 0)):
                continue

            # Alle stemmen voor dit guild+channel
            scoped = (
                await load_votes(
                    getattr(guild, "id", "0"),
                    getattr(channel, "id", "0"),
                )
                or {}
            )

            # Verzamel user-IDs die al hebben gestemd (leden en gasten)
            voted_ids: set[str] = set()
            for uid, per_dag in scoped.items():
                try:
                    tijden = (per_dag or {}).get(dag, [])
                    if not isinstance(tijden, list):
                        continue
                    if tijden:
                        # guests: <owner>_guest::<gast>
                        if isinstance(uid, str) and "_guest::" in uid:
                            uid = uid.split("_guest::", 1)[0]
                        voted_ids.add(str(uid))
                except Exception:
                    continue

            # Zoek alle leden in het kanaal (val terug op guild.members)
            members = getattr(channel, "members", None) or getattr(guild, "members", [])
            non_voters: list[str] = []
            for member in members:
                try:
                    # Sla bots over
                    if getattr(member, "bot", False):
                        continue
                    m_id = str(getattr(member, "id", ""))
                    if m_id in voted_ids:
                        continue
                    mention = getattr(member, "mention", None)
                    if mention:
                        non_voters.append(mention)
                except Exception:
                    continue

            if non_voters:
                msg = f"{', '.join(non_voters)} - jullie hebben nog niet gestemd. Graag stemmen vóór 18:00. Dank!"
                # Controleer of het kanaal een send‑methode heeft
                send_func = getattr(channel, "send", None)
                if send_func:
                    try:
                        await safe_call(send_func, msg)
                    except Exception as e:
                        # Tests willen dat dit niet crasht
                        print(
                            f"Fout bij herinneren in kanaal {getattr(channel, 'name', channel)}: {e}"
                        )


async def notify_voters_if_avond_gaat_door(bot, dag: str) -> None:
    """
    Stuur melding als een tijd >= MIN_NOTIFY_VOTES stemmen heeft (gelijkstand → 20:30).
    De deelnemers worden eerst genoemd, daarna volgt de zin 'de DMK-avond van … gaat door'.
    """
    log_job("notify", dag=dag, status="executed")
    KEY_19 = "om 19:00 uur"
    KEY_2030 = "om 20:30 uur"

    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            if is_channel_disabled(getattr(channel, "id", 0)):
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

            # Bouw mention-lijst op basis van member objects
            mentions: List[str] = []
            for uid in winner_set:
                try:
                    member = (
                        guild.get_member(int(uid))
                        if hasattr(guild, "get_member")
                        else None
                    )
                    if member and getattr(member, "mention", None):
                        mentions.append(member.mention)
                except Exception:
                    continue

            # Berichttekst
            if mentions:
                prefix = ", ".join(mentions)
                message = f"{prefix} - de DMK-avond van {dag} om {winnaar_txt} gaat door! Tot dan!"
            else:
                message = f"De DMK-avond van {dag} om {winnaar_txt} gaat door! Tot dan!"

            send_func = getattr(channel, "send", None)
            if send_func:
                try:
                    await safe_call(send_func, message)
                except Exception as e:
                    # Tests willen dat dit niet crasht (b.v. 'send kapot')
                    print(
                        f"Fout bij notificeren in kanaal {getattr(channel, 'name', channel)}: {e}"
                    )


async def reset_polls(bot) -> None:
    """
    Maak stemmen leeg + verwijder bericht-IDs en stuur een resetmelding.
    Reset wordt alleen uitgevoerd in het resetvenster (dinsdag 20:00 - 20:05).
    """
    now = datetime.now(TZ)
    if not _within_reset_window(now):
        log_job("reset_polls", status="skipped_outside_window")
        return

    log_job("reset_polls", status="executed")
    await reset_votes()
    for guild in getattr(bot, "guilds", []) or []:
        for channel in get_channels(guild):
            try:
                cid = int(getattr(channel, "id"))
            except Exception:
                continue

            # Wis alle bekende keys, exceptions negeren
            for key in ["vrijdag", "zaterdag", "zondag", "stemmen"]:
                try:
                    _ = get_message_id(cid, key)
                    clear_message_id(cid, key)
                except Exception:
                    pass

            # Stuur resetbericht (@everyone) maar slik exceptions in
            send_func = getattr(channel, "send", None)
            if send_func:
                try:
                    await safe_call(
                        send_func,
                        "⬆️@everyone De poll is zojuist gereset voor het nieuwe weekend. "
                        "Je kunt weer stemmen. Veel plezier!",
                    )
                except Exception as e:
                    print(
                        f"Fout bij versturen resetmelding in kanaal {getattr(channel, 'name', 'onbekend')}: {e}"
                    )
