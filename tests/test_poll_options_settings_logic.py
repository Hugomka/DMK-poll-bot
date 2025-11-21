# tests/test_poll_options_settings_logic.py
"""
Tests voor poll-opties instellingen logic (apps/utils/poll_settings.py).

Test coverage:
- get_poll_option_state()
- set_poll_option_state()
- toggle_poll_option()
- get_all_poll_options_state()
- is_day_completely_disabled()
- get_enabled_poll_days()
"""

import json
import os
import tempfile

from apps.utils import poll_settings
from tests.base import BaseTestCase

EXPECTED_DAYS = ["vrijdag", "zaterdag", "zondag"]


class TestPollOptionsSettingsLogic(BaseTestCase):
    """Tests voor poll-opties instellingen logic."""

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

    async def test_get_poll_option_state_default_enabled(self):
        """Test dat poll opties standaard enabled zijn."""
        # Default: alle opties enabled
        self.assertTrue(poll_settings.get_poll_option_state(123, "vrijdag", "19:00"))
        self.assertTrue(poll_settings.get_poll_option_state(123, "zaterdag", "20:30"))
        self.assertTrue(poll_settings.get_poll_option_state(123, "zondag", "19:00"))

    async def test_set_poll_option_state_disabled(self):
        """Test dat poll optie disabled kan worden."""
        channel_id = 123

        # Disable vrijdag 19:00
        result = poll_settings.set_poll_option_state(
            channel_id, "vrijdag", "19:00", False
        )
        self.assertFalse(result)

        # Check dat het opgeslagen is
        self.assertFalse(
            poll_settings.get_poll_option_state(channel_id, "vrijdag", "19:00")
        )

        # Andere opties blijven enabled
        self.assertTrue(
            poll_settings.get_poll_option_state(channel_id, "vrijdag", "20:30")
        )

    async def test_set_poll_option_state_enabled(self):
        """Test dat poll optie enabled kan worden."""
        channel_id = 123

        # Disable eerst
        poll_settings.set_poll_option_state(channel_id, "zondag", "20:30", False)

        # Enable weer
        result = poll_settings.set_poll_option_state(
            channel_id, "zondag", "20:30", True
        )
        self.assertTrue(result)

        # Check dat het opgeslagen is
        self.assertTrue(
            poll_settings.get_poll_option_state(channel_id, "zondag", "20:30")
        )

    async def test_toggle_poll_option_enable_to_disable(self):
        """Test toggle van enabled naar disabled."""
        channel_id = 123

        # Default enabled
        self.assertTrue(
            poll_settings.get_poll_option_state(channel_id, "zaterdag", "19:00")
        )

        # Toggle naar disabled
        result = poll_settings.toggle_poll_option(channel_id, "zaterdag", "19:00")
        self.assertFalse(result)

        # Check dat het disabled is
        self.assertFalse(
            poll_settings.get_poll_option_state(channel_id, "zaterdag", "19:00")
        )

    async def test_toggle_poll_option_disable_to_enable(self):
        """Test toggle van disabled naar enabled."""
        channel_id = 123

        # Disable eerst
        poll_settings.set_poll_option_state(channel_id, "vrijdag", "20:30", False)

        # Toggle naar enabled
        result = poll_settings.toggle_poll_option(channel_id, "vrijdag", "20:30")
        self.assertTrue(result)

        # Check dat het enabled is
        self.assertTrue(
            poll_settings.get_poll_option_state(channel_id, "vrijdag", "20:30")
        )

    async def test_get_all_poll_options_state_default(self):
        """Test dat alle poll opties standaard enabled zijn."""
        channel_id = 123

        states = poll_settings.get_all_poll_options_state(channel_id)

        # Alle 6 opties enabled
        self.assertTrue(states.get("vrijdag_19:00", False))
        self.assertTrue(states.get("vrijdag_20:30", False))
        self.assertTrue(states.get("zaterdag_19:00", False))
        self.assertTrue(states.get("zaterdag_20:30", False))
        self.assertTrue(states.get("zondag_19:00", False))
        self.assertTrue(states.get("zondag_20:30", False))

    async def test_get_all_poll_options_state_mixed(self):
        """Test get_all_poll_options_state met mixed enabled/disabled."""
        channel_id = 123

        # Disable enkele opties
        poll_settings.set_poll_option_state(channel_id, "vrijdag", "19:00", False)
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "20:30", False)

        states = poll_settings.get_all_poll_options_state(channel_id)

        # Check disabled opties
        self.assertFalse(states.get("vrijdag_19:00", True))
        self.assertFalse(states.get("zaterdag_20:30", True))

        # Check enabled opties
        self.assertTrue(states.get("vrijdag_20:30", False))
        self.assertTrue(states.get("zaterdag_19:00", False))
        self.assertTrue(states.get("zondag_19:00", False))
        self.assertTrue(states.get("zondag_20:30", False))

    async def test_is_day_completely_disabled_default(self):
        """Test dat dagen standaard niet volledig disabled zijn."""
        channel_id = 123

        # Geen dag is volledig disabled (default: alles enabled)
        self.assertFalse(
            poll_settings.is_day_completely_disabled(channel_id, "vrijdag")
        )
        self.assertFalse(
            poll_settings.is_day_completely_disabled(channel_id, "zaterdag")
        )
        self.assertFalse(poll_settings.is_day_completely_disabled(channel_id, "zondag"))

    async def test_is_day_completely_disabled_one_time_disabled(self):
        """Test dat dag niet volledig disabled is als één tijd disabled is."""
        channel_id = 123

        # Disable alleen 19:00
        poll_settings.set_poll_option_state(channel_id, "vrijdag", "19:00", False)

        # Vrijdag niet volledig disabled (20:30 nog enabled)
        self.assertFalse(
            poll_settings.is_day_completely_disabled(channel_id, "vrijdag")
        )

    async def test_is_day_completely_disabled_both_times_disabled(self):
        """Test dat dag volledig disabled is als beide tijden disabled zijn."""
        channel_id = 123

        # Disable beide tijden
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "19:00", False)
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "20:30", False)

        # Zaterdag volledig disabled
        self.assertTrue(
            poll_settings.is_day_completely_disabled(channel_id, "zaterdag")
        )

        # Andere dagen niet disabled
        self.assertFalse(
            poll_settings.is_day_completely_disabled(channel_id, "vrijdag")
        )
        self.assertFalse(poll_settings.is_day_completely_disabled(channel_id, "zondag"))

    async def test_get_enabled_poll_days_all_enabled(self):
        """Test dat alle dagen enabled zijn als default."""
        channel_id = 123

        # Disable maandag t/m donderdag (alleen weekend dagen actief)
        for dag in ["maandag", "dinsdag", "woensdag", "donderdag"]:
            poll_settings.set_poll_option_state(channel_id, dag, "19:00", False)
            poll_settings.set_poll_option_state(channel_id, dag, "20:30", False)

        enabled_days = poll_settings.get_enabled_poll_days(channel_id)

        # Alle 3 weekend dagen enabled
        self.assertEqual(enabled_days, EXPECTED_DAYS)

    async def test_get_enabled_poll_days_one_disabled(self):
        """Test get_enabled_poll_days met één volledig disabled dag."""
        channel_id = 123

        # Disable maandag t/m donderdag (alleen weekend dagen actief)
        for dag in ["maandag", "dinsdag", "woensdag", "donderdag"]:
            poll_settings.set_poll_option_state(channel_id, dag, "19:00", False)
            poll_settings.set_poll_option_state(channel_id, dag, "20:30", False)

        # Disable vrijdag volledig
        poll_settings.set_poll_option_state(channel_id, "vrijdag", "19:00", False)
        poll_settings.set_poll_option_state(channel_id, "vrijdag", "20:30", False)

        enabled_days = poll_settings.get_enabled_poll_days(channel_id)

        # Alleen zaterdag en zondag enabled
        self.assertEqual(enabled_days, ["zaterdag", "zondag"])

    async def test_get_enabled_poll_days_only_sunday(self):
        """Test get_enabled_poll_days met alleen zondag enabled."""
        channel_id = 123

        # Disable alle dagen behalve zondag
        for dag in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"]:
            poll_settings.set_poll_option_state(channel_id, dag, "19:00", False)
            poll_settings.set_poll_option_state(channel_id, dag, "20:30", False)

        enabled_days = poll_settings.get_enabled_poll_days(channel_id)

        # Alleen zondag enabled
        self.assertEqual(enabled_days, ["zondag"])

    async def test_get_enabled_poll_days_all_disabled(self):
        """Test get_enabled_poll_days als alle dagen disabled zijn."""
        channel_id = 123

        # Disable alle 7 dagen volledig
        for dag in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]:
            poll_settings.set_poll_option_state(channel_id, dag, "19:00", False)
            poll_settings.set_poll_option_state(channel_id, dag, "20:30", False)

        enabled_days = poll_settings.get_enabled_poll_days(channel_id)

        # Geen dagen enabled
        self.assertEqual(enabled_days, [])

    async def test_poll_options_per_channel_isolated(self):
        """Test dat poll-opties per channel geïsoleerd zijn."""
        channel_1 = 123
        channel_2 = 456

        # Disable vrijdag 19:00 in channel 1
        poll_settings.set_poll_option_state(channel_1, "vrijdag", "19:00", False)

        # Channel 1: vrijdag 19:00 disabled
        self.assertFalse(
            poll_settings.get_poll_option_state(channel_1, "vrijdag", "19:00")
        )

        # Channel 2: vrijdag 19:00 enabled (default)
        self.assertTrue(
            poll_settings.get_poll_option_state(channel_2, "vrijdag", "19:00")
        )

    async def test_poll_options_persistence(self):
        """Test dat poll-opties persistent opgeslagen worden."""
        channel_id = 123

        # Disable zaterdag 20:30
        poll_settings.set_poll_option_state(channel_id, "zaterdag", "20:30", False)

        # Read direct van file
        with open(self.temp_settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check dat het opgeslagen is in file
        self.assertFalse(
            data.get(str(channel_id), {})
            .get("__poll_options__", {})
            .get("zaterdag_20:30", True)
        )
