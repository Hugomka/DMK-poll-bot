# apps/commands/dmk_poll.py
#
# Parent orchestrator voor DMK-poll commands
# Registreert alle child cogs en beheert globale error handling
#
# Richtlijn:
# - Standaard mogen *alle leden* commands gebruiken (geen decorator nodig).
# - Voor admin en moderator als default gebruik je @app_commands.default_permissions(moderate_members=True).
# - Alle DMK-commands zijn server-only (geen DM's): @app_commands.guild_only()
#
# Beheerders kunnen deze defaults later aanpassen per server via:
# Server Settings → Integrations → [jouw bot] → Commands.
# (Daar kun je per command rollen/leden/kanalen aan- of uitzetten.)

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class DMKPoll(commands.Cog):
    """Parent Cog voor globale error handling van DMK-poll commands."""

    def __init__(self, bot):
        self.bot = bot

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Globale error handler voor alle app commands."""
        if isinstance(
            error, (app_commands.MissingPermissions, app_commands.CheckFailure)
        ):
            await interaction.response.send_message(
                "🚫 Sorry, je bent geen beheerder of moderator. Je kunt dit commando niet gebruiken.",
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot) -> None:
    """
    Setup functie die alle DMK-poll cogs registreert.

    Deze parent cog registreert:
    - PollLifecycle: /dmk-poll-on, /dmk-poll-reset, /dmk-poll-pauze, /dmk-poll-verwijderen
    - PollStatus: /dmk-poll-status, /dmk-poll-notify
    - PollArchive: /dmk-poll-archief
    - PollGuests: /gast-add, /gast-remove
    - PollVotes: /dmk-poll-stemmen
    """
    # Registreer parent cog voor error handling
    parent = DMKPoll(bot)
    bot.tree.on_error = parent.on_app_command_error
    await bot.add_cog(parent)

    # Registreer alle child cogs
    from apps.commands.poll_lifecycle import setup as setup_lifecycle
    from apps.commands.poll_status import setup as setup_status
    from apps.commands.poll_archive import setup as setup_archive
    from apps.commands.poll_guests import setup as setup_guests
    from apps.commands.poll_votes import setup as setup_votes
    from apps.commands.poll_config import setup as setup_config

    await setup_lifecycle(bot)
    await setup_status(bot)
    await setup_archive(bot)
    await setup_guests(bot)
    await setup_votes(bot)
    await setup_config(bot)
