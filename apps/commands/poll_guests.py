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
from apps.utils.poll_storage import add_guest_votes, remove_guest_votes


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
    @app_commands.choices(
        slot=[
            # Maandag / Monday
            app_commands.Choice(
                name="Maandag 19:00 (Monday 7 PM)", value="maandag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Maandag 20:30 (Monday 8:30 PM)", value="maandag|om 20:30 uur"
            ),
            # Dinsdag / Tuesday
            app_commands.Choice(
                name="Dinsdag 19:00 (Tuesday 7 PM)", value="dinsdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Dinsdag 20:30 (Tuesday 8:30 PM)", value="dinsdag|om 20:30 uur"
            ),
            # Woensdag / Wednesday
            app_commands.Choice(
                name="Woensdag 19:00 (Wednesday 7 PM)", value="woensdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Woensdag 20:30 (Wednesday 8:30 PM)", value="woensdag|om 20:30 uur"
            ),
            # Donderdag / Thursday
            app_commands.Choice(
                name="Donderdag 19:00 (Thursday 7 PM)", value="donderdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Donderdag 20:30 (Thursday 8:30 PM)",
                value="donderdag|om 20:30 uur",
            ),
            # Vrijdag / Friday
            app_commands.Choice(
                name="Vrijdag 19:00 (Friday 7 PM)", value="vrijdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Vrijdag 20:30 (Friday 8:30 PM)", value="vrijdag|om 20:30 uur"
            ),
            # Zaterdag / Saturday
            app_commands.Choice(
                name="Zaterdag 19:00 (Saturday 7 PM)", value="zaterdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Zaterdag 20:30 (Saturday 8:30 PM)", value="zaterdag|om 20:30 uur"
            ),
            # Zondag / Sunday
            app_commands.Choice(
                name="Zondag 19:00 (Sunday 7 PM)", value="zondag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Zondag 20:30 (Sunday 8:30 PM)", value="zondag|om 20:30 uur"
            ),
        ],
    )
    @app_commands.describe(names="Names separated by comma / Namen gescheiden door komma")
    async def guest_add(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        names: str,
    ) -> None:
        """Example: /guest-add slot:'Friday 8:30 PM' names:'Mario, Luigi, Peach'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)

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
                parts.append(t(cid, "COMMANDS.guest_added_list", names=", ".join(added)))
            if skipped:
                parts.append(t(cid, "COMMANDS.guest_skipped", skipped=", ".join(skipped)))
            if not parts:
                parts = [t(cid, "COMMANDS.nothing_changed")]

            await interaction.followup.send(
                t(cid, "COMMANDS.guest_added", dag=dag, tijd=tijd) + "\n" + "\n".join(parts),
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
    @app_commands.choices(
        slot=[
            # Maandag / Monday
            app_commands.Choice(
                name="Maandag 19:00 (Monday 7 PM)", value="maandag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Maandag 20:30 (Monday 8:30 PM)", value="maandag|om 20:30 uur"
            ),
            # Dinsdag / Tuesday
            app_commands.Choice(
                name="Dinsdag 19:00 (Tuesday 7 PM)", value="dinsdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Dinsdag 20:30 (Tuesday 8:30 PM)", value="dinsdag|om 20:30 uur"
            ),
            # Woensdag / Wednesday
            app_commands.Choice(
                name="Woensdag 19:00 (Wednesday 7 PM)", value="woensdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Woensdag 20:30 (Wednesday 8:30 PM)", value="woensdag|om 20:30 uur"
            ),
            # Donderdag / Thursday
            app_commands.Choice(
                name="Donderdag 19:00 (Thursday 7 PM)", value="donderdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Donderdag 20:30 (Thursday 8:30 PM)",
                value="donderdag|om 20:30 uur",
            ),
            # Vrijdag / Friday
            app_commands.Choice(
                name="Vrijdag 19:00 (Friday 7 PM)", value="vrijdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Vrijdag 20:30 (Friday 8:30 PM)", value="vrijdag|om 20:30 uur"
            ),
            # Zaterdag / Saturday
            app_commands.Choice(
                name="Zaterdag 19:00 (Saturday 7 PM)", value="zaterdag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Zaterdag 20:30 (Saturday 8:30 PM)", value="zaterdag|om 20:30 uur"
            ),
            # Zondag / Sunday
            app_commands.Choice(
                name="Zondag 19:00 (Sunday 7 PM)", value="zondag|om 19:00 uur"
            ),
            app_commands.Choice(
                name="Zondag 20:30 (Sunday 8:30 PM)", value="zondag|om 20:30 uur"
            ),
        ],
    )
    @app_commands.describe(names="Names separated by comma / Namen gescheiden door komma")
    async def guest_remove(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        names: str,
    ) -> None:
        """Example: /guest-remove slot:'Friday 8:30 PM' names:'Mario, Luigi'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)
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
                parts.append(t(cid, "COMMANDS.guest_removed_list", names=", ".join(removed)))
            if not_found:
                parts.append(t(cid, "COMMANDS.guest_not_found", names=", ".join(not_found)))
            if not parts:
                parts = [t(cid, "COMMANDS.nothing_changed")]

            await interaction.followup.send(
                t(cid, "COMMANDS.guest_removed", dag=dag, tijd=tijd) + "\n" + "\n".join(parts),
                ephemeral=True,
            )
        except Exception as e:  # pragma: no cover
            cid = getattr(interaction.channel, "id", 0) or 0
            await interaction.followup.send(
                t(cid, "ERRORS.generic_error", error=str(e)), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollGuests(bot))
