import os
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f"Bot is online als {bot.user}")

async def main():
    async with bot:
        await bot.load_extension("apps.commands.dmk_poll")
        await bot.start(TOKEN)

asyncio.run(main())

bot.run(TOKEN)
