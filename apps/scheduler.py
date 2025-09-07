# apps/scheduler.py

import asyncio
import json
import os
from datetime import datetime, timedelta
from datetime import time as dt_time

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

scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Amsterdam"))

MIN_NOTIFY_VOTES = 6

# Bestanden voor lock en catch-up status
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


async def _run_catch_up(bot) -> None:
    """Voer gemiste jobs (18:00 dagelijks, ma 00:00 reset, 18:00 notificaties) precies één keer uit."""
    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz)
    state = _read_state()

    def should_run(last_str: str | None, scheduled_dt: datetime) -> bool:
        if last_str is None:
            return True
        try:
            last = datetime.fromisoformat(last_str)
        except Exception:
            return True
        return last < scheduled_dt

    missed: list[str] = []  # opgeslagen namen van jobs die zijn ingehaald

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

    # Wekelijkse reset (maandag 00:00)
    last_reset = state.get("reset_polls")
    days_since_monday = (now.weekday() - 0) % 7
    monday = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    last_sched_reset = monday if now >= monday else monday - timedelta(days=7)
    if should_run(last_reset, last_sched_reset):
        await reset_polls(bot)
        state["reset_polls"] = now.isoformat()
        missed.append("reset_polls")
        log_job("reset_polls", status="executed")
    else:
        log_job("reset_polls", status="skipped")

    # Notificaties (vr/za/zo 18:00)
    weekday_map = {"vrijdag": 4, "zaterdag": 5, "zondag": 6}
    for dag, target_wd in weekday_map.items():
        key = f"notify_{dag}"
        last_notify = state.get(key)
        days_since = (now.weekday() - target_wd) % 7
        last_date = (now - timedelta(days=days_since)).date()
        last_occurrence = tz.localize(datetime.combine(last_date, dt_time(18, 0)))
        if now < last_occurrence:
            last_occurrence -= timedelta(days=7)
        if should_run(last_notify, last_occurrence):
            await notify_voters_if_avond_gaat_door(bot, dag)
            state[key] = now.isoformat()
            missed.append(f"notify_{dag}")
            log_job("notify", dag=dag, status="executed")
        else:
            log_job("notify", dag=dag, status="skipped")

    _write_state(state)
    # Log bij opstart welke jobs ingehaald zijn
    log_startup(missed)


async def _run_catch_up_with_lock(bot) -> None:
    """Voer catch-up met file-lock uit zodat deze niet dubbel draait bij herstart-spikes."""
    try:
        if os.path.exists(LOCK_PATH):
            try:
                mtime = os.path.getmtime(LOCK_PATH)
                # Als lock <5 min oud is, sla catch-up over (waarschijnlijk dubbele start)
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


def setup_scheduler(bot):
    """Wordt sync aangeroepen in main.py. Plant jobs en start catch-up async."""
    scheduler.add_job(
        update_all_polls,
        CronTrigger(hour=18, minute=0),
        args=[bot],
        name="Dagelijkse pollupdate om 18:00",
    )
    scheduler.add_job(
        reset_polls,
        CronTrigger(day_of_week="mon", hour=0, minute=0),
        args=[bot],
        name="Wekelijkse reset",
    )
    scheduler.add_job(
        notify_voters_if_avond_gaat_door,
        CronTrigger(day_of_week="fri", hour=18, minute=0),
        args=[bot, "vrijdag"],
        name="Notificatie vrijdag",
    )
    scheduler.add_job(
        notify_voters_if_avond_gaat_door,
        CronTrigger(day_of_week="sat", hour=18, minute=0),
        args=[bot, "zaterdag"],
        name="Notificatie zaterdag",
    )
    scheduler.add_job(
        notify_voters_if_avond_gaat_door,
        CronTrigger(day_of_week="sun", hour=18, minute=0),
        args=[bot, "zondag"],
        name="Notificatie zondag",
    )
    scheduler.start()

    # Catch-up kort na start, maar niet blokkerend
    asyncio.create_task(_run_catch_up_with_lock(bot))


async def update_all_polls(bot):
    # update elk dagbericht in elk tekstkanaal (gecoalesced via schedule_poll_update)
    log_job("update_all_polls", status="executed")
    tasks = []
    for guild in bot.guilds:
        for channel in get_channels(guild):
            # sla uitgeschakelde kanalen over
            try:
                if is_channel_disabled(getattr(channel, "id", 0)):
                    continue
            except Exception:
                pass
            for dag in ["vrijdag", "zaterdag", "zondag"]:
                tasks.append(schedule_poll_update(channel, dag, delay=0.0))
    if tasks:
        # Wacht tot alle geplande updates afgerond zijn
        await asyncio.gather(*tasks, return_exceptions=True)


async def reset_polls(bot):
    # stemmen leegmaken en keys opruimen (nieuwe week)
    log_job("reset_polls", status="executed")
    await reset_votes()
    for guild in bot.guilds:
        for channel in get_channels(guild):
            for key in ["vrijdag", "zaterdag", "zondag", "stemmen"]:
                mid = get_message_id(channel.id, key)
                if mid:
                    try:
                        clear_message_id(channel.id, key)
                    except Exception:
                        pass
    # Optioneel: hier /dmk-poll-on aanroepen via je Cog.


async def notify_voters_if_avond_gaat_door(bot, dag: str):
    """Stuur om 18:00 een melding per kanaal als één tijd >= 6 stemmen heeft.
    Bij gelijk → 20:30 wint (DMK‑regel)."""
    log_job("notify", dag=dag, status="executed")
    KEY_19 = "om 19:00 uur"
    KEY_2030 = "om 20:30 uur"

    for guild in bot.guilds:
        for channel in get_channels(guild):
            try:
                # sla uitgeschakelde kanalen over
                if is_channel_disabled(getattr(channel, "id", 0)):
                    continue
                # Scoped stemmen voor dit kanaal
                scoped = await load_votes(
                    getattr(guild, "id", "0"), getattr(channel, "id", "0")
                )
                # Verzamel stemmers per tijd voor de gevraagde dag
                voters_19 = set()
                voters_2030 = set()
                for uid, per_dag in (scoped or {}).items():
                    tijden = (per_dag or {}).get(dag, [])
                    if not isinstance(tijden, list):
                        continue
                    if KEY_19 in tijden:
                        if isinstance(uid, str) and "_guest::" in uid:
                            owner_id = uid.split("_guest::", 1)[0]
                            voters_19.add(owner_id)
                        else:
                            voters_19.add(str(uid))
                    if KEY_2030 in tijden:
                        if isinstance(uid, str) and "_guest::" in uid:
                            owner_id = uid.split("_guest::", 1)[0]
                            voters_2030.add(owner_id)
                        else:
                            voters_2030.add(str(uid))

                c19, c2030 = len(voters_19), len(voters_2030)

                # Geen doorgang → geen melding voor dit kanaal
                if c19 < 6 and c2030 < 6:
                    continue

                # winnaar (gelijk → 20:30)
                if c2030 >= c19:
                    winnaar_txt = "20:30"
                    winnaar_set = voters_2030
                else:
                    winnaar_txt = "19:00"
                    winnaar_set = voters_19

                mentions = []
                for uid in winnaar_set:
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

                suffix = f"{' '.join(mentions)}" if mentions else ""
                await safe_call(
                    channel.send,
                    f"📢 DMK op **{dag} {winnaar_txt}** gaat door!{suffix}",
                )
            except Exception as e:
                print(
                    f"Fout bij notificeren in kanaal {getattr(channel, 'name', channel)}: {e}"
                )
