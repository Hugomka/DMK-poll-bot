# tests/test_scheduler_reset_window.py
from datetime import datetime
from unittest.mock import patch

import pytz

from apps import scheduler
from tests.base import BaseTestCase

TZ = pytz.timezone("Europe/Amsterdam")


class ResetWindowTestCase(BaseTestCase):
    def test__within_reset_window_true_at_exact_time(self):
        with patch.object(scheduler, "RESET_DAY_OF_WEEK", 1), patch.object(
            scheduler, "RESET_HOUR", 20
        ):
            now = TZ.localize(datetime(2024, 5, 28, 20, 0, 30))  # di 20:00:30
            self.assertTrue(scheduler._within_reset_window(now, minutes=5))

    def test__within_reset_window_false_outside_minute_window(self):
        with patch.object(scheduler, "RESET_DAY_OF_WEEK", 1), patch.object(
            scheduler, "RESET_HOUR", 20
        ):
            now = TZ.localize(datetime(2024, 5, 28, 20, 6, 0))  # di 20:06
            self.assertFalse(scheduler._within_reset_window(now, minutes=5))

    def test__within_reset_window_naive_datetime_is_localized(self):
        with patch.object(scheduler, "RESET_DAY_OF_WEEK", 1), patch.object(
            scheduler, "RESET_HOUR", 20
        ):
            naive = datetime(2024, 5, 28, 20, 3, 0)
            self.assertTrue(scheduler._within_reset_window(naive, minutes=5))

    def test_should_run_varianten(self):
        occurrence = TZ.localize(datetime(2024, 6, 4, 20, 0, 0))  # di 20:00
        self.assertTrue(scheduler.should_run(None, occurrence), "None → moet runnen")
        self.assertTrue(
            scheduler.should_run(
                TZ.localize(datetime(2024, 6, 3, 12, 0, 0)), occurrence
            ),
            "Oudere last_run → moet runnen",
        )
        self.assertFalse(
            scheduler.should_run(
                TZ.localize(datetime(2024, 6, 4, 20, 0, 0)), occurrence
            ),
            "Gelijke timestamp → niet runnen",
        )
        self.assertFalse(
            scheduler.should_run(
                TZ.localize(datetime(2024, 6, 4, 21, 0, 0)), occurrence
            ),
            "Recenter last_run → niet runnen",
        )
