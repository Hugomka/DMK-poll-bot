# apps/commands/poll_guests.py
#
# Gasten beheer voor DMK-poll

from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

from apps.utils.poll_message import update_poll_message
from apps.utils.poll_storage import add_guest_votes, remove_guest_votes


class PollGuests(commands.Cog):
    """Gasten beheer"""

    def __init__(self, bot):
        self.bot = bot

    # Iedereen mag gasten toevoegen
    @app_commands.guild_only()
    @app_commands.command(
        name="gast-add",
        description="Voeg gaststemmen toe voor een dag+tijd. Meerdere namen scheiden met , of ;",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name="Vrijdag 19:00", value="vrijdag|om 19:00 uur"),
            app_commands.Choice(name="Vrijdag 20:30", value="vrijdag|om 20:30 uur"),
            app_commands.Choice(name="Zaterdag 19:00", value="zaterdag|om 19:00 uur"),
            app_commands.Choice(name="Zaterdag 20:30", value="zaterdag|om 20:30 uur"),
            app_commands.Choice(name="Zondag 19:00", value="zondag|om 19:00 uur"),
            app_commands.Choice(name="Zondag 20:30", value="zondag|om 20:30 uur"),
        ],
    )
    @app_commands.describe(namen="Meerdere namen met komma, bv: Mario, Luigi, Peach")
    async def gast_add(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        namen: str,
    ) -> None:
        """Voorbeeld: /gast-add slot:'Vrijdag 20:30' namen:'Mario, Luigi, Peach'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)

            # Split op komma of puntkomma
            ruwe = [p.strip() for p in re.split(r"[;,]", namen or "") if p.strip()]
            if not ruwe:
                await interaction.followup.send(
                    "⚠️ Geen geldige namen opgegeven.", ephemeral=True
                )
                return

            toegevoegd, overgeslagen = await add_guest_votes(
                interaction.user.id,
                dag,
                tijd,
                ruwe,
                (
                    getattr(interaction.guild, "id", "0")
                    if interaction.guild is not None
                    else "0"
                ),
                getattr(interaction.channel, "id", "0") or "0",
            )

            # Publieke pollbericht voor díe dag even updaten
            await update_poll_message(channel=interaction.channel, dag=dag)

            parts: list[str] = []
            if toegevoegd:
                parts.append(f"✅ Toegevoegd: {', '.join(toegevoegd)}")
            if overgeslagen:
                parts.append(f"ℹ️ Overgeslagen (bestond al): {', '.join(overgeslagen)}")
            if not parts:
                parts = ["(niets gewijzigd)"]

            await interaction.followup.send(
                f"👥 Gaststemmen voor **{dag} {tijd}**\n" + "\n".join(parts),
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(
        name="gast-remove",
        description="Verwijder gaststemmen voor een dag+tijd. Meerdere namen scheiden met , of ;",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name="Vrijdag 19:00", value="vrijdag|om 19:00 uur"),
            app_commands.Choice(name="Vrijdag 20:30", value="vrijdag|om 20:30 uur"),
            app_commands.Choice(name="Zaterdag 19:00", value="zaterdag|om 19:00 uur"),
            app_commands.Choice(name="Zaterdag 20:30", value="zaterdag|om 20:30 uur"),
            app_commands.Choice(name="Zondag 19:00", value="zondag|om 19:00 uur"),
            app_commands.Choice(name="Zondag 20:30", value="zondag|om 20:30 uur"),
        ],
    )
    @app_commands.describe(namen="Meerdere namen met komma, bv: Mario, Luigi, Peach")
    async def gast_remove(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        namen: str,
    ) -> None:
        """Voorbeeld: /gast-remove slot:'Vrijdag 20:30' namen:'Mario, Luigi'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)
            ruwe = [p.strip() for p in re.split(r"[;,]", namen or "") if p.strip()]
            if not ruwe:
                await interaction.followup.send(
                    "⚠️ Geen geldige namen opgegeven.", ephemeral=True
                )
                return

            verwijderd, nietgevonden = await remove_guest_votes(
                interaction.user.id,
                dag,
                tijd,
                ruwe,
                (
                    getattr(interaction.guild, "id", "0")
                    if interaction.guild is not None
                    else "0"
                ),
                getattr(interaction.channel, "id", "0") or "0",
            )

            # Publieke pollbericht voor díe dag updaten
            await update_poll_message(channel=interaction.channel, dag=dag)

            parts: list[str] = []
            if verwijderd:
                parts.append(f"✅ Verwijderd: {', '.join(verwijderd)}")
            if nietgevonden:
                parts.append(f"ℹ️ Niet gevonden: {', '.join(nietgevonden)}")
            if not parts:
                parts = ["(niets gewijzigd)"]

            await interaction.followup.send(
                f"👥 Gaststemmen verwijderd voor **{dag} {tijd}**\n" + "\n".join(parts),
                ephemeral=True,
            )
        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollGuests(bot))
