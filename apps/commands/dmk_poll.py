import discord
import pytz
from discord import app_commands
from discord.ext import commands
from apps.utils.poll_storage import get_votes_for_option
from apps.utils.poll_message import save_message_id, get_message_id
from apps.utils.poll_storage import add_vote, remove_vote
from apps.utils.message_builder import build_poll_message, update_poll_message
from datetime import datetime


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

    @app_commands.command(name="dmk-poll-stem", description="Stem op een dag en tijd")
    @app_commands.describe(
        dag="Kies een dag: vrijdag, zaterdag of zondag",
        tijd="Kies een tijd: 19:00 of 20:30"
    )
    async def stem(self, interaction: discord.Interaction, dag: str, tijd: str):
        user_id = interaction.user.id
        dag = dag.lower()
        tijd = tijd.strip()

        if dag not in ["vrijdag", "zaterdag", "zondag"] or tijd not in ["19:00", "20:30"]:
            await interaction.response.send_message("❌ Ongeldige dag of tijd.", ephemeral=True)
            return

        add_vote(user_id, dag, tijd)
        await update_poll_message(interaction.channel)
        await interaction.response.send_message(f"✅ Je stem voor {dag} {tijd} uur is opgeslagen.", ephemeral=True)

    @app_commands.command(name="dmk-poll-verwijder", description="Verwijder je stem op een dag en tijd")
    @app_commands.describe(
        dag="Dag waarvan je je stem wilt verwijderen",
        tijd="Tijd die je wilt verwijderen"
    )
    async def verwijder(self, interaction: discord.Interaction, dag: str, tijd: str):
        user_id = interaction.user.id
        dag = dag.lower()
        tijd = tijd.strip()

        if dag not in ["vrijdag", "zaterdag", "zondag"] or tijd not in ["19:00", "20:30"]:
            await interaction.response.send_message("❌ Ongeldige dag of tijd.", ephemeral=True)
            return

        remove_vote(user_id, dag, tijd)
        await update_poll_message(interaction.channel)
        await interaction.response.send_message(f"🗑️ Je stem voor {dag} {tijd} uur is verwijderd.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(DMKPoll(bot))
