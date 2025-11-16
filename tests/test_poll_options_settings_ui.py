# tests/test_poll_options_settings_ui.py
"""
Tests voor poll-opties instellingen UI (apps/ui/poll_options_settings.py).

Test coverage:
- PollOptionsSettingsView constructie met buttons
- PollOptionButton style (groen/grijs) op basis van enabled state
- PollOptionButton callback toggle logica
- _refresh_poll_messages efficiënte update logica
- _recreate_all_poll_messages voor nieuwe dagen
- _delete_day_message cleanup
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from apps.ui.poll_options_settings import (
    PollOptionButton,
    PollOptionsSettingsView,
    create_poll_options_settings_embed,
)
from apps.utils import poll_settings
from tests.base import BaseTestCase


class TestPollOptionsSettingsUI(BaseTestCase):
    """Tests voor poll-opties instellingen UI."""

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

    async def test_create_poll_options_settings_embed(self):
        """Test dat embed correct wordt aangemaakt."""
        embed = create_poll_options_settings_embed()

        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "⚙️ Instellingen Poll-opties")
        self.assertIn("Activeer of deactiveer", embed.description)
        self.assertIn("🟢 Groen = Actief", embed.description)
        self.assertIn("⚪ Grijs = Uitgeschakeld", embed.description)

    async def test_poll_options_settings_view_construction(self):
        """Test dat PollOptionsSettingsView correct wordt aangemaakt met 6 buttons."""
        channel_id = 123
        channel = MagicMock()

        view = PollOptionsSettingsView(channel_id, channel)

        # View heeft 6 buttons
        self.assertEqual(len(view.children), 6)

        # Check dat alle buttons PollOptionButton zijn
        for child in view.children:
            self.assertIsInstance(child, PollOptionButton)

        # Check volgorde: vrijdag 19:00, vrijdag 20:30, zaterdag 19:00, etc.
        self.assertEqual(view.children[0].dag, "vrijdag")
        self.assertEqual(view.children[0].tijd, "19:00")
        self.assertEqual(view.children[1].dag, "vrijdag")
        self.assertEqual(view.children[1].tijd, "20:30")
        self.assertEqual(view.children[2].dag, "zaterdag")
        self.assertEqual(view.children[2].tijd, "19:00")
        self.assertEqual(view.children[3].dag, "zaterdag")
        self.assertEqual(view.children[3].tijd, "20:30")
        self.assertEqual(view.children[4].dag, "zondag")
        self.assertEqual(view.children[4].tijd, "19:00")
        self.assertEqual(view.children[5].dag, "zondag")
        self.assertEqual(view.children[5].tijd, "20:30")

    async def test_poll_option_button_style_enabled(self):
        """Test dat enabled button groen (success) is."""
        button = PollOptionButton("vrijdag", "19:00", enabled=True)

        self.assertEqual(button.style, discord.ButtonStyle.success)
        self.assertEqual(button.label, "Vrijdag 19:00")
        self.assertEqual(str(button.emoji), "🔴")
        self.assertTrue(button.enabled)

    async def test_poll_option_button_style_disabled(self):
        """Test dat disabled button grijs (secondary) is."""
        button = PollOptionButton("zaterdag", "20:30", enabled=False)

        self.assertEqual(button.style, discord.ButtonStyle.secondary)
        self.assertEqual(button.label, "Zaterdag 20:30")
        self.assertEqual(str(button.emoji), "🟡")
        self.assertFalse(button.enabled)

    async def test_poll_option_button_emoji_colors(self):
        """Test dat elke dag de juiste emoji kleur heeft."""
        vrijdag_btn = PollOptionButton("vrijdag", "19:00", enabled=True)
        zaterdag_btn = PollOptionButton("zaterdag", "19:00", enabled=True)
        zondag_btn = PollOptionButton("zondag", "19:00", enabled=True)

        self.assertEqual(str(vrijdag_btn.emoji), "🔴")  # Rood
        self.assertEqual(str(zaterdag_btn.emoji), "🟡")  # Geel
        self.assertEqual(str(zondag_btn.emoji), "🟢")  # Groen

    async def test_poll_option_button_custom_id(self):
        """Test dat custom_id correct wordt gegenereerd."""
        button = PollOptionButton("zondag", "20:30", enabled=True)

        self.assertEqual(button.custom_id, "poll_option_zondag_20:30")

    @patch("apps.ui.poll_options_settings.is_channel_disabled")
    async def test_poll_option_button_callback_toggle_enable_to_disable(
        self, mock_is_disabled
    ):
        """Test button callback toggle van enabled naar disabled."""
        channel_id = 123
        channel = MagicMock()
        mock_is_disabled.return_value = False  # Bot is actief

        view = PollOptionsSettingsView(channel_id, channel)
        button = view.children[0]  # Vrijdag 19:00

        # Mock interaction
        interaction = MagicMock()
        interaction.channel_id = channel_id
        interaction.channel = channel
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Initial: enabled
        self.assertTrue(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.success)

        # Click button (toggle naar disabled)
        with patch.object(button, "_refresh_poll_messages", AsyncMock()):
            await button.callback(interaction)

        # Check dat button disabled is
        self.assertFalse(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.secondary)

        # Check dat state opgeslagen is
        self.assertFalse(
            poll_settings.get_poll_option_state(channel_id, "vrijdag", "19:00")
        )

        # Check dat interaction.response.edit_message called is
        interaction.response.edit_message.assert_called_once()

    @patch("apps.ui.poll_options_settings.is_channel_disabled")
    async def test_poll_option_button_callback_toggle_disable_to_enable(
        self, mock_is_disabled
    ):
        """Test button callback toggle van disabled naar enabled."""
        channel_id = 123
        channel = MagicMock()
        mock_is_disabled.return_value = False  # Bot is actief

        # Disable eerst
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "20:30", False)

        view = PollOptionsSettingsView(channel_id, channel)
        button = view.children[3]  # Zaterdag 20:30

        # Mock interaction
        interaction = MagicMock()
        interaction.channel_id = channel_id
        interaction.channel = channel
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Initial: disabled
        self.assertFalse(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.secondary)

        # Click button (toggle naar enabled)
        with patch.object(button, "_refresh_poll_messages", AsyncMock()):
            await button.callback(interaction)

        # Check dat button enabled is
        self.assertTrue(button.enabled)
        self.assertEqual(button.style, discord.ButtonStyle.success)

        # Check dat state opgeslagen is
        self.assertTrue(
            poll_settings.get_poll_option_state(channel_id, "zaterdag", "20:30")
        )

    @patch("apps.ui.poll_options_settings.is_channel_disabled")
    async def test_poll_option_button_callback_bot_inactive_shows_warning(
        self, mock_is_disabled
    ):
        """Test dat waarschuwing getoond wordt als bot niet actief is."""
        channel_id = 123
        channel = MagicMock()
        mock_is_disabled.return_value = True  # Bot is NIET actief

        view = PollOptionsSettingsView(channel_id, channel)
        button = view.children[0]

        # Mock interaction
        interaction = MagicMock()
        interaction.channel_id = channel_id
        interaction.channel = channel
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Click button
        await button.callback(interaction)

        # Check dat waarschuwing getoond wordt
        interaction.followup.send.assert_called_once()
        args = interaction.followup.send.call_args
        self.assertIn("niet actief", args[0][0])
        self.assertTrue(args[1]["ephemeral"])

    @patch("apps.ui.poll_options_settings.is_channel_disabled")
    @patch("apps.ui.poll_options_settings.schedule_poll_update")
    @patch("apps.ui.poll_options_settings.get_message_id")
    async def test_refresh_poll_messages_efficient_edit(
        self, mock_get_msg_id, mock_schedule, mock_is_disabled
    ):
        """Test efficiënte edit als message bestaat (geen nieuwe dag)."""
        channel_id = 123
        channel = MagicMock()
        mock_is_disabled.return_value = False

        # Alle dagen hebben messages
        mock_get_msg_id.side_effect = lambda cid, dag: 999

        # schedule_poll_update moet AsyncMock returnen
        async def mock_schedule_async(*args, **kwargs):
            pass

        mock_schedule.side_effect = mock_schedule_async

        view = PollOptionsSettingsView(channel_id, channel)
        button = view.children[0]  # Vrijdag 19:00
        # button.view is al gezet door add_item in PollOptionsSettingsView

        # Toggle vrijdag 19:00 uit
        poll_settings.set_poll_option_state(channel_id, "vrijdag", "19:00", False)

        # Refresh
        await button._refresh_poll_messages(channel)

        # Check dat schedule_poll_update called is voor vrijdag (edit)
        # Geen nieuwe dag, dus efficiënte edit
        calls = [call[0][1] for call in mock_schedule.call_args_list]
        self.assertIn("vrijdag", calls)

    async def test_is_day_completely_disabled_integration(self):
        """Test dat is_day_completely_disabled correct werkt met toggle logic."""
        channel_id = 123

        # Disable zaterdag volledig
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "19:00", False)
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "20:30", False)

        # Check dat zaterdag volledig disabled is
        from apps.utils.poll_settings import is_day_completely_disabled

        self.assertTrue(is_day_completely_disabled(channel_id, "zaterdag"))

        # Enable één tijd
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "20:30", True)

        # Zaterdag niet meer volledig disabled
        self.assertFalse(is_day_completely_disabled(channel_id, "zaterdag"))

    @patch("apps.ui.poll_options_settings.is_channel_disabled")
    @patch("apps.ui.poll_options_settings.get_message_id")
    async def test_refresh_poll_messages_recreate_on_new_day(
        self, mock_get_msg_id, mock_is_disabled
    ):
        """Test dat alles opnieuw gemaakt wordt als nieuwe dag enabled wordt."""
        channel_id = 123
        channel = MagicMock()
        mock_is_disabled.return_value = False

        # Zondag heeft GEEN message (was disabled)
        def get_msg_side_effect(cid, dag):
            return 999 if dag != "zondag" else None

        mock_get_msg_id.side_effect = get_msg_side_effect

        # Enable zondag (was disabled)
        poll_settings.set_poll_option_state(channel_id, "zondag", "20:30", True)

        view = PollOptionsSettingsView(channel_id, channel)
        button = view.children[4]  # Zondag 19:00
        # button.view is al gezet door add_item

        # Mock _recreate_all_poll_messages
        with patch.object(
            button, "_recreate_all_poll_messages", AsyncMock()
        ) as mock_recreate:
            await button._refresh_poll_messages(channel)

            # Check dat alles opnieuw gemaakt wordt (nieuwe dag)
            mock_recreate.assert_called_once_with(channel)

    async def test_delete_day_message_removes_message_and_clears_id(self):
        """Test dat _delete_day_message message verwijdert en ID cleart."""
        channel_id = 123
        channel = MagicMock()

        view = PollOptionsSettingsView(channel_id, channel)
        button = view.children[0]
        # button.view is al gezet door add_item

        # Mock message
        mock_msg = MagicMock()
        mock_msg.delete = AsyncMock()

        with patch(
            "apps.ui.poll_options_settings.get_message_id", return_value=999
        ), patch(
            "apps.ui.poll_options_settings.fetch_message_or_none",
            return_value=mock_msg,
        ), patch(
            "apps.ui.poll_options_settings.clear_message_id"
        ) as mock_clear:
            await button._delete_day_message(channel, "vrijdag")

            # Check dat message.delete called is
            mock_msg.delete.assert_called_once()

            # Check dat message ID gecleared is
            mock_clear.assert_called_once_with(channel_id, "vrijdag")

    async def test_delete_day_message_no_message_id(self):
        """Test dat _delete_day_message niets doet als geen message ID."""
        channel_id = 123
        channel = MagicMock()

        view = PollOptionsSettingsView(channel_id, channel)
        button = view.children[0]
        # button.view is al gezet door add_item

        with patch(
            "apps.ui.poll_options_settings.get_message_id", return_value=None
        ), patch(
            "apps.ui.poll_options_settings.fetch_message_or_none"
        ) as mock_fetch:
            await button._delete_day_message(channel, "zaterdag")

            # fetch_message_or_none niet called (geen message ID)
            mock_fetch.assert_not_called()
