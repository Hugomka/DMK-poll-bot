# tests/test_scheduler_utils.py
"""
Tests for utility functions in apps/scheduler.py:
- _load_poll_config
- _weekly_reset_threshold
- should_run
- _is_deadline_mode
- _within_reset_window
- _read_state and _write_state
"""

import json
import os
from datetime import datetime
from unittest.mock import patch


from apps import scheduler
from tests.base import BaseTestCase


class TestLoadPollConfig(BaseTestCase):
    """Tests for _load_poll_config"""

    async def test_load_poll_config_no_file_returns_defaults(self):
        """Test that _load_poll_config preserves defaults when file doesn't exist"""
        # Save original values
        original_reminder_hour = scheduler.REMINDER_HOUR
        original_reset_day = scheduler.RESET_DAY_OF_WEEK
        original_reset_hour = scheduler.RESET_HOUR
        original_min_votes = scheduler.MIN_NOTIFY_VOTES

        try:
            # Set known values first
            scheduler.REMINDER_HOUR = 16
            scheduler.RESET_DAY_OF_WEEK = 1
            scheduler.RESET_HOUR = 20
            scheduler.MIN_NOTIFY_VOTES = 6

            with patch("os.path.exists", return_value=False):
                scheduler._load_poll_config()

                # Should not change from the values we just set (no file to load)
                assert scheduler.REMINDER_HOUR == 16
                assert scheduler.RESET_DAY_OF_WEEK == 1
                assert scheduler.RESET_HOUR == 20
                assert scheduler.MIN_NOTIFY_VOTES == 6
        finally:
            # Restore original values
            scheduler.REMINDER_HOUR = original_reminder_hour
            scheduler.RESET_DAY_OF_WEEK = original_reset_day
            scheduler.RESET_HOUR = original_reset_hour
            scheduler.MIN_NOTIFY_VOTES = original_min_votes

    async def test_load_poll_config_with_custom_values(self):
        """Test that _load_poll_config loads custom values from JSON file"""
        import tempfile
        # Save original values
        original_reminder_hour = scheduler.REMINDER_HOUR
        original_reset_day = scheduler.RESET_DAY_OF_WEEK
        original_reset_hour = scheduler.RESET_HOUR
        original_min_votes = scheduler.MIN_NOTIFY_VOTES
        original_early_reminder_hour = scheduler.EARLY_REMINDER_HOUR
        original_early_reminder_day = scheduler.EARLY_REMINDER_DAY
        original_reminder_days = scheduler.REMINDER_DAYS.copy()

        try:
            # Create temp config file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as f:
                custom_config = {
                    "reminder_hour": 15,
                    "reset_day_of_week": 2,
                    "reset_hour": 21,
                    "min_notify_votes": 10,
                    "early_reminder_hour": 19,
                    "early_reminder_day": "woensdag",
                    "reminder_days": {"vrijdag": 4, "zaterdag": 5, "zondag": 6},
                }
                json.dump(custom_config, f)
                config_file = f.name

            # Monkeypatch CONFIG_PATH
            with patch.object(scheduler, "CONFIG_PATH", config_file):
                scheduler._load_poll_config()

                # Verify values are updated
                assert scheduler.REMINDER_HOUR == 15
                assert scheduler.RESET_DAY_OF_WEEK == 2
                assert scheduler.RESET_HOUR == 21
                assert scheduler.MIN_NOTIFY_VOTES == 10
                assert scheduler.EARLY_REMINDER_HOUR == 19
                assert scheduler.EARLY_REMINDER_DAY == "woensdag"
                assert scheduler.REMINDER_DAYS["vrijdag"] == 4
                assert scheduler.REMINDER_DAYS["zaterdag"] == 5
                assert scheduler.REMINDER_DAYS["zondag"] == 6
        finally:
            # Clean up temp file
            try:
                os.unlink(config_file)
            except:
                pass
            # Restore original values
            scheduler.REMINDER_HOUR = original_reminder_hour
            scheduler.RESET_DAY_OF_WEEK = original_reset_day
            scheduler.RESET_HOUR = original_reset_hour
            scheduler.MIN_NOTIFY_VOTES = original_min_votes
            scheduler.EARLY_REMINDER_HOUR = original_early_reminder_hour
            scheduler.EARLY_REMINDER_DAY = original_early_reminder_day
            scheduler.REMINDER_DAYS = original_reminder_days

    async def test_load_poll_config_partial_values(self):
        """Test that _load_poll_config only updates provided values"""
        import tempfile
        # Save original values
        original_reminder_hour = scheduler.REMINDER_HOUR
        original_reset_day = scheduler.RESET_DAY_OF_WEEK

        try:
            # Create temp config file with partial values
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as f:
                partial_config = {
                    "reminder_hour": 17,
                    # Missing other fields
                }
                json.dump(partial_config, f)
                config_file = f.name

            # Monkeypatch CONFIG_PATH
            with patch.object(scheduler, "CONFIG_PATH", config_file):
                scheduler._load_poll_config()

                # Only reminder_hour should be updated
                assert scheduler.REMINDER_HOUR == 17
                # Others should remain at defaults
                assert scheduler.RESET_DAY_OF_WEEK == 1
                assert scheduler.RESET_HOUR == 20
        finally:
            # Clean up temp file
            try:
                os.unlink(config_file)
            except:
                pass
            # Restore original values
            scheduler.REMINDER_HOUR = original_reminder_hour
            scheduler.RESET_DAY_OF_WEEK = original_reset_day

    async def test_load_poll_config_invalid_json_preserves_defaults(self):
        """Test that _load_poll_config preserves defaults on invalid JSON"""
        import tempfile
        # Save original value
        original_reminder_hour = scheduler.REMINDER_HOUR

        try:
            # Set known value first
            scheduler.REMINDER_HOUR = 16

            # Create temp file with invalid JSON
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as f:
                f.write("{ invalid json }")
                config_file = f.name

            # Monkeypatch CONFIG_PATH
            with patch.object(scheduler, "CONFIG_PATH", config_file):
                scheduler._load_poll_config()

                # Should preserve the value we set (invalid JSON doesn't change anything)
                assert scheduler.REMINDER_HOUR == 16
        finally:
            # Clean up temp file
            try:
                os.unlink(config_file)
            except:
                pass
            # Restore original value
            scheduler.REMINDER_HOUR = original_reminder_hour


class TestWeeklyResetThreshold(BaseTestCase):
    """Tests for _weekly_reset_threshold"""

    async def test_weekly_reset_threshold_monday_before_sunday_2030(self):
        """Test threshold when now is Monday (before last Sunday 20:30)"""
        # Monday, 2025-12-29, 19:00 Amsterdam time
        now = scheduler.TZ.localize(datetime(2025, 12, 29, 19, 0))
        result = scheduler._weekly_reset_threshold(now)

        # Should return last Sunday (2025-12-28) at 20:30
        expected = scheduler.TZ.localize(datetime(2025, 12, 28, 20, 30))
        assert result == expected

    async def test_weekly_reset_threshold_sunday_before_2030(self):
        """Test threshold when now is Sunday before 20:30"""
        # Sunday, 2025-12-28, 19:00 (before 20:30)
        now = scheduler.TZ.localize(datetime(2025, 12, 28, 19, 0))
        result = scheduler._weekly_reset_threshold(now)

        # Should return previous Sunday (2025-12-21) at 20:30
        expected = scheduler.TZ.localize(datetime(2025, 12, 21, 20, 30))
        assert result == expected

    async def test_weekly_reset_threshold_sunday_after_2030(self):
        """Test threshold when now is Sunday after 20:30"""
        # Sunday, 2025-12-28, 21:00 (after 20:30)
        now = scheduler.TZ.localize(datetime(2025, 12, 28, 21, 0))
        result = scheduler._weekly_reset_threshold(now)

        # Should return this Sunday (2025-12-28) at 20:30
        expected = scheduler.TZ.localize(datetime(2025, 12, 28, 20, 30))
        assert result == expected

    async def test_weekly_reset_threshold_sunday_exactly_2030(self):
        """Test threshold when now is Sunday exactly at 20:30"""
        # Sunday, 2025-12-28, 20:30
        now = scheduler.TZ.localize(datetime(2025, 12, 28, 20, 30))
        result = scheduler._weekly_reset_threshold(now)

        # Should return this Sunday (2025-12-28) at 20:30
        expected = scheduler.TZ.localize(datetime(2025, 12, 28, 20, 30))
        assert result == expected

    async def test_weekly_reset_threshold_with_naive_datetime(self):
        """Test that naive datetime is localized properly"""
        # Naive datetime - Monday, 2025-12-29, 19:00
        now = datetime(2025, 12, 29, 19, 0)
        result = scheduler._weekly_reset_threshold(now)

        # Should return last Sunday (2025-12-28) at 20:30 in Amsterdam time
        expected = scheduler.TZ.localize(datetime(2025, 12, 28, 20, 30))
        assert result == expected
        assert result.tzinfo is not None

    async def test_weekly_reset_threshold_friday(self):
        """Test threshold when now is Friday"""
        # Friday, 2026-01-02, 18:00
        now = scheduler.TZ.localize(datetime(2026, 1, 2, 18, 0))
        result = scheduler._weekly_reset_threshold(now)

        # Should return last Sunday (2025-12-28) at 20:30
        expected = scheduler.TZ.localize(datetime(2025, 12, 28, 20, 30))
        assert result == expected


class TestShouldRun(BaseTestCase):
    """Tests for should_run"""

    async def test_should_run_with_none_last_run(self):
        """Test that None last_run always returns True"""
        occurrence = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        result = scheduler.should_run(None, occurrence)
        assert result is True

    async def test_should_run_with_earlier_last_run(self):
        """Test that earlier last_run returns True"""
        occurrence = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        last_run = scheduler.TZ.localize(datetime(2025, 12, 30, 18, 0))
        result = scheduler.should_run(last_run, occurrence)
        assert result is True

    async def test_should_run_with_later_last_run(self):
        """Test that later last_run returns False"""
        occurrence = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        last_run = scheduler.TZ.localize(datetime(2026, 1, 1, 18, 0))
        result = scheduler.should_run(last_run, occurrence)
        assert result is False

    async def test_should_run_with_equal_last_run(self):
        """Test that equal last_run returns False"""
        occurrence = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        last_run = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        result = scheduler.should_run(last_run, occurrence)
        assert result is False

    async def test_should_run_with_iso_string_last_run(self):
        """Test that ISO string last_run is parsed correctly"""
        occurrence = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        last_run_str = "2025-12-30T18:00:00+01:00"
        result = scheduler.should_run(last_run_str, occurrence)
        assert result is True

    async def test_should_run_with_naive_datetime_last_run(self):
        """Test that naive datetime last_run is localized"""
        occurrence = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        last_run = datetime(2025, 12, 30, 18, 0)  # Naive
        result = scheduler.should_run(last_run, occurrence)
        assert result is True

    async def test_should_run_with_naive_occurrence(self):
        """Test that naive occurrence is localized"""
        occurrence = datetime(2025, 12, 31, 18, 0)  # Naive
        last_run = scheduler.TZ.localize(datetime(2025, 12, 30, 18, 0))
        result = scheduler.should_run(last_run, occurrence)
        assert result is True

    async def test_should_run_with_invalid_last_run_string(self):
        """Test that invalid last_run string returns True (fallback)"""
        occurrence = scheduler.TZ.localize(datetime(2025, 12, 31, 18, 0))
        last_run_str = "invalid datetime string"
        result = scheduler.should_run(last_run_str, occurrence)
        assert result is True


class TestIsDeadlineMode(BaseTestCase):
    """Tests for _is_deadline_mode"""

    async def test_is_deadline_mode_no_setting_returns_true(self):
        """Test that no setting defaults to deadline mode"""
        with patch("apps.utils.poll_settings.get_setting", return_value=None):
            result = scheduler._is_deadline_mode(123, "vrijdag")
            assert result is True

    async def test_is_deadline_mode_empty_dict_returns_true(self):
        """Test that empty dict defaults to deadline mode"""
        with patch("apps.utils.poll_settings.get_setting", return_value={}):
            result = scheduler._is_deadline_mode(123, "vrijdag")
            assert result is True

    async def test_is_deadline_mode_explicit_deadline_returns_true(self):
        """Test that explicit deadline mode returns True"""
        with patch(
            "apps.utils.poll_settings.get_setting",
            return_value={"modus": "deadline", "tijd": "18:00"},
        ):
            result = scheduler._is_deadline_mode(123, "vrijdag")
            assert result is True

    async def test_is_deadline_mode_altijd_returns_false(self):
        """Test that altijd mode returns False"""
        with patch(
            "apps.scheduler.get_setting",
            return_value={"modus": "altijd", "tijd": "18:00"},
        ):
            result = scheduler._is_deadline_mode(123, "vrijdag")
            assert result is False

    async def test_is_deadline_mode_non_dict_returns_true(self):
        """Test that non-dict setting defaults to deadline mode"""
        with patch("apps.utils.poll_settings.get_setting", return_value="invalid"):
            result = scheduler._is_deadline_mode(123, "vrijdag")
            assert result is True

    async def test_is_deadline_mode_exception_returns_true(self):
        """Test that exception defaults to deadline mode"""
        with patch(
            "apps.utils.poll_settings.get_setting",
            side_effect=Exception("Database error"),
        ):
            result = scheduler._is_deadline_mode(123, "vrijdag")
            assert result is True

    async def test_is_deadline_mode_missing_modus_key_defaults_deadline(self):
        """Test that missing modus key defaults to deadline"""
        with patch(
            "apps.utils.poll_settings.get_setting", return_value={"tijd": "18:00"}
        ):
            result = scheduler._is_deadline_mode(123, "vrijdag")
            assert result is True


class TestWithinResetWindow(BaseTestCase):
    """Tests for _within_reset_window"""

    async def test_within_reset_window_tuesday_2000_returns_true(self):
        """Test that Tuesday 20:00 is within window"""
        # Tuesday (weekday=1), 20:00
        now = scheduler.TZ.localize(datetime(2025, 12, 30, 20, 0))
        result = scheduler._within_reset_window(now)
        assert result is True

    async def test_within_reset_window_tuesday_2004_returns_true(self):
        """Test that Tuesday 20:04 is within window"""
        # Tuesday, 20:04
        now = scheduler.TZ.localize(datetime(2025, 12, 30, 20, 4))
        result = scheduler._within_reset_window(now)
        assert result is True

    async def test_within_reset_window_tuesday_1959_returns_false(self):
        """Test that Tuesday 19:59 is outside window"""
        # Tuesday, 19:59
        now = scheduler.TZ.localize(datetime(2025, 12, 30, 19, 59))
        result = scheduler._within_reset_window(now)
        assert result is False

    async def test_within_reset_window_tuesday_2005_returns_false(self):
        """Test that Tuesday 20:05 is outside window (>= 5 minutes)"""
        # Tuesday, 20:05
        now = scheduler.TZ.localize(datetime(2025, 12, 30, 20, 5))
        result = scheduler._within_reset_window(now)
        assert result is False

    async def test_within_reset_window_monday_2000_returns_false(self):
        """Test that Monday 20:00 is outside window"""
        # Monday (weekday=0), 20:00
        now = scheduler.TZ.localize(datetime(2025, 12, 29, 20, 0))
        result = scheduler._within_reset_window(now)
        assert result is False

    async def test_within_reset_window_wednesday_2000_returns_false(self):
        """Test that Wednesday 20:00 is outside window"""
        # Wednesday (weekday=2), 20:00
        now = scheduler.TZ.localize(datetime(2025, 12, 31, 20, 0))
        result = scheduler._within_reset_window(now)
        assert result is False

    async def test_within_reset_window_with_naive_datetime(self):
        """Test that naive datetime is localized"""
        # Naive Tuesday, 20:00
        now = datetime(2025, 12, 30, 20, 0)
        result = scheduler._within_reset_window(now)
        assert result is True

    async def test_within_reset_window_custom_minutes(self):
        """Test custom minutes parameter"""
        # Tuesday, 20:07 - should be outside default 5 min window
        now = scheduler.TZ.localize(datetime(2025, 12, 30, 20, 7))
        result = scheduler._within_reset_window(now, minutes=5)
        assert result is False

        # But within 10 minute window
        result = scheduler._within_reset_window(now, minutes=10)
        assert result is True


class TestReadWriteState(BaseTestCase):
    """Tests for _read_state and _write_state"""

    async def test_write_state_creates_file(self):
        """Test that _write_state creates a new state file"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            with patch.object(scheduler, "STATE_PATH", state_file):
                test_data = {"foo": "bar", "count": 42}
                scheduler._write_state(test_data)

                # Verify file exists and contains correct data
                assert os.path.exists(state_file)
                with open(state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                assert loaded == test_data
        finally:
            try:
                os.unlink(state_file)
            except:
                pass

    async def test_write_state_uses_atomic_write(self):
        """Test that _write_state uses atomic .tmp file"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            with patch.object(scheduler, "STATE_PATH", state_file):
                test_data = {"atomic": "write"}
                scheduler._write_state(test_data)

                # Verify final file exists
                assert os.path.exists(state_file)

                # Verify .tmp file was cleaned up (replaced)
                tmp_file = state_file + ".tmp"
                assert not os.path.exists(tmp_file)
        finally:
            try:
                os.unlink(state_file)
            except:
                pass

    async def test_read_state_returns_written_data(self):
        """Test that _read_state returns data written by _write_state"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            with patch.object(scheduler, "STATE_PATH", state_file):
                test_data = {"key1": "value1", "key2": 123}
                scheduler._write_state(test_data)
                result = scheduler._read_state()

                assert result == test_data
        finally:
            try:
                os.unlink(state_file)
            except:
                pass

    async def test_read_state_no_file_returns_empty_dict(self):
        """Test that _read_state returns empty dict when file doesn't exist"""
        import tempfile
        state_file = os.path.join(tempfile.gettempdir(), "nonexistent_" + str(os.getpid()) + ".json")

        with patch.object(scheduler, "STATE_PATH", state_file):
            result = scheduler._read_state()
            assert result == {}

    async def test_read_state_invalid_json_returns_empty_dict(self):
        """Test that _read_state returns empty dict on invalid JSON"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as f:
            f.write("{ invalid json }")
            state_file = f.name

        try:
            with patch.object(scheduler, "STATE_PATH", state_file):
                result = scheduler._read_state()
                assert result == {}
        finally:
            try:
                os.unlink(state_file)
            except:
                pass

    async def test_write_read_state_roundtrip(self):
        """Test complete roundtrip of write and read"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            with patch.object(scheduler, "STATE_PATH", state_file):
                # Write complex data
                original = {
                    "reset_polls": "2025-12-30T20:00:00+01:00",
                    "update_all_polls": "2025-12-31T18:00:00+01:00",
                    "notify_vrijdag": "2026-01-03T18:05:00+01:00",
                    "counter": 999,
                }
                scheduler._write_state(original)

                # Read it back
                result = scheduler._read_state()

                assert result == original
        finally:
            try:
                os.unlink(state_file)
            except:
                pass

    async def test_write_state_overwrites_existing(self):
        """Test that _write_state overwrites existing file"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            with patch.object(scheduler, "STATE_PATH", state_file):
                # Write initial data
                initial = {"old": "data"}
                scheduler._write_state(initial)

                # Overwrite with new data
                new_data = {"new": "data", "more": "fields"}
                scheduler._write_state(new_data)

                # Verify new data is there
                result = scheduler._read_state()
                assert result == new_data
                assert "old" not in result
        finally:
            try:
                os.unlink(state_file)
            except:
                pass


if __name__ == "__main__":
    import unittest

    unittest.main()
