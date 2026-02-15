# tests/test_status_schedule_field.py

"""
Tests for period schedule field display in /dmk-poll-status command.
"""

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.commands.poll_status import PollStatus
from apps.utils import poll_settings
from apps.utils.poll_settings import set_period_settings


class TestStatusScheduleField(unittest.IsolatedAsyncioTestCase):
    """Test that /dmk-poll-status shows period schedule fields correctly."""

    def setUp(self):
        """Reset settings before each test using temp file."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        self.temp_file.close()
        self.temp_settings_path = self.temp_file.name

        self.original_settings_file = poll_settings.SETTINGS_FILE
        poll_settings.SETTINGS_FILE = self.temp_settings_path

    def tearDown(self):
        """Clean up after each test."""
        poll_settings.SETTINGS_FILE = self.original_settings_file
        try:
            if os.path.exists(self.temp_settings_path):
                os.remove(self.temp_settings_path)
        except Exception:
            pass

    def _make_interaction(self, channel_id=123456, guild_id=789):
        mock_guild = MagicMock()
        mock_guild.id = guild_id

        mock_channel = MagicMock()
        mock_channel.id = channel_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = mock_channel
        interaction.guild = mock_guild
        return interaction

    def _get_embed(self, interaction):
        call_kwargs = interaction.followup.send.call_args[1]
        return call_kwargs.get("embed")

    def _get_field_by_name(self, embed, substr):
        for field in embed.fields:
            if substr in str(field.name):
                return field
        return None

    async def test_status_shows_both_periods(self):
        """Test that status shows both vr-zo and ma-do period fields."""
        set_period_settings(123456, "vr-zo", enabled=True, open_day="dinsdag", open_time="20:00", close_day="maandag", close_time="00:00")
        set_period_settings(123456, "ma-do", enabled=True, open_day="vrijdag", open_time="20:00", close_day="vrijdag", close_time="00:00")

        cog = PollStatus(MagicMock())
        interaction = self._make_interaction()

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(interaction)

        embed = self._get_embed(interaction)
        self.assertIsNotNone(embed)

        vrzo_field = self._get_field_by_name(embed, "vr-zo")
        mado_field = self._get_field_by_name(embed, "ma-do")

        self.assertIsNotNone(vrzo_field, f"vr-zo field not found. Fields: {[f.name for f in embed.fields]}")
        self.assertIsNotNone(mado_field, f"ma-do field not found. Fields: {[f.name for f in embed.fields]}")

        assert vrzo_field is not None
        assert mado_field is not None
        self.assertIn("Ingeschakeld", str(vrzo_field.value))
        self.assertIn("Ingeschakeld", str(mado_field.value))

    async def test_status_shows_open_close_times(self):
        """Test that enabled periods show open/close day and time."""
        set_period_settings(123456, "vr-zo", enabled=True, open_day="dinsdag", open_time="20:00", close_day="maandag", close_time="00:00")

        cog = PollStatus(MagicMock())
        interaction = self._make_interaction()

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(interaction)

        embed = self._get_embed(interaction)
        vrzo_field = self._get_field_by_name(embed, "vr-zo")
        self.assertIsNotNone(vrzo_field)
        assert vrzo_field is not None

        value = str(vrzo_field.value)
        self.assertIn("dinsdag", value)
        self.assertIn("20:00", value)
        self.assertIn("maandag", value)
        self.assertIn("00:00", value)

    async def test_status_disabled_period_shows_uitgeschakeld(self):
        """Test that disabled period shows 'Uitgeschakeld' without open/close times."""
        set_period_settings(123456, "ma-do", enabled=False)

        cog = PollStatus(MagicMock())
        interaction = self._make_interaction()

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(interaction)

        embed = self._get_embed(interaction)
        mado_field = self._get_field_by_name(embed, "ma-do")
        self.assertIsNotNone(mado_field)
        assert mado_field is not None

        value = str(mado_field.value)
        self.assertIn("Uitgeschakeld", value)
        # Should not show open/close times for disabled period
        self.assertNotIn("Opent:", value)
        self.assertNotIn("Sluit:", value)

    async def test_status_shows_open_closed_indicator(self):
        """Test that enabled periods show open/closed status indicator."""
        set_period_settings(123456, "vr-zo", enabled=True, open_day="dinsdag", open_time="20:00", close_day="maandag", close_time="00:00")

        cog = PollStatus(MagicMock())
        interaction = self._make_interaction()

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(interaction)

        embed = self._get_embed(interaction)
        vrzo_field = self._get_field_by_name(embed, "vr-zo")
        self.assertIsNotNone(vrzo_field)
        assert vrzo_field is not None

        value = str(vrzo_field.value)
        # Should show either Open or Gesloten indicator
        self.assertTrue(
            "🟢 Open" in value or "🔴 Gesloten" in value,
            f"Expected open/closed indicator in: {value}",
        )


if __name__ == "__main__":
    unittest.main()
