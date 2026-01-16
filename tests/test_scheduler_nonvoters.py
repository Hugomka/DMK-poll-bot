# tests/test_scheduler_nonvoters.py
import unittest
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


class TestNotifyNonVoters(unittest.IsolatedAsyncioTestCase):
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

        # Mock datetime om tijd check te laten passen
        from datetime import datetime
        fake_now = datetime.now().replace(hour=16)

        with patch.object(
            scheduler, "get_channels", side_effect=lambda g: g.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "is_paused", return_value=False
        ), patch.object(
            scheduler, "is_notification_enabled", return_value=True
        ), patch.object(
            scheduler, "get_reminder_time", return_value="16:00"
        ), patch.object(
            scheduler, "_is_deadline_mode", return_value=True
        ), patch.object(
            scheduler, "get_enabled_poll_days", return_value=["vrijdag", "zaterdag", "zondag"]
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
        ), patch.object(
            scheduler, "send_non_voter_notification", new_callable=AsyncMock
        ) as mock_nonvoter_notification, patch("datetime.datetime") as mock_dt:

            mock_dt.now.return_value = fake_now
            # --- VRIJDAG ---
            await scheduler.notify_non_voters(bot, "vrijdag")

            mock_nonvoter_notification.assert_awaited()
            # Pak de mentions uit de eerste call
            call_args = mock_nonvoter_notification.await_args_list[0]
            mentions = call_args.kwargs.get("mentions_str", "")

            assert "<@1>" in mentions
            assert "<@3>" in mentions

            # --- ZATERDAG ---
            mock_nonvoter_notification.reset_mock()
            await scheduler.notify_non_voters(bot, "zaterdag")

            # Pak de mentions uit de tweede call
            call_args = mock_nonvoter_notification.await_args_list[0]
            mentions = call_args.kwargs.get("mentions_str", "")

            assert "<@1>" in mentions
            assert "<@3>" not in mentions

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
            scheduler, "is_paused", return_value=False
        ), patch.object(
            scheduler, "is_notification_enabled", return_value=True
        ), patch.object(
            scheduler, "_is_deadline_mode", return_value=True
        ), patch.object(
            scheduler, "get_enabled_poll_days", return_value=["vrijdag", "zaterdag", "zondag"]
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
        ), patch.object(
            scheduler, "send_non_voter_notification", new_callable=AsyncMock
        ) as mock_nonvoter_notification:
            await scheduler.notify_non_voters(bot, "vrijdag")
            mock_nonvoter_notification.assert_not_awaited()

    async def test_notify_non_voters_skip_disabled_dagen(self):
        """Test dat notify_non_voters geen notificatie stuurt voor disabled dagen."""
        bot = type("B", (), {"guilds": [FakeGuild(channel=FakeChannel())]})()

        def fake_load_votes(guild_id, channel_id):
            # User 1 heeft niet gestemd voor vrijdag
            return {"1": {"vrijdag": []}}

        with patch.object(
            scheduler, "get_channels", side_effect=lambda g: g.text_channels
        ), patch.object(
            scheduler, "is_channel_disabled", return_value=False
        ), patch.object(
            scheduler, "is_paused", return_value=False
        ), patch.object(
            scheduler, "is_notification_enabled", return_value=True
        ), patch.object(
            scheduler, "_is_deadline_mode", return_value=True
        ), patch.object(
            scheduler, "get_enabled_poll_days", return_value=["zondag"]  # Alleen zondag enabled
        ), patch.object(
            scheduler, "load_votes", side_effect=fake_load_votes
        ), patch.object(
            scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
        ), patch.object(
            scheduler, "send_non_voter_notification", new_callable=AsyncMock
        ) as mock_nonvoter_notification:
            # Roep aan met vrijdag (die niet enabled is)
            await scheduler.notify_non_voters(bot, "vrijdag")

            # Notificatie mag NIET worden verstuurd omdat vrijdag disabled is
            mock_nonvoter_notification.assert_not_awaited()
