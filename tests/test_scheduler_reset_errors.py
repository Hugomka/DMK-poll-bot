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
