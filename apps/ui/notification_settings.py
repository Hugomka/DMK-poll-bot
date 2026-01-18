# apps/ui/notification_settings.py
#
# UI voor notificatie instellingen met toggle buttons

import discord

from apps.utils.poll_settings import (
    get_all_notification_states,
    toggle_notification_setting,
)

# Notificatie type definities met labels en tijden
NOTIFICATION_TYPES = [
    {
        "key": "poll_opened",
        "label": "Poll geopend",
        "tijd": "di 20:00",
        "emoji": "📂",
        "default": True,
    },
    {
        "key": "poll_reset",
        "label": "Poll gereset",
        "tijd": "di 20:00",
        "emoji": "🔄",
        "default": True,
    },
    {
        "key": "poll_closed",
        "label": "Poll gesloten",
        "tijd": "ma 00:00",
        "emoji": "🔒",
        "default": True,
    },
    {
        "key": "reminders",
        "label": "Herinnering stemmen",
        "tijd": "vr/za/zo 16:00",
        "emoji": "⏰",
        "default": False,
    },
    {
        "key": "thursday_reminder",
        "label": "Herinnering weekend",
        "tijd": "do 20:00",
        "emoji": "📅",
        "default": False,
    },
    {
        "key": "misschien",
        "label": "Herinnering misschien",
        "tijd": "17:00",
        "emoji": "❓",
        "default": False,
    },
    {
        "key": "doorgaan",
        "label": "Doorgaan",
        "tijd": "18:00",
        "emoji": "✅",
        "default": True,
    },
    {
        "key": "celebration",
        "label": "Felicitatie",
        "tijd": "automaat",
        "emoji": "🎉",
        "default": True,
    },
]


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

            self.add_item(
                NotificationButton(
                    key=key,
                    label=notif_type["label"],
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
                "❌ Kan channel ID niet bepalen.", ephemeral=True
            )
            return

        try:
            # Toggle de notificatie instelling
            nieuwe_status = toggle_notification_setting(channel_id, self.key)

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
                f"❌ Fout bij togglen notificatie: {e}", ephemeral=True
            )


def create_notification_settings_embed() -> discord.Embed:
    """Maak embed voor notificatie instellingen."""
    # Voeg legenda toe voor elke notificatie
    legend_lines = []
    for notif in NOTIFICATION_TYPES:
        legend_lines.append(f"{notif['emoji']} **{notif['label']}**: {notif['tijd']}")

    description = (
        "Schakel automatische notificaties in of uit. "
        "Deze instellingen bepalen welke notificaties de bot automatisch verstuurt.\n\n"
        "**Legenda:**\n"
        + "\n".join(legend_lines)
        + "\n\n**Status:**\n🟢 Groen = Actief\n⚪ Grijs = Uitgeschakeld"
    )

    embed = discord.Embed(
        title="🔔 Instellingen Notificaties",
        description=description,
        color=discord.Color.blue(),
    )

    embed.set_footer(text="Klik op een knop om de status te togglen")

    return embed
