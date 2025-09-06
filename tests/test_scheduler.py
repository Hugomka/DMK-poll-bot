# tests/test_scheduler.py

import json
import os
import unittest
from datetime import datetime
from unittest.mock import patch

import pytz

from apps import scheduler


class SchedulerTestCase(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the scheduler catch-up logic and state persistence.
    """

    async def test_write_state_atomic(self):
        """
        Ensure that the _write_state function writes state atomically.  A
        temporary state file should be replaced in a single operation and the
        temporary .tmp file should not remain on disk after the write.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            with patch.object(scheduler, "STATE_PATH", state_file):
                data = {"foo": "bar", "number": 42}
                scheduler._write_state(data)
                tmp_path = f"{state_file}.tmp"
                self.assertFalse(
                    os.path.exists(tmp_path), "Temporary file not cleaned up"
                )
                self.assertTrue(os.path.exists(state_file), "State file not created")
                with open(state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.assertEqual(
                    loaded, data, "Written state does not match expected data"
                )

    async def test_catch_up_idempotent(self):
        """
        Verify that the catch-up logic only runs missed jobs once.  When run
        twice in succession without advancing the simulated time, the jobs
        should execute on the first call and be skipped on the second call.
        """
        tz = pytz.timezone("Europe/Amsterdam")
        fixed_now = tz.localize(datetime(2024, 5, 27, 19, 0, 0))

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fixed_now

            @classmethod
            def fromisoformat(cls, s):  # type: ignore[override]
                return datetime.fromisoformat(s)

        calls = {"update_all_polls": 0, "reset_polls": 0, "notify": []}

        async def dummy_update_all_polls(bot):
            calls["update_all_polls"] += 1

        async def dummy_reset_polls(bot):
            calls["reset_polls"] += 1

        async def dummy_notify(bot, dag: str):
            calls["notify"].append(dag)

        state: dict = {}

        def fake_read_state():
            return state.copy()

        def fake_write_state(new_state: dict):
            state.clear()
            state.update(new_state)

        class DummyBot:
            pass

        bot = DummyBot()

        with (
            patch.object(scheduler, "datetime", FixedDateTime),
            patch.object(
                scheduler, "update_all_polls", dummy_update_all_polls, create=True
            ),
            patch.object(scheduler, "reset_polls", dummy_reset_polls, create=True),
            patch.object(
                scheduler, "notify_voters_if_avond_gaat_door", dummy_notify, create=True
            ),
            patch.object(scheduler, "_read_state", side_effect=fake_read_state),
            patch.object(scheduler, "_write_state", side_effect=fake_write_state),
        ):
            await scheduler._run_catch_up(bot)
            self.assertEqual(
                calls["update_all_polls"],
                1,
                "update_all_polls should run once on first call",
            )
            self.assertEqual(
                calls["reset_polls"], 1, "reset_polls should run once on first call"
            )
            self.assertCountEqual(calls["notify"], ["vrijdag", "zaterdag", "zondag"])
            await scheduler._run_catch_up(bot)
            self.assertEqual(
                calls["update_all_polls"], 1, "update_all_polls should not run again"
            )
            self.assertEqual(
                calls["reset_polls"], 1, "reset_polls should not run again"
            )
            self.assertEqual(len(calls["notify"]), 3, "notify should not run again")
