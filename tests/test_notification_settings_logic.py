# tests/test_notification_settings_logic.py
"""
Tests voor notificatie instellingen logic (apps/utils/poll_settings.py).

Test coverage:
- get_all_notification_states()
- toggle_notification_setting()
- is_notification_enabled()
- Default states (poll_opened, poll_reset, poll_closed, doorgaan, celebration = True)
- Default states (reminders, thursday_reminder, misschien = False)
- Per-channel isolation
- Persistence
"""

import json
import os
import tempfile

from apps.utils import poll_settings
from tests.base import BaseTestCase


class TestNotificationSettingsLogic(BaseTestCase):
    """Tests voor notificatie instellingen logic."""

    async def asyncSetUp(self):
        """Set up isolated test environment met temp settings file."""
        await super().asyncSetUp()
        # Create temp file voor elke test
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        self.temp_file.close()
        self.temp_settings_path = self.temp_file.name

        # Patch SETTINGS_FILE naar temp file
        self.original_settings_file = poll_settings.SETTINGS_FILE
        poll_settings.SETTINGS_FILE = self.temp_settings_path

    async def asyncTearDown(self):
        """Clean up temp file en restore originele settings."""
        # Restore origineel
        poll_settings.SETTINGS_FILE = self.original_settings_file

        # Verwijder temp file
        try:
            if os.path.exists(self.temp_settings_path):
                os.unlink(self.temp_settings_path)
        except Exception:  # pragma: no cover
            pass

        await super().asyncTearDown()

    async def test_get_all_notification_states_defaults(self):
        """Test dat get_all_notification_states de juiste defaults teruggeeft."""
        channel_id = 123

        states = poll_settings.get_all_notification_states(channel_id)

        # Check enabled defaults
        self.assertTrue(states["poll_opened"])
        self.assertTrue(states["poll_reset"])
        self.assertTrue(states["poll_closed"])
        self.assertTrue(states["doorgaan"])
        self.assertTrue(states["celebration"])

        # Check disabled defaults
        self.assertFalse(states["reminders"])
        self.assertFalse(states["thursday_reminder"])
        self.assertFalse(states["misschien"])

    async def test_is_notification_enabled_defaults(self):
        """Test dat is_notification_enabled de juiste defaults teruggeeft."""
        channel_id = 123

        # Enabled defaults
        self.assertTrue(poll_settings.is_notification_enabled(channel_id, "poll_opened"))
        self.assertTrue(poll_settings.is_notification_enabled(channel_id, "poll_reset"))
        self.assertTrue(poll_settings.is_notification_enabled(channel_id, "poll_closed"))
        self.assertTrue(poll_settings.is_notification_enabled(channel_id, "doorgaan"))
        self.assertTrue(poll_settings.is_notification_enabled(channel_id, "celebration"))

        # Disabled defaults
        self.assertFalse(poll_settings.is_notification_enabled(channel_id, "reminders"))
        self.assertFalse(poll_settings.is_notification_enabled(channel_id, "thursday_reminder"))
        self.assertFalse(poll_settings.is_notification_enabled(channel_id, "misschien"))

    async def test_toggle_notification_setting_enable_to_disable(self):
        """Test toggle van enabled naar disabled."""
        channel_id = 123

        # Default: poll_opened is enabled
        self.assertTrue(poll_settings.is_notification_enabled(channel_id, "poll_opened"))

        # Toggle naar disabled
        result = poll_settings.toggle_notification_setting(channel_id, "poll_opened")
        self.assertFalse(result)

        # Check dat het disabled is
        self.assertFalse(poll_settings.is_notification_enabled(channel_id, "poll_opened"))

    async def test_toggle_notification_setting_disable_to_enable(self):
        """Test toggle van disabled naar enabled."""
        channel_id = 123

        # Default: reminders is disabled
        self.assertFalse(poll_settings.is_notification_enabled(channel_id, "reminders"))

        # Toggle naar enabled
        result = poll_settings.toggle_notification_setting(channel_id, "reminders")
        self.assertTrue(result)

        # Check dat het enabled is
        self.assertTrue(poll_settings.is_notification_enabled(channel_id, "reminders"))

    async def test_toggle_notification_setting_multiple_times(self):
        """Test dat toggle meerdere keren werkt."""
        channel_id = 123

        # Toggle 1: enabled -> disabled
        result1 = poll_settings.toggle_notification_setting(channel_id, "doorgaan")
        self.assertFalse(result1)

        # Toggle 2: disabled -> enabled
        result2 = poll_settings.toggle_notification_setting(channel_id, "doorgaan")
        self.assertTrue(result2)

        # Toggle 3: enabled -> disabled
        result3 = poll_settings.toggle_notification_setting(channel_id, "doorgaan")
        self.assertFalse(result3)

    async def test_notification_settings_per_channel_isolated(self):
        """Test dat notificatie instellingen per channel geïsoleerd zijn."""
        channel_1 = 123
        channel_2 = 456

        # Disable poll_opened in channel 1
        poll_settings.toggle_notification_setting(channel_1, "poll_opened")

        # Channel 1: poll_opened disabled
        self.assertFalse(poll_settings.is_notification_enabled(channel_1, "poll_opened"))

        # Channel 2: poll_opened enabled (default)
        self.assertTrue(poll_settings.is_notification_enabled(channel_2, "poll_opened"))

    async def test_notification_settings_persistence(self):
        """Test dat notificatie instellingen persistent opgeslagen worden."""
        channel_id = 123

        # Enable reminders (default: disabled)
        poll_settings.toggle_notification_setting(channel_id, "reminders")

        # Read direct van file
        with open(self.temp_settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check dat het opgeslagen is in file
        self.assertTrue(
            data.get(str(channel_id), {})
            .get("__notification_states__", {})
            .get("reminders", False)
        )

    async def test_get_all_notification_states_mixed(self):
        """Test get_all_notification_states met mixed enabled/disabled."""
        channel_id = 123

        # Toggle enkele notificaties
        poll_settings.toggle_notification_setting(channel_id, "poll_opened")  # disabled
        poll_settings.toggle_notification_setting(channel_id, "reminders")  # enabled
        poll_settings.toggle_notification_setting(channel_id, "celebration")  # disabled

        states = poll_settings.get_all_notification_states(channel_id)

        # Check toggled notificaties
        self.assertFalse(states["poll_opened"])
        self.assertTrue(states["reminders"])
        self.assertFalse(states["celebration"])

        # Check niet-toggled notificaties (defaults)
        self.assertTrue(states["poll_reset"])
        self.assertTrue(states["poll_closed"])
        self.assertTrue(states["doorgaan"])
        self.assertFalse(states["thursday_reminder"])
        self.assertFalse(states["misschien"])

    async def test_all_notification_types_toggleable(self):
        """Test dat alle 8 notificatie types togglebaar zijn."""
        channel_id = 123

        all_types = [
            "poll_opened",
            "poll_reset",
            "poll_closed",
            "reminders",
            "thursday_reminder",
            "misschien",
            "doorgaan",
            "celebration",
        ]

        for notif_type in all_types:
            # Toggle
            initial = poll_settings.is_notification_enabled(channel_id, notif_type)
            result = poll_settings.toggle_notification_setting(channel_id, notif_type)

            # Check dat toggle werkt
            self.assertEqual(result, not initial)
            self.assertEqual(
                poll_settings.is_notification_enabled(channel_id, notif_type),
                not initial
            )
