# main.py

import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

from apps.ui.poll_buttons import OneStemButtonView


def _hide_pynacl_warning(record: logging.LogRecord) -> bool:
    return "PyNaCl is not installed" not in record.getMessage()


logging.basicConfig(level=logging.INFO)
logging.getLogger("discord.client").addFilter(_hide_pynacl_warning)
discord.utils.setup_logging(level=logging.INFO)

load_dotenv()
TOKEN_ENV: Optional[str] = os.getenv("DISCORD_TOKEN")
if not TOKEN_ENV:
    raise RuntimeError("❌ DISCORD_TOKEN ontbreekt in .env of omgeving!")
TOKEN: str = TOKEN_ENV

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

    setup_scheduler(bot)  # start de APScheduler jobs

    await bot.load_extension("apps.commands.dmk_poll")
    bot.add_view(OneStemButtonView())  # persistente view

    await bot.start(TOKEN)


asyncio.run(main())
