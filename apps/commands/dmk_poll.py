from discord import app_commands
from discord.ext import commands

class DMKPoll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dmk-poll-on", description="Start de DMK poll.")
    async def on(self, interaction):
        await interaction.response.send_message("✅ DMK poll is gestart.")

    @app_commands.command(name="dmk-poll-off", description="Zet de DMK poll uit.")
    async def off(self, interaction):
        await interaction.response.send_message("🛑 DMK poll is gestopt.")

    @app_commands.command(name="dmk-poll-reset", description="Reset de poll naar nieuwe week.")
    async def reset(self, interaction):
        await interaction.response.send_message("🔄 Poll is gereset voor een nieuwe week.")

async def setup(bot):
    await bot.add_cog(DMKPoll(bot))
