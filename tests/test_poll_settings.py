# tests/test_poll_settings.py
"""
Comprehensive tests for apps/utils/poll_settings.py
"""

import json
import os
import tempfile
from datetime import datetime, timedelta

from apps.utils import poll_settings
from tests.base import BaseTestCase


class TestPollSettings(BaseTestCase):
    """Tests for poll_settings functions"""

    async def asyncSetUp(self):
        """Set up isolated test environment with temp settings file"""
        await super().asyncSetUp()
        # Create temp file for each test
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        self.temp_file.close()
        self.temp_settings_path = self.temp_file.name

        # Patch SETTINGS_FILE to use temp file
        self.original_settings_file = poll_settings.SETTINGS_FILE
        poll_settings.SETTINGS_FILE = self.temp_settings_path

    async def asyncTearDown(self):
        """Clean up temp file and restore original settings"""
        # Restore original
        poll_settings.SETTINGS_FILE = self.original_settings_file

        # Remove temp file
        try:
            if os.path.exists(self.temp_settings_path):
                os.unlink(self.temp_settings_path)
        except Exception:  # pragma: no cover
            pass

        await super().asyncTearDown()

    def _dt_for_weekday(
        self, weekday: int, hour: int = 12, minute: int = 0
    ) -> datetime:
        """
        Create a datetime with desired weekday (mon=0 ... sun=6).
        """
        today = datetime.now()
        diff = weekday - today.weekday()
        base = today + timedelta(days=diff)
        return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


class TestGetSettingAndSetVisibility(TestPollSettings):
    """Tests for get_setting and set_visibility"""

    async def test_get_setting_no_file_returns_default(self):
        """Test that get_setting returns default when no file exists"""
        # File doesn't exist yet
        result = poll_settings.get_setting(123, "vrijdag")
        assert result == {"modus": "deadline", "tijd": "18:00"}

    async def test_get_setting_no_channel_returns_default(self):
        """Test that get_setting returns default for unknown channel"""
        # Set something for channel 1
        poll_settings.set_visibility(1, "vrijdag", "altijd")

        # Request for channel 999 (doesn't exist)
        result = poll_settings.get_setting(999, "vrijdag")
        assert result == {"modus": "deadline", "tijd": "18:00"}

    async def test_get_setting_no_dag_returns_default(self):
        """Test that get_setting returns default for unknown dag"""
        # Set something for vrijdag
        poll_settings.set_visibility(1, "vrijdag", "altijd")

        # Request for zaterdag (doesn't exist for this channel)
        result = poll_settings.get_setting(1, "zaterdag")
        assert result == {"modus": "deadline", "tijd": "18:00"}

    async def test_set_visibility_altijd_ignores_tijd_param(self):
        """Test that set_visibility with altijd always uses 18:00"""
        result = poll_settings.set_visibility(1, "vrijdag", "altijd", tijd="12:34")
        assert result == {"modus": "altijd", "tijd": "18:00"}

        # Verify it persists
        saved = poll_settings.get_setting(1, "vrijdag")
        assert saved == {"modus": "altijd", "tijd": "18:00"}

    async def test_set_visibility_deadline_uses_custom_tijd(self):
        """Test that set_visibility with deadline uses custom tijd"""
        result = poll_settings.set_visibility(1, "vrijdag", "deadline", tijd="17:30")
        assert result == {"modus": "deadline", "tijd": "17:30"}

        # Verify it persists
        saved = poll_settings.get_setting(1, "vrijdag")
        assert saved == {"modus": "deadline", "tijd": "17:30"}

    async def test_set_visibility_deadline_default_tijd(self):
        """Test that set_visibility with deadline defaults to 18:00"""
        result = poll_settings.set_visibility(1, "vrijdag", "deadline")
        assert result == {"modus": "deadline", "tijd": "18:00"}

    async def test_set_visibility_deadline_show_ghosts_uses_custom_tijd(self):
        """Test dat set_visibility met deadline_show_ghosts custom tijd gebruikt"""
        result = poll_settings.set_visibility(
            1, "vrijdag", "deadline_show_ghosts", tijd="17:30"
        )
        assert result == {"modus": "deadline_show_ghosts", "tijd": "17:30"}

        # Verifieer dat het is opgeslagen
        saved = poll_settings.get_setting(1, "vrijdag")
        assert saved == {"modus": "deadline_show_ghosts", "tijd": "17:30"}

    async def test_set_visibility_deadline_show_ghosts_default_tijd(self):
        """Test dat set_visibility met deadline_show_ghosts default naar 18:00"""
        result = poll_settings.set_visibility(1, "vrijdag", "deadline_show_ghosts")
        assert result == {"modus": "deadline_show_ghosts", "tijd": "18:00"}

    async def test_set_visibility_persists_to_json(self):
        """Test that set_visibility saves to JSON file"""
        poll_settings.set_visibility(1, "vrijdag", "altijd")
        poll_settings.set_visibility(2, "zaterdag", "deadline", "19:00")

        # Read JSON directly
        with open(self.temp_settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "1" in data
        assert data["1"]["vrijdag"] == {"modus": "altijd", "tijd": "18:00"}
        assert "2" in data
        assert data["2"]["zaterdag"] == {"modus": "deadline", "tijd": "19:00"}

    async def test_set_visibility_multiple_channels_and_days(self):
        """Test setting visibility for multiple channels and days"""
        poll_settings.set_visibility(1, "vrijdag", "altijd")
        poll_settings.set_visibility(1, "zaterdag", "deadline", "17:00")
        poll_settings.set_visibility(2, "vrijdag", "deadline", "19:00")

        # Verify all are stored correctly
        assert poll_settings.get_setting(1, "vrijdag") == {
            "modus": "altijd",
            "tijd": "18:00",
        }
        assert poll_settings.get_setting(1, "zaterdag") == {
            "modus": "deadline",
            "tijd": "17:00",
        }
        assert poll_settings.get_setting(2, "vrijdag") == {
            "modus": "deadline",
            "tijd": "19:00",
        }

    async def test_load_data_corrupt_file_returns_empty_dict(self):
        """Test that corrupt JSON file returns empty dict (uses pragma: no cover path)"""
        # Write invalid JSON
        with open(self.temp_settings_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")

        # Should return default (empty dict from _load_data)
        result = poll_settings.get_setting(123, "vrijdag")
        assert result == {"modus": "deadline", "tijd": "18:00"}


class TestShouldHideCounts(TestPollSettings):
    """Tests for should_hide_counts"""

    async def test_should_hide_counts_altijd_always_returns_false(self):
        """Test that altijd mode never hides counts"""
        poll_settings.set_visibility(1, "vrijdag", "altijd")

        # Before the day
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] - 1, 23, 59)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is False

        # On the day, before deadline
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 10, 0)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is False

        # After the day
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] + 1, 0, 1)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is False

    async def test_should_hide_counts_deadline_before_day_returns_true(self):
        """Test that deadline mode hides counts before target day"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Thursday (day before Friday)
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] - 1, 23, 59)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is True

    async def test_should_hide_counts_deadline_after_day_returns_false(self):
        """Test that deadline mode shows counts after target day"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Saturday (day after Friday)
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] + 1, 0, 1)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is False

    async def test_should_hide_counts_deadline_same_day_before_time_returns_true(self):
        """Test that deadline mode hides counts before deadline time on same day"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Friday at 17:59
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 17, 59)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is True

    async def test_should_hide_counts_deadline_same_day_at_time_returns_false(self):
        """Test that deadline mode shows counts at deadline time"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Friday at 18:00
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 18, 0)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is False

    async def test_should_hide_counts_deadline_same_day_after_time_returns_false(self):
        """Test that deadline mode shows counts after deadline time"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Friday at 18:01
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 18, 1)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is False

    async def test_should_hide_counts_unknown_day_returns_false(self):
        """Test that unknown day name returns False"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 12, 0)
        result = poll_settings.should_hide_counts(1, "onbekendedag", now)
        assert result is False

    async def test_should_hide_counts_invalid_time_uses_fallback(self):
        """Test that invalid time format uses fallback 18:00 (pragma: no cover path)"""
        # Manually set invalid time in settings
        data = poll_settings._load_data()
        data.setdefault("1", {})["vrijdag"] = {"modus": "deadline", "tijd": "xx:yy"}
        poll_settings._save_data(data)

        # Friday at 17:59 - should hide (fallback to 18:00)
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 17, 59)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is True

        # Friday at 18:01 - should show
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 18, 1)
        assert poll_settings.should_hide_counts(1, "vrijdag", now) is False

    async def test_should_hide_counts_custom_deadline_time(self):
        """Test should_hide_counts with custom deadline time"""
        poll_settings.set_visibility(1, "zaterdag", "deadline", "17:30")

        # Saturday at 17:29 - hide
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["zaterdag"], 17, 29)
        assert poll_settings.should_hide_counts(1, "zaterdag", now) is True

        # Saturday at 17:30 - show
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["zaterdag"], 17, 30)
        assert poll_settings.should_hide_counts(1, "zaterdag", now) is False


class TestShouldHideGhosts(TestPollSettings):
    """Tests voor should_hide_ghosts functie"""

    async def test_should_hide_ghosts_altijd_always_returns_false(self):
        """Test dat altijd mode nooit ghosts verbergt"""
        poll_settings.set_visibility(1, "vrijdag", "altijd")

        # Voor de dag
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] - 1, 23, 59)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

        # Op de dag, voor deadline
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 10, 0)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

        # Na de dag
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] + 1, 0, 1)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

    async def test_should_hide_ghosts_deadline_show_ghosts_always_returns_false(self):
        """Test dat deadline_show_ghosts mode nooit ghosts verbergt"""
        poll_settings.set_visibility(1, "vrijdag", "deadline_show_ghosts", "18:00")

        # Voor de dag
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] - 1, 23, 59)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

        # Op de dag, voor deadline
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 10, 0)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

        # Op de dag, na deadline
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 18, 1)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

        # Na de dag
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] + 1, 0, 1)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

    async def test_should_hide_ghosts_deadline_before_day_returns_true(self):
        """Test dat deadline mode ghosts verbergt voor target dag"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Donderdag (dag voor vrijdag)
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] - 1, 23, 59)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is True

    async def test_should_hide_ghosts_deadline_after_day_returns_false(self):
        """Test dat deadline mode ghosts toont na target dag"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Zaterdag (dag na vrijdag)
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"] + 1, 0, 1)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

    async def test_should_hide_ghosts_deadline_same_day_before_time_returns_true(self):
        """Test dat deadline mode ghosts verbergt voor deadline tijd op zelfde dag"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Vrijdag om 17:59
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 17, 59)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is True

    async def test_should_hide_ghosts_deadline_same_day_at_time_returns_false(self):
        """Test dat deadline mode ghosts toont op deadline tijd"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Vrijdag om 18:00
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 18, 0)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

    async def test_should_hide_ghosts_deadline_same_day_after_time_returns_false(self):
        """Test dat deadline mode ghosts toont na deadline tijd"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        # Vrijdag om 18:01
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 18, 1)
        assert poll_settings.should_hide_ghosts(1, "vrijdag", now) is False

    async def test_should_hide_ghosts_unknown_day_returns_false(self):
        """Test dat onbekende dag naam False retourneert"""
        poll_settings.set_visibility(1, "vrijdag", "deadline", "18:00")

        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 12, 0)
        result = poll_settings.should_hide_ghosts(1, "onbekendedag", now)
        assert result is False

    async def test_should_hide_ghosts_custom_deadline_time(self):
        """Test should_hide_ghosts met custom deadline tijd"""
        poll_settings.set_visibility(1, "zaterdag", "deadline", "17:30")

        # Zaterdag om 17:29 - verberg
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["zaterdag"], 17, 29)
        assert poll_settings.should_hide_ghosts(1, "zaterdag", now) is True

        # Zaterdag om 17:30 - toon
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["zaterdag"], 17, 30)
        assert poll_settings.should_hide_ghosts(1, "zaterdag", now) is False


class TestPauseFunctions(TestPollSettings):
    """Tests for pause-related functions"""

    async def test_is_paused_default_returns_false(self):
        """Test that is_paused returns False by default"""
        assert poll_settings.is_paused(42) is False

    async def test_set_paused_true_returns_true(self):
        """Test that set_paused(True) sets and returns True"""
        result = poll_settings.set_paused(42, True)
        assert result is True
        assert poll_settings.is_paused(42) is True

    async def test_set_paused_false_returns_false(self):
        """Test that set_paused(False) sets and returns False"""
        # First set to True
        poll_settings.set_paused(42, True)

        # Then set to False
        result = poll_settings.set_paused(42, False)
        assert result is False
        assert poll_settings.is_paused(42) is False

    async def test_set_paused_persists(self):
        """Test that paused state persists in JSON"""
        poll_settings.set_paused(42, True)

        # Read JSON directly
        with open(self.temp_settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["42"]["__paused__"] is True

    async def test_toggle_paused_false_to_true(self):
        """Test toggle_paused flips False to True"""
        # Starts as False
        assert poll_settings.is_paused(42) is False

        # Toggle
        result = poll_settings.toggle_paused(42)
        assert result is True
        assert poll_settings.is_paused(42) is True

    async def test_toggle_paused_true_to_false(self):
        """Test toggle_paused flips True to False"""
        # Set to True first
        poll_settings.set_paused(42, True)

        # Toggle
        result = poll_settings.toggle_paused(42)
        assert result is False
        assert poll_settings.is_paused(42) is False

    async def test_toggle_paused_multiple_times(self):
        """Test multiple toggles work correctly"""
        assert poll_settings.is_paused(42) is False

        assert poll_settings.toggle_paused(42) is True
        assert poll_settings.toggle_paused(42) is False
        assert poll_settings.toggle_paused(42) is True
        assert poll_settings.toggle_paused(42) is False

    async def test_paused_separate_channels(self):
        """Test that paused state is per-channel"""
        poll_settings.set_paused(1, True)
        poll_settings.set_paused(2, False)

        assert poll_settings.is_paused(1) is True
        assert poll_settings.is_paused(2) is False


class TestScheduledActivation(TestPollSettings):
    """Tests for scheduled activation functions"""

    async def test_get_scheduled_activation_none_by_default(self):
        """Test that get_scheduled_activation returns None by default"""
        result = poll_settings.get_scheduled_activation(123)
        assert result is None

    async def test_set_scheduled_activation_datum(self):
        """Test set_scheduled_activation with datum type"""
        result = poll_settings.set_scheduled_activation(
            123, "datum", "18:00", datum="2025-12-31"
        )

        assert result == {"type": "datum", "tijd": "18:00", "datum": "2025-12-31"}

        # Verify it's stored
        stored = poll_settings.get_scheduled_activation(123)
        assert stored == {"type": "datum", "tijd": "18:00", "datum": "2025-12-31"}

    async def test_set_scheduled_activation_wekelijks(self):
        """Test set_scheduled_activation with wekelijks type"""
        result = poll_settings.set_scheduled_activation(
            456, "wekelijks", "20:00", dag="vrijdag"
        )

        assert result == {"type": "wekelijks", "tijd": "20:00", "dag": "vrijdag"}

        # Verify it's stored
        stored = poll_settings.get_scheduled_activation(456)
        assert stored == {"type": "wekelijks", "tijd": "20:00", "dag": "vrijdag"}

    async def test_set_scheduled_activation_persists_to_json(self):
        """Test that scheduled activation persists in JSON"""
        poll_settings.set_scheduled_activation(123, "wekelijks", "19:00", dag="maandag")

        # Read JSON directly
        with open(self.temp_settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "__scheduled_activation__" in data["123"]
        assert data["123"]["__scheduled_activation__"] == {
            "type": "wekelijks",
            "tijd": "19:00",
            "dag": "maandag",
        }

    async def test_clear_scheduled_activation(self):
        """Test clear_scheduled_activation removes schedule"""
        # First set a schedule
        poll_settings.set_scheduled_activation(
            123, "datum", "18:00", datum="2025-12-31"
        )
        assert poll_settings.get_scheduled_activation(123) is not None

        # Clear it
        poll_settings.clear_scheduled_activation(123)

        # Should be None now
        assert poll_settings.get_scheduled_activation(123) is None

    async def test_clear_scheduled_activation_nonexistent_channel(self):
        """Test clearing activation for nonexistent channel doesn't error"""
        # Should not raise error
        poll_settings.clear_scheduled_activation(999)
        assert poll_settings.get_scheduled_activation(999) is None

    async def test_set_scheduled_activation_overwrites_previous(self):
        """Test that setting activation overwrites previous schedule"""
        # Set datum schedule
        poll_settings.set_scheduled_activation(
            123, "datum", "18:00", datum="2025-12-31"
        )

        # Overwrite with wekelijks
        poll_settings.set_scheduled_activation(123, "wekelijks", "20:00", dag="vrijdag")

        # Should have wekelijks schedule
        stored = poll_settings.get_scheduled_activation(123)
        assert stored == {"type": "wekelijks", "tijd": "20:00", "dag": "vrijdag"}

    async def test_scheduled_activation_multiple_channels(self):
        """Test scheduled activation for multiple channels"""
        poll_settings.set_scheduled_activation(1, "datum", "18:00", datum="2025-12-31")
        poll_settings.set_scheduled_activation(2, "wekelijks", "19:00", dag="zaterdag")

        assert poll_settings.get_scheduled_activation(1) == {
            "type": "datum",
            "tijd": "18:00",
            "datum": "2025-12-31",
        }
        assert poll_settings.get_scheduled_activation(2) == {
            "type": "wekelijks",
            "tijd": "19:00",
            "dag": "zaterdag",
        }


class TestScheduledDeactivation(TestPollSettings):
    """Tests for scheduled deactivation functions"""

    async def test_get_scheduled_deactivation_none_by_default(self):
        """Test that get_scheduled_deactivation returns None by default"""
        result = poll_settings.get_scheduled_deactivation(123)
        assert result is None

    async def test_set_scheduled_deactivation_datum(self):
        """Test set_scheduled_deactivation with datum type"""
        result = poll_settings.set_scheduled_deactivation(
            123, "datum", "22:00", datum="2026-01-01"
        )

        assert result == {"type": "datum", "tijd": "22:00", "datum": "2026-01-01"}

        # Verify it's stored
        stored = poll_settings.get_scheduled_deactivation(123)
        assert stored == {"type": "datum", "tijd": "22:00", "datum": "2026-01-01"}

    async def test_set_scheduled_deactivation_wekelijks(self):
        """Test set_scheduled_deactivation with wekelijks type"""
        result = poll_settings.set_scheduled_deactivation(
            456, "wekelijks", "23:00", dag="zondag"
        )

        assert result == {"type": "wekelijks", "tijd": "23:00", "dag": "zondag"}

        # Verify it's stored
        stored = poll_settings.get_scheduled_deactivation(456)
        assert stored == {"type": "wekelijks", "tijd": "23:00", "dag": "zondag"}

    async def test_set_scheduled_deactivation_persists_to_json(self):
        """Test that scheduled deactivation persists in JSON"""
        poll_settings.set_scheduled_deactivation(
            123, "wekelijks", "21:00", dag="dinsdag"
        )

        # Read JSON directly
        with open(self.temp_settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "__scheduled_deactivation__" in data["123"]
        assert data["123"]["__scheduled_deactivation__"] == {
            "type": "wekelijks",
            "tijd": "21:00",
            "dag": "dinsdag",
        }

    async def test_clear_scheduled_deactivation(self):
        """Test clear_scheduled_deactivation removes schedule"""
        # First set a schedule
        poll_settings.set_scheduled_deactivation(
            123, "datum", "22:00", datum="2026-01-01"
        )
        assert poll_settings.get_scheduled_deactivation(123) is not None

        # Clear it
        poll_settings.clear_scheduled_deactivation(123)

        # Should be None now
        assert poll_settings.get_scheduled_deactivation(123) is None

    async def test_clear_scheduled_deactivation_nonexistent_channel(self):
        """Test clearing deactivation for nonexistent channel doesn't error"""
        # Should not raise error
        poll_settings.clear_scheduled_deactivation(999)
        assert poll_settings.get_scheduled_deactivation(999) is None

    async def test_set_scheduled_deactivation_overwrites_previous(self):
        """Test that setting deactivation overwrites previous schedule"""
        # Set datum schedule
        poll_settings.set_scheduled_deactivation(
            123, "datum", "22:00", datum="2026-01-01"
        )

        # Overwrite with wekelijks
        poll_settings.set_scheduled_deactivation(
            123, "wekelijks", "23:00", dag="zondag"
        )

        # Should have wekelijks schedule
        stored = poll_settings.get_scheduled_deactivation(123)
        assert stored == {"type": "wekelijks", "tijd": "23:00", "dag": "zondag"}

    async def test_scheduled_deactivation_multiple_channels(self):
        """Test scheduled deactivation for multiple channels"""
        poll_settings.set_scheduled_deactivation(
            1, "datum", "22:00", datum="2026-01-01"
        )
        poll_settings.set_scheduled_deactivation(2, "wekelijks", "23:00", dag="zondag")

        assert poll_settings.get_scheduled_deactivation(1) == {
            "type": "datum",
            "tijd": "22:00",
            "datum": "2026-01-01",
        }
        assert poll_settings.get_scheduled_deactivation(2) == {
            "type": "wekelijks",
            "tijd": "23:00",
            "dag": "zondag",
        }

    async def test_activation_and_deactivation_coexist(self):
        """Test that activation and deactivation schedules can coexist"""
        poll_settings.set_scheduled_activation(123, "wekelijks", "18:00", dag="vrijdag")
        poll_settings.set_scheduled_deactivation(
            123, "wekelijks", "22:00", dag="zondag"
        )

        assert poll_settings.get_scheduled_activation(123) == {
            "type": "wekelijks",
            "tijd": "18:00",
            "dag": "vrijdag",
        }
        assert poll_settings.get_scheduled_deactivation(123) == {
            "type": "wekelijks",
            "tijd": "22:00",
            "dag": "zondag",
        }


class TestResetSettings(TestPollSettings):
    """Tests for reset_settings"""

    async def test_reset_settings_removes_file(self):
        """Test that reset_settings removes the settings file"""
        # Create some settings
        poll_settings.set_visibility(1, "vrijdag", "altijd")
        poll_settings.set_paused(2, True)

        # Verify file exists
        assert os.path.exists(self.temp_settings_path)

        # Reset
        poll_settings.reset_settings()

        # File should be gone
        assert not os.path.exists(self.temp_settings_path)

    async def test_reset_settings_returns_to_defaults(self):
        """Test that after reset, settings return to defaults"""
        # Create some settings
        poll_settings.set_visibility(1, "vrijdag", "altijd")
        poll_settings.set_paused(2, True)
        poll_settings.set_scheduled_activation(3, "wekelijks", "18:00", dag="maandag")

        # Reset
        poll_settings.reset_settings()

        # All should return defaults
        assert poll_settings.get_setting(1, "vrijdag") == {
            "modus": "deadline",
            "tijd": "18:00",
        }
        assert poll_settings.is_paused(2) is False
        assert poll_settings.get_scheduled_activation(3) is None

    async def test_reset_settings_nonexistent_file_doesnt_error(self):
        """Test that reset_settings doesn't error if file doesn't exist"""
        # Remove file if it exists
        if os.path.exists(self.temp_settings_path):
            os.unlink(self.temp_settings_path)

        # Should not raise error
        poll_settings.reset_settings()

    async def test_reset_settings_then_create_new(self):
        """Test that after reset, new settings can be created"""
        # Create settings
        poll_settings.set_visibility(1, "vrijdag", "altijd")

        # Reset
        poll_settings.reset_settings()

        # Create new settings
        poll_settings.set_visibility(2, "zaterdag", "deadline", "17:00")

        # Should work
        assert poll_settings.get_setting(2, "zaterdag") == {
            "modus": "deadline",
            "tijd": "17:00",
        }


class TestNotificationSettings(TestPollSettings):
    """Tests voor notification settings"""

    async def test_set_notification_setting_enables(self):
        """Test dat set_notification_setting een notificatie kan inschakelen"""
        # Default is False voor reminders
        assert poll_settings.is_notification_enabled(123, "reminders") is False

        # Zet aan
        poll_settings.set_notification_setting(123, "reminders", True)

        # Check dat het nu aan is
        assert poll_settings.is_notification_enabled(123, "reminders") is True

    async def test_set_notification_setting_disables(self):
        """Test dat set_notification_setting een notificatie kan uitschakelen"""
        # Zet eerst aan
        poll_settings.set_notification_setting(123, "doorgaan", True)
        assert poll_settings.is_notification_enabled(123, "doorgaan") is True

        # Zet uit
        poll_settings.set_notification_setting(123, "doorgaan", False)

        # Check dat het nu uit is
        assert poll_settings.is_notification_enabled(123, "doorgaan") is False


if __name__ == "__main__":
    import unittest

    unittest.main()
