# apps/ui/notification_settings.py
#
# UI voor notificatie instellingen met toggle buttons

import discord

from apps.utils.poll_settings import (
    get_all_notification_states,
    get_reminder_time,
    set_notification_setting,
    set_reminder_time,
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


# ========================================================================
# Helper functies voor reminder tijd formatting
# ========================================================================


def _get_default_deadline_hour() -> int:
    """Haal standaard deadline uur op (18:00)."""
    return 18


def _format_minutes_before(minuten: int) -> str:
    """Format minuten naar leesbare tekst (bijv. '2 uur' of '30 minuten')."""
    if minuten >= 60:
        uren = minuten // 60
        rest_minuten = minuten % 60
        if rest_minuten == 0:
            return f"{uren} uur"
        return f"{uren} uur en {rest_minuten} min"
    return f"{minuten} min"


def _calculate_reminder_time(deadline_uur: int, minuten_voor: int) -> str:
    """Bereken de absolute tijd gegeven deadline en minuten ervoor."""
    # Totaal minuten vanaf middernacht voor deadline
    deadline_minuten = deadline_uur * 60
    # Trek minuten_voor af
    reminder_minuten = deadline_minuten - minuten_voor

    # Zorg dat we niet negatief gaan (wrap naar vorige dag niet ondersteund)
    if reminder_minuten < 0:
        reminder_minuten = 0

    uur = reminder_minuten // 60
    minuut = reminder_minuten % 60
    return f"{uur:02d}:{minuut:02d}"


class NotificationSettingsView(discord.ui.View):
    """View met 8 toggle buttons voor notificatie instellingen."""

    def __init__(self, channel_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.channel_id = channel_id

        # Haal huidige status op
        states = get_all_notification_states(channel_id)

        # Haal reminder minuten op (voor "reminders" button)
        reminder_value = get_reminder_time(channel_id)

        # Voeg buttons toe (2 per rij, 4 rijen totaal)
        for notif_type in NOTIFICATION_TYPES:
            key = notif_type["key"]
            enabled = states.get(key, notif_type["default"])

            # Voor "reminders": toon minuten vóór deadline
            if key == "reminders":
                try:
                    minuten = int(reminder_value)
                    tijd_display = f"{_format_minutes_before(minuten)} vóór"
                except ValueError:
                    tijd_display = "2 uur vóór"  # Default display
            else:
                tijd_display = notif_type["tijd"]

            self.add_item(
                NotificationButton(
                    key=key,
                    label=notif_type["label"],
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
                "❌ Kan channel ID niet bepalen.", ephemeral=True
            )
            return

        try:
            # Speciale behandeling voor "reminders":
            # - Als UIT: open modal om tijd in te stellen (schakelt automatisch in)
            # - Als AAN: toggle naar UIT
            if self.key == "reminders":
                if self.enabled:
                    # Is AAN -> zet UIT (toggle gedrag)
                    nieuwe_status = toggle_notification_setting(channel_id, self.key)
                    self.enabled = nieuwe_status
                    self.style = discord.ButtonStyle.secondary

                    # Update view
                    await interaction.response.edit_message(view=self.view)
                    return
                else:
                    # Is UIT -> open modal om tijd in te stellen
                    current_value = get_reminder_time(channel_id)
                    # Converteer naar int (minuten), default 120 (2 uur)
                    try:
                        current_minutes = int(current_value)
                    except ValueError:
                        current_minutes = 120  # Default: 2 uur vóór deadline
                    modal = ReminderTimeModal(channel_id, current_minutes)
                    await interaction.response.send_modal(modal)
                    return

            # Voor andere notificaties: gewoon togglen
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


def create_notification_settings_embed(channel_id: int | None = None) -> discord.Embed:
    """Maak embed voor notificatie instellingen."""
    # Haal reminder minuten op voor dynamische display
    reminder_display = "2 uur vóór deadline"  # Default
    if channel_id is not None:
        reminder_value = get_reminder_time(channel_id)
        try:
            minuten = int(reminder_value)
            deadline_uur = _get_default_deadline_hour()
            tijd_str = _calculate_reminder_time(deadline_uur, minuten)
            reminder_display = f"{_format_minutes_before(minuten)} vóór deadline ({tijd_str})"
        except ValueError:
            pass  # Gebruik default

    # Voeg legenda toe voor elke notificatie
    legend_lines = []
    for notif in NOTIFICATION_TYPES:
        # Voor "reminders": toon minuten vóór deadline
        if notif["key"] == "reminders":
            tijd_display = reminder_display
        else:
            tijd_display = notif["tijd"]
        legend_lines.append(f"{notif['emoji']} **{notif['label']}**: {tijd_display}")

    description = (
        "Schakel automatische notificaties in of uit. "
        "Deze instellingen bepalen welke notificaties de bot automatisch verstuurt.\n\n"
        "**Legenda:**\n"
        + "\n".join(legend_lines)
        + "\n\n**Status:**\n🟢 Groen = Actief\n⚪ Grijs = Uitgeschakeld\n\n"
        "💡 **Tip:** Klik op ⏰ Herinnering stemmen om de tijd aan te passen!"
    )

    embed = discord.Embed(
        title="🔔 Instellingen Notificaties",
        description=description,
        color=discord.Color.blue(),
    )

    embed.set_footer(text="Klik op een knop om de status te togglen")

    return embed


# ========================================================================
# Time Picker Modal voor Reminder Tijd
# ========================================================================


class ReminderTimeModal(discord.ui.Modal, title="⏰ Herinnering Instellen"):
    """Modal voor het instellen van de reminder tijd voor ghost notifications."""

    def __init__(self, channel_id: int, current_minutes_before: int):
        super().__init__()
        self.channel_id = channel_id
        self.deadline_uur = _get_default_deadline_hour()

        # Input voor minuten vóór deadline
        self.minuten_input = discord.ui.TextInput(
            label=f"Minuten vóór deadline ({self.deadline_uur}:00)",
            placeholder="120",
            default=str(current_minutes_before),
            min_length=1,
            max_length=4,
            required=True,
        )
        self.add_item(self.minuten_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Verwerk de input en sla op."""
        try:
            # Valideer input
            minuten_voor = int(self.minuten_input.value)
            if minuten_voor < 1:
                await interaction.response.send_message(
                    "❌ Moet minimaal 1 minuut vóór deadline zijn.", ephemeral=True
                )
                return

            # Max is deadline_uur * 60 (hele dag)
            max_minuten = self.deadline_uur * 60
            if minuten_voor > max_minuten:
                await interaction.response.send_message(
                    f"❌ Maximum is {max_minuten} minuten ({self.deadline_uur} uur) vóór deadline.",
                    ephemeral=True,
                )
                return

            # Sla op als minuten (niet als tijd string)
            set_reminder_time(self.channel_id, str(minuten_voor))

            # Zet de notificatie AAN
            set_notification_setting(self.channel_id, "reminders", True)

            # Bereken de resulterende tijd voor feedback
            tijd_str = _calculate_reminder_time(self.deadline_uur, minuten_voor)
            tijd_beschrijving = _format_minutes_before(minuten_voor)

            # Update het originele bericht met vernieuwde embed en view
            new_embed = create_notification_settings_embed(self.channel_id)
            new_view = NotificationSettingsView(self.channel_id)

            await interaction.response.edit_message(
                content=f"✅ Herinnering ingesteld op **{tijd_beschrijving}** vóór deadline "
                f"(om **{tijd_str}**)",
                embed=new_embed,
                view=new_view,
            )

        except ValueError:
            await interaction.response.send_message(
                "❌ Ongeldige invoer. Gebruik alleen cijfers.", ephemeral=True
            )
