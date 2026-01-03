# tests/test_scheduler_catchup.py

import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytz

from apps import scheduler

TZ = pytz.timezone("Europe/Amsterdam")


class _FakeDateTime(datetime):
    _fixed_now = None

    @classmethod
    def set_now(cls, dt):
        cls._fixed_now = dt

    @classmethod
    def now(cls, tz=None):
        return cls._fixed_now if cls._fixed_now is not None else datetime.now(tz)

    @classmethod
    def fromisoformat(cls, s):
        d = datetime.fromisoformat(s)
        return cls(
            d.year, d.month, d.day, d.hour, d.minute, d.second, d.microsecond, d.tzinfo
        )

    @classmethod
    def combine(cls, date, time, tzinfo=None):
        d = datetime.combine(date, time, tzinfo=tzinfo)
        return cls(
            d.year, d.month, d.day, d.hour, d.minute, d.second, d.microsecond, d.tzinfo
        )


class SchedulerCatchupTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests voor catch-up en lock mechanismen."""

    async def test_catchup_always_executes_daily_update_for_cleanup(self):
        """Test dat dagelijkse update ALTIJD wordt uitgevoerd bij startup voor cleanup."""
        # Zet tijd op vandaag 10:00 (voor 18:00 deadline)
        # Met recente state (na gisteren 18:00) zodat should_run False is
        now = TZ.localize(datetime(2024, 5, 27, 10, 0, 0))
        last_update = TZ.localize(datetime(2024, 5, 26, 18, 5, 0))  # gisteren na 18:00
        state = {"update_all_polls": last_update.isoformat()}

        class Bot:
            guilds = []

        bot = Bot()

        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state") as mock_write,
            patch.object(
                scheduler, "update_all_polls", new_callable=AsyncMock
            ) as mock_update,
            patch.object(scheduler, "log_job") as mock_log_job,
            patch.object(scheduler, "log_startup"),
        ):

            await scheduler._run_catch_up(bot)

        # Assert: update_all_polls is ALTIJD aangeroepen (zelfs als should_run False is)
        mock_update.assert_awaited_once_with(bot)
        # Assert: log_job is aangeroepen met executed_startup_cleanup (niet gemiste deadline)
        mock_log_job.assert_any_call("update_all_polls", status="executed_startup_cleanup")
        # Assert: state is geschreven
        mock_write.assert_called_once()

    async def test_catchup_executes_daily_update(self):
        """Test dat dagelijkse update wordt uitgevoerd na 18:00."""
        # Zet tijd op vandaag 19:00 (na 18:00)
        now = TZ.localize(datetime(2024, 5, 27, 19, 0, 0))

        class Bot:
            guilds = []

        bot = Bot()

        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state") as mock_write,
            patch.object(
                scheduler, "update_all_polls", new_callable=AsyncMock
            ) as mock_update,
            patch.object(scheduler, "log_job") as mock_log_job,
            patch.object(scheduler, "log_startup"),
        ):

            await scheduler._run_catch_up(bot)

        # Assert: update_all_polls is ALTIJD aangeroepen (voor cleanup oude berichten)
        mock_update.assert_awaited_once_with(bot)
        # Assert: log_job is aangeroepen met executed (gemiste deadline)
        mock_log_job.assert_any_call("update_all_polls", status="executed")
        # Assert: state is geschreven
        mock_write.assert_called_once()

    async def test_catchup_update_after_week_offline(self):
        """Test dat oude poll-berichten worden opgeruimd na week offline."""
        # Bot was offline van 1 mei (dinsdag) tot 8 mei (volgende dinsdag)
        # Laatste update was 30 april (maandag) om 18:00
        # Nu is het 8 mei (dinsdag) om 10:00
        now = TZ.localize(datetime(2024, 5, 8, 10, 0, 0))
        last_update = TZ.localize(datetime(2024, 4, 30, 18, 0, 0))
        state = {"update_all_polls": last_update.isoformat()}

        class Bot:
            guilds = []

        bot = Bot()

        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state") as mock_write,
            patch.object(
                scheduler, "update_all_polls", new_callable=AsyncMock
            ) as mock_update,
            patch.object(scheduler, "log_job"),
            patch.object(scheduler, "log_startup") as mock_log_startup,
        ):

            await scheduler._run_catch_up(bot)

        # Assert: update_all_polls is ALTIJD aangeroepen (oude berichten cleanup)
        mock_update.assert_awaited_once_with(bot)
        # Assert: update_all_polls is in missed list (gemiste deadline)
        startup_call = mock_log_startup.call_args[0][0]
        self.assertIn("update_all_polls", startup_call)
        # Assert: state is bijgewerkt
        call_args = mock_write.call_args[0][0]
        self.assertIn("update_all_polls", call_args)

    async def test_catchup_executes_reset(self):
        """Test dat reset wordt uitgevoerd op dinsdag 20:01."""
        # Dinsdag 20:01
        now = TZ.localize(datetime(2024, 5, 28, 20, 1, 0))

        class Bot:
            guilds = []

        bot = Bot()

        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state") as mock_write,
            patch.object(scheduler, "update_all_polls", new_callable=AsyncMock),
            patch.object(
                scheduler, "reset_polls", new_callable=AsyncMock, return_value=True
            ) as mock_reset,
            patch.object(scheduler, "log_job"),
            patch.object(scheduler, "log_startup") as mock_log_startup,
        ):

            await scheduler._run_catch_up(bot)

        # Assert: reset_polls is aangeroepen
        mock_reset.assert_awaited_once_with(bot)
        # Assert: state bevat reset_polls
        call_args = mock_write.call_args[0][0]
        self.assertIn("reset_polls", call_args)
        # Assert: log_startup bevat reset_polls
        startup_call = mock_log_startup.call_args[0][0]
        self.assertIn("reset_polls", startup_call)

    async def test_catchup_skips_reset_when_should_run_false(self):
        """Test dat reset wordt geskipt als should_run False is."""
        now = TZ.localize(datetime(2024, 5, 28, 20, 1, 0))  # Dinsdag 20:01
        # State met recente reset
        recent_reset = TZ.localize(datetime(2024, 5, 28, 20, 0, 0))
        state = {"reset_polls": recent_reset.isoformat()}

        class Bot:
            guilds = []

        bot = Bot()

        # Patch de datetime module op scheduler niveau (niet builtin datetime)
        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state"),
            patch.object(scheduler, "update_all_polls", new_callable=AsyncMock),
            patch.object(
                scheduler, "reset_polls", new_callable=AsyncMock
            ) as mock_reset,
            patch.object(scheduler, "log_job") as mock_log_job,
            patch.object(scheduler, "log_startup"),
        ):

            await scheduler._run_catch_up(bot)

        # Assert: reset_polls NIET aangeroepen
        mock_reset.assert_not_awaited()
        # Assert: log_job met skipped
        mock_log_job.assert_any_call("reset_polls", status="skipped")

    async def test_catchup_executes_notify_vrijdag(self):
        """Test dat notify voor vrijdag wordt uitgevoerd na 18:05."""
        # Vrijdag 18:06
        now = TZ.localize(datetime(2024, 5, 31, 18, 6, 0))

        class Bot:
            guilds = []

        bot = Bot()

        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state") as mock_write,
            patch.object(scheduler, "update_all_polls", new_callable=AsyncMock),
            patch.object(
                scheduler,
                "notify_voters_if_avond_gaat_door",
                new_callable=AsyncMock,
            ) as mock_notify,
            patch.object(scheduler, "log_job"),
            patch.object(scheduler, "log_startup") as mock_log_startup,
        ):

            await scheduler._run_catch_up(bot)

        # Assert: notify_voters_if_avond_gaat_door aangeroepen voor vrijdag
        mock_notify.assert_any_await(bot, "vrijdag")
        # Assert: state key notify_vrijdag gezet
        call_args = mock_write.call_args[0][0]
        self.assertIn("notify_vrijdag", call_args)
        # Assert: log_startup bevat notify_vrijdag
        startup_call = mock_log_startup.call_args[0][0]
        self.assertIn("notify_vrijdag", startup_call)

    async def test_catchup_executes_reminder_vrijdag(self):
        """Test dat reminder voor vrijdag wordt uitgevoerd na 17:00."""
        # Vrijdag 17:05
        now = TZ.localize(datetime(2024, 5, 31, 17, 5, 0))

        class Bot:
            guilds = []

        bot = Bot()

        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state") as mock_write,
            patch.object(scheduler, "update_all_polls", new_callable=AsyncMock),
            patch.object(
                scheduler, "notify_non_voters", new_callable=AsyncMock
            ) as mock_reminder,
            patch.object(scheduler, "log_job"),
            patch.object(scheduler, "log_startup") as mock_log_startup,
        ):

            await scheduler._run_catch_up(bot)

        # Assert: notify_non_voters aangeroepen voor vrijdag
        mock_reminder.assert_any_await(bot, "vrijdag")
        # Assert: state key reminder_vrijdag gezet
        call_args = mock_write.call_args[0][0]
        self.assertIn("reminder_vrijdag", call_args)
        # Assert: log_startup bevat reminder_vrijdag
        startup_call = mock_log_startup.call_args[0][0]
        self.assertIn("reminder_vrijdag", startup_call)

    async def test_catchup_executes_thursday_reminder(self):
        """Test dat donderdag-reminder wordt uitgevoerd na 20:00."""
        # Donderdag 20:05
        now = TZ.localize(datetime(2024, 5, 30, 20, 5, 0))

        class Bot:
            guilds = []

        bot = Bot()

        _FakeDateTime.set_now(now)
        with (
            patch.object(scheduler, "datetime", _FakeDateTime),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state") as mock_write,
            patch.object(scheduler, "update_all_polls", new_callable=AsyncMock),
            patch.object(
                scheduler, "notify_non_voters_thursday", new_callable=AsyncMock
            ) as mock_thu,
            patch.object(scheduler, "log_job"),
            patch.object(scheduler, "log_startup") as mock_log_startup,
        ):

            await scheduler._run_catch_up(bot)

        # Assert: notify_non_voters_thursday aangeroepen
        mock_thu.assert_awaited_once_with(bot)
        # Assert: state key reminder_thursday gezet
        call_args = mock_write.call_args[0][0]
        self.assertIn("reminder_thursday", call_args)
        # Assert: log_startup bevat reminder_thursday
        startup_call = mock_log_startup.call_args[0][0]
        self.assertIn("reminder_thursday", startup_call)

    async def test_catchup_with_lock_skips_on_recent_lock(self):
        """Test dat catch-up wordt geskipt als lock recent is."""

        class Bot:
            guilds = []

        bot = Bot()

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, ".scheduler.lock")
            # Schrijf recent lock bestand
            with open(lock_path, "w") as f:
                f.write(str(os.getpid()))

            with (
                patch.object(scheduler, "LOCK_PATH", lock_path),
                patch.object(
                    scheduler, "_run_catch_up", new_callable=AsyncMock
                ) as mock_catchup,
            ):
                await scheduler._run_catch_up_with_lock(bot)

            # Assert: _run_catch_up NIET aangeroepen (lock is recent)
            mock_catchup.assert_not_awaited()

    async def test_catchup_with_lock_removes_old_lock_and_runs(self):
        """Test dat oude lock wordt verwijderd en catch-up runt."""

        class Bot:
            guilds = []

        bot = Bot()

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, ".scheduler.lock")
            # Schrijf oud lock bestand (>5 min geleden)
            with open(lock_path, "w") as f:
                f.write(str(os.getpid()))
            # Zet mtime 6 minuten geleden
            old_time = datetime.now().timestamp() - 360
            os.utime(lock_path, (old_time, old_time))

            with (
                patch.object(scheduler, "LOCK_PATH", lock_path),
                patch.object(
                    scheduler, "_run_catch_up", new_callable=AsyncMock
                ) as mock_catchup,
            ):
                await scheduler._run_catch_up_with_lock(bot)

            # Assert: _run_catch_up WEL aangeroepen
            mock_catchup.assert_awaited_once_with(bot)
            # Assert: lock is verwijderd na afloop
            self.assertFalse(os.path.exists(lock_path))


if __name__ == "__main__":
    unittest.main()
