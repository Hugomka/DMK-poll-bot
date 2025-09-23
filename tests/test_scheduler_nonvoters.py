# tests/test_scheduler_nonvoters.py
from unittest.mock import AsyncMock, patch

from apps import scheduler
from tests.base import BaseTestCase


class FakeMember:
    def __init__(self, uid, bot=False):
        self.id = uid
        self.bot = bot
        self.mention = f"<@{uid}>"


class FakeChannel:
    def __init__(self, cid=1, members=None):
        self.id = cid
        self.name = "inschrijvingen"
        self.members = members or []
        self.sent = []

        async def fake_send(msg):
            self.sent.append(msg)

        self.send = AsyncMock(side_effect=fake_send)


class FakeGuild:
    def __init__(self, gid=42, channel=None):
        self.id = gid
        self.text_channels = [
            channel
            or FakeChannel(
                members=[FakeMember(1), FakeMember(2, bot=True), FakeMember(3)]
            )
        ]


class NonVotersTestCase(BaseTestCase):
    async def test_notify_non_voters_met_leeg_en_guest_data(self):
        bot = type("B", (), {"guilds": [FakeGuild()]})()

        def fake_load_votes(guild_id, channel_id):
            # Let op: guests-key moet "<owner>_guest::<guest>" zijn.
            return {
                "1": {"vrijdag": []},  # niet gestemd
                "2": {"vrijdag": ["20:30"]},  # bot, wordt toch gefilterd
                "3_guest::77": {
                    "zaterdag": ["21:00"]
                },  # owner=3 heeft (elders) gestemd → telt als '3'
            }

        with patch.object(
            scheduler, "get_channels", side_effect=lambda g: g.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", new_callable=AsyncMock
        ) as mock_safe:
            await scheduler.notify_non_voters(bot, "vrijdag")
            # safe_call is aangeroepen en de tekst bevat alleen <@1>, niet <@3>
            mock_safe.assert_awaited()
            args, kwargs = mock_safe.await_args
            text = " ".join(str(a) for a in args)
            assert "<@1>" in text
            assert "<@3>" not in text

    async def test_notify_non_voters_safe_call_niet_aangeroepen_bij_geen_nonvoters(
        self,
    ):
        bot = type("B", (), {"guilds": [FakeGuild(channel=FakeChannel())]})()

        def fake_load_votes(guild_id, channel_id):
            return {"9": {"vrijdag": ["20:30"]}}  # iedereen heeft gestemd

        with patch.object(
            scheduler, "get_channels", side_effect=lambda g: g.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", new_callable=AsyncMock
        ) as mock_safe:
            await scheduler.notify_non_voters(bot, "vrijdag")
            mock_safe.assert_not_awaited()
