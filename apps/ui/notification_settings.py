# apps/ui/notification_settings.py
#
# UI voor notificatie instellingen met toggle buttons

import discord

from apps.utils.i18n import t
from apps.utils.poll_settings import (
    get_all_notification_states,
    get_reminder_time,
    set_reminder_time,
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

        # Haal reminder tijd op (voor "reminders" button)
        reminder_time = get_reminder_time(channel_id)

        # Voeg buttons toe (2 per rij, 4 rijen totaal)
        for notif_type in NOTIFICATION_TYPES:
            key = notif_type["key"]
            enabled = states.get(key, notif_type["default"])
            label = get_notification_label(key, channel_id)

            # Voor "reminders": toon de ingestelde tijd in plaats van standaard tijd
            if key == "reminders":
                tijd_display = reminder_time
            else:
                tijd_display = notif_type["tijd"]

            self.add_item(
                NotificationButton(
                    key=key,
                    label=label,
                    tijd=tijd_display,
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
        """Toggle de notificatie instelling of open tijd modal voor reminders."""
        channel_id = interaction.channel_id
        if not channel_id:
            await interaction.response.send_message(
                "❌ Cannot determine channel ID.", ephemeral=True
            )
            return

        try:
            # Speciale behandeling voor "reminders": open tijd modal
            if self.key == "reminders":
                current_time = get_reminder_time(channel_id)
                modal = ReminderTimeModal(channel_id, current_time)
                await interaction.response.send_modal(modal)
                return

            # Voor andere notificaties: gewoon togglen
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

    # Haal reminder tijd op voor dynamische display
    reminder_time = "16:00"  # Default
    if channel_id is not None:
        reminder_time = get_reminder_time(channel_id)

    # Voeg legenda toe voor elke notificatie
    legend_lines = []
    for notif in NOTIFICATION_TYPES:
        label = get_notification_label(notif["key"], cid)
        # Voor "reminders": toon de ingestelde tijd
        if notif["key"] == "reminders" and channel_id is not None:
            tijd_display = reminder_time
        else:
            tijd_display = notif["tijd"]
        legend_lines.append(f"{notif['emoji']} **{label}**: {tijd_display}")

    description = (
        f"{t(cid, 'SETTINGS.notification_settings_description')}\n\n"
        f"**{t(cid, 'SETTINGS.notification_legend')}:**\n"
        + "\n".join(legend_lines)
        + f"\n\n**{t(cid, 'SETTINGS.notification_status')}:**\n"
        + f"{t(cid, 'SETTINGS.status_active')}\n{t(cid, 'SETTINGS.status_inactive')}\n\n"
        + t(cid, "SETTINGS.reminder_tip")
    )

    embed = discord.Embed(
        title=t(cid, "SETTINGS.notification_settings_title"),
        description=description,
        color=discord.Color.blue(),
    )

    embed.set_footer(text=t(cid, "SETTINGS.click_to_toggle"))

    return embed


# ========================================================================
# Time Picker Modal voor Reminder Tijd
# ========================================================================


class ReminderTimeModal(discord.ui.Modal, title="⏰ Herinnering Tijd Instellen"):
    """Modal voor het instellen van de reminder tijd voor ghost notifications."""

    def __init__(self, channel_id: int, current_time: str):
        super().__init__()
        self.channel_id = channel_id

        # Parse huidige tijd
        try:
            uur, minuut = current_time.split(":")
            uur_int = int(uur)
            minuut_int = int(minuut)
        except (ValueError, IndexError):
            uur_int = 16
            minuut_int = 0

        # Uur input (0-23)
        self.uur_input = discord.ui.TextInput(
            label="Uur (0-23)",
            placeholder="16",
            default=str(uur_int),
            min_length=1,
            max_length=2,
            required=True,
        )
        self.add_item(self.uur_input)

        # Minuut input (0-59)
        self.minuut_input = discord.ui.TextInput(
            label="Minuut (0, 15, 30, 45)",
            placeholder="0",
            default=str(minuut_int),
            min_length=1,
            max_length=2,
            required=True,
        )
        self.add_item(self.minuut_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Verwerk de tijd input en sla op."""
        try:
            # Valideer uur
            uur = int(self.uur_input.value)
            if uur < 0 or uur > 23:
                await interaction.response.send_message(
                    "❌ Uur moet tussen 0 en 23 zijn.", ephemeral=True
                )
                return

            # Valideer minuut
            minuut = int(self.minuut_input.value)
            if minuut < 0 or minuut > 59:
                await interaction.response.send_message(
                    "❌ Minuut moet tussen 0 en 59 zijn.", ephemeral=True
                )
                return

            # Suggestie: gebruik alleen 0, 15, 30, 45 voor minuten (maar accepteer alle waarden)
            if minuut not in [0, 15, 30, 45]:
                await interaction.response.send_message(
                    f"⚠️ Tijd ingesteld op **{uur:02d}:{minuut:02d}**\n"
                    f"💡 Tip: Het is handiger om minuten als 0, 15, 30 of 45 te gebruiken.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"✅ Herinnering tijd ingesteld op **{uur:02d}:{minuut:02d}**",
                    ephemeral=True,
                )

            # Sla tijd op
            tijd_str = f"{uur:02d}:{minuut:02d}"
            set_reminder_time(self.channel_id, tijd_str)

        except ValueError:
            await interaction.response.send_message(
                "❌ Ongeldige invoer. Gebruik alleen cijfers.", ephemeral=True
            )
