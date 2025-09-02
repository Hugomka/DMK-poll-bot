# apps/scheduler.py

import asyncio
import os
import json
from datetime import datetime, timedelta, time as dt_time

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.utils.poll_storage import load_votes, reset_votes
from apps.utils.poll_message import get_message_id, update_poll_message, clear_message_id

scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Amsterdam"))

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

    # Dagelijkse update (18:00)
    last_update = state.get("update_all_polls")
    today_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
    last_sched_update = today_18 if now >= today_18 else today_18 - timedelta(days=1)
    if should_run(last_update, last_sched_update):
        await update_all_polls(bot)
        state["update_all_polls"] = now.isoformat()

    # Wekelijkse reset (maandag 00:00)
    last_reset = state.get("reset_polls")
    days_since_monday = (now.weekday() - 0) % 7
    monday = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    last_sched_reset = monday if now >= monday else monday - timedelta(days=7)
    if should_run(last_reset, last_sched_reset):
        await reset_polls(bot)
        state["reset_polls"] = now.isoformat()

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

    _write_state(state)


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
    scheduler.add_job(update_all_polls, CronTrigger(hour=18, minute=0), args=[bot], name="Dagelijkse pollupdate om 18:00")
    scheduler.add_job(reset_polls, CronTrigger(day_of_week="mon", hour=0, minute=0), args=[bot], name="Wekelijkse reset")
    scheduler.add_job(notify_voters_if_avond_gaat_door, CronTrigger(day_of_week="fri", hour=18, minute=0), args=[bot, "vrijdag"], name="Notificatie vrijdag")
    scheduler.add_job(notify_voters_if_avond_gaat_door, CronTrigger(day_of_week="sat", hour=18, minute=0), args=[bot, "zaterdag"], name="Notificatie zaterdag")
    scheduler.add_job(notify_voters_if_avond_gaat_door, CronTrigger(day_of_week="sun", hour=18, minute=0), args=[bot, "zondag"], name="Notificatie zondag")
    scheduler.start()

    # Catch-up kort na start, maar niet blokkerend
    asyncio.create_task(_run_catch_up_with_lock(bot))


async def update_all_polls(bot):
    # update elk dagbericht in elk tekstkanaal
    for guild in bot.guilds:
        for channel in guild.text_channels:
            for dag in ["vrijdag", "zaterdag", "zondag"]:
                await update_poll_message(channel, dag)


async def reset_polls(bot):
    # stemmen leegmaken en keys opruimen (nieuwe week)
    await reset_votes()
    for guild in bot.guilds:
        for channel in guild.text_channels:
            for key in ["vrijdag", "zaterdag", "zondag", "stemmen"]:
                mid = get_message_id(channel.id, key)
                if mid:
                    try:
                        clear_message_id(channel.id, key)
                    except Exception:
                        pass
    # Optioneel: hier /dmk-poll-on aanroepen via je Cog.


async def notify_voters_if_avond_gaat_door(bot, dag: str):
    """
    Stuur om 18:00 een melding als één tijd >= 6 stemmen heeft.
    Bij gelijk → 20:30 wint (DMK-regel).
    """
    stemmen = await load_votes()
    # Let op: jouw labels heten "om 19:00 uur" en "om 20:30 uur"
    keys = {"19": "om 19:00 uur", "2030": "om 20:30 uur"}

    voters_19 = set()
    voters_2030 = set()

    for user_id, dagen in stemmen.items():
        keuzes = dagen.get(dag, [])
        if keys["19"] in keuzes:
            voters_19.add(user_id)
        if keys["2030"] in keuzes:
            voters_2030.add(user_id)

    c19, c2030 = len(voters_19), len(voters_2030)

    # Geen doorgang → geen melding
    if c19 < 6 and c2030 < 6:
        return

    # winnaar bepalen (gelijk → 20:30)
    if c2030 >= c19:
        winnaar_txt = "20:30"
        winnaar_set = voters_2030
    else:
        winnaar_txt = "19:00"
        winnaar_set = voters_19

    # Verstuur mentions in elk kanaal waar de poll staat
    for guild in bot.guilds:
        for channel in guild.text_channels:
            # alleen kanalen waar onze poll-keys bestaan (minstens één dagbericht)
            if not any(get_message_id(channel.id, k) for k in ["vrijdag", "zaterdag", "zondag"]):
                continue

            mentions = []
            for uid in winnaar_set:
                member = guild.get_member(int(uid))
                if member:
                    mentions.append(member.mention)

            if mentions:
                try:
                    await channel.send(
                        f"📢 DMK op **{dag} {winnaar_txt}** gaat door!\n{' '.join(mentions)}"
                    )
                except Exception as e:
                    print(f"Fout bij notificeren in kanaal {channel.name}: {e}")
