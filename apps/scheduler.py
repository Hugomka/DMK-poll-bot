from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
from apps.utils.message_builder import update_poll_message
from apps.utils.poll_storage import save_votes
from apps.utils.poll_message import get_message_id

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
                    await channel.send("🔄 Nieuwe week! Stem opnieuw via `/dmk-poll stem`")
                except:
                    pass
