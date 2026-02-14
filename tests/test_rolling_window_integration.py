# tests/test_rolling_window_integration.py
"""Integratie tests voor period-based system met dmk-poll-on command."""

from datetime import datetime
from zoneinfo import ZoneInfo

from apps.utils.poll_settings import get_enabled_period_days
from tests.base import BaseTestCase


class TestPeriodSystemIntegration(BaseTestCase):
    """Test period-based system integratie met dmk-poll-on."""

    def test_period_system_returns_correct_days_for_vr_zo_period(self):
        """Test dat period system correcte dagen retourneert voor vr-zo periode."""
        # Woensdag 3 december 2025, 07:15 (binnen vr-zo open-venster: di 20:00 - ma 00:00)
        tuesday = datetime(2025, 12, 3, 7, 15, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        channel_id = 12345

        # Setup: Enable vr-zo period with all days
        from apps.utils.poll_settings import set_poll_option_state, set_period_settings

        for dag in ["vrijdag", "zaterdag", "zondag"]:
            set_poll_option_state(channel_id, dag, "om 19:00 uur", True)
            set_poll_option_state(channel_id, dag, "om 20:30 uur", True)

        # Enable vr-zo period (default enabled)
        set_period_settings(channel_id, "vr-zo", enabled=True)
        set_period_settings(channel_id, "ma-do", enabled=False)

        # Get enabled days
        dagen_info = get_enabled_period_days(channel_id, reference_date=tuesday)

        # Should return 3 days (vr, za, zo) from this week
        self.assertEqual(len(dagen_info), 3)

        dag_namen = [d["dag"] for d in dagen_info]
        self.assertIn("vrijdag", dag_namen)
        self.assertIn("zaterdag", dag_namen)
        self.assertIn("zondag", dag_namen)

        # Check dates are from this week (Nov 30 - Dec 2, week starting Nov 30)
        # ISO week 48: Nov 30 - Dec 6, Monday = Nov 30
        vrijdag = next(d for d in dagen_info if d["dag"] == "vrijdag")
        self.assertEqual(vrijdag["datum_iso"], "2025-12-05")  # Friday of this ISO week

    def test_period_system_returns_correct_days_for_ma_do_period(self):
        """Test dat period system correcte dagen retourneert voor ma-do periode."""
        # Dinsdag 2 december 2025
        tuesday = datetime(2025, 12, 2, 7, 15, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        channel_id = 12345

        # Setup: Enable ma-do period with all days
        from apps.utils.poll_settings import set_poll_option_state, set_period_settings

        for dag in ["maandag", "dinsdag", "woensdag", "donderdag"]:
            set_poll_option_state(channel_id, dag, "om 19:00 uur", True)
            set_poll_option_state(channel_id, dag, "om 20:30 uur", True)

        # Enable ma-do period
        set_period_settings(channel_id, "vr-zo", enabled=False)
        set_period_settings(channel_id, "ma-do", enabled=True)

        # Get enabled days
        dagen_info = get_enabled_period_days(channel_id, reference_date=tuesday)

        # Should return 4 days (ma, di, wo, do) from this week (since we're on Tuesday)
        self.assertEqual(len(dagen_info), 4)

        dag_namen = [d["dag"] for d in dagen_info]
        self.assertIn("maandag", dag_namen)
        self.assertIn("dinsdag", dag_namen)
        self.assertIn("woensdag", dag_namen)
        self.assertIn("donderdag", dag_namen)

    def test_period_system_with_both_periods_enabled(self):
        """Test dat beide periodes tegelijk kunnen werken."""
        # Woensdag: beide periodes open (vr-zo sinds di 20:00, ma-do sinds vr 20:00)
        tuesday = datetime(2025, 12, 3, 7, 15, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        channel_id = 12345

        # Setup: Enable both periods with all days
        from apps.utils.poll_settings import set_poll_option_state, set_period_settings

        for dag in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]:
            set_poll_option_state(channel_id, dag, "om 19:00 uur", True)
            set_poll_option_state(channel_id, dag, "om 20:30 uur", True)

        # Enable both periods
        set_period_settings(channel_id, "vr-zo", enabled=True)
        set_period_settings(channel_id, "ma-do", enabled=True)

        # Get enabled days
        dagen_info = get_enabled_period_days(channel_id, reference_date=tuesday)

        # Should return all 7 days
        self.assertEqual(len(dagen_info), 7)

    def test_period_system_skips_disabled_days(self):
        """Test dat disabled dagen binnen een periode worden geskipt."""
        # Woensdag: binnen vr-zo open-venster
        tuesday = datetime(2025, 12, 3, 7, 15, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        channel_id = 12345

        # Setup: Enable vr-zo period but disable zaterdag
        from apps.utils.poll_settings import set_poll_option_state, set_period_settings

        set_poll_option_state(channel_id, "vrijdag", "om 19:00 uur", True)
        set_poll_option_state(channel_id, "vrijdag", "om 20:30 uur", True)
        set_poll_option_state(channel_id, "zaterdag", "om 19:00 uur", False)
        set_poll_option_state(channel_id, "zaterdag", "om 20:30 uur", False)
        set_poll_option_state(channel_id, "zondag", "om 19:00 uur", True)
        set_poll_option_state(channel_id, "zondag", "om 20:30 uur", True)

        set_period_settings(channel_id, "vr-zo", enabled=True)
        set_period_settings(channel_id, "ma-do", enabled=False)

        # Get enabled days
        dagen_info = get_enabled_period_days(channel_id, reference_date=tuesday)

        # Should return only vrijdag and zondag (zaterdag is disabled)
        self.assertEqual(len(dagen_info), 2)

        dag_namen = [d["dag"] for d in dagen_info]
        self.assertIn("vrijdag", dag_namen)
        self.assertIn("zondag", dag_namen)
        self.assertNotIn("zaterdag", dag_namen)


if __name__ == "__main__":
    import unittest
    unittest.main()
