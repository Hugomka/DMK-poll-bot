# apps/commands/poll_config.py
#
# Poll configuratie commands voor moderator/admin gebruik

import discord
from discord import app_commands

from apps.ui.notification_settings import (
    NotificationSettingsView,
    create_notification_settings_embed,
)
from apps.ui.poll_options_settings import (
    PollOptionsSettingsView,
    create_poll_options_settings_embed,
)


@app_commands.command(
    name="dmk-poll-instelling",
    description="⚙️ Open instellingen voor de poll (admin/moderator)",
)
@app_commands.describe(
    instelling="Welke instelling wil je aanpassen?"
)
@app_commands.choices(
    instelling=[
        app_commands.Choice(name="📊 Poll-opties (vrijdag/zaterdag/zondag 19:00/20:30)", value="poll-opties"),
        app_commands.Choice(name="🔔 Notificaties (reminders/donderdag/misschien)", value="notificaties"),
    ]
)
@app_commands.default_permissions(moderate_members=True)
@app_commands.guild_only()
async def poll_instelling(
    interaction: discord.Interaction, instelling: app_commands.Choice[str]
):
    """
    Open instellingen paneel voor de poll.

    Opties:
    - Poll-opties: Toggle vrijdag/zaterdag/zondag 19:00/20:30 aan/uit
    - Notificaties: Toggle reminders/donderdag/misschien aan/uit
    """
    await interaction.response.defer(ephemeral=True)

    channel_id = interaction.channel_id
    if not channel_id:
        await interaction.followup.send(
            "❌ Kan channel ID niet bepalen.", ephemeral=True
        )
        return

    try:
        if instelling.value == "poll-opties":
            # Open poll-opties settings UI
            channel = interaction.channel
            if not isinstance(channel, discord.TextChannel):
                await interaction.followup.send(
                    "❌ Dit command werkt alleen in text channels.", ephemeral=True
                )
                return

            embed = create_poll_options_settings_embed()
            view = PollOptionsSettingsView(channel_id, channel)

            await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=True
            )

        elif instelling.value == "notificaties":
            # Open notificatie instellingen UI
            embed = create_notification_settings_embed()
            view = NotificationSettingsView(channel_id)

            await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=True
            )

        else:
            await interaction.followup.send(
                "❌ Onbekende instelling gekozen.", ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Fout bij openen instellingen: {e}", ephemeral=True
        )


async def setup(bot):
    """Registreer poll config commands."""
    bot.tree.add_command(poll_instelling)
