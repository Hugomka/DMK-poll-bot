# tests/test_scheduler_reset_errors.py
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytz

from apps import scheduler
from tests.base import BaseTestCase

TZ = pytz.timezone("Europe/Amsterdam")


class FakeChannel:
    def __init__(self, name="speelavond"):
        self.name = name

        async def fail_send(*args, **kwargs):
            raise RuntimeError("send kapot")

        self.send = AsyncMock(side_effect=fail_send)


class FakeGuild:
    def __init__(self):
        self.id = 123
        self.text_channels = [FakeChannel()]


class ResetErrorsTestCase(BaseTestCase):
    async def test_reset_polls_slikt_exceptions_bij_melding(self):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return TZ.localize(
                    datetime(2024, 5, 28, 20, 1, 0)
                )  # di 20:01 (binnen venster)

        bot = type("B", (), {"guilds": [FakeGuild()]})()

        with patch.object(scheduler, "datetime", FixedDateTime), patch.object(
            scheduler, "get_channels", side_effect=lambda g: g.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "clear_message_id"
        ), patch.object(
            scheduler, "TZ", TZ
        ):
            # save_message_id bestaat niet in scheduler → niet patchen
            await scheduler.reset_polls(bot)  # mag niet crashen

    async def test_reset_polls_reset_votes_scoped_fails_fallback_to_save(self):
        """Test dat fallback naar save_votes_scoped werkt als reset_votes_scoped faalt."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.send = AsyncMock()

        class Guild:
            def __init__(self):
                self.id = 123
                self.text_channels = [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        async def fake_reset_votes_scoped(_gid, _cid):
            raise RuntimeError("reset failed")

        def fake_get_message_id(_cid, _key):
            return 999  # Heeft polls

        # Mock de dynamische import van save_votes_scoped
        mock_save = AsyncMock()

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "get_channels", lambda g: g.text_channels),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "reset_votes_scoped", side_effect=fake_reset_votes_scoped
            ),
            patch("apps.utils.poll_storage.save_votes_scoped", mock_save),
            patch.object(scheduler, "clear_message_id"),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock),
        ):
            result = await scheduler.reset_polls(bot)

        # Assert: True geretourneerd (fallback succesvol)
        self.assertTrue(result)
        # Assert: save_votes_scoped aangeroepen als fallback
        mock_save.assert_awaited_once()

    async def test_reset_polls_clear_message_id_exception_ignored(self):
        """Test dat exception in clear_message_id wordt genegeerd."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.send = AsyncMock()

        class Guild:
            def __init__(self):
                self.id = 123
                self.text_channels = [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_message_id(_cid, _key):
            return 999

        def fake_clear_message_id(_cid, _key):
            raise RuntimeError("clear failed")

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "get_channels", lambda g: g.text_channels),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "reset_votes_scoped", new_callable=AsyncMock
            ) as mock_reset,
            patch.object(
                scheduler, "clear_message_id", side_effect=fake_clear_message_id
            ),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock),
        ):
            result = await scheduler.reset_polls(bot)

        # Assert: True geretourneerd (exception genegeerd)
        self.assertTrue(result)
        # Assert: reset_votes_scoped wel aangeroepen
        mock_reset.assert_awaited_once()

    async def test_reset_polls_safe_call_exception_continue(self):
        """Test dat exception in safe_call (resetbericht) wordt genegeerd."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.send = AsyncMock()

        class Guild:
            def __init__(self):
                self.id = 123
                self.text_channels = [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_message_id(_cid, _key):
            return 999

        async def fake_safe_call(*_args, **_kwargs):
            raise RuntimeError("safe_call failed")

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "get_channels", lambda g: g.text_channels),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "reset_votes_scoped", new_callable=AsyncMock
            ) as mock_reset,
            patch.object(scheduler, "clear_message_id"),
            patch.object(scheduler, "safe_call", side_effect=fake_safe_call),
        ):
            result = await scheduler.reset_polls(bot)

        # Assert: True geretourneerd (exception in safe_call genegeerd)
        self.assertTrue(result)
        # Assert: reset_votes_scoped wel aangeroepen
        mock_reset.assert_awaited_once()

    async def test_reset_polls_write_state_exception_ignored(self):
        """Test dat exception in _write_state wordt genegeerd."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.send = AsyncMock()

        class Guild:
            def __init__(self):
                self.id = 123
                self.text_channels = [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_message_id(_cid, _key):
            return 999

        def fake_write_state(_state):
            raise RuntimeError("write_state failed")

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value={}),
            patch.object(scheduler, "_write_state", side_effect=fake_write_state),
            patch.object(scheduler, "get_channels", lambda g: g.text_channels),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "reset_votes_scoped", new_callable=AsyncMock
            ) as mock_reset,
            patch.object(scheduler, "clear_message_id"),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock),
        ):
            result = await scheduler.reset_polls(bot)

        # Assert: True geretourneerd (exception in _write_state genegeerd)
        self.assertTrue(result)
        # Assert: reset_votes_scoped wel aangeroepen
        mock_reset.assert_awaited_once()
