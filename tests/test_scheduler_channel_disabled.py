# tests/test_scheduler_channel_disabled.py
from unittest.mock import AsyncMock, patch

from apps import scheduler
from tests.base import BaseTestCase


class FakeChannel:
    def __init__(self, cid=1):
        self.id = cid

        async def fake_send(msg):
            return

        self.send = AsyncMock(side_effect=fake_send)


class FakeGuild:
    def __init__(self):
        self.id = 321
        self.text_channels = [FakeChannel()]


class ChannelDisabledTestCase(BaseTestCase):
    async def test_notify_voters_if_avond_gaat_door_overslaat_disabled_channel(self):
        bot = type("B", (), {"guilds": [FakeGuild()]})()

        def fake_load_votes(guild_id, channel_id):
            # drempel ≥6 voor vrijdag
            return {
                "1": {"vrijdag": ["20:30"]},
                "2": {"vrijdag": ["20:30"]},
                "3": {"vrijdag": ["21:00"]},
                "4": {"vrijdag": ["21:00"]},
                "5": {"vrijdag": ["20:30"]},
                "6": {"vrijdag": ["20:30"]},
            }

        with patch.object(
            scheduler, "get_channels", side_effect=lambda g: g.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=True
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", new_callable=AsyncMock
        ) as mock_safe:
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")
            mock_safe.assert_not_awaited()
