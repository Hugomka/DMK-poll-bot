# tests/test_period_settings_functions.py
"""Tests voor nieuwe period-based settings functies."""

import json
from datetime import datetime
from unittest.mock import patch, mock_open
from zoneinfo import ZoneInfo

from apps.utils.poll_settings import (
    get_period_settings,
    set_period_settings,
    get_enabled_periods,
    get_enabled_period_days,
    is_period_currently_open,
)
from tests.base import BaseTestCase

AMS = ZoneInfo("Europe/Amsterdam")


class TestPeriodSettingsFunctions(BaseTestCase):
    """Test de nieuwe period settings functies."""

    def setUp(self):
        """Setup voor elke test."""
        super().setUp()
        self.test_channel_id = 123456789

    def test_get_period_settings_vr_zo_defaults(self):
        """Test dat vr-zo default settings correct zijn."""
        empty_data = {"defaults": {}}

        mock_data = json.dumps(empty_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                settings = get_period_settings(self.test_channel_id, "vr-zo")

        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["close_day"], "maandag")
        self.assertEqual(settings["close_time"], "00:00")
        self.assertEqual(settings["open_day"], "dinsdag")
        self.assertEqual(settings["open_time"], "20:00")

    def test_get_period_settings_ma_do_defaults(self):
        """Test dat ma-do default settings correct zijn."""
        empty_data = {"defaults": {}}

        mock_data = json.dumps(empty_data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                settings = get_period_settings(self.test_channel_id, "ma-do")

        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["close_day"], "vrijdag")
        self.assertEqual(settings["close_time"], "00:00")
        self.assertEqual(settings["open_day"], "vrijdag")
        self.assertEqual(settings["open_time"], "20:00")

    def test_get_period_settings_custom_values(self):
        """Test dat custom period settings correct worden opgehaald."""
        data_with_custom = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {
                        "enabled": False,
                        "close_day": "dinsdag",
                        "close_time": "08:00",
                        "open_day": "woensdag",
                        "open_time": "18:00",
                    }
                }
            }
        }

        mock_data = json.dumps(data_with_custom)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                settings = get_period_settings(self.test_channel_id, "vr-zo")

        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["close_day"], "dinsdag")
        self.assertEqual(settings["close_time"], "08:00")
        self.assertEqual(settings["open_day"], "woensdag")
        self.assertEqual(settings["open_time"], "18:00")

    def test_get_period_settings_invalid_period_raises_error(self):
        """Test dat ongeldige periode een ValueError geeft."""
        with self.assertRaises(ValueError) as context:
            get_period_settings(self.test_channel_id, "invalid-period")

        self.assertIn("Ongeldige periode", str(context.exception))

    def test_set_period_settings_enable_period(self):
        """Test dat een periode enabled kan worden."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {
                        "enabled": False,
                        "close_day": "maandag",
                        "close_time": "00:00",
                        "open_day": "dinsdag",
                        "open_time": "20:00",
                    }
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump") as _mock_dump:
                    result = set_period_settings(
                        self.test_channel_id,
                        "vr-zo",
                        enabled=True
                    )

        self.assertTrue(result["enabled"])
        # Verify it was saved
        call_args = _mock_dump.call_args[0][0]
        self.assertTrue(call_args[str(self.test_channel_id)]["__period_settings__"]["vr-zo"]["enabled"])

    def test_set_period_settings_change_times(self):
        """Test dat open/close tijden gewijzigd kunnen worden."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {
                        "enabled": True,
                        "close_day": "maandag",
                        "close_time": "00:00",
                        "open_day": "dinsdag",
                        "open_time": "20:00",
                    }
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with patch("json.dump"):
                    result = set_period_settings(
                        self.test_channel_id,
                        "vr-zo",
                        close_day="woensdag",
                        close_time="08:00",
                        open_day="donderdag",
                        open_time="19:00"
                    )

        self.assertEqual(result["close_day"], "woensdag")
        self.assertEqual(result["close_time"], "08:00")
        self.assertEqual(result["open_day"], "donderdag")
        self.assertEqual(result["open_time"], "19:00")

    def test_set_period_settings_validation_close_before_open(self):
        """Test dat validatie faalt als close >= open op dezelfde dag."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {
                        "enabled": True,
                        "close_day": "maandag",
                        "close_time": "00:00",
                        "open_day": "maandag",
                        "open_time": "20:00",
                    }
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                with self.assertRaises(ValueError) as context:
                    set_period_settings(
                        self.test_channel_id,
                        "vr-zo",
                        close_time="21:00"  # 21:00 is na 20:00
                    )

        # Check that validation error is raised
        self.assertIn("moet vóór openingstijd", str(context.exception))

    def test_set_period_settings_validation_same_time_fails(self):
        """Test dat sluitings- en openingstijd niet gelijk kunnen zijn op dezelfde dag."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {
                        "enabled": True,
                        "close_day": "maandag",
                        "close_time": "20:00",
                        "open_day": "maandag",
                        "open_time": "20:00",
                    }
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                # Current settings already invalid, try to change something
                with self.assertRaises(ValueError):
                    set_period_settings(
                        self.test_channel_id,
                        "vr-zo",
                        enabled=True  # No change, should still validate
                    )

    def test_get_enabled_periods_both_enabled(self):
        """Test dat beide enabled periodes worden geretourneerd."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": True},
                    "ma-do": {"enabled": True}
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                enabled = get_enabled_periods(self.test_channel_id)

        self.assertEqual(enabled, ["vr-zo", "ma-do"])

    def test_get_enabled_periods_only_vr_zo(self):
        """Test dat alleen vr-zo wordt geretourneerd als alleen die enabled is."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": True},
                    "ma-do": {"enabled": False}
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                enabled = get_enabled_periods(self.test_channel_id)

        self.assertEqual(enabled, ["vr-zo"])

    def test_get_enabled_periods_only_ma_do(self):
        """Test dat alleen ma-do wordt geretourneerd als alleen die enabled is."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": False},
                    "ma-do": {"enabled": True}
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                enabled = get_enabled_periods(self.test_channel_id)

        self.assertEqual(enabled, ["ma-do"])

    def test_get_enabled_periods_none_enabled(self):
        """Test dat lege lijst wordt geretourneerd als geen enkele periode enabled is."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": False},
                    "ma-do": {"enabled": False}
                }
            }
        }

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                enabled = get_enabled_periods(self.test_channel_id)

        self.assertEqual(enabled, [])

    def test_get_enabled_period_days_vr_zo_only(self):
        """Test dat alleen vr-zo dagen worden geretourneerd."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": True, "open_day": "dinsdag", "open_time": "20:00", "close_day": "maandag", "close_time": "00:00"},
                    "ma-do": {"enabled": False, "open_day": "vrijdag", "open_time": "20:00", "close_day": "vrijdag", "close_time": "00:00"}
                },
                "__poll_options__": {
                    "vrijdag_19:00": True,
                    "vrijdag_20:30": True,
                    "zaterdag_19:00": True,
                    "zaterdag_20:30": True,
                    "zondag_19:00": True,
                    "zondag_20:30": True,
                }
            }
        }

        # Test op woensdag 7 januari 2026 (binnen vr-zo open-venster: di 20:00 - ma 00:00)
        reference_date = datetime(2026, 1, 7, 12, 0, 0, tzinfo=AMS)

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                days = get_enabled_period_days(self.test_channel_id, reference_date)

        # Should return vr-zo days (9-11 januari)
        self.assertEqual(len(days), 3)
        dag_namen = [d["dag"] for d in days]
        self.assertIn("vrijdag", dag_namen)
        self.assertIn("zaterdag", dag_namen)
        self.assertIn("zondag", dag_namen)

        # Check dates
        vr_day = next(d for d in days if d["dag"] == "vrijdag")
        self.assertEqual(vr_day["datum_iso"], "2026-01-09")

    def test_get_enabled_period_days_ma_do_only(self):
        """Test dat alleen ma-do dagen worden geretourneerd."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": False, "open_day": "dinsdag", "open_time": "20:00", "close_day": "maandag", "close_time": "00:00"},
                    "ma-do": {"enabled": True, "open_day": "vrijdag", "open_time": "20:00", "close_day": "vrijdag", "close_time": "00:00"}
                },
                "__poll_options__": {
                    "maandag_19:00": True,
                    "maandag_20:30": True,
                    "dinsdag_19:00": True,
                    "dinsdag_20:30": True,
                    "woensdag_19:00": True,
                    "woensdag_20:30": True,
                    "donderdag_19:00": True,
                    "donderdag_20:30": True,
                }
            }
        }

        # Test op maandag 5 januari 2026 (binnen ma-do open-venster: vr 20:00 - vr 00:00)
        reference_date = datetime(2026, 1, 5, 12, 0, 0, tzinfo=AMS)

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                days = get_enabled_period_days(self.test_channel_id, reference_date)

        # Should return ma-do days (5-8 januari - THIS week)
        self.assertEqual(len(days), 4)
        dag_namen = [d["dag"] for d in days]
        self.assertIn("maandag", dag_namen)
        self.assertIn("dinsdag", dag_namen)
        self.assertIn("woensdag", dag_namen)
        self.assertIn("donderdag", dag_namen)

        # Check dates
        ma_day = next(d for d in days if d["dag"] == "maandag")
        self.assertEqual(ma_day["datum_iso"], "2026-01-05")

    def test_get_enabled_period_days_both_periods(self):
        """Test dat beide periodes' dagen worden geretourneerd."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": True, "open_day": "dinsdag", "open_time": "20:00", "close_day": "maandag", "close_time": "00:00"},
                    "ma-do": {"enabled": True, "open_day": "vrijdag", "open_time": "20:00", "close_day": "vrijdag", "close_time": "00:00"}
                },
                "__poll_options__": {
                    "maandag_19:00": True,
                    "maandag_20:30": True,
                    "dinsdag_19:00": True,
                    "dinsdag_20:30": True,
                    "woensdag_19:00": True,
                    "woensdag_20:30": True,
                    "donderdag_19:00": True,
                    "donderdag_20:30": True,
                    "vrijdag_19:00": True,
                    "vrijdag_20:30": True,
                    "zaterdag_19:00": True,
                    "zaterdag_20:30": True,
                    "zondag_19:00": True,
                    "zondag_20:30": True,
                }
            }
        }

        # Woensdag 7 jan 2026: beide periodes open (vr-zo sinds di 20:00, ma-do sinds vr 20:00)
        reference_date = datetime(2026, 1, 7, 12, 0, 0, tzinfo=AMS)

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                days = get_enabled_period_days(self.test_channel_id, reference_date)

        # Should return all 7 days
        self.assertEqual(len(days), 7)

    def test_get_enabled_period_days_skips_disabled_days(self):
        """Test dat disabled dagen binnen een periode worden geskipt."""
        data = {
            str(self.test_channel_id): {
                "__period_settings__": {
                    "vr-zo": {"enabled": True, "open_day": "dinsdag", "open_time": "20:00", "close_day": "maandag", "close_time": "00:00"},
                    "ma-do": {"enabled": False, "open_day": "vrijdag", "open_time": "20:00", "close_day": "vrijdag", "close_time": "00:00"}
                },
                "__poll_options__": {
                    "vrijdag_19:00": True,
                    "vrijdag_20:30": True,
                    "zaterdag_19:00": False,  # Beide tijden disabled
                    "zaterdag_20:30": False,
                    "zondag_19:00": True,
                    "zondag_20:30": True,
                }
            }
        }

        # Woensdag 7 jan 2026 (binnen vr-zo open-venster)
        reference_date = datetime(2026, 1, 7, 12, 0, 0, tzinfo=AMS)

        mock_data = json.dumps(data)
        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                days = get_enabled_period_days(self.test_channel_id, reference_date)

        # Should return only vrijdag and zondag (zaterdag is completely disabled)
        self.assertEqual(len(days), 2)
        dag_namen = [d["dag"] for d in days]
        self.assertIn("vrijdag", dag_namen)
        self.assertIn("zondag", dag_namen)
        self.assertNotIn("zaterdag", dag_namen)


class TestIsPeriodCurrentlyOpen(BaseTestCase):
    """Test is_period_currently_open met default vr-zo en ma-do instellingen."""

    def setUp(self):
        super().setUp()
        # Default vr-zo: open dinsdag 20:00, close maandag 00:00
        self.vr_zo = {
            "enabled": True,
            "open_day": "dinsdag",
            "open_time": "20:00",
            "close_day": "maandag",
            "close_time": "00:00",
        }
        # Default ma-do: open vrijdag 20:00, close vrijdag 00:00
        self.ma_do = {
            "enabled": True,
            "open_day": "vrijdag",
            "open_time": "20:00",
            "close_day": "vrijdag",
            "close_time": "00:00",
        }

    def test_dinsdag_1800_vr_zo_gesloten(self):
        """Dinsdag 18:00: vr-zo nog niet open (opent pas 20:00)."""
        now = datetime(2026, 1, 6, 18, 0, tzinfo=AMS)  # Dinsdag
        self.assertFalse(is_period_currently_open(self.vr_zo, now))

    def test_dinsdag_1800_ma_do_open(self):
        """Dinsdag 18:00: ma-do is open (opende vrijdag 20:00)."""
        now = datetime(2026, 1, 6, 18, 0, tzinfo=AMS)  # Dinsdag
        self.assertTrue(is_period_currently_open(self.ma_do, now))

    def test_dinsdag_2100_beide_open(self):
        """Dinsdag 21:00: beide periodes open."""
        now = datetime(2026, 1, 6, 21, 0, tzinfo=AMS)  # Dinsdag
        self.assertTrue(is_period_currently_open(self.vr_zo, now))
        self.assertTrue(is_period_currently_open(self.ma_do, now))

    def test_vrijdag_1200_vr_zo_open_ma_do_gesloten(self):
        """Vrijdag 12:00: vr-zo open, ma-do gesloten (sloot vrijdag 00:00)."""
        now = datetime(2026, 1, 9, 12, 0, tzinfo=AMS)  # Vrijdag
        self.assertTrue(is_period_currently_open(self.vr_zo, now))
        self.assertFalse(is_period_currently_open(self.ma_do, now))

    def test_vrijdag_2100_beide_open(self):
        """Vrijdag 21:00: beide periodes open (ma-do opende 20:00)."""
        now = datetime(2026, 1, 9, 21, 0, tzinfo=AMS)  # Vrijdag
        self.assertTrue(is_period_currently_open(self.vr_zo, now))
        self.assertTrue(is_period_currently_open(self.ma_do, now))

    def test_maandag_0100_ma_do_open_vr_zo_gesloten(self):
        """Maandag 01:00: ma-do open, vr-zo gesloten (sloot maandag 00:00)."""
        now = datetime(2026, 1, 5, 1, 0, tzinfo=AMS)  # Maandag
        self.assertFalse(is_period_currently_open(self.vr_zo, now))
        self.assertTrue(is_period_currently_open(self.ma_do, now))

    def test_zaterdag_1800_beide_open(self):
        """Zaterdag 18:00: beide open (vr-zo sinds di 20:00, ma-do sinds vr 20:00)."""
        now = datetime(2026, 1, 10, 18, 0, tzinfo=AMS)  # Zaterdag
        self.assertTrue(is_period_currently_open(self.vr_zo, now))
        self.assertTrue(is_period_currently_open(self.ma_do, now))

    def test_maandag_0000_exact_close_vr_zo(self):
        """Maandag 00:00 exact: vr-zo net gesloten."""
        now = datetime(2026, 1, 5, 0, 0, tzinfo=AMS)  # Maandag 00:00
        self.assertFalse(is_period_currently_open(self.vr_zo, now))

    def test_vrijdag_0000_exact_close_ma_do(self):
        """Vrijdag 00:00 exact: ma-do net gesloten."""
        now = datetime(2026, 1, 9, 0, 0, tzinfo=AMS)  # Vrijdag 00:00
        self.assertFalse(is_period_currently_open(self.ma_do, now))

    def test_dinsdag_2000_exact_open_vr_zo(self):
        """Dinsdag 20:00 exact: vr-zo opent nu."""
        now = datetime(2026, 1, 6, 20, 0, tzinfo=AMS)  # Dinsdag 20:00
        self.assertTrue(is_period_currently_open(self.vr_zo, now))

    def test_vrijdag_2000_exact_open_ma_do(self):
        """Vrijdag 20:00 exact: ma-do opent nu."""
        now = datetime(2026, 1, 9, 20, 0, tzinfo=AMS)  # Vrijdag 20:00
        self.assertTrue(is_period_currently_open(self.ma_do, now))

    def test_ongeldige_dag_returns_false(self):
        """Ongeldige dag in settings retourneert False."""
        bad_settings = {"open_day": "foobar", "open_time": "20:00",
                        "close_day": "maandag", "close_time": "00:00"}
        now = datetime(2026, 1, 7, 12, 0, tzinfo=AMS)
        self.assertFalse(is_period_currently_open(bad_settings, now))


if __name__ == "__main__":
    import unittest
    unittest.main()
