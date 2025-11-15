# apps/commands/poll_votes.py
#
# Stemmen command voor DMK-poll

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apps.commands import with_default_suffix
from apps.utils.poll_message import update_poll_message
from apps.utils.poll_settings import set_visibility


class PollVotes(commands.Cog):
    """Stemmen zichtbaarheid beheer"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-stemmen",
        description=with_default_suffix(
            "Toon of verberg stemmenaantallen tot de deadline"
        ),
    )
    @app_commands.choices(
        actie=[
            app_commands.Choice(name="Zichtbaar maken", value="altijd"),
            app_commands.Choice(
                name="Verbergen tot deadline behalve niet gestemd",
                value="deadline_show_ghosts",
            ),
            app_commands.Choice(name="Verbergen tot deadline", value="deadline"),
        ],
        dag=[
            app_commands.Choice(name="Vrijdag", value="vrijdag"),
            app_commands.Choice(name="Zaterdag", value="zaterdag"),
            app_commands.Choice(name="Zondag", value="zondag"),
        ],
    )
    @app_commands.describe(tijd="Tijdstip in uu:mm (alleen nodig bij verborgen modus)")
    async def stemmen(
        self,
        interaction: discord.Interaction,
        actie: app_commands.Choice[str],
        dag: Optional[app_commands.Choice[str]] = None,
        tijd: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        try:
            if dag and dag.value:
                doel_dagen = [dag.value]
            else:
                doel_dagen = ["vrijdag", "zaterdag", "zondag"]

            laatste: Optional[dict] = None
            for d in doel_dagen:
                # Gebruik de actie.value direct als modus (altijd, deadline_show_ghosts, deadline)
                laatste = set_visibility(
                    channel.id, d, modus=actie.value, tijd=(tijd or "18:00")
                )
                await update_poll_message(channel, d)

            tijd_txt = (laatste or {}).get("tijd", "18:00")
            modus = (laatste or {}).get("modus", "deadline")

            if modus == "altijd":
                modus_txt = "altijd zichtbaar"
            elif modus == "deadline_show_ghosts":
                modus_txt = f"verborgen tot {tijd_txt} (behalve niet gestemd)"
            else:
                modus_txt = f"verborgen tot {tijd_txt}"

            if dag and dag.value:
                await interaction.followup.send(
                    f"⚙️ Instelling voor {dag.value} gewijzigd naar: **{modus_txt}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"⚙️ Instellingen voor alle dagen gewijzigd naar: **{modus_txt}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
                    ephemeral=True,
                )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollVotes(bot))
