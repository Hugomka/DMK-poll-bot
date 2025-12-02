# tests/test_status_schedule_field.py

"""
Tests for schedule field display in /dmk-poll-status command.
"""

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.commands.poll_status import PollStatus
from apps.utils import poll_settings
from apps.utils.poll_settings import (
    set_default_activation,
    set_default_deactivation,
    set_scheduled_activation,
    set_scheduled_deactivation,
)


class TestStatusScheduleField(unittest.IsolatedAsyncioTestCase):
    """Test that /dmk-poll-status shows schedule fields correctly with default labels."""

    def setUp(self):
        """Reset settings before each test using temp file."""
        # Create temp file for this test
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        self.temp_file.close()
        self.temp_settings_path = self.temp_file.name

        # Patch SETTINGS_FILE to use temp file
        self.original_settings_file = poll_settings.SETTINGS_FILE
        poll_settings.SETTINGS_FILE = self.temp_settings_path

    def tearDown(self):
        """Clean up after each test."""
        # Restore original settings file
        poll_settings.SETTINGS_FILE = self.original_settings_file

        # Remove temp file
        try:
            if os.path.exists(self.temp_settings_path):
                os.remove(self.temp_settings_path)
        except Exception:
            pass

    async def test_status_shows_geen_when_no_schedules(self):
        """Test that status shows 'Geen' when no schedules are set."""
        # Clear any seeded defaults
        set_default_activation(None)
        set_default_deactivation(None)

        # Mock bot and interaction
        mock_bot = MagicMock()
        mock_interaction = MagicMock()
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        # Mock channel with ID
        mock_channel = MagicMock()
        mock_channel.id = 123456
        mock_interaction.channel = mock_channel

        # Mock guild
        mock_guild = MagicMock()
        mock_guild.id = 789
        mock_interaction.guild = mock_guild

        cog = PollStatus(mock_bot)

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(mock_interaction)

        # Check that followup.send was called
        self.assertTrue(mock_interaction.followup.send.called)

        # Get the embed that was sent
        call_kwargs = mock_interaction.followup.send.call_args[1]
        embed = call_kwargs.get("embed")

        self.assertIsNotNone(embed)

        # Find the schedule fields
        act_field = None
        deact_field = None
        for field in embed.fields:
            if "activatie" in field.name.lower():
                act_field = field
            if "deactivatie" in field.name.lower():
                deact_field = field

        self.assertIsNotNone(act_field, "Activation field should exist")
        self.assertIsNotNone(deact_field, "Deactivation field should exist")
        assert act_field is not None  # Type narrowing for Pylance
        assert deact_field is not None  # Type narrowing for Pylance

        # Both should show "Geen"
        self.assertEqual(act_field.value, "Geen")
        self.assertEqual(deact_field.value, "Geen")

    async def test_status_shows_default_label_when_using_defaults(self):
        """Test that status shows '(default)' label when using default schedules."""
        # Set defaults
        set_default_activation({"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"})
        set_default_deactivation({"type": "wekelijks", "dag": "maandag", "tijd": "00:00"})

        # Mock bot and interaction
        mock_bot = MagicMock()
        mock_interaction = MagicMock()
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        # Mock channel with ID (no override)
        mock_channel = MagicMock()
        mock_channel.id = 123456
        mock_interaction.channel = mock_channel

        # Mock guild
        mock_guild = MagicMock()
        mock_guild.id = 789
        mock_interaction.guild = mock_guild

        cog = PollStatus(mock_bot)

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(mock_interaction)

        # Get the embed that was sent
        call_kwargs = mock_interaction.followup.send.call_args[1]
        embed = call_kwargs.get("embed")

        self.assertIsNotNone(embed)

        # Find the schedule fields
        act_field = None
        deact_field = None
        for field in embed.fields:
            if "geplande activatie" in field.name.lower():
                act_field = field
            elif "geplande deactivatie" in field.name.lower():
                deact_field = field

        self.assertIsNotNone(act_field, f"Activation field not found. Fields: {[f.name for f in embed.fields]}")
        self.assertIsNotNone(deact_field, f"Deactivation field not found. Fields: {[f.name for f in embed.fields]}")
        assert act_field is not None  # Type narrowing for Pylance
        assert deact_field is not None  # Type narrowing for Pylance

        # Both should show the schedule with (default) label
        self.assertIn("dinsdag", act_field.value, f"Expected 'dinsdag' in activation field, got: {act_field.value}")
        self.assertIn("20:00", act_field.value)
        self.assertIn("(default)", act_field.value)

        self.assertIn("maandag", deact_field.value, f"Expected 'maandag' in deactivation field, got: {deact_field.value}")
        self.assertIn("00:00", deact_field.value)
        self.assertIn("(default)", deact_field.value)

    async def test_status_shows_no_default_label_when_channel_has_override(self):
        """Test that status shows no '(default)' label when channel has override."""
        # Set defaults
        set_default_activation({"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"})
        set_default_deactivation({"type": "wekelijks", "dag": "maandag", "tijd": "00:00"})

        # Set channel overrides
        channel_id = 123456
        set_scheduled_activation(channel_id, "wekelijks", "19:00", dag="woensdag")
        set_scheduled_deactivation(channel_id, "wekelijks", "23:00", dag="zondag")

        # Mock bot and interaction
        mock_bot = MagicMock()
        mock_interaction = MagicMock()
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        # Mock channel with ID
        mock_channel = MagicMock()
        mock_channel.id = channel_id
        mock_interaction.channel = mock_channel

        # Mock guild
        mock_guild = MagicMock()
        mock_guild.id = 789
        mock_interaction.guild = mock_guild

        cog = PollStatus(mock_bot)

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(mock_interaction)

        # Get the embed that was sent
        call_kwargs = mock_interaction.followup.send.call_args[1]
        embed = call_kwargs.get("embed")

        self.assertIsNotNone(embed)

        # Find the schedule fields
        act_field = None
        deact_field = None
        for field in embed.fields:
            if "geplande activatie" in field.name.lower():
                act_field = field
            elif "geplande deactivatie" in field.name.lower():
                deact_field = field

        self.assertIsNotNone(act_field, f"Activation field not found. Fields: {[f.name for f in embed.fields]}")
        self.assertIsNotNone(deact_field, f"Deactivation field not found. Fields: {[f.name for f in embed.fields]}")
        assert act_field is not None  # Type narrowing for Pylance
        assert deact_field is not None  # Type narrowing for Pylance

        # Should show channel overrides WITHOUT (default) label
        self.assertIn("woensdag", act_field.value, f"Expected 'woensdag' in activation field, got: {act_field.value}")
        self.assertIn("19:00", act_field.value)
        self.assertNotIn("(default)", act_field.value)

        self.assertIn("zondag", deact_field.value, f"Expected 'zondag' in deactivation field, got: {deact_field.value}")
        self.assertIn("23:00", deact_field.value)
        self.assertNotIn("(default)", deact_field.value)

    async def test_status_mixed_default_and_override(self):
        """Test status when one schedule is default and one is override."""
        # Set defaults
        set_default_activation({"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"})
        set_default_deactivation({"type": "wekelijks", "dag": "maandag", "tijd": "00:00"})

        # Set only activation override (deactivation should use default)
        channel_id = 123456
        set_scheduled_activation(channel_id, "wekelijks", "19:00", dag="vrijdag")

        # Mock bot and interaction
        mock_bot = MagicMock()
        mock_interaction = MagicMock()
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        # Mock channel with ID
        mock_channel = MagicMock()
        mock_channel.id = channel_id
        mock_interaction.channel = mock_channel

        # Mock guild
        mock_guild = MagicMock()
        mock_guild.id = 789
        mock_interaction.guild = mock_guild

        cog = PollStatus(mock_bot)

        with patch("apps.utils.poll_storage.load_votes", return_value={}):
            await cog._status_impl(mock_interaction)

        # Get the embed that was sent
        call_kwargs = mock_interaction.followup.send.call_args[1]
        embed = call_kwargs.get("embed")

        # Find the schedule fields
        act_field = None
        deact_field = None
        for field in embed.fields:
            if "geplande activatie" in field.name.lower():
                act_field = field
            elif "geplande deactivatie" in field.name.lower():
                deact_field = field

        self.assertIsNotNone(act_field, f"Activation field not found. Fields: {[f.name for f in embed.fields]}")
        self.assertIsNotNone(deact_field, f"Deactivation field not found. Fields: {[f.name for f in embed.fields]}")
        assert act_field is not None  # Type narrowing for Pylance
        assert deact_field is not None  # Type narrowing for Pylance

        # Activation should show override (no default label)
        self.assertIn("vrijdag", act_field.value, f"Expected 'vrijdag' in activation field, got: {act_field.value}")
        self.assertIn("19:00", act_field.value)
        self.assertNotIn("(default)", act_field.value)

        # Deactivation should show default (with default label)
        self.assertIn("maandag", deact_field.value, f"Expected 'maandag' in deactivation field, got: {deact_field.value}")
        self.assertIn("00:00", deact_field.value)
        self.assertIn("(default)", deact_field.value)


if __name__ == "__main__":
    unittest.main()
