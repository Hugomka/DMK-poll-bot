from discord import app_commands
from discord.ext import commands
from apps.utils.poll_storage import get_votes_for_option
from apps.utils.poll_message import save_message_id, get_message_id
from datetime import datetime
import pytz


class DMKPoll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dmk-poll-on", description="Post of update de DMK poll")
    @app_commands.checks.has_permissions(administrator=True)
    async def on(self, interaction):
        await interaction.response.defer()
        channel = interaction.channel
        content = build_poll_message()
        message_id = get_message_id(channel.id)

        try:
            if message_id:
                # Probeer het bestaande bericht te bewerken
                message = await channel.fetch_message(message_id)
                await message.edit(content=content)
            else:
                # Geen bestaand bericht: maak een nieuwe
                message = await channel.send(content)
                save_message_id(channel.id, message.id)

            await interaction.followup.send("✅ Poll is geplaatst of bijgewerkt.")
        except Exception as e:
            await interaction.followup.send(f"❌ Er is een fout opgetreden: {e}")


    @app_commands.command(name="dmk-poll-off", description="Zet de DMK poll uit.")
    @app_commands.checks.has_permissions(administrator=True)
    async def off(self, interaction):
        await interaction.response.send_message("🛑 DMK poll is gestopt.")

    @app_commands.command(name="dmk-poll-reset", description="Reset de poll naar nieuwe week.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction):
        await interaction.response.send_message("🔄 Poll is gereset voor een nieuwe week.")

async def setup(bot):
    await bot.add_cog(DMKPoll(bot))
