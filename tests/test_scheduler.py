# tests/test_scheduler.py

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

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

    async def test_read_state_returns_empty_on_exception(self):
        with patch.object(scheduler, "STATE_PATH", "/nope/.does-not-exist.json"):
            # Forceer open() om te falen
            with patch("builtins.open", side_effect=IOError("boom")):
                self.assertEqual(scheduler._read_state(), {})

    async def test_run_catch_up_should_run_exception_and_future_occurrence(self):
        tz = pytz.timezone("Europe/Amsterdam")
        # Donderdag 17:00 → voor vrijdag 18:00, triggert 'now < last_occurrence' pad
        fixed_now = tz.localize(datetime(2024, 5, 23, 17, 0, 0))

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fixed_now

            @classmethod
            def fromisoformat(cls, s):  # type: ignore[override]
                # Laat parsing falen voor specifieke string om except-pad van should_run te raken
                if s == "BAD":
                    raise ValueError("bad isoformat")
                return datetime.fromisoformat(s)

        calls = {"update": 0, "reset": 0, "notify": []}

        async def dummy_update(_):
            calls["update"] += 1

        async def dummy_reset(_):
            calls["reset"] += 1

        async def dummy_notify(_, dag: str):
            calls["notify"].append(dag)

        # State met 'slechte' waarden zodat should_run except → True
        state = {
            "update_all_polls": "BAD",
            "reset_polls": "BAD",
            "notify_vrijdag": "BAD",
            "notify_zaterdag": "BAD",
            "notify_zondag": "BAD",
        }

        def fake_read_state():
            return state.copy()

        def fake_write_state(new_state: dict):
            # overschrijven om side-effects te simuleren
            state.clear()
            state.update(new_state)

        class DummyBot: ...

        bot = DummyBot()

        with (
            patch.object(scheduler, "datetime", FixedDateTime),
            patch.object(scheduler, "update_all_polls", dummy_update, create=True),
            patch.object(scheduler, "reset_polls", dummy_reset, create=True),
            patch.object(
                scheduler, "notify_voters_if_avond_gaat_door", dummy_notify, create=True
            ),
            patch.object(scheduler, "_read_state", side_effect=fake_read_state),
            patch.object(scheduler, "_write_state", side_effect=fake_write_state),
        ):
            await scheduler._run_catch_up(bot)

        # Alles moet precies één keer uitgevoerd zijn
        self.assertEqual(calls["update"], 1)
        self.assertEqual(calls["reset"], 1)
        self.assertCountEqual(calls["notify"], ["vrijdag", "zaterdag", "zondag"])

    async def test_run_catch_up_with_lock_skips_when_recent_lock(self):
        class DummyBot: ...

        bot = DummyBot()

        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile = os.path.join(tmpdir, "lock")
            # Maak lock en zet mtime "net" (0 seconden verschil)
            with open(lockfile, "w", encoding="utf-8") as f:
                f.write("pid")

            # timestamp gelijk aan mtime → delta < 300 → skip
            fake_now_ts = os.path.getmtime(lockfile)

            class FakeNowObj:
                @staticmethod
                def timestamp():
                    return fake_now_ts

            class FakeDateTime:
                @staticmethod
                def now():
                    return FakeNowObj()

            with (
                patch.object(scheduler, "LOCK_PATH", lockfile),
                patch.object(scheduler, "datetime", FakeDateTime),
                patch.object(
                    scheduler, "_run_catch_up", new_callable=AsyncMock
                ) as run_co,
            ):
                await scheduler._run_catch_up_with_lock(bot)
                run_co.assert_not_awaited()

    async def test_run_catch_up_with_lock_old_lock_removed_and_runs(self):
        class DummyBot: ...

        bot = DummyBot()

        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile = os.path.join(tmpdir, "lock")
            with open(lockfile, "w", encoding="utf-8") as f:
                f.write("pid")

            # Zet mtime 10 minuten terug zodat hij "oud" is
            old_mtime = os.path.getmtime(lockfile) - 600
            os.utime(lockfile, (old_mtime, old_mtime))

            with (
                patch.object(scheduler, "LOCK_PATH", lockfile),
                patch.object(
                    scheduler, "_run_catch_up", new_callable=AsyncMock
                ) as run_co,
            ):
                await scheduler._run_catch_up_with_lock(bot)
                run_co.assert_awaited()
                # lock moet opgeruimd zijn
                # (de finally in _run_catch_up_with_lock verwijdert lock)
                # We accepteren beide: weg of niet → maar hier verwachten we weg.
                # Daarom:
                # assertFalse
                try:
                    exists = os.path.exists(lockfile)
                except Exception:
                    exists = True
                assert not exists

    async def test_setup_scheduler_adds_jobs_and_creates_task(self):
        fake_bot = object()
        added = []

        def fake_add_job(func, trigger, args, name):
            added.append((getattr(func, "__name__", str(func)), args, name))

        with (
            patch.object(scheduler, "scheduler") as mock_sched,
            patch.object(
                scheduler, "_run_catch_up_with_lock", new_callable=AsyncMock
            ) as mock_cu,
        ):
            mock_sched.add_job.side_effect = fake_add_job

            import asyncio

            loop = asyncio.get_event_loop()

            def consume(coro):
                # Plan de coroutine echt in de event loop
                return loop.create_task(coro)

            with patch("asyncio.create_task", side_effect=consume) as mock_task:
                scheduler.setup_scheduler(fake_bot)

                # Geef de event loop 1 tick om de task te laten starten
                await asyncio.sleep(0)

                # 5 jobs: update, reset, notify vr/za/zo
                self.assertEqual(mock_sched.add_job.call_count, 5)
                mock_task.assert_called_once()
                self.assertEqual(added[0][1], [fake_bot])
                # Catch-up is daadwerkelijk gestart (geawait door de Task)
                mock_cu.assert_awaited()

    async def test_update_all_polls_honours_env_and_channel_state(self):
        class Ch:
            def __init__(self, id, name):
                self.id = id
                self.name = name

        class Guild:
            def __init__(self, channels):
                self._channels = channels

            @property
            def text_channels(self):
                return self._channels

        class Bot:
            def __init__(self, guilds):
                self.guilds = guilds

        ch_ok = Ch(1, "dmk-speelavond")
        ch_denied = Ch(2, "general")
        ch_disabled = Ch(3, "dmk-discussie")

        bot = Bot([Guild([ch_ok, ch_denied, ch_disabled])])

        scheduled = []

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            # Alleen kanaal 1 heeft al een poll- of stemmenbericht
            return 111 if cid == 1 and key in {"vrijdag", "stemmen"} else None

        async def fake_schedule_poll_update(ch, dag, delay=0.0):
            scheduled.append((ch.id, dag))
            return "ok"

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(
                scheduler, "is_channel_disabled", side_effect=lambda cid: cid == 3
            ),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler,
                "schedule_poll_update",
                side_effect=fake_schedule_poll_update,
            ),
            patch.dict(
                os.environ,
                {
                    "DENY_CHANNEL_NAMES": "general,algemeen",
                    "ALLOW_FROM_PER_CHANNEL_ONLY": "true",
                },
                clear=False,
            ),
        ):
            await scheduler.update_all_polls(bot)

        self.assertEqual(scheduled, [(1, "vrijdag"), (1, "zaterdag"), (1, "zondag")])

        # (Optioneel) Als je in deze test óók setup_scheduler wilt checken:
        with (
            patch.object(scheduler, "scheduler") as mock_sched,
            patch.object(
                scheduler, "_run_catch_up_with_lock", new_callable=AsyncMock
            ) as mock_cu,
        ):
            # Move definitions here so they are in scope
            fake_bot = object()
            added = []

            def fake_add_job(func, trigger, args, name):
                added.append((getattr(func, "__name__", str(func)), args, name))

            import asyncio

            loop = asyncio.get_event_loop()

            def consume(coro):
                # Plan de coroutine netjes in de event loop (zodat hij ook echt draait)
                return loop.create_task(coro)

            mock_sched.add_job.side_effect = fake_add_job

            with patch("asyncio.create_task", side_effect=consume) as mock_task:
                scheduler.setup_scheduler(fake_bot)

                # Geef de event loop 1 tick om de task te laten starten
                await asyncio.sleep(0)

                # 5 jobs: update, reset, notify vr/za/zo
                self.assertEqual(mock_sched.add_job.call_count, 5)
                mock_task.assert_called_once()
                # eerste job args moeten het bot object bevatten
                self.assertEqual(added[0][1], [fake_bot])
                # en de catch-up coroutine is daadwerkelijk gestart (geawait door de Task)
                mock_cu.assert_awaited()

    async def test_reset_polls_clears_message_ids_and_ignores_errors(self):
        class Ch:
            def __init__(self, id, name="x"):
                self.id = id
                self.name = name

        class Guild:
            def __init__(self, channels):
                self._channels = channels

            @property
            def text_channels(self):
                return self._channels

        class Bot:
            def __init__(self, guilds):
                self.guilds = guilds

        ch = Ch(10)
        bot = Bot([Guild([ch])])

        cleared = []

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999  # altijd aanwezig

        def fake_clear_message_id(cid, key):
            cleared.append((cid, key))
            # gooi fout op één van de keys om except-pad te raken
            if key == "zondag":
                raise RuntimeError("kapot")

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "clear_message_id", side_effect=fake_clear_message_id
            ),
            patch.object(scheduler, "reset_votes", new_callable=AsyncMock),
        ):
            await scheduler.reset_polls(bot)

        # Alle keys geprobeerd, inclusief dat except niet doorlekt
        expected_keys = {"vrijdag", "zaterdag", "zondag", "stemmen"}
        assert set(k for _, k in cleared) == expected_keys

    async def test_read_state_success_returns_json(self):
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"a": 1}, f)
            with patch.object(scheduler, "STATE_PATH", state_file):
                self.assertEqual(scheduler._read_state(), {"a": 1})

    async def test_run_catch_up_adjusts_future_last_occurrence(self):
        tz = pytz.timezone("Europe/Amsterdam")
        # Maandag 17:00 → notify (vr/za/zo 18:00) liggen in de toekomst → pad met -7 dagen
        fixed_now = tz.localize(datetime(2024, 5, 20, 17, 0, 0))  # maandag

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fixed_now

            @classmethod
            def fromisoformat(cls, s):  # type: ignore[override]
                return datetime.fromisoformat(s)

        calls = []

        async def dummy_notify(_, dag: str):
            calls.append(dag)

        state = {}

        with (
            patch.object(scheduler, "datetime", FixedDateTime),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "update_all_polls", new_callable=AsyncMock),
            patch.object(scheduler, "reset_polls", new_callable=AsyncMock),
            patch.object(
                scheduler,
                "notify_voters_if_avond_gaat_door",
                side_effect=dummy_notify,
                create=True,
            ),
        ):

            class DummyBot: ...

            await scheduler._run_catch_up(DummyBot())

        # Alle drie dagen aangeroepen → branch is geraakt
        self.assertCountEqual(calls, ["vrijdag", "zaterdag", "zondag"])

    async def test_run_catch_up_with_lock_inner_exceptions_are_swallowed(self):
        class DummyBot: ...

        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile = os.path.join(tmpdir, "lock")
            # Zorg dat LOCK_PATH bestaat zodat de 'if os.path.exists' branch in gaat
            with open(lockfile, "w", encoding="utf-8") as f:
                f.write("pid")

            # getmtime → exception (triggert except: pass op regels 125-126)
            def failing_getmtime(_):
                raise OSError("no mtime")

            # os.remove → exception in finally (triggert except: pass op regels 136-137)
            def failing_remove(_):
                raise OSError("cannot remove")

            with (
                patch.object(scheduler, "LOCK_PATH", lockfile),
                patch("os.path.getmtime", side_effect=failing_getmtime),
                patch.object(scheduler, "_run_catch_up", new_callable=AsyncMock),
                patch("os.remove", side_effect=failing_remove),
            ):
                # Moet niet crashen, exceptions worden geslikt
                await scheduler._run_catch_up_with_lock(DummyBot())

    async def test_update_all_polls_handles_bad_channel_id_and_get_message_id_exception(
        self,
    ):
        class BadId:
            def __int__(self):  # int(..) gooit fout → except-pad 197-198
                raise ValueError("not int")

        class Ch:
            def __init__(self):
                self.id = BadId()
                self.name = "dmk-avond"

        class Guild:
            def __init__(self, channels):
                self._channels = channels

            @property
            def text_channels(self):
                return self._channels

        class Bot:
            def __init__(self, guilds):
                self.guilds = guilds

        bot = Bot([Guild([Ch()])])

        scheduled = []

        async def fake_schedule_poll_update(ch, dag, delay=0.0):
            scheduled.append((ch, dag))
            return "ok"

        with (
            patch.object(
                scheduler, "get_channels", side_effect=lambda g: g.text_channels
            ),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            # get_message_id gooit → except-pad 216-217 en vervolgens guard op 220 → continue
            patch.object(scheduler, "get_message_id", side_effect=RuntimeError("boom")),
            patch.object(
                scheduler, "schedule_poll_update", side_effect=fake_schedule_poll_update
            ),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.update_all_polls(bot)

        # Door de guard (regel 220) wordt er niets ingepland
        self.assertEqual(scheduled, [])

    async def test_run_catch_up_friday_before_18_shifts_last_occurrence_back_one_week(
        self,
    ):
        # Arrange: Vrijdag 12:00 → voor vrijdag 18:00, dus now < last_occurrence → subtract 7 days branch
        tz = pytz.timezone("Europe/Amsterdam")
        fixed_now = tz.localize(
            datetime(2024, 5, 24, 12, 0, 0)
        )  # 24-05-2024 is vrijdag

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fixed_now

            @classmethod
            def fromisoformat(cls, s):  # type: ignore[override]
                return datetime.fromisoformat(s)

        calls = []

        async def dummy_notify(_, dag: str):
            calls.append(dag)

        # Lege state → should_run True voor alle drie (vr/za/zo).
        # Vooral belangrijk: voor 'vrijdag' is last_occurrence initieel in de toekomst (18:00),
        # dus de code moet 7 dagen terugzetten (regel 100).
        with (
            patch.object(scheduler, "datetime", FixedDateTime),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "update_all_polls", new_callable=AsyncMock),
            patch.object(scheduler, "reset_polls", new_callable=AsyncMock),
            patch.object(
                scheduler,
                "notify_voters_if_avond_gaat_door",
                side_effect=dummy_notify,
                create=True,
            ),
        ):

            class DummyBot: ...

            await scheduler._run_catch_up(DummyBot())

        # Assert: alle drie zijn aangeroepen en in elk geval 'vrijdag' (de branch met -7 dagen) is geraakt.
        self.assertIn("vrijdag", calls)
        self.assertCountEqual(calls, ["vrijdag", "zaterdag", "zondag"])
