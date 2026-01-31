# apps/ui/notification_settings.py
#
# UI voor notificatie instellingen met toggle buttons

import discord

from apps.utils.i18n import t
from apps.utils.poll_settings import (
    get_all_notification_states,
    toggle_notification_setting,
)

# Notificatie type definities (labels komen uit i18n)
# Key mapping naar i18n keys
NOTIFICATION_TYPE_KEYS = {
    "poll_opened": "notif_poll_opened",
    "poll_reset": "notif_poll_reset",
    "poll_closed": "notif_poll_closed",
    "reminders": "notif_reminders",
    "thursday_reminder": "notif_thursday_reminder",
    "misschien": "notif_misschien",
    "doorgaan": "notif_doorgaan",
    "celebration": "notif_celebration",
}

# Notificatie type definities met tijden en defaults
NOTIFICATION_TYPES = [
    {"key": "poll_opened", "tijd": "di 20:00", "emoji": "📂", "default": True},
    {"key": "poll_reset", "tijd": "di 20:00", "emoji": "🔄", "default": True},
    {"key": "poll_closed", "tijd": "ma 00:00", "emoji": "🔒", "default": True},
    {"key": "reminders", "tijd": "vr/za/zo 16:00", "emoji": "⏰", "default": False},
    {"key": "thursday_reminder", "tijd": "do 20:00", "emoji": "📅", "default": False},
    {"key": "misschien", "tijd": "17:00", "emoji": "❓", "default": False},
    {"key": "doorgaan", "tijd": "18:00", "emoji": "✅", "default": True},
    {"key": "celebration", "tijd": "automaat", "emoji": "🎉", "default": True},
]


def get_notification_label(key: str, channel_id: int = 0) -> str:
    """Get translated label for a notification type."""
    i18n_key = NOTIFICATION_TYPE_KEYS.get(key, key)
    return t(channel_id, f"SETTINGS.{i18n_key}")


class NotificationSettingsView(discord.ui.View):
    """View met 8 toggle buttons voor notificatie instellingen."""

    def __init__(self, channel_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.channel_id = channel_id

        # Haal huidige status op
        states = get_all_notification_states(channel_id)

        # Voeg buttons toe (2 per rij, 4 rijen totaal)
        for notif_type in NOTIFICATION_TYPES:
            key = notif_type["key"]
            enabled = states.get(key, notif_type["default"])
            label = get_notification_label(key, channel_id)

            self.add_item(
                NotificationButton(
                    key=key,
                    label=label,
                    tijd=notif_type["tijd"],
                    emoji=notif_type["emoji"],
                    enabled=enabled,
                )
            )


class NotificationButton(discord.ui.Button):
    """Toggle button voor een specifieke notificatie."""

    def __init__(
        self, key: str, label: str, tijd: str, emoji: str, enabled: bool | None
    ):
        self.key = key
        self.label_text = label
        self.tijd = tijd
        self.enabled = enabled if enabled is not None else True

        # Style: groen als enabled, grijs als disabled
        style = (
            discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary
        )

        # Label met tijd info
        button_label = f"{label}"

        super().__init__(
            style=style,
            label=button_label,
            emoji=emoji,
            custom_id=f"notification_{key}",
        )

    async def callback(self, interaction: discord.Interaction):
        """Toggle de notificatie instelling."""
        channel_id = interaction.channel_id
        if not channel_id:
            await interaction.response.send_message(
                "❌ Cannot determine channel ID.", ephemeral=True
            )
            return

        try:
            # Toggle de notificatie instelling
            nieuwe_status = toggle_notification_setting(channel_id, self.key)

            # Sync all settings to linked channels in the category
            from apps.utils.poll_settings import sync_settings_to_category

            sync_settings_to_category(interaction.channel)

            # Update button style
            self.enabled = nieuwe_status
            self.style = (
                discord.ButtonStyle.success
                if nieuwe_status
                else discord.ButtonStyle.secondary
            )

            # Update de settings message met nieuwe button states
            await interaction.response.edit_message(view=self.view)

        except Exception as e:
            # Toon errors
            await interaction.followup.send(
                f"❌ {t(channel_id, 'ERRORS.toggle_notification', error=str(e))}", ephemeral=True
            )


def create_notification_settings_embed(channel_id: int | None = None) -> discord.Embed:
    """Maak embed voor notificatie instellingen."""
    cid = channel_id or 0

    # Voeg legenda toe voor elke notificatie
    legend_lines = []
    for notif in NOTIFICATION_TYPES:
        label = get_notification_label(notif["key"], cid)
        legend_lines.append(f"{notif['emoji']} **{label}**: {notif['tijd']}")

    description = (
        f"{t(cid, 'SETTINGS.notification_settings_description')}\n\n"
        f"**{t(cid, 'SETTINGS.notification_legend')}:**\n"
        + "\n".join(legend_lines)
        + f"\n\n**{t(cid, 'SETTINGS.notification_status')}:**\n"
        + f"{t(cid, 'SETTINGS.status_active')}\n{t(cid, 'SETTINGS.status_inactive')}"
    )

    embed = discord.Embed(
        title=t(cid, "SETTINGS.notification_settings_title"),
        description=description,
        color=discord.Color.blue(),
    )

    embed.set_footer(text=t(cid, "SETTINGS.click_to_toggle"))

    return embed
