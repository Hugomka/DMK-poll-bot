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
    append_week_snapshot_scoped,
    archive_exists_scoped,
    create_archive,
    open_archive_bytes_scoped,
)

try:
    from apps.ui.archive_view import ArchiveView
except Exception:  # pragma: no cover
    ArchiveView = None


class PollArchive(commands.Cog):
    """Archief beheer"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-archief",
        description=with_default_suffix(
            "Bekijk en beheer het CSV-archief met weekresultaten"
        ),
    )
    async def archief(self, interaction: discord.Interaction) -> None:
        await self._handle_download(interaction)

    async def _handle_download(self, interaction: discord.Interaction) -> None:
        """Toon archief met delimiter selectie en delete knop."""
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        guild = getattr(interaction, "guild", None) or getattr(channel, "guild", None)
        gid = int(getattr(guild, "id", 0)) if guild else 0
        cid = int(getattr(channel, "id", 0))

        try:
            # Update archief met huidige week data (overschrijft bestaande week-rij)
            await append_week_snapshot_scoped(gid, cid, channel=channel)

            if not archive_exists_scoped(gid, cid):
                await interaction.followup.send(
                    "Er is nog geen archief voor dit kanaal.", ephemeral=True
                )
                return

            # Check if ArchiveView is available
            if ArchiveView is None:
                # Fallback naar oude methode
                filename, data = open_archive_bytes_scoped(gid, cid)
                if not data:
                    await interaction.followup.send(
                        "Archief kon niet worden gelezen.", ephemeral=True
                    )
                    return

                await interaction.followup.send(
                    content="CSV-archief met weekresultaten voor dit kanaal.",
                    file=File(io.BytesIO(data), filename=filename),
                    ephemeral=True,
                )
                return

            # Genereer weekend archief (altijd aanwezig)
            weekend_view = ArchiveView(gid, cid, weekday=False)
            weekend_csv = create_archive(gid, cid, weekend_view.selected_delimiter, weekday=False)

            if not weekend_csv:
                await interaction.followup.send(
                    "❌ Kon weekend archief niet genereren.", ephemeral=True
                )
                return

            # Weekend bericht
            weekend_content = (
                "\n📊 **DMK Poll Archief - Weekend (vrijdag-zondag)**\n"
                "Je kunt een **CSV-formaat** tussen NL en US kiezen en download het archiefbestand dat geschikt is voor je spreadsheet.\n\n"
                "⚠️ **Let op**:\n"
                "Op de 'Verwijder archief'-knop klikken verwijdert je het hele archief permanent."
            )

            weekend_filename = f"dmk_archive_{gid}_{cid}_weekend.csv"
            await interaction.followup.send(
                content=weekend_content,
                file=File(io.BytesIO(weekend_csv), filename=weekend_filename),
                view=weekend_view,
                ephemeral=True,
            )

            # Check of er ook weekday archief is
            weekday_csv_check = create_archive(gid, cid, ",", weekday=True)

            if weekday_csv_check:
                # Weekday archief bestaat - stuur tweede bericht
                weekday_view = ArchiveView(gid, cid, weekday=True)
                weekday_csv = create_archive(gid, cid, weekday_view.selected_delimiter, weekday=True)

                if weekday_csv:  # Type guard voor None check
                    weekday_content = (
                        "\n📊 **DMK Poll Archief - Weekday (maandag-donderdag)**\n"
                        "Je kunt een **CSV-formaat** tussen NL en US kiezen en download het archiefbestand dat geschikt is voor je spreadsheet.\n\n"
                        "⚠️ **Let op**:\n"
                        "Op de 'Verwijder archief'-knop klikken verwijdert je het hele archief permanent."
                    )

                    weekday_filename = f"dmk_archive_{gid}_{cid}_weekday.csv"
                    await interaction.followup.send(
                        content=weekday_content,
                        file=File(io.BytesIO(weekday_csv), filename=weekday_filename),
                        view=weekday_view,
                        ephemeral=True,
                    )
        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollArchive(bot))
