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
from apps.utils.poll_settings import WEEK_DAYS
from apps.utils.poll_storage import get_votes_for_option


@app_commands.command(
    name="dmk-poll-instelling",
    description="⚙️ Open instellingen voor de poll (admin/moderator)",
)
@app_commands.describe(instelling="Welke instelling wil je aanpassen?")
@app_commands.choices(
    instelling=[
        app_commands.Choice(name="📊 Poll-opties", value="poll-opties"),
        app_commands.Choice(name="🔔 Notificaties", value="notificaties"),
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
    - Poll-opties: Toggle maandag t/m zondag 19:00/20:30 aan/uit
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

            # Haal guild_id op
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ Kan guild ID niet bepalen.", ephemeral=True
                )
                return

            # Verzamel stemmen per optie (voor alle dagen en tijden)
            votes_per_option: dict[str, int] = {}
            for dag in WEEK_DAYS:
                for tijd_key in ["om 19:00 uur", "om 20:30 uur"]:
                    optie_key = f"{dag}_{tijd_key}"
                    try:
                        stemmen = await get_votes_for_option(
                            dag, tijd_key, guild_id, channel_id
                        )
                        votes_per_option[optie_key] = stemmen
                    except Exception:  # pragma: no cover
                        votes_per_option[optie_key] = 0

            embed = create_poll_options_settings_embed(channel_id)
            view = PollOptionsSettingsView(
                channel_id, channel, guild_id, votes_per_option
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        elif instelling.value == "notificaties":
            # Open notificatie instellingen UI
            embed = create_notification_settings_embed(channel_id)
            view = NotificationSettingsView(channel_id)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        else:
            await interaction.followup.send(
                "❌ Onbekende instelling gekozen.", ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Fout bij openen instellingen: {e}", ephemeral=True
        )


@app_commands.command(
    name="dmk-poll-taal",
    description="🌐 Set bot language / Stel bot taal in",
)
@app_commands.describe(language="Choose language / Kies taal")
@app_commands.choices(
    language=[
        app_commands.Choice(name="🇳🇱 Nederlands", value="nl"),
        app_commands.Choice(name="🇬🇧 English", value="en"),
    ]
)
@app_commands.default_permissions(moderate_members=True)
@app_commands.guild_only()
async def poll_taal(
    interaction: discord.Interaction, language: app_commands.Choice[str]
):
    """
    Set the bot language for this channel.
    Stel de bot taal in voor dit kanaal.
    """
    channel_id = interaction.channel_id
    if not channel_id:
        await interaction.response.send_message(
            "❌ Cannot determine channel ID.", ephemeral=True
        )
        return

    try:
        from apps.utils.poll_settings import set_language
        from apps.utils.i18n import t

        set_language(channel_id, language.value)
        await interaction.response.send_message(
            t(channel_id, "UI.language_changed"),
            ephemeral=True,
        )

    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error setting language: {e}", ephemeral=True
        )


async def setup(bot):
    """Registreer poll config commands."""
    bot.tree.add_command(poll_instelling)
    bot.tree.add_command(poll_taal)
