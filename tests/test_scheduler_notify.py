# tests/test_scheduler_notify.py

from unittest.mock import AsyncMock, patch

from apps import scheduler
from apps.scheduler import notify_voters_if_avond_gaat_door
from tests.base import BaseTestCase


class FakeMember:
    def __init__(self, uid):
        self.id = uid
        self.mention = f"<@{uid}>"


class FakeChannel:
    def __init__(self, id=999, name="chan"):
        self.id = id
        self.name = name
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


class FakeGuild:
    def __init__(self, gid, channels, members_map=None):
        self.id = gid
        self._channels = channels
        self._members = members_map or {}

    def get_member(self, uid):
        return self._members.get(uid)

    @property
    def text_channels(self):
        return self._channels


class FakeBot:
    def __init__(self, guilds):
        self.guilds = guilds


class TestSchedulerNotify(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_notify_sends_when_6_or_more_votes(self):
        votes = {
            "1": {"vrijdag": ["om 20:30 uur"]},
            "2": {"vrijdag": ["om 20:30 uur"]},
            "3": {"vrijdag": ["om 20:30 uur"]},
            "4": {"vrijdag": ["om 20:30 uur"]},
            "5": {"vrijdag": ["om 20:30 uur"]},
            "6": {"vrijdag": ["om 20:30 uur"]},
        }

        async def fake_load_votes(*args, **kwargs):
            return votes

        with patch("apps.scheduler.get_message_id", return_value=111), patch(
            "apps.scheduler.load_votes", side_effect=fake_load_votes
        ):
            channel = FakeChannel()
            g = FakeGuild(
                1,
                [channel],
                members_map={int(i): FakeMember(int(i)) for i in votes.keys()},
            )
            bot = FakeBot([g])

            await notify_voters_if_avond_gaat_door(bot, "vrijdag")

            ch = g.text_channels[0]
            assert len(ch.sent) == 1
            assert "20:30" in ch.sent[0]

    async def test_notify_skips_disabled_and_non_list(self):
        g = FakeGuild(1, [FakeChannel(5, "dmk")])
        bot = FakeBot([g])

        # Stemmen: tijden voor 'vrijdag' is géén lijst → skip
        votes = {"123": {"vrijdag": "om 19:00 uur"}}

        async def fake_load_votes(*args, **kwargs):
            return votes

        with patch.object(
            scheduler, "get_channels", side_effect=lambda guild: guild.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", side_effect=lambda cid: True
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", new_callable=AsyncMock
        ) as mock_safe:
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")
            mock_safe.assert_not_awaited()  # Disabled → geen send

    async def test_notify_guest_collapse_counts_and_continue_when_under_6(self):
        ch = FakeChannel(7, "dmk")
        g = FakeGuild(1, [ch])
        bot = FakeBot([g])

        # 2 gasten voor 19:00 moeten samentellen als 1 owner
        votes = {
            "111_guest::42": {"vrijdag": ["om 19:00 uur"]},
            "222_guest::42": {"vrijdag": ["om 19:00 uur"]},
            "333": {"vrijdag": ["om 20:30 uur"]},  # 1 voor 20:30
        }

        async def fake_load_votes(*args, **kwargs):
            return votes

        with patch.object(
            scheduler, "get_channels", side_effect=lambda guild: guild.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", new_callable=AsyncMock
        ) as mock_safe:
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")
            # Totaal 1 (owner 42) vs 1 → beide < 6 → geen melding
            mock_safe.assert_not_awaited()
            assert len(ch.sent) == 0

    async def test_notify_winner_19_and_exception_in_member_lookup_and_channel_send(
        self,
    ):
        ch = FakeChannel(9, "speelavond")
        # Voeg een member 7 toe; 'NaN' zal except-pad raken
        members = {7: type("M", (), {"mention": "<@7>"})()}
        g = FakeGuild(1, [ch], members_map=members)
        bot = FakeBot([g])

        # 6 stemmers voor 19:00 (inclusief een 'NaN' voor except-pad), 0 voor 20:30
        votes = {
            "1": {"vrijdag": ["om 19:00 uur"]},
            "2": {"vrijdag": ["om 19:00 uur"]},
            "3": {"vrijdag": ["om 19:00 uur"]},
            "4": {"vrijdag": ["om 19:00 uur"]},
            "5": {"vrijdag": ["om 19:00 uur"]},
            "NaN": {"vrijdag": ["om 19:00 uur"]},  # int('NaN') → except → continue
        }

        async def fake_load_votes(*args, **kwargs):
            return votes

        async def failing_safe_call(func, content):
            # Forceer except in outer try/except
            raise RuntimeError("send kapot")

        with patch.object(
            scheduler, "get_channels", side_effect=lambda guild: guild.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", side_effect=failing_safe_call
        ):
            # Moet niet crashen ondanks except in safe_call; winner is 19:00
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")
            # Geen exceptions bubbelen door; ch.sent blijft leeg omdat safe_call faalde
            assert len(ch.sent) == 0

    async def test_notify_non_list_tijden_skips_when_channel_enabled(self):
        ch = FakeChannel(5, "dmk")
        g = FakeGuild(1, [ch])
        bot = FakeBot([g])

        # Tijden is géén lijst → moet worden overgeslagen
        votes = {"u1": {"vrijdag": "om 20:30 uur"}}

        async def fake_load_votes(*_, **__):
            return votes

        with patch.object(
            scheduler, "get_channels", side_effect=lambda guild: guild.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", new_callable=AsyncMock
        ) as mock_safe:
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")
            mock_safe.assert_not_awaited()
            assert len(ch.sent) == 0

    async def test_notify_guest_collapse_for_2030_under_threshold(self):
        ch = FakeChannel(6, "dmk")
        g = FakeGuild(1, [ch])
        bot = FakeBot([g])

        # Twee gasten voor 20:30 met dezelfde owner → telt als 1 stem 20:30
        votes = {
            "g1_guest::42": {"vrijdag": ["om 20:30 uur"]},
            "g2_guest::42": {"vrijdag": ["om 20:30 uur"]},
            "u3": {"vrijdag": ["om 19:00 uur"]},  # 1 stem 19:00
        }

        async def fake_load_votes(*_, **__):
            return votes

        with patch.object(
            scheduler, "get_channels", side_effect=lambda guild: guild.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "safe_call", new_callable=AsyncMock
        ) as mock_safe:
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")
            # Beide < 6 → geen bericht; maar branch 277-278 is geraakt
            mock_safe.assert_not_awaited()
            assert len(ch.sent) == 0
