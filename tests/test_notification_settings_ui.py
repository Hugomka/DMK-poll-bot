# tests/test_notification_settings_ui.py
"""
Tests voor notificatie instellingen UI (apps/ui/notification_settings.py).

Test coverage:
- NotificationSettingsView constructie met 8 buttons
- NotificationButton style (groen/grijs) op basis van enabled state
- NotificationButton callback toggle logica
- create_notification_settings_embed
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock

import discord

from apps.ui.notification_settings import (
    NOTIFICATION_TYPES,
    NotificationButton,
    NotificationSettingsView,
    create_notification_settings_embed,
)
from apps.utils import poll_settings
from tests.base import BaseTestCase


class TestNotificationSettingsUI(BaseTestCase):
    """Tests voor notificatie instellingen UI."""

    async def asyncSetUp(self):
        """Set up isolated test environment."""
        await super().asyncSetUp()

        # Create temp file voor settings
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        self.temp_file.close()
        self.temp_settings_path = self.temp_file.name

        # Patch SETTINGS_FILE
        self.original_settings_file = poll_settings.SETTINGS_FILE
        poll_settings.SETTINGS_FILE = self.temp_settings_path

    async def asyncTearDown(self):
        """Clean up."""
        poll_settings.SETTINGS_FILE = self.original_settings_file

        import os
        try:
            if os.path.exists(self.temp_settings_path):
                os.unlink(self.temp_settings_path)
        except Exception:  # pragma: no cover
            pass

        await super().asyncTearDown()

    async def test_create_notification_settings_embed(self):
        """Test dat embed correct wordt aangemaakt."""
        embed = create_notification_settings_embed()

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "🔔 Instellingen Notificaties")
        self.assertIn("Schakel automatische notificaties in of uit", embed.description)
        self.assertIn("🟢 Groen = Actief", embed.description)
        self.assertIn("⚪ Grijs = Uitgeschakeld", embed.description)

    async def test_notification_settings_view_construction(self):
        """Test dat NotificationSettingsView correct wordt aangemaakt met 8 buttons."""
        channel_id = 123

        view = NotificationSettingsView(channel_id)

        # View heeft 8 buttons
        self.assertEqual(len(view.children), 8)

        # Check dat alle buttons NotificationButton zijn
        for child in view.children:
            self.assertIsInstance(child, NotificationButton)

    async def test_notification_settings_view_button_order(self):
        """Test dat buttons in juiste volgorde staan."""
        channel_id = 123
        view = NotificationSettingsView(channel_id)

        # Check volgorde matches NOTIFICATION_TYPES
        for i, notif_type in enumerate(NOTIFICATION_TYPES):
            button = view.children[i]
            self.assertEqual(button.key, notif_type["key"])

    async def test_notification_button_style_enabled(self):
        """Test dat enabled button groen (success) is."""
        button = NotificationButton(
            key="poll_opened",
            label="Poll geopend",
            tijd="di 20:00",
            emoji="📂",
            enabled=True
        )

        self.assertEqual(button.style, discord.ButtonStyle.success)
        self.assertEqual(button.label, "Poll geopend")
        self.assertEqual(str(button.emoji), "📂")
        self.assertTrue(button.enabled)

    async def test_notification_button_style_disabled(self):
        """Test dat disabled button grijs (secondary) is."""
        button = NotificationButton(
            key="reminders",
            label="Herinnering stemmen",
            tijd="vr/za/zo 16:00",
            emoji="⏰",
            enabled=False
        )

        self.assertEqual(button.style, discord.ButtonStyle.secondary)
        self.assertEqual(button.label, "Herinnering stemmen")
        self.assertEqual(str(button.emoji), "⏰")
        self.assertFalse(button.enabled)

    async def test_notification_button_custom_id(self):
        """Test dat custom_id correct wordt gegenereerd."""
        button = NotificationButton(
            key="celebration",
            label="Felicitatie",
            tijd="automaat",
            emoji="🎉",
            enabled=True
        )

        self.assertEqual(button.custom_id, "notification_celebration")

    async def test_notification_button_callback_toggle_enable_to_disable(self):
        """Test button callback toggle van enabled naar disabled."""
        channel_id = 123
        view = NotificationSettingsView(channel_id)
        button = view.children[0]  # poll_opened

        # Mock interaction
        interaction = MagicMock()
        interaction.channel_id = channel_id
        interaction.response = AsyncMock()

        # Initial: enabled (default voor poll_opened)
        self.assertTrue(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.success)

        # Click button (toggle naar disabled)
        await button.callback(interaction)

        # Check dat button disabled is
        self.assertFalse(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.secondary)

        # Check dat state opgeslagen is
        self.assertFalse(
            poll_settings.is_notification_enabled(channel_id, "poll_opened")
        )

        # Check dat interaction.response.edit_message called is
        interaction.response.edit_message.assert_called_once()

    async def test_notification_button_callback_toggle_disable_to_enable(self):
        """Test button callback toggle van disabled naar enabled."""
        channel_id = 123
        view = NotificationSettingsView(channel_id)
        button = view.children[3]  # reminders (default disabled)

        # Mock interaction
        interaction = MagicMock()
        interaction.channel_id = channel_id
        interaction.response = AsyncMock()

        # Initial: disabled (default voor reminders)
        self.assertFalse(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.secondary)

        # Click button (toggle naar enabled)
        await button.callback(interaction)

        # Check dat button enabled is
        self.assertTrue(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.success)

        # Check dat state opgeslagen is
        self.assertTrue(
            poll_settings.is_notification_enabled(channel_id, "reminders")
        )

    async def test_notification_button_callback_no_channel_id(self):
        """Test dat error getoond wordt als geen channel ID."""
        channel_id = 123
        view = NotificationSettingsView(channel_id)
        button = view.children[0]

        # Mock interaction zonder channel_id
        interaction = MagicMock()
        interaction.channel_id = None
        interaction.response = AsyncMock()

        # Click button
        await button.callback(interaction)

        # Check dat error message getoond wordt
        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args
        self.assertIn("Kan channel ID niet bepalen", args[0][0])
        self.assertTrue(args[1]["ephemeral"])

    async def test_notification_button_callback_exception_handling(self):
        """Test dat exceptions netjes afgehandeld worden."""
        channel_id = 123
        view = NotificationSettingsView(channel_id)
        button = view.children[0]

        # Mock interaction die exception gooit bij edit_message
        interaction = MagicMock()
        interaction.channel_id = channel_id
        interaction.response = AsyncMock()
        interaction.response.edit_message.side_effect = Exception("Test error")
        interaction.followup = AsyncMock()

        # Click button
        await button.callback(interaction)

        # Check dat error via followup getoond wordt
        interaction.followup.send.assert_called_once()
        args = interaction.followup.send.call_args
        self.assertIn("Fout bij togglen notificatie", args[0][0])
        self.assertTrue(args[1]["ephemeral"])

    async def test_all_notification_types_have_correct_defaults(self):
        """Test dat alle notificatie types de juiste default hebben."""
        channel_id = 123
        view = NotificationSettingsView(channel_id)

        # Check dat defaults correct zijn
        enabled_defaults = ["poll_opened", "poll_reset", "poll_closed", "doorgaan", "celebration"]
        disabled_defaults = ["reminders", "thursday_reminder", "misschien"]

        for i, notif_type in enumerate(NOTIFICATION_TYPES):
            button = view.children[i]

            if notif_type["key"] in enabled_defaults:
                self.assertTrue(button.enabled, f"{notif_type['key']} should be enabled by default")
                self.assertEqual(button.style, discord.ButtonStyle.success)
            elif notif_type["key"] in disabled_defaults:
                self.assertFalse(button.enabled, f"{notif_type['key']} should be disabled by default")
                self.assertEqual(button.style, discord.ButtonStyle.secondary)

    async def test_notification_types_constant_has_8_entries(self):
        """Test dat NOTIFICATION_TYPES 8 entries heeft."""
        self.assertEqual(len(NOTIFICATION_TYPES), 8)

    async def test_notification_types_have_required_fields(self):
        """Test dat alle notification types de vereiste velden hebben."""
        required_fields = ["key", "label", "tijd", "emoji", "default"]

        for notif_type in NOTIFICATION_TYPES:
            for field in required_fields:
                self.assertIn(field, notif_type, f"Missing {field} in {notif_type}")

    async def test_embed_contains_all_notification_types(self):
        """Test dat embed alle 8 notificatie types bevat in legenda."""
        embed = create_notification_settings_embed()

        # Check dat alle labels in description staan
        for notif_type in NOTIFICATION_TYPES:
            self.assertIn(notif_type["label"], embed.description)
            self.assertIn(notif_type["emoji"], embed.description)
