# tests/test_scheduler_nonvoters.py
from unittest.mock import AsyncMock, patch

from apps import scheduler


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

    async def test_notify_non_voters_met_leeg_en_guest_data(self):
        bot = type("B", (), {"guilds": [FakeGuild()]})()

        def fake_load_votes(guild_id, channel_id):
            # 1 heeft nergens gestemd
            # 2 is bot (gestemd op vrijdag, maar bots worden gefilterd)
            # 3 heeft alleen zaterdag gestemd via guest-key
            return {
                "1": {"vrijdag": []},
                "2": {"vrijdag": ["20:30"]},
                "3_guest::77": {"zaterdag": ["21:00"]},
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

            # --- VRIJDAG ---
            await scheduler.notify_non_voters(bot, "vrijdag")

            mock_safe.assert_awaited()
            texts = [
                " ".join(str(a) for a in call.args)
                for call in mock_safe.await_args_list
            ]
            text = " ".join(texts)

            assert "<@1>" in text
            assert "<@3>" in text

            # --- ZATERDAG ---
            mock_safe.reset_mock()
            await scheduler.notify_non_voters(bot, "zaterdag")

            texts = [
                " ".join(str(a) for a in call.args)
                for call in mock_safe.await_args_list
            ]
            text = " ".join(texts)

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
