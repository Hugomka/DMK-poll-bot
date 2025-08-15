# apps/scheduler.py

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.utils.poll_storage import load_votes, reset_votes
from apps.utils.poll_message import get_message_id, update_poll_message, clear_message_id

scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Amsterdam"))

def setup_scheduler(bot):
    scheduler.add_job(update_all_polls, CronTrigger(hour=18, minute=0), args=[bot], name="Dagelijkse pollupdate om 18:00")
    scheduler.add_job(reset_polls, CronTrigger(day_of_week="mon", hour=0, minute=0), args=[bot], name="Wekelijkse reset")
    scheduler.add_job(notify_voters_if_avond_gaat_door, CronTrigger(day_of_week="fri", hour=18, minute=0), args=[bot, "vrijdag"], name="Notificatie vrijdag")
    scheduler.add_job(notify_voters_if_avond_gaat_door, CronTrigger(day_of_week="sat", hour=18, minute=0), args=[bot, "zaterdag"], name="Notificatie zaterdag")
    scheduler.add_job(notify_voters_if_avond_gaat_door, CronTrigger(day_of_week="sun", hour=18, minute=0), args=[bot, "zondag"], name="Notificatie zondag")
    scheduler.start()

async def update_all_polls(bot):
    # update elk dagbericht in elk tekstkanaal
    for guild in bot.guilds:
        for channel in guild.text_channels:
            for dag in ["vrijdag", "zaterdag", "zondag"]:
                await update_poll_message(channel, dag)

async def reset_polls(bot):
    # stemmen leegmaken en keys opruimen (nieuwe week)
    reset_votes()
    for guild in bot.guilds:
        for channel in guild.text_channels:
            for key in ["vrijdag", "zaterdag", "zondag", "stemmen"]:
                mid = get_message_id(channel.id, key)
                if mid:
                    try:
                        clear_message_id(channel.id, key)
                    except Exception:
                        pass
    # Je kunt hier eventueel ook meteen /dmk-poll-on laten draaien via je Cog,
    # maar dat kan ook handmatig door admin.

async def notify_voters_if_avond_gaat_door(bot, dag: str):
    """
    Stuur om 18:00 een melding als één tijd >= 6 stemmen heeft.
    Bij gelijk → 20:30 wint (DMK-regel).
    """
    stemmen = load_votes()
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
