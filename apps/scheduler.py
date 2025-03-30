from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from apps.utils.poll_storage import save_votes, load_votes
from apps.utils.poll_message import get_message_id, update_poll_message, clear_message_id

scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Amsterdam"))

def setup_scheduler(bot):
    # Dagelijks om 18:00 → update poll (bijv. zichtbaar maken)
    scheduler.add_job(
        lambda: update_all_polls(bot),
        CronTrigger(hour=18, minute=0),
        name="Dagelijkse pollupdate om 18:00"
    )

    # Elke maandag 00:00 → reset stemmen en poll
    scheduler.add_job(
        lambda: reset_polls(bot),
        CronTrigger(day_of_week="mon", hour=0, minute=0),
        name="Wekelijkse reset"
    )

    scheduler.add_job(lambda: notify_voters_if_avond_gaat_door(bot, "vrijdag"),
        CronTrigger(day_of_week="fri", hour=18, minute=0),
        name="Notificatie vrijdagavond")

    scheduler.add_job(lambda: notify_voters_if_avond_gaat_door(bot, "zaterdag"),
        CronTrigger(day_of_week="sat", hour=18, minute=0),
        name="Notificatie zaterdagavond")

    scheduler.add_job(lambda: notify_voters_if_avond_gaat_door(bot, "zondag"),
        CronTrigger(day_of_week="sun", hour=18, minute=0),
        name="Notificatie zondagavond")


    scheduler.start()

async def update_all_polls(bot):
    for guild in bot.guilds:
        for channel in guild.text_channels:
            message_id = get_message_id(channel.id)
            if message_id:
                try:
                    await update_poll_message(channel)
                except:
                    pass  # Je kunt logging toevoegen hier

async def reset_polls(bot):
    save_votes({})  # Leeg stemmenbestand
    for guild in bot.guilds:
        for channel in guild.text_channels:
            message_id = get_message_id(channel.id)
            if message_id:
                try:
                    clear_message_id(message_id)
                    await channel.send("🔄 Nieuwe week! Stem opnieuw via `/dmk-poll stem`")
                except:
                    pass

async def notify_voters_if_avond_gaat_door(bot, dag):
    stemmen = load_votes()
    stemmen_per_tijd = {"19:00": [], "20:30": []}

    for user_id, dagen in stemmen.items():
        if tijds := dagen.get(dag, []):
            for tijd in tijds:
                if tijd in stemmen_per_tijd:
                    stemmen_per_tijd[tijd].append(user_id)

    count_19 = len(set(stemmen_per_tijd["19:00"]))
    count_20 = len(set(stemmen_per_tijd["20:30"]))

    if count_19 < 6 and count_20 < 6:
        return  # Avond gaat niet door → geen melding

    winnaar = "20:30" if count_20 >= count_19 else "19:00"
    user_ids = set(stemmen_per_tijd[winnaar])

    for guild in bot.guilds:
        for channel in guild.text_channels:
            message_id = get_message_id(channel.id)
            if not message_id:
                continue

            mentions = []
            for user_id in user_ids:
                member = guild.get_member(int(user_id))
                if member:
                    mentions.append(member.mention)

            if mentions:
                try:
                    await channel.send(
                        f"📢 DMK op **{dag} {winnaar}** gaat door!\n"
                        f"{' '.join(mentions)}"
                    )
                except Exception as e:
                    print(f"Fout bij notificeren in kanaal {channel.name}: {e}")
