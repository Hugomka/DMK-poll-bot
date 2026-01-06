# tests/test_period_migration.py
"""Tests voor migratie van oude settings naar nieuwe period-based settings."""

import json
from unittest.mock import patch, mock_open

from apps.utils.poll_settings import (
    migrate_channel_to_periods,
    migrate_all_channels_to_periods,
)
from tests.base import BaseTestCase


class TestPeriodMigration(BaseTestCase):
    """Test migratie van oude naar nieuwe period settings."""

    def setUp(self):
        """Setup voor elke test."""
        super().setUp()
        self.test_channel_id = 123456789
        self.test_data_path = "data/poll_settings.json"

    def test_migrate_channel_with_old_settings_vr_zo_only(self):
        """Test migratie van kanaal met alleen vr-zo dagen enabled."""
        # Maak test data met oude format
        old_data = {
            str(self.test_channel_id): {
                "__poll_options__": {
                    "maandag_19:00": False,
                    "maandag_20:30": False,
                    "dinsdag_19:00": False,
                    "dinsdag_20:30": False,
                    "woensdag_19:00": False,
                    "woensdag_20:30": False,
                    "donderdag_19:00": False,
                    "donderdag_20:30": False,
                    "vrijdag_19:00": True,
                    "vrijdag_20:30": True,
                    "zaterdag_19:00": True,
                    "zaterdag_20:30": True,
                    "zondag_19:00": True,
                    "zondag_20:30": True,
                },
                "__scheduled_activation__": {
                    "dag": "dinsdag",
                    "tijd": "20:00"
                },
                "__scheduled_deactivation__": {
                    "dag": "maandag",
                    "tijd": "00:00"
                }
            }
        }

        mock_data = json.dumps(old_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump") as mock_dump:
                    result = migrate_channel_to_periods(self.test_channel_id)

        self.assertTrue(result)

        # Verify correct data was written
        call_args = mock_dump.call_args[0][0]
        migrated_settings = call_args[str(self.test_channel_id)]["__period_settings__"]

        # vr-zo should be enabled with migrated settings
        self.assertTrue(migrated_settings["vr-zo"]["enabled"])
        self.assertEqual(migrated_settings["vr-zo"]["close_day"], "maandag")
        self.assertEqual(migrated_settings["vr-zo"]["close_time"], "00:00")
        self.assertEqual(migrated_settings["vr-zo"]["open_day"], "dinsdag")
        self.assertEqual(migrated_settings["vr-zo"]["open_time"], "20:00")

        # ma-do should be disabled with defaults
        self.assertFalse(migrated_settings["ma-do"]["enabled"])
        self.assertEqual(migrated_settings["ma-do"]["close_day"], "vrijdag")
        self.assertEqual(migrated_settings["ma-do"]["close_time"], "00:00")

        # Old settings should be removed
        self.assertNotIn("__scheduled_activation__", call_args[str(self.test_channel_id)])
        self.assertNotIn("__scheduled_deactivation__", call_args[str(self.test_channel_id)])

    def test_migrate_channel_with_old_settings_ma_do_only(self):
        """Test migratie van kanaal met alleen ma-do dagen enabled."""
        old_data = {
            str(self.test_channel_id): {
                "__poll_options__": {
                    "maandag_19:00": True,
                    "maandag_20:30": True,
                    "dinsdag_19:00": True,
                    "dinsdag_20:30": True,
                    "woensdag_19:00": True,
                    "woensdag_20:30": True,
                    "donderdag_19:00": True,
                    "donderdag_20:30": True,
                    "vrijdag_19:00": False,
                    "vrijdag_20:30": False,
                    "zaterdag_19:00": False,
                    "zaterdag_20:30": False,
                    "zondag_19:00": False,
                    "zondag_20:30": False,
                },
                "__scheduled_activation__": {
                    "dag": "vrijdag",
                    "tijd": "18:00"
                },
                "__scheduled_deactivation__": {
                    "dag": "donderdag",
                    "tijd": "23:59"
                }
            }
        }

        mock_data = json.dumps(old_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump") as mock_dump:
                    result = migrate_channel_to_periods(self.test_channel_id)

        self.assertTrue(result)

        call_args = mock_dump.call_args[0][0]
        migrated_settings = call_args[str(self.test_channel_id)]["__period_settings__"]

        # vr-zo should be disabled but inherit old settings
        self.assertFalse(migrated_settings["vr-zo"]["enabled"])
        self.assertEqual(migrated_settings["vr-zo"]["close_day"], "donderdag")
        self.assertEqual(migrated_settings["vr-zo"]["close_time"], "23:59")
        self.assertEqual(migrated_settings["vr-zo"]["open_day"], "vrijdag")
        self.assertEqual(migrated_settings["vr-zo"]["open_time"], "18:00")

        # ma-do should be enabled with defaults
        self.assertTrue(migrated_settings["ma-do"]["enabled"])

    def test_migrate_channel_with_both_periods_enabled(self):
        """Test migratie van kanaal met beide periodes enabled."""
        old_data = {
            str(self.test_channel_id): {
                "__poll_options__": {
                    "maandag_19:00": True,
                    "maandag_20:30": False,
                    "dinsdag_19:00": False,
                    "dinsdag_20:30": False,
                    "woensdag_19:00": False,
                    "woensdag_20:30": False,
                    "donderdag_19:00": False,
                    "donderdag_20:30": False,
                    "vrijdag_19:00": True,
                    "vrijdag_20:30": False,
                    "zaterdag_19:00": False,
                    "zaterdag_20:30": False,
                    "zondag_19:00": False,
                    "zondag_20:30": False,
                },
                "__scheduled_activation__": {
                    "dag": "dinsdag",
                    "tijd": "20:00"
                },
                "__scheduled_deactivation__": {
                    "dag": "maandag",
                    "tijd": "00:00"
                }
            }
        }

        mock_data = json.dumps(old_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump") as mock_dump:
                    result = migrate_channel_to_periods(self.test_channel_id)

        self.assertTrue(result)

        call_args = mock_dump.call_args[0][0]
        migrated_settings = call_args[str(self.test_channel_id)]["__period_settings__"]

        # Both should be enabled
        self.assertTrue(migrated_settings["vr-zo"]["enabled"])
        self.assertTrue(migrated_settings["ma-do"]["enabled"])

    def test_migrate_channel_with_no_enabled_days_defaults_to_vr_zo(self):
        """Test dat kanaal zonder enabled dagen default naar vr-zo gaat."""
        old_data = {
            str(self.test_channel_id): {
                "__poll_options__": {
                    "maandag_19:00": False,
                    "maandag_20:30": False,
                    "dinsdag_19:00": False,
                    "dinsdag_20:30": False,
                    "woensdag_19:00": False,
                    "woensdag_20:30": False,
                    "donderdag_19:00": False,
                    "donderdag_20:30": False,
                    "vrijdag_19:00": False,
                    "vrijdag_20:30": False,
                    "zaterdag_19:00": False,
                    "zaterdag_20:30": False,
                    "zondag_19:00": False,
                    "zondag_20:30": False,
                }
            }
        }

        mock_data = json.dumps(old_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump") as mock_dump:
                    result = migrate_channel_to_periods(self.test_channel_id)

        self.assertTrue(result)

        call_args = mock_dump.call_args[0][0]
        migrated_settings = call_args[str(self.test_channel_id)]["__period_settings__"]

        # vr-zo should be enabled as default
        self.assertTrue(migrated_settings["vr-zo"]["enabled"])
        self.assertFalse(migrated_settings["ma-do"]["enabled"])

    def test_migrate_channel_already_migrated_returns_false(self):
        """Test dat migreren van al gemigreerd kanaal False returnt."""
        already_migrated_data = {
            str(self.test_channel_id): {
                "__poll_options__": {},
                "__period_settings__": {
                    "vr-zo": {"enabled": True},
                    "ma-do": {"enabled": False}
                }
            }
        }

        mock_data = json.dumps(already_migrated_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                result = migrate_channel_to_periods(self.test_channel_id)

        self.assertFalse(result)

    def test_migrate_channel_nonexistent_returns_false(self):
        """Test dat migreren van niet-bestaand kanaal False returnt."""
        empty_data = {"defaults": {}}

        mock_data = json.dumps(empty_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                result = migrate_channel_to_periods(99999999)

        self.assertFalse(result)

    def test_migrate_all_channels_success(self):
        """Test migratie van meerdere kanalen tegelijk."""
        multi_channel_data = {
            "defaults": {},
            "111111": {
                "__poll_options__": {
                    "vrijdag_19:00": True,
                    "zaterdag_19:00": True,
                    "zondag_19:00": True,
                }
            },
            "222222": {
                "__poll_options__": {
                    "maandag_19:00": True,
                    "dinsdag_19:00": True,
                }
            },
            "333333": {
                "__poll_options__": {},
                "__period_settings__": {
                    "vr-zo": {"enabled": True},
                    "ma-do": {"enabled": False}
                }
            }
        }

        mock_data = json.dumps(multi_channel_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump"):
                    stats = migrate_all_channels_to_periods()

        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["migrated"], 2)  # 111111 and 222222
        self.assertEqual(stats["already_migrated"], 1)  # 333333

    def test_migrate_all_channels_with_invalid_keys(self):
        """Test dat ongeldige channel IDs worden geskipt."""
        data_with_invalid = {
            "defaults": {},
            "123456": {"__poll_options__": {"vrijdag_19:00": True}},
            "invalid_key": {"__poll_options__": {}},
            "another_bad": {"__poll_options__": {}},
        }

        mock_data = json.dumps(data_with_invalid)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump"):
                    stats = migrate_all_channels_to_periods()

        # Only valid channel ID should be counted
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["migrated"], 1)

    def test_migrate_all_channels_empty_data(self):
        """Test migreren van lege dataset."""
        empty_data = {"defaults": {}}

        mock_data = json.dumps(empty_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                stats = migrate_all_channels_to_periods()

        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["migrated"], 0)
        self.assertEqual(stats["already_migrated"], 0)

    def test_migrate_preserves_other_settings(self):
        """Test dat andere settings behouden blijven na migratie."""
        old_data = {
            str(self.test_channel_id): {
                "__poll_options__": {
                    "vrijdag_19:00": True,
                    "zaterdag_19:00": True,
                },
                "__scheduled_activation__": {
                    "dag": "dinsdag",
                    "tijd": "20:00"
                },
                "__scheduled_deactivation__": {
                    "dag": "maandag",
                    "tijd": "00:00"
                },
                "__paused__": True,
                "__notification_states__": {
                    "some_state": True
                },
                "custom_setting": "some_value"
            }
        }

        mock_data = json.dumps(old_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump") as mock_dump:
                    result = migrate_channel_to_periods(self.test_channel_id)

        self.assertTrue(result)

        call_args = mock_dump.call_args[0][0]
        migrated_channel = call_args[str(self.test_channel_id)]

        # Check that other settings are preserved
        self.assertTrue(migrated_channel["__paused__"])
        self.assertEqual(migrated_channel["__notification_states__"], {"some_state": True})
        self.assertEqual(migrated_channel["custom_setting"], "some_value")

        # But old activation/deactivation should be gone
        self.assertNotIn("__scheduled_activation__", migrated_channel)
        self.assertNotIn("__scheduled_deactivation__", migrated_channel)


if __name__ == "__main__":
    import unittest
    unittest.main()
