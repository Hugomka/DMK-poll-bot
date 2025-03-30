import discord
from discord import app_commands
from discord.ext import commands
from apps.utils.poll_message import save_message_id, get_message_id, clear_message_id, update_poll_message
from apps.utils.poll_storage import add_vote, remove_vote
from apps.utils.message_builder import build_poll_message
from apps.utils.poll_storage import save_votes, load_votes, reset_votes
from apps.ui.poll_buttons import PollButtonView



class DMKPoll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dmk-poll-on", description="Post of update de DMK poll")
    @app_commands.checks.has_permissions(administrator=True)
    async def on(self, interaction):
        await interaction.response.defer(ephemeral=True)
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
                message = await channel.send(content=content, view=PollButtonView())
                save_message_id(channel.id, message.id)

            await interaction.followup.send("✅ Poll is geplaatst of bijgewerkt.")
        except Exception as e:
            await interaction.followup.send(f"❌ Er is een fout opgetreden: {e}")


    @app_commands.command(name="dmk-poll-stop", description="Verwijder de poll uit dit kanaal")
    @app_commands.checks.has_permissions(administrator=True)
    async def stop(self, interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel

        try:
            message_id = get_message_id(channel.id)
            if message_id:
                message = await channel.fetch_message(message_id)
                await message.delete()
                clear_message_id(channel.id)
                await interaction.followup.send("🛑 De poll is gestopt en verwijderd.")
            else:
                await interaction.followup.send("⚠️ Geen bestaand pollbericht gevonden.")
        except Exception as e:
            await interaction.followup.send(f"❌ Fout bij het stoppen van de poll: {e}")

    @app_commands.command(name="dmk-poll-reset", description="Reset de poll naar nieuwe week.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        try:
            message_id = get_message_id(channel.id)
            if message_id:
                message = await channel.fetch_message(message_id)
                reset_votes()
                new_content = build_poll_message()
                await message.edit(content=new_content)
                await interaction.followup.send("🔄 Poll is succesvol gereset voor een nieuwe week.")
            else:
                await interaction.followup.send("⚠️ Geen bestaand pollbericht gevonden om te resetten.")
        except Exception as e:
            await interaction.followup.send(f"❌ Reset is mislukt: {e}")

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
