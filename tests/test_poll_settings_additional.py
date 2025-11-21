# tests/test_poll_settings_additional.py
"""
Additional tests for poll_settings.py to increase coverage.

Test coverage:
- set_scheduled_activation with wekelijks type
- set_scheduled_deactivation with wekelijks type
- get_enabled_days with different scenarios
- set_enabled_days with validation
- get_enabled_times_for_day with different combinations
"""

import os
import tempfile

from apps.utils import poll_settings
from tests.base import BaseTestCase

EXPECTED_DAYS = ["vrijdag", "zaterdag", "zondag"]


class TestPollSettingsAdditional(BaseTestCase):
    """Additional tests for poll_settings functions."""

    async def asyncSetUp(self):
        """Set up isolated test environment with temp settings file."""
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
        """Clean up temp file and restore original settings."""
        # Restore original
        poll_settings.SETTINGS_FILE = self.original_settings_file

        # Remove temp file
        try:
            if os.path.exists(self.temp_settings_path):
                os.unlink(self.temp_settings_path)
        except Exception:  # pragma: no cover
            pass

        await super().asyncTearDown()

    # ========================================================================
    # Tests for set_scheduled_activation - wekelijks branch
    # ========================================================================

    async def test_set_scheduled_activation_wekelijks(self):
        """Test set_scheduled_activation met type='wekelijks'."""
        result = poll_settings.set_scheduled_activation(
            channel_id=123,
            activation_type="wekelijks",
            tijd="20:00",
            dag="dinsdag",
        )

        # Check return value
        self.assertEqual(result["type"], "wekelijks")
        self.assertEqual(result["tijd"], "20:00")
        self.assertEqual(result["dag"], "dinsdag")
        self.assertNotIn("datum", result)

        # Verify persistence
        saved = poll_settings.get_scheduled_activation(123)
        self.assertEqual(saved, result)

    async def test_set_scheduled_activation_datum(self):
        """Test set_scheduled_activation met type='datum'."""
        result = poll_settings.set_scheduled_activation(
            channel_id=123, activation_type="datum", tijd="14:30", datum="2025-12-25"
        )

        # Check return value
        self.assertEqual(result["type"], "datum")
        self.assertEqual(result["tijd"], "14:30")
        self.assertEqual(result["datum"], "2025-12-25")
        self.assertNotIn("dag", result)

    async def test_set_scheduled_activation_missing_parameters(self):
        """Test set_scheduled_activation zonder datum/dag parameters (edge case)."""
        # Edge case: type='datum' but no datum provided
        result = poll_settings.set_scheduled_activation(
            channel_id=123, activation_type="datum", tijd="14:30"
        )

        # Should still save, but without datum field
        self.assertEqual(result["type"], "datum")
        self.assertEqual(result["tijd"], "14:30")
        self.assertNotIn("datum", result)

    # ========================================================================
    # Tests for set_scheduled_deactivation - wekelijks branch
    # ========================================================================

    async def test_set_scheduled_deactivation_wekelijks(self):
        """Test set_scheduled_deactivation met type='wekelijks'."""
        result = poll_settings.set_scheduled_deactivation(
            channel_id=456,
            activation_type="wekelijks",
            tijd="00:00",
            dag="maandag",
        )

        # Check return value
        self.assertEqual(result["type"], "wekelijks")
        self.assertEqual(result["tijd"], "00:00")
        self.assertEqual(result["dag"], "maandag")
        self.assertNotIn("datum", result)

        # Verify persistence
        saved = poll_settings.get_scheduled_deactivation(456)
        self.assertEqual(saved, result)

    async def test_set_scheduled_deactivation_datum(self):
        """Test set_scheduled_deactivation met type='datum'."""
        result = poll_settings.set_scheduled_deactivation(
            channel_id=456, activation_type="datum", tijd="23:59", datum="2025-12-31"
        )

        # Check return value
        self.assertEqual(result["type"], "datum")
        self.assertEqual(result["tijd"], "23:59")
        self.assertEqual(result["datum"], "2025-12-31")
        self.assertNotIn("dag", result)

    async def test_set_scheduled_deactivation_missing_parameters(self):
        """Test set_scheduled_deactivation zonder datum/dag parameters (edge case)."""
        # Edge case: type='wekelijks' but no dag provided
        result = poll_settings.set_scheduled_deactivation(
            channel_id=456, activation_type="wekelijks", tijd="00:00"
        )

        # Should still save, but without dag field
        self.assertEqual(result["type"], "wekelijks")
        self.assertEqual(result["tijd"], "00:00")
        self.assertNotIn("dag", result)

    # ========================================================================
    # Tests for get_enabled_days
    # ========================================================================

    async def test_get_enabled_days_default(self):
        """Test get_enabled_days returns default when not set."""
        result = poll_settings.get_enabled_days(789)

        # Default: vrijdag, zaterdag, zondag
        self.assertEqual(result, EXPECTED_DAYS)

    async def test_get_enabled_days_custom(self):
        """Test get_enabled_days returns custom value when set."""
        # Set custom enabled days
        poll_settings.set_enabled_days(789, ["zondag"])

        # Retrieve
        result = poll_settings.get_enabled_days(789)
        self.assertEqual(result, ["zondag"])

    async def test_get_enabled_days_invalid_type_returns_default(self):
        """Test get_enabled_days returns default if stored value is not a list."""
        # Manually corrupt data to non-list value
        data = poll_settings._load_data()
        data["789"] = {"__enabled_days__": "not-a-list"}
        poll_settings._save_data(data)

        # Should return default
        result = poll_settings.get_enabled_days(789)
        self.assertEqual(result, EXPECTED_DAYS)

    # ========================================================================
    # Tests for set_enabled_days
    # ========================================================================

    async def test_set_enabled_days_valid_single_day(self):
        """Test set_enabled_days met één dag."""
        result = poll_settings.set_enabled_days(111, ["zondag"])

        # Check return value
        self.assertEqual(result, ["zondag"])

        # Verify persistence
        saved = poll_settings.get_enabled_days(111)
        self.assertEqual(saved, ["zondag"])

    async def test_set_enabled_days_valid_multiple_days(self):
        """Test set_enabled_days met meerdere dagen."""
        result = poll_settings.set_enabled_days(222, EXPECTED_DAYS)

        # Check return value
        self.assertEqual(result, EXPECTED_DAYS)

        # Verify persistence
        saved = poll_settings.get_enabled_days(222)
        self.assertEqual(saved, EXPECTED_DAYS)

    async def test_set_enabled_days_case_insensitive(self):
        """Test set_enabled_days normalizes to lowercase."""
        result = poll_settings.set_enabled_days(333, ["Vrijdag", "ZATERDAG", "ZoNdAg"])

        # Should be normalized to lowercase
        self.assertEqual(result, EXPECTED_DAYS)

    async def test_set_enabled_days_invalid_day_raises_error(self):
        """Test set_enabled_days raises ValueError voor ongeldige dag."""
        with self.assertRaises(ValueError) as context:
            poll_settings.set_enabled_days(444, ["invalid-day"])

        # Check error message
        self.assertIn("Ongeldige dag", str(context.exception))
        self.assertIn("invalid-day", str(context.exception))

    async def test_set_enabled_days_mixed_valid_invalid_raises_error(self):
        """Test set_enabled_days raises ValueError als één dag ongeldig is."""
        with self.assertRaises(ValueError) as context:
            poll_settings.set_enabled_days(555, ["vrijdag", "foobar", "zondag"])

        # Check error message
        self.assertIn("Ongeldige dag", str(context.exception))
        self.assertIn("foobar", str(context.exception))

    # ========================================================================
    # Tests for get_enabled_times_for_day
    # ========================================================================

    async def test_get_enabled_times_for_day_both_enabled(self):
        """Test get_enabled_times_for_day met beide tijden enabled (default)."""
        # Default: both times enabled
        result = poll_settings.get_enabled_times_for_day(666, "vrijdag")

        # Should return both times
        self.assertEqual(result, ["om 19:00 uur", "om 20:30 uur"])

    async def test_get_enabled_times_for_day_only_1900_enabled(self):
        """Test get_enabled_times_for_day met alleen 19:00 enabled."""
        # Disable 20:30
        poll_settings.set_poll_option_state(777, "zaterdag", "20:30", False)

        result = poll_settings.get_enabled_times_for_day(777, "zaterdag")

        # Should return only 19:00
        self.assertEqual(result, ["om 19:00 uur"])

    async def test_get_enabled_times_for_day_only_2030_enabled(self):
        """Test get_enabled_times_for_day met alleen 20:30 enabled."""
        # Disable 19:00
        poll_settings.set_poll_option_state(888, "zondag", "19:00", False)

        result = poll_settings.get_enabled_times_for_day(888, "zondag")

        # Should return only 20:30
        self.assertEqual(result, ["om 20:30 uur"])

    async def test_get_enabled_times_for_day_none_enabled(self):
        """Test get_enabled_times_for_day met beide tijden disabled."""
        # Disable both times
        poll_settings.set_poll_option_state(999, "vrijdag", "19:00", False)
        poll_settings.set_poll_option_state(999, "vrijdag", "20:30", False)

        result = poll_settings.get_enabled_times_for_day(999, "vrijdag")

        # Should return empty list
        self.assertEqual(result, [])
