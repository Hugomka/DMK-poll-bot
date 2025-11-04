import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytz

from apps import scheduler


class SchedulerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_load_poll_config_success(self):
        """Test _load_poll_config met geldig config bestand.
        Bewaart en herstelt globale waarden om testvervuiling te voorkomen.
        """
        # Save original values
        orig_reminder_hour = scheduler.REMINDER_HOUR
        orig_early_reminder_hour = scheduler.EARLY_REMINDER_HOUR
        orig_reset_day = scheduler.RESET_DAY_OF_WEEK
        orig_reset_hour = scheduler.RESET_HOUR
        orig_min_votes = scheduler.MIN_NOTIFY_VOTES
        orig_reminder_days = scheduler.REMINDER_DAYS.copy()
        orig_early_day = scheduler.EARLY_REMINDER_DAY
        orig_config_path = scheduler.CONFIG_PATH

        try:
            config_data = {
                "reminder_hour": 16,
                "early_reminder_hour": 19,
                "reset_day_of_week": 2,
                "reset_hour": 21,
                "min_notify_votes": 8,
                "reminder_days": {"vrijdag": 4, "zaterdag": 5},
                "early_reminder_day": "woensdag",
            }

            with tempfile.TemporaryDirectory() as tmpdir:
                config_file = os.path.join(tmpdir, "config.json")
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config_data, f)

                with patch.object(scheduler, "CONFIG_PATH", config_file):
                    scheduler._load_poll_config()

                # Controleer dat waarden zijn overschreven
                self.assertEqual(scheduler.REMINDER_HOUR, 16)
                self.assertEqual(scheduler.EARLY_REMINDER_HOUR, 19)
                self.assertEqual(scheduler.RESET_DAY_OF_WEEK, 2)
                self.assertEqual(scheduler.RESET_HOUR, 21)
                self.assertEqual(scheduler.MIN_NOTIFY_VOTES, 8)
                self.assertIn(4, scheduler.REMINDER_DAYS.values())
                self.assertEqual(scheduler.EARLY_REMINDER_DAY, "woensdag")
        finally:
            # Restore original values
            scheduler.REMINDER_HOUR = orig_reminder_hour
            scheduler.EARLY_REMINDER_HOUR = orig_early_reminder_hour
            scheduler.RESET_DAY_OF_WEEK = orig_reset_day
            scheduler.RESET_HOUR = orig_reset_hour
            scheduler.MIN_NOTIFY_VOTES = orig_min_votes
            scheduler.REMINDER_DAYS = orig_reminder_days
            scheduler.EARLY_REMINDER_DAY = orig_early_day
            scheduler.CONFIG_PATH = orig_config_path

    async def test_load_poll_config_missing_file(self):
        """Test _load_poll_config met ontbrekend bestand."""
        with patch.object(scheduler, "CONFIG_PATH", "/nope/does-not-exist.json"):
            # Mag niet crashen
            scheduler._load_poll_config()

    async def test_should_run_with_naive_datetime(self):
        """Test should_run met naive datetime (zonder timezone)."""
        occurrence = datetime(2024, 5, 27, 18, 0, 0)  # Naive
        last_run = datetime(2024, 5, 26, 18, 0, 0)  # Naive

        result = scheduler.should_run(last_run, occurrence)
        self.assertTrue(result)

    async def test_should_run_with_equal_timestamps(self):
        """Test should_run met gelijke timestamps."""
        tz = pytz.timezone("Europe/Amsterdam")
        occurrence = tz.localize(datetime(2024, 5, 27, 18, 0, 0))
        last_run = occurrence

        result = scheduler.should_run(last_run, occurrence)
        self.assertFalse(result)  # Gelijk → niet runnen

    async def test_weekly_reset_threshold_before_sunday_2030(self):
        """Test _weekly_reset_threshold voor zondag 20:30."""
        tz = pytz.timezone("Europe/Amsterdam")
        # Zondag 20:00 (voor 20:30)
        now = tz.localize(datetime(2024, 5, 26, 20, 0, 0))

        threshold = scheduler._weekly_reset_threshold(now)

        # Moet vorige week zondag 20:30 zijn
        self.assertEqual(threshold.weekday(), 6)  # Zondag
        self.assertEqual(threshold.hour, 20)
        self.assertEqual(threshold.minute, 30)
        self.assertTrue(threshold < now)

    async def test_weekly_reset_threshold_after_sunday_2030(self):
        """Test _weekly_reset_threshold na zondag 20:30."""
        tz = pytz.timezone("Europe/Amsterdam")
        # Zondag 21:00 (na 20:30)
        now = tz.localize(datetime(2024, 5, 26, 21, 0, 0))

        threshold = scheduler._weekly_reset_threshold(now)

        # Moet huidige week zondag 20:30 zijn
        self.assertEqual(threshold.weekday(), 6)  # Zondag
        self.assertEqual(threshold.hour, 20)
        self.assertEqual(threshold.minute, 30)
        self.assertTrue(threshold <= now)

    async def test_within_reset_window_inside(self):
        """Test _within_reset_window binnen het venster."""
        tz = pytz.timezone("Europe/Amsterdam")
        # RESET_DAY_OF_WEEK is 1 (dinsdag), RESET_HOUR is 20
        # Gebruik 14 oktober 2025 (dinsdag)
        now = tz.localize(datetime(2025, 10, 14, 20, 3, 0))
        # Verifieer dat dit een dinsdag is
        self.assertEqual(
            now.weekday(),
            1,
            f"14 mei 2024 moet een dinsdag zijn, maar is {now.weekday()}",
        )

        result = scheduler._within_reset_window(now)
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.weekday(), 1)
        self.assertEqual(now.hour, 20)
        self.assertEqual(now.minute, 3)
        self.assertTrue(result)

    async def test_within_reset_window_outside(self):
        """Test _within_reset_window buiten het venster."""
        tz = pytz.timezone("Europe/Amsterdam")
        # Dinsdag 20:10 (na 5 minuten)
        now = tz.localize(datetime(2024, 5, 28, 20, 10, 0))

        result = scheduler._within_reset_window(now)
        self.assertFalse(result)

    async def test_reset_polls_outside_window_returns_false(self):
        """Test reset_polls buiten het resetvenster."""

        class Bot:
            guilds = []

        bot = Bot()

        with patch.object(scheduler, "_within_reset_window", return_value=False):
            result = await scheduler.reset_polls(bot)

        self.assertFalse(result)

    async def test_reset_polls_already_reset_this_week(self):
        """Test reset_polls als er al is gereset deze week."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = tz.localize(datetime(2024, 5, 28, 20, 2, 0))  # Dinsdag 20:02

        # Last reset was afgelopen zondag 21:00 (na de threshold van 20:30)
        last_reset = tz.localize(datetime(2024, 5, 26, 21, 0, 0))

        state = {"reset_polls": last_reset.isoformat()}

        class Bot:
            guilds = []

        bot = Bot()

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "datetime") as mock_dt,
        ):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = await scheduler.reset_polls(bot)

        self.assertFalse(result)

    async def test_reset_polls_resets_all_channels_regardless_of_messages(self):
        """Test reset_polls reset alle kanalen, ook zonder berichten (werkt op data-niveau)."""

        class Channel:
            def __init__(self, id):
                self.id = id

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "reset_votes_scoped", new_callable=AsyncMock) as mock_rvs,
            patch.object(scheduler, "clear_message_id", side_effect=lambda *args: None),
            patch.object(scheduler, "send_temporary_mention", new_callable=AsyncMock),
        ):
            result = await scheduler.reset_polls(bot)

        self.assertTrue(result)
        # Controleer dat reset_votes_scoped werd aangeroepen voor het kanaal
        mock_rvs.assert_awaited_once_with(1, 10)

    async def test_load_poll_config_corrupt_json(self):
        """Test _load_poll_config met corrupt JSON bestand."""
        # Save original values
        orig_reminder_hour = scheduler.REMINDER_HOUR
        orig_config_path = scheduler.CONFIG_PATH

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                config_file = os.path.join(tmpdir, "corrupt.json")
                # Schrijf corrupt JSON
                with open(config_file, "w", encoding="utf-8") as f:
                    f.write("{ this is not valid json }")

                with patch.object(scheduler, "CONFIG_PATH", config_file):
                    # Mag niet crashen
                    scheduler._load_poll_config()

                # Assert: Waarden ongewijzigd (defaults blijven staan)
                self.assertEqual(scheduler.REMINDER_HOUR, orig_reminder_hour)
        finally:
            # Restore original values
            scheduler.REMINDER_HOUR = orig_reminder_hour
            scheduler.CONFIG_PATH = orig_config_path

    async def test_load_poll_config_reminder_days_not_dict(self):
        """Test _load_poll_config met reminder_days als niet-dict."""
        # Save original values
        orig_reminder_days = scheduler.REMINDER_DAYS.copy()
        orig_config_path = scheduler.CONFIG_PATH

        try:
            config_data = {
                "reminder_hour": 17,
                "reminder_days": ["not", "a", "dict"],  # Array i.p.v. dict
            }

            with tempfile.TemporaryDirectory() as tmpdir:
                config_file = os.path.join(tmpdir, "config.json")
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config_data, f)

                with patch.object(scheduler, "CONFIG_PATH", config_file):
                    scheduler._load_poll_config()

                # Assert: reminder_hour WEL overschreven (17)
                self.assertEqual(scheduler.REMINDER_HOUR, 17)
                # Assert: REMINDER_DAYS ongewijzigd (niet geupdatet met array)
                # De originele waarden moeten nog steeds aanwezig zijn
                for dag in orig_reminder_days:
                    self.assertIn(dag, scheduler.REMINDER_DAYS)
        finally:
            # Restore original values
            scheduler.REMINDER_DAYS = orig_reminder_days
            scheduler.CONFIG_PATH = orig_config_path
