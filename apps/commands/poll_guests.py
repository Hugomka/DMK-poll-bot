# apps/commands/poll_guests.py
#
# Guest management for DMK-poll

from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

from apps.utils.i18n import t
from apps.utils.poll_message import update_poll_message
from apps.utils.poll_settings import get_poll_option_state
from apps.utils.poll_storage import add_guest_votes, remove_guest_votes

# All possible slots (day|time combinations)
ALL_SLOTS = [
    ("maandag", "19:00", "🟥 Maandag 19:00 (Monday 7 PM)"),
    ("maandag", "20:30", "🟧 Maandag 20:30 (Monday 8:30 PM)"),
    ("dinsdag", "19:00", "🟨 Dinsdag 19:00 (Tuesday 7 PM)"),
    ("dinsdag", "20:30", "⬜ Dinsdag 20:30 (Tuesday 8:30 PM)"),
    ("woensdag", "19:00", "🟩 Woensdag 19:00 (Wednesday 7 PM)"),
    ("woensdag", "20:30", "🟦 Woensdag 20:30 (Wednesday 8:30 PM)"),
    ("donderdag", "19:00", "🟪 Donderdag 19:00 (Thursday 7 PM)"),
    ("donderdag", "20:30", "🟫 Donderdag 20:30 (Thursday 8:30 PM)"),
    ("vrijdag", "19:00", "🔴 Vrijdag 19:00 (Friday 7 PM)"),
    ("vrijdag", "20:30", "🟠 Vrijdag 20:30 (Friday 8:30 PM)"),
    ("zaterdag", "19:00", "🟡 Zaterdag 19:00 (Saturday 7 PM)"),
    ("zaterdag", "20:30", "⚪ Zaterdag 20:30 (Saturday 8:30 PM)"),
    ("zondag", "19:00", "🟢 Zondag 19:00 (Sunday 7 PM)"),
    ("zondag", "20:30", "🔵 Zondag 20:30 (Sunday 8:30 PM)"),
]


async def slot_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """
    Autocomplete function for slot parameter.
    Returns only enabled slots based on channel's poll settings.
    """
    channel_id = getattr(interaction.channel, "id", 0) or 0

    choices = []
    for dag, tijd, display_name in ALL_SLOTS:
        # Check if this slot is enabled in settings
        if get_poll_option_state(channel_id, dag, tijd):
            value = f"{dag}|om {tijd} uur"
            # Filter by current input (case-insensitive)
            if current.lower() in display_name.lower():
                choices.append(app_commands.Choice(name=display_name, value=value))

    # Discord limits autocomplete to 25 choices
    return choices[:25]


class PollGuests(commands.Cog):
    """Guest management"""

    def __init__(self, bot):
        self.bot = bot

    # Everyone can add guests
    @app_commands.guild_only()
    @app_commands.command(
        name="guest-add",
        description="Add guest votes for a day+time / Voeg gaststemmen toe",
    )
    @app_commands.autocomplete(slot=slot_autocomplete)
    @app_commands.describe(
        slot="Day and time / Dag en tijd",
        names="Names separated by comma / Namen gescheiden door komma",
    )
    async def guest_add(
        self,
        interaction: discord.Interaction,
        slot: str,
        names: str,
    ) -> None:
        """Example: /guest-add slot:'Friday 8:30 PM' names:'Mario, Luigi, Peach'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.split("|", 1)

            cid = getattr(interaction.channel, "id", 0) or 0

            # Split on comma or semicolon
            raw_names = [p.strip() for p in re.split(r"[;,]", names or "") if p.strip()]
            if not raw_names:
                await interaction.followup.send(
                    f"⚠️ {t(cid, 'COMMANDS.no_valid_names')}", ephemeral=True
                )
                return

            added, skipped = await add_guest_votes(
                interaction.user.id,
                dag,
                tijd,
                raw_names,
                (
                    getattr(interaction.guild, "id", "0")
                    if interaction.guild is not None
                    else "0"
                ),
                getattr(interaction.channel, "id", "0") or "0",
            )

            # Update public poll message for that day
            await update_poll_message(channel=interaction.channel, dag=dag)

            parts: list[str] = []
            if added:
                parts.append(
                    t(cid, "COMMANDS.guest_added_list", names=", ".join(added))
                )
            if skipped:
                parts.append(
                    t(cid, "COMMANDS.guest_skipped", skipped=", ".join(skipped))
                )
            if not parts:
                parts = [t(cid, "COMMANDS.nothing_changed")]

            await interaction.followup.send(
                t(cid, "COMMANDS.guest_added", dag=dag, tijd=tijd)
                + "\n"
                + "\n".join(parts),
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            cid = getattr(interaction.channel, "id", 0) or 0
            await interaction.followup.send(
                t(cid, "ERRORS.generic_error", error=str(e)), ephemeral=True
            )

    @app_commands.guild_only()
    @app_commands.command(
        name="guest-remove",
        description="Remove guest votes for a day+time / Verwijder gaststemmen",
    )
    @app_commands.autocomplete(slot=slot_autocomplete)
    @app_commands.describe(
        slot="Day and time / Dag en tijd",
        names="Names separated by comma / Namen gescheiden door komma",
    )
    async def guest_remove(
        self,
        interaction: discord.Interaction,
        slot: str,
        names: str,
    ) -> None:
        """Example: /guest-remove slot:'Friday 8:30 PM' names:'Mario, Luigi'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.split("|", 1)
            cid = getattr(interaction.channel, "id", 0) or 0

            raw_names = [p.strip() for p in re.split(r"[;,]", names or "") if p.strip()]
            if not raw_names:
                await interaction.followup.send(
                    f"⚠️ {t(cid, 'COMMANDS.no_valid_names')}", ephemeral=True
                )
                return

            removed, not_found = await remove_guest_votes(
                interaction.user.id,
                dag,
                tijd,
                raw_names,
                (
                    getattr(interaction.guild, "id", "0")
                    if interaction.guild is not None
                    else "0"
                ),
                getattr(interaction.channel, "id", "0") or "0",
            )

            # Update public poll message for that day
            await update_poll_message(channel=interaction.channel, dag=dag)

            parts: list[str] = []
            if removed:
                parts.append(
                    t(cid, "COMMANDS.guest_removed_list", names=", ".join(removed))
                )
            if not_found:
                parts.append(
                    t(cid, "COMMANDS.guest_not_found", names=", ".join(not_found))
                )
            if not parts:
                parts = [t(cid, "COMMANDS.nothing_changed")]

            await interaction.followup.send(
                t(cid, "COMMANDS.guest_removed", dag=dag, tijd=tijd)
                + "\n"
                + "\n".join(parts),
                ephemeral=True,
            )
        except Exception as e:  # pragma: no cover
            cid = getattr(interaction.channel, "id", 0) or 0
            await interaction.followup.send(
                t(cid, "ERRORS.generic_error", error=str(e)), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollGuests(bot))
