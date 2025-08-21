# main.py

import os
import discord
import asyncio
import logging
from discord.ext import commands
from dotenv import load_dotenv
from apps.ui.poll_buttons import OneStemButtonView

logging.basicConfig(level=logging.INFO)
discord.utils.setup_logging(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is online als {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔧 Slash commands gesynchroniseerd: {len(synced)}")
    except Exception as e:
        print(f"❌ Fout bij synchroniseren van slash commands: {e}")

async def main():
    from apps.scheduler import setup_scheduler
    setup_scheduler(bot)  # <-- start de APScheduler jobs

    await bot.load_extension("apps.commands.dmk_poll")
    bot.add_view(OneStemButtonView())  # persistente view

    await bot.start(TOKEN)

asyncio.run(main())
