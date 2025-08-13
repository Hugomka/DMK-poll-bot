import discord
from discord import app_commands
from discord.ext import commands
from apps.utils.poll_message import (
    save_message_id,
    get_message_id,
    clear_message_id,
    update_poll_message,
)
from apps.utils.poll_storage import remove_vote, reset_votes
from apps.utils.message_builder import build_poll_message_for_day
from apps.ui.poll_buttons import PollButtonView

class DMKPoll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dmk-poll-on", description="Plaats of update de polls per avond")
    @app_commands.checks.has_permissions(administrator=True)
    async def on(self, interaction):
        """
        Plaatst of werkt drie aparte pollberichten bij voor vrijdag, zaterdag en zondag.
        """
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        user_id = str(interaction.user.id)
        dagen = ["vrijdag", "zaterdag", "zondag"]

        for dag in dagen:
            content = build_poll_message_for_day(dag)
            view = PollButtonView(dag, user_id)
            message_id = get_message_id(channel.id, dag)

            if message_id:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.edit(content=content, view=view)
                except Exception:
                    # Als het oude bericht niet gevonden kan worden, maak een nieuw bericht
                    message = await channel.send(content=content, view=view)
                    save_message_id(channel.id, dag, message.id)
            else:
                message = await channel.send(content=content, view=view)
                save_message_id(channel.id, dag, message.id)

        await interaction.followup.send("✅ De polls zijn geplaatst of bijgewerkt.", ephemeral=True)

    @app_commands.command(name="dmk-poll-reset", description="Reset de polls naar een nieuwe week.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction):
        """
        Reset alle stemmen en zet de drie polls terug naar nul stemmen.
        """
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        dagen = ["vrijdag", "zaterdag", "zondag"]
        gevonden = False

        # leeg het stemmenbestand
        reset_votes()

        for dag in dagen:
            message_id = get_message_id(channel.id, dag)
            if not message_id:
                continue
            gevonden = True
            try:
                message = await channel.fetch_message(message_id)
                nieuwe_inhoud = build_poll_message_for_day(dag)
                await message.edit(content=nieuwe_inhoud, view=PollButtonView(dag))
            except Exception as e:
                print(f"Fout bij resetten van poll voor {dag}: {e}")

        if gevonden:
            await interaction.followup.send("🔄 De polls zijn gereset voor een nieuwe week.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Geen polls gevonden om te resetten.", ephemeral=True)

    @app_commands.command(name="dmk-poll-pauze", description="Pauzeer of hervat alle polls")
    @app_commands.checks.has_permissions(administrator=True)
    async def pauze(self, interaction: discord.Interaction):
        """
        Zet alle pollknoppen uit (pauze) of aan (hervat) en past de tekst aan.
        """
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        dagen = ["vrijdag", "zaterdag", "zondag"]
        message_ids = [get_message_id(channel.id, dag) for dag in dagen]
        # filter alleen bestaande berichten
        ids_met_dagen = [(dag, mid) for dag, mid in zip(dagen, message_ids) if mid]
        if not ids_met_dagen:
            await interaction.followup.send("⚠️ Geen polls gevonden om te pauzeren.", ephemeral=True)
            return

        # Bepaal nieuwe status aan de hand van het eerste bericht (aan/uit)
        eerste_dag, eerste_id = ids_met_dagen[0]
        try:
            eerste_bericht = await channel.fetch_message(eerste_id)
        except Exception:
            await interaction.followup.send("⚠️ Er kon geen pollbericht worden opgehaald.", ephemeral=True)
            return

        huidige_status = all(button.disabled for row in eerste_bericht.components for button in row.children)
        nieuwe_status = not huidige_status  # wissel pauze/herstart

        for dag, mid in ids_met_dagen:
            try:
                bericht = await channel.fetch_message(mid)
                nieuwe_view = PollButtonView(dag)
                for knop in nieuwe_view.children:
                    knop.disabled = nieuwe_status
                nieuwe_inhoud = build_poll_message_for_day(dag, pauze=nieuwe_status)
                await bericht.edit(content=nieuwe_inhoud, view=nieuwe_view)
            except Exception as e:
                print(f"Fout bij pauzeren van poll voor {dag}: {e}")

        tekst = "gepauzeerd" if nieuwe_status else "hervat"
        await interaction.followup.send(f"⏯️ De polls zijn {tekst}.", ephemeral=True)

    @app_commands.command(name="dmk-poll-verwijderen", description="Verwijder alle pollberichten uit het kanaal en uit het systeem.")
    @app_commands.checks.has_permissions(administrator=True)
    async def verwijderbericht(self, interaction: discord.Interaction):
        """
        Verwijdert de drie polls definitief en verwijdert de opgeslagen IDs.
        """
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        dagen = ["vrijdag", "zaterdag", "zondag"]
        gevonden = False

        for dag in dagen:
            message_id = get_message_id(channel.id, dag)
            if not message_id:
                continue
            gevonden = True
            try:
                message = await channel.fetch_message(message_id)
                afsluit_tekst = "📴 Deze poll is gesloten. Dank voor je deelname."
                await message.edit(content=afsluit_tekst, view=None)
                clear_message_id(channel.id, dag)
            except Exception as e:
                print(f"❌ Fout bij verwijderen poll ({dag}): {e}")

        if gevonden:
            await interaction.followup.send("✅ De polls zijn verwijderd en afgesloten.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Geen polls gevonden om te verwijderen.", ephemeral=True)

async def setup(bot):
    """
    Laadt deze cog in het Discord-bot systeem.
    """
    await bot.add_cog(DMKPoll(bot))
