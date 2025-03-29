import discord
import pytz
from discord import app_commands
from discord.ext import commands
from apps.utils.poll_storage import get_votes_for_option
from apps.utils.poll_message import save_message_id, get_message_id, update_poll_message
from apps.utils.poll_storage import add_vote, remove_vote
from apps.utils.message_builder import build_poll_message, update_poll_message
from apps.utils.poll_storage import save_votes, load_votes
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


    @app_commands.command(name="dmk-poll-stop", description="Verwijder de poll uit dit kanaal")
    @app_commands.checks.has_permissions(administrator=True)
    async def stop(self, interaction):
        await interaction.response.defer()
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
        await interaction.response.defer()
        channel = interaction.channel
        try:
            reset_votes()
            clear_message_id(channel.id)

            # Verwijder oud bericht als dat er is
            old_message_id = get_message_id(channel.id)
            if old_message_id:
                old_msg = await channel.fetch_message(old_message_id)
                await old_msg.delete()

            # Plaats nieuw bericht
            content = build_poll_message()
            message = await channel.send(content)
            save_message_id(channel.id, message.id)

            await interaction.followup.send("🔄 Poll is volledig gereset voor een nieuwe week.")
        except Exception as e:
            await interaction.followup.send(f"❌ Reset is mislukt: {e}")
    
    @app_commands.command(name="dmk-poll-stem", description="Stem op een dag en tijd")
    @app_commands.describe(
        dag="Kies een dag: vrijdag, zaterdag of zondag",
        tijd="Kies een tijd: 19:00 of 20:30"
    )
    async def stem(self, interaction: discord.Interaction, dag: str, tijd: str):
        try:
            print("✅ Commando /dmk-poll stem ontvangen")
            print(f"📅 dag = {dag}, ⏰ tijd = {tijd}")
            user_id = str(interaction.user.id)
            print(f"👤 gebruiker = {user_id}")

            votes = load_votes()
            votes.setdefault(user_id, {"vrijdag": [], "zaterdag": [], "zondag": []})

            if tijd not in votes[user_id][dag]:
                votes[user_id][dag].append(tijd)
                print("📝 Tijd toegevoegd:", tijd)
            else:
                print("ℹ️ Tijd stond er al in")

            save_votes(votes)
            print("💾 Stem succesvol opgeslagen")

            await interaction.response.send_message(
                f"✅ Je stem voor **{dag} {tijd} uur** is geregistreerd.",
                ephemeral=True
            )
            print("📤 Antwoord verzonden")
            await update_poll_message(interaction.channel)

            
        except Exception as e:
            print("❌ Fout tijdens stemverwerking:", e)
            try:
                await interaction.response.send_message(
                    "⚠️ Er is iets misgegaan bij het verwerken van je stem.",
                    ephemeral=True
                )
            except Exception as inner_e:
                print("❌ Kan geen response meer sturen:", inner_e)

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
