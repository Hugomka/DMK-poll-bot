# apps/commands/poll_archive.py
#
# Archief beheer voor DMK-poll

from __future__ import annotations

import io

import discord
from discord import File, app_commands
from discord.ext import commands

from apps.commands import with_default_suffix
from apps.utils.archive import (
    archive_exists_scoped,
    delete_archive_scoped,
    open_archive_bytes_scoped,
)

try:
    from apps.ui.archive_view import ArchiveDeleteView
except Exception:  # pragma: no cover
    ArchiveDeleteView = None


class PollArchive(commands.Cog):
    """Archief beheer"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-archief-download",
        description=with_default_suffix("Download het CSV-archief met weekresultaten"),
    )
    async def archief_download(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        guild = getattr(interaction, "guild", None) or getattr(channel, "guild", None)
        gid = int(getattr(guild, "id", 0)) if guild else 0
        cid = int(getattr(channel, "id", 0))

        try:
            if not archive_exists_scoped(gid, cid):
                await interaction.followup.send(
                    "Er is nog geen archief voor dit kanaal.", ephemeral=True
                )
                return

            filename, data = open_archive_bytes_scoped(gid, cid)
            if not data:
                await interaction.followup.send(
                    "Archief kon niet worden gelezen.", ephemeral=True
                )
                return

            if ArchiveDeleteView is None:
                await interaction.followup.send(
                    content="CSV-archief met weekresultaten voor dit kanaal.",
                    file=File(io.BytesIO(data), filename=filename),
                )
                return

            view = ArchiveDeleteView(gid, cid)
            await interaction.followup.send(
                "CSV-archief met weekresultaten voor dit kanaal. Wil je het hierna verwijderen?",
                file=File(io.BytesIO(data), filename=filename),
                view=view,
            )
        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-archief-verwijderen",
        description=with_default_suffix("Verwijder het volledige archief"),
    )
    async def archief_verwijderen(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        guild = getattr(interaction, "guild", None) or getattr(channel, "guild", None)
        gid = int(getattr(guild, "id", 0)) if guild else 0
        cid = int(getattr(channel, "id", 0))

        try:
            ok = delete_archive_scoped(gid, cid)
            msg = (
                "Archief voor dit kanaal verwijderd. ✅"
                if ok
                else "Er was geen archief om te verwijderen voor dit kanaal."
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollArchive(bot))
