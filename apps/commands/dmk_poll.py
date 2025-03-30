import discord
from discord import app_commands
from discord.ext import commands
from apps.entities.poll_option import POLL_OPTIONS
from apps.utils.poll_message import save_message_id, get_message_id, clear_message_id, update_poll_message
from apps.utils.poll_storage import remove_vote
from apps.utils.message_builder import build_poll_message
from apps.utils.poll_storage import reset_votes
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
        view = PollButtonView(str(interaction.user.id))

        # Bekijk of je wilt editen of nieuw bericht
        message_id = get_message_id(channel.id)

        try:
            if message_id:
                # Probeer het bestaande bericht te bewerken
                message = await channel.fetch_message(message_id)
                await message.edit(content=content, view=view)
            else:
                # Geen bestaand bericht: maak een nieuwe
                message = await channel.send(content=content, view=view)
                save_message_id(channel.id, message.id)

            await interaction.followup.send("✅ Poll is geplaatst of bijgewerkt.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Er is iets fout gegaan: {e}", ephemeral=True)

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
                await interaction.followup.send("🔄 Poll is succesvol gereset voor een nieuwe week.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Geen bestaand pollbericht gevonden om te resetten.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Reset is mislukt: {e}", ephemeral=True)

    @app_commands.command(name="dmk-poll-pauze", description="Pauzeer of hervat de pollknoppen")
    @app_commands.checks.has_permissions(administrator=True)
    async def pauze(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            channel = interaction.channel
            message_id = get_message_id(channel.id)
            if not message_id:
                await interaction.followup.send("⚠️ Geen bestaand pollbericht gevonden.", ephemeral=True)
                return
            message = await channel.fetch_message(message_id)
            nieuwe_status = not all(button.disabled for row in message.components for button in row.children)
            nieuwe_view = PollButtonView()
            for child in nieuwe_view.children:
                child.disabled = nieuwe_status
            new_content = build_poll_message(pauze=nieuwe_status)
            await message.edit(content=new_content, view=nieuwe_view)
            tekst = "gepauzeerd" if nieuwe_status else "hervat"
            await interaction.followup.send(f"⏯️ De poll is {tekst}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Fout tijdens pauzeren/hervatten: {e}", ephemeral=True)


    @app_commands.command(name="dmk-poll-verwijderen", description="Verwijder het pollbericht uit het kanaal en uit het systeem.")
    @app_commands.checks.has_permissions(administrator=True)
    async def verwijderbericht(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        message_id = get_message_id(channel.id)

        if not message_id:
            await interaction.followup.send("⚠️ Geen pollbericht gevonden om te verwijderen.", ephemeral=True)
            return

        try:
            message = await channel.fetch_message(message_id)

            # Verwijder view/knoppen en vervang door afsluittekst
            afsluit_tekst = "📴 Deze poll is gesloten. Dank voor je deelname."
            await message.edit(content=afsluit_tekst, view=None)

            # Verwijder message ID uit JSON
            clear_message_id(channel.id)
            await interaction.followup.send("✅ De poll is verwijderd en afgesloten.", ephemeral=True)

        except Exception as e:
            print(f"❌ Fout bij verwijderen poll: {e}")
            await interaction.followup.send(f"❌ Er is iets fout gegaan: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DMKPoll(bot))
