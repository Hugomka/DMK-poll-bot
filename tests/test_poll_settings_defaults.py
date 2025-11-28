# tests/test_poll_settings_defaults.py

"""
Tests for global default schedules in poll_settings.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from apps.utils import poll_settings
from apps.utils.poll_settings import (
    get_default_activation,
    get_default_deactivation,
    get_effective_activation,
    get_effective_deactivation,
    set_default_activation,
    set_default_deactivation,
    set_scheduled_activation,
    set_scheduled_deactivation,
)


class TestDefaultSchedules(unittest.TestCase):
    """Test global default schedule getters and setters."""

    def setUp(self):
        """Reset settings before each test using temp file."""
        # Create temp file for this test
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        self.temp_file.close()
        self.temp_settings_path = self.temp_file.name

        # Patch environment variable (for module reloads)
        self.original_settings_env = os.environ.get("SETTINGS_FILE")
        os.environ["SETTINGS_FILE"] = self.temp_settings_path

        # Patch SETTINGS_FILE to use temp file
        self.original_settings_file = poll_settings.SETTINGS_FILE
        poll_settings.SETTINGS_FILE = self.temp_settings_path

    def tearDown(self):
        """Clean up after each test."""
        # Restore original settings file
        poll_settings.SETTINGS_FILE = self.original_settings_file

        # Restore environment variable
        if self.original_settings_env is not None:
            os.environ["SETTINGS_FILE"] = self.original_settings_env
        else:
            os.environ.pop("SETTINGS_FILE", None)

        # Remove temp file
        try:
            if os.path.exists(self.temp_settings_path):
                os.remove(self.temp_settings_path)
        except Exception:
            pass

    @patch.dict(os.environ, {"SEED_DEFAULT_SCHEDULES": "false"})
    def test_no_defaults_when_seeding_disabled(self):
        """Test that no defaults are seeded when SEED_DEFAULT_SCHEDULES=false."""
        # Force reimport to apply env var
        import importlib
        import apps.utils.poll_settings
        importlib.reload(apps.utils.poll_settings)

        from apps.utils.poll_settings import get_default_activation, get_default_deactivation

        act = get_default_activation()
        deact = get_default_deactivation()

        self.assertIsNone(act)
        self.assertIsNone(deact)

    def test_get_default_activation_returns_none_when_not_set(self):
        """Test that get_default_activation returns None when not set."""
        # Clear any seeded defaults
        set_default_activation(None)
        result = get_default_activation()
        self.assertIsNone(result)

    def test_get_default_deactivation_returns_none_when_not_set(self):
        """Test that get_default_deactivation returns None when not set."""
        # Clear any seeded defaults
        set_default_deactivation(None)
        result = get_default_deactivation()
        self.assertIsNone(result)

    def test_set_and_get_default_activation(self):
        """Test setting and getting default activation."""
        schedule = {"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"}
        set_default_activation(schedule)

        result = get_default_activation()
        self.assertEqual(result, schedule)

    def test_set_and_get_default_deactivation(self):
        """Test setting and getting default deactivation."""
        schedule = {"type": "wekelijks", "dag": "maandag", "tijd": "00:00"}
        set_default_deactivation(schedule)

        result = get_default_deactivation()
        self.assertEqual(result, schedule)

    def test_set_default_activation_to_none_removes_it(self):
        """Test that setting default activation to None removes it."""
        schedule = {"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"}
        set_default_activation(schedule)
        self.assertIsNotNone(get_default_activation())

        set_default_activation(None)
        self.assertIsNone(get_default_activation())

    def test_set_default_deactivation_to_none_removes_it(self):
        """Test that setting default deactivation to None removes it."""
        schedule = {"type": "wekelijks", "dag": "maandag", "tijd": "00:00"}
        set_default_deactivation(schedule)
        self.assertIsNotNone(get_default_deactivation())

        set_default_deactivation(None)
        self.assertIsNone(get_default_deactivation())


class TestEffectiveSchedules(unittest.TestCase):
    """Test effective schedule getters with fallback logic."""

    def setUp(self):
        """Reset settings before each test using temp file."""
        # Create temp file for this test
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        self.temp_file.close()
        self.temp_settings_path = self.temp_file.name

        # Patch environment variable (for module reloads)
        self.original_settings_env = os.environ.get("SETTINGS_FILE")
        os.environ["SETTINGS_FILE"] = self.temp_settings_path

        # Patch SETTINGS_FILE to use temp file
        self.original_settings_file = poll_settings.SETTINGS_FILE
        poll_settings.SETTINGS_FILE = self.temp_settings_path

    def tearDown(self):
        """Clean up after each test."""
        # Restore original settings file
        poll_settings.SETTINGS_FILE = self.original_settings_file

        # Restore environment variable
        if self.original_settings_env is not None:
            os.environ["SETTINGS_FILE"] = self.original_settings_env
        else:
            os.environ.pop("SETTINGS_FILE", None)

        # Remove temp file
        try:
            if os.path.exists(self.temp_settings_path):
                os.remove(self.temp_settings_path)
        except Exception:
            pass

    def test_effective_activation_with_no_defaults_and_no_channel_override(self):
        """Test that effective activation returns (None, False) when nothing is set."""
        # Clear any seeded defaults
        set_default_activation(None)

        schedule, is_default = get_effective_activation(123)
        self.assertIsNone(schedule)
        self.assertFalse(is_default)

    def test_effective_deactivation_with_no_defaults_and_no_channel_override(self):
        """Test that effective deactivation returns (None, False) when nothing is set."""
        # Clear any seeded defaults
        set_default_deactivation(None)

        schedule, is_default = get_effective_deactivation(123)
        self.assertIsNone(schedule)
        self.assertFalse(is_default)

    def test_effective_activation_returns_default_when_no_channel_override(self):
        """Test that effective activation returns default when channel has no override."""
        default_schedule = {"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"}
        set_default_activation(default_schedule)

        schedule, is_default = get_effective_activation(123)
        self.assertEqual(schedule, default_schedule)
        self.assertTrue(is_default)

    def test_effective_deactivation_returns_default_when_no_channel_override(self):
        """Test that effective deactivation returns default when channel has no override."""
        default_schedule = {"type": "wekelijks", "dag": "maandag", "tijd": "00:00"}
        set_default_deactivation(default_schedule)

        schedule, is_default = get_effective_deactivation(123)
        self.assertEqual(schedule, default_schedule)
        self.assertTrue(is_default)

    def test_effective_activation_prefers_channel_override_over_default(self):
        """Test that effective activation returns channel override when both exist."""
        default_schedule = {"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"}
        set_default_activation(default_schedule)

        set_scheduled_activation(123, "wekelijks", "18:00", dag="woensdag")

        schedule, is_default = get_effective_activation(123)
        self.assertIsNotNone(schedule)
        assert schedule is not None  # Type narrowing for Pylance
        self.assertEqual(schedule["dag"], "woensdag")
        self.assertEqual(schedule["tijd"], "18:00")
        self.assertFalse(is_default)

    def test_effective_deactivation_prefers_channel_override_over_default(self):
        """Test that effective deactivation returns channel override when both exist."""
        default_schedule = {"type": "wekelijks", "dag": "maandag", "tijd": "00:00"}
        set_default_deactivation(default_schedule)

        set_scheduled_deactivation(123, "wekelijks", "23:00", dag="zondag")

        schedule, is_default = get_effective_deactivation(123)
        self.assertIsNotNone(schedule)
        assert schedule is not None  # Type narrowing for Pylance
        self.assertEqual(schedule["dag"], "zondag")
        self.assertEqual(schedule["tijd"], "23:00")
        self.assertFalse(is_default)

    def test_effective_schedules_work_for_multiple_channels_independently(self):
        """Test that effective schedules work independently for multiple channels."""
        default_act = {"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"}
        set_default_activation(default_act)

        # Channel 123 has an override
        set_scheduled_activation(123, "wekelijks", "19:00", dag="vrijdag")

        # Channel 456 has no override (should get default)
        act_123, is_default_123 = get_effective_activation(123)
        act_456, is_default_456 = get_effective_activation(456)

        # Channel 123 should return its override
        self.assertIsNotNone(act_123)
        assert act_123 is not None  # Type narrowing for Pylance
        self.assertEqual(act_123["dag"], "vrijdag")
        self.assertFalse(is_default_123)

        # Channel 456 should return the default
        self.assertIsNotNone(act_456)
        assert act_456 is not None  # Type narrowing for Pylance
        self.assertEqual(act_456["dag"], "dinsdag")
        self.assertTrue(is_default_456)


if __name__ == "__main__":
    unittest.main()
