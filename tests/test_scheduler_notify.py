import os
import unittest
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from apps import scheduler


class TestSchedulerNotify(unittest.IsolatedAsyncioTestCase):
    async def test_notify_non_voters_with_specific_channel(self):
        """Test notify_non_voters met een specifiek kanaal (commando-modus)."""

        class FakeMember:
            def __init__(self, id, bot=False):
                self.id = id
                self.bot = bot
                self.mention = f"<@{id}>"

        class FakeChannel:
            def __init__(self, id, guild):
                self.id = id
                self.guild = guild
                self.members = [
                    FakeMember(100),
                    FakeMember(200),
                    FakeMember(300, bot=True),
                ]
                self.send = AsyncMock()

        class FakeGuild:
            def __init__(self, id):
                self.id = id

        guild = FakeGuild(1)
        channel = FakeChannel(10, guild)

        # Votes: user 100 heeft gestemd voor vrijdag, 200 niet
        votes = {"100": {"vrijdag": ["om 19:00 uur"]}}

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
            ),
            patch.object(
                scheduler, "send_non_voter_notification", new_callable=AsyncMock
            ) as mock_nonvoter_notification,
        ):
            result = await scheduler.notify_non_voters(
                None, "vrijdag", cast(discord.TextChannel, channel)
            )

        self.assertTrue(result)
        mock_nonvoter_notification.assert_awaited_once()
        # Controleer dat de mentions user 200 bevat (niet-stemmer)
        args, kwargs = mock_nonvoter_notification.call_args
        mentions = kwargs.get("mentions_str", args[2] if len(args) > 2 else "")
        self.assertIn("<@200>", mentions)
        self.assertNotIn("<@100>", mentions)

    async def test_notify_non_voters_without_dag_weekend_mode(self):
        """Test notify_non_voters zonder dag (weekend-breed)."""

        class Member:
            def __init__(self, id, bot=False):
                self.id = id
                self.bot = bot
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = [Member(100), Member(200)]
                self.send = AsyncMock()

            @property
            def guild(self):
                return Guild(1)

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # User 100 heeft ergens gestemd, user 200 niet
        votes = {"100": {"zaterdag": ["om 20:30 uur"]}}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999  # Polls bestaan

        # Mock datetime om tijd check te laten passen
        from datetime import datetime
        fake_now = datetime.now()
        fake_now = fake_now.replace(hour=16)  # Match default reminder tijd

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "is_notification_enabled", return_value=True),
            patch.object(scheduler, "get_reminder_time", return_value="16:00"),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(scheduler.TZ, "localize", return_value=fake_now),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            with patch("datetime.datetime") as mock_dt:
                mock_dt.now.return_value = fake_now
                result = await scheduler.notify_non_voters(bot, dag=None)

        self.assertTrue(result)
        mock_mention.assert_awaited_once()
        args, kwargs = mock_mention.call_args
        mentions = kwargs.get("mentions", args[1] if len(args) > 1 else "")
        self.assertIn("<@200>", mentions)
        self.assertNotIn("<@100>", mentions)

    async def test_notify_non_voters_guest_vote_owner_extraction(self):
        """Test dat gast-stemmen correct worden toegewezen aan de eigenaar."""

        class FakeMember:
            def __init__(self, id, bot=False):
                self.id = id
                self.bot = bot
                self.mention = f"<@{id}>"

        class FakeChannel:
            def __init__(self, id, guild):
                self.id = id
                self.guild = guild
                self.members = [FakeMember(100), FakeMember(200)]
                self.send = AsyncMock()

        class FakeGuild:
            def __init__(self, id):
                self.id = id

        guild = FakeGuild(1)
        channel = FakeChannel(10, guild)

        # User 100 heeft gestemd (inclusief gast), user 200 niet
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},
            "100_guest::Mario": {"vrijdag": ["om 19:00 uur"]},
        }

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
            ),
            patch.object(
                scheduler, "send_non_voter_notification", new_callable=AsyncMock
            ) as mock_nonvoter_notification,
        ):
            result = await scheduler.notify_non_voters(
                None, "vrijdag", cast(discord.TextChannel, channel)
            )

        self.assertTrue(result)
        args, kwargs = mock_nonvoter_notification.call_args
        mentions = kwargs.get("mentions_str", args[2] if len(args) > 2 else "")
        self.assertIn("<@200>", mentions)
        self.assertNotIn("<@100>", mentions)

    async def test_notify_non_voters_no_non_voters(self):
        """Test notify_non_voters als iedereen al heeft gestemd."""

        class Member:
            def __init__(self, id, bot=False):
                self.id = id
                self.bot = bot
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, guild):
                self.id = id
                self.guild = guild
                self.members = [Member(100)]
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

        guild = Guild(1)
        channel = Channel(10, guild)

        votes = {"100": {"vrijdag": ["om 19:00 uur"]}}

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
            ),
            patch.object(
                scheduler, "send_non_voter_notification", new_callable=AsyncMock
            ) as mock_nonvoter_notification,
        ):
            result = await scheduler.notify_non_voters(
                None, "vrijdag", cast(discord.TextChannel, channel)
            )

        self.assertFalse(result)
        mock_nonvoter_notification.assert_not_awaited()

    # --- Nieuwe, eenvoudige tests zonder skip om coverage te verhogen ---

    async def test_notify_voters_if_avond_gaat_door_basic(self):
        """Eenvoudige happy-path test: genoeg stemmen → 1 bericht."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 6 stemmen op vrijdag (drempel gehaald)
        votes = {str(i): {"vrijdag": ["om 19:00 uur"]} for i in range(100, 106)}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_persistent_mention", new_callable=AsyncMock
            ) as mock_persistent,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        mock_persistent.assert_awaited_once()

    async def test_notify_voters_if_avond_gaat_door_tie_current_behavior(self):
        """Gelijkstand 19:00 vs 20:30 → huidige gedrag: GEEN notificatie.
        TODO: Als tie-breaker (20:30 voorrang) later wordt geïmplementeerd,
        verander deze test om wél een notificatie te verwachten.
        """

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 3 stemmen 19:00 en 3 stemmen 20:30 → gelijkstand
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},
            "101": {"vrijdag": ["om 19:00 uur"]},
            "102": {"vrijdag": ["om 19:00 uur"]},
            "103": {"vrijdag": ["om 20:30 uur"]},
            "104": {"vrijdag": ["om 20:30 uur"]},
            "105": {"vrijdag": ["om 20:30 uur"]},
        }

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Huidig gedrag: bij gelijkstand geen bericht
        mock_call.assert_not_awaited()

    async def test_notify_voters_if_avond_gaat_door_prefers_2030_when_more_votes(self):
        """Als 20:30 strikt meer stemmen heeft dan 19:00 → notificatie."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 5 stemmen 19:00 en 7 stemmen 20:30 → 20:30 wint duidelijk (haalt drempel)
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},
            "101": {"vrijdag": ["om 19:00 uur"]},
            "102": {"vrijdag": ["om 19:00 uur"]},
            "103": {"vrijdag": ["om 19:00 uur"]},
            "104": {"vrijdag": ["om 19:00 uur"]},
            "105": {"vrijdag": ["om 20:30 uur"]},
            "106": {"vrijdag": ["om 20:30 uur"]},
            "107": {"vrijdag": ["om 20:30 uur"]},
            "108": {"vrijdag": ["om 20:30 uur"]},
            "109": {"vrijdag": ["om 20:30 uur"]},
            "110": {"vrijdag": ["om 20:30 uur"]},
            "111": {"vrijdag": ["om 20:30 uur"]},
        }

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_persistent_mention", new_callable=AsyncMock
            ) as mock_persistent,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Nu moet er 1 bericht zijn verstuurd
        mock_persistent.assert_awaited_once()

    async def test_notify_voters_if_avond_gaat_door_not_enough_votes(self):
        """Te weinig stemmen → geen notificatie."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # Slechts 3 stemmen
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},
            "101": {"vrijdag": ["om 19:00 uur"]},
            "102": {"vrijdag": ["om 19:00 uur"]},
        }

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        mock_call.assert_not_awaited()

    async def test_notify_non_voters_thursday_basic(self):
        """Donderdag-herinnering: er zijn niet-stemmers → één bericht."""

        class Member:
            def __init__(self, id, bot=False):
                self.id = id
                self.bot = bot
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = [Member(100), Member(200)]
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # Alleen 100 heeft ergens gestemd → 200 is non-voter
        votes = {"100": {"vrijdag": ["om 19:00 uur"]}}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "is_notification_enabled", return_value=True),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_non_voters_thursday(bot)

        mock_mention.assert_awaited_once()

    async def test_notify_for_channel_not_enough_votes(self):
        """Test notify_for_channel met te weinig stemmen."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.send = AsyncMock()

            @property
            def guild(self):
                return Guild(1)

        class Guild:
            def __init__(self, id):
                self.id = id

        channel = Channel(10)

        # Slechts 2 stemmen
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},
            "101": {"vrijdag": ["om 19:00 uur"]},
        }

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            result = await scheduler.notify_for_channel(channel, "vrijdag")

        self.assertFalse(result)
        mock_call.assert_not_awaited()

    async def test_notify_for_channel_basic(self):
        """Genoeg stemmen in specifiek kanaal → één bericht."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.send = AsyncMock()

            @property
            def guild(self):
                return Guild(1)

        class Guild:
            def __init__(self, id):
                self.id = id

        channel = Channel(10)

        # 6 stemmen → drempel gehaald
        votes = {str(i): {"vrijdag": ["om 19:00 uur"]} for i in range(100, 106)}

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            result = await scheduler.notify_for_channel(channel, "vrijdag")

        self.assertTrue(result)
        mock_call.assert_awaited_once()

    async def test_notify_for_channel_disabled_channel(self):
        """Test notify_for_channel met uitgeschakeld kanaal."""

        class Channel:
            def __init__(self, id):
                self.id = id

        channel = Channel(10)

        with patch.object(scheduler, "is_channel_disabled", return_value=True):
            result = await scheduler.notify_for_channel(channel, "vrijdag")

        self.assertFalse(result)

    async def test_notify_for_channel_denied_channel(self):
        """Test notify_for_channel met geweigerd kanaal."""

        class Channel:
            def __init__(self, id, name="general"):
                self.id = id
                self.name = name

        channel = Channel(10)

        with (
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.dict(os.environ, {"DENY_CHANNEL_NAMES": "general"}, clear=False),
        ):
            result = await scheduler.notify_for_channel(channel, "vrijdag")

        self.assertFalse(result)

    async def test_notify_for_channel_no_active_poll(self):
        """Test notify_for_channel zonder actieve poll."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name

        channel = Channel(10)

        def fake_get_message_id(cid, key):
            return None  # Geen polls

        with (
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            result = await scheduler.notify_for_channel(channel, "vrijdag")

        self.assertFalse(result)

    async def test_notify_for_channel_exception_returns_false(self):
        """Test dat exceptions in notify_for_channel False teruggeven."""

        class Channel:
            def __init__(self, id):
                self.id = id

        channel = Channel(10)

        with patch.object(
            scheduler, "is_channel_disabled", side_effect=RuntimeError("boom")
        ):
            result = await scheduler.notify_for_channel(channel, "vrijdag")

        self.assertFalse(result)

    async def test_notify_non_voters_handles_invalid_votes_gracefully(self):
        """Test dat ongeldige vote-data niet crasht."""

        class Member:
            def __init__(self, id):
                self.id = id
                self.bot = False
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, guild):
                self.id = id
                self.guild = guild
                self.members = [Member(100), Member(200)]
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

        guild = Guild(1)
        channel = Channel(10, guild)

        # Ongeldige data: niet-dict dagen_map, niet-list tijden
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},
            "invalid_user": "not_a_dict",  # Ongeldig
            "200": {"vrijdag": "not_a_list"},  # Ongeldig
        }

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
            ),
            patch.object(
                scheduler, "send_non_voter_notification", new_callable=AsyncMock
            ) as mock_nonvoter_notification,
        ):
            result = await scheduler.notify_non_voters(
                None, "vrijdag", cast(discord.TextChannel, channel)
            )

        # User 200 moet in de lijst staan (ongeldige data = niet gestemd)
        self.assertTrue(result)
        args, kwargs = mock_nonvoter_notification.call_args
        mentions = kwargs.get("mentions_str", args[2] if len(args) > 2 else "")
        self.assertIn("<@200>", mentions)

    # --- Extra tests voor notify_voters_if_avond_gaat_door ---

    async def test_notify_voters_no_members_found_sends_message_without_mentions(self):
        """Test dat bericht zonder mentions wordt verzonden als er geen members zijn."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []  # Geen members
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 7 stemmen op vrijdag (drempel gehaald: 20:30 >= 6)
        votes = {str(i): {"vrijdag": ["om 20:30 uur"]} for i in range(100, 107)}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_persistent_mention", new_callable=AsyncMock
            ) as mock_persistent,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Assert: persistent mention WEL aangeroepen
        mock_persistent.assert_awaited_once()
        # Assert: bericht bevat GEEN mentions (want geen members)
        args, kwargs = mock_persistent.call_args
        # New signature: send_persistent_mention(channel, mentions, text)
        mentions = args[1] if len(args) > 1 else ""
        text = args[2] if len(args) > 2 else ""

        # Verify no mentions
        self.assertEqual(mentions, "")
        # Assert: bericht bevat wel de dag en Hammertime
        self.assertIn("vrijdag", text)
        self.assertIn("<t:", text)  # Hammertime format
        self.assertIn(":t>", text)

    async def test_notify_voters_send_missing_no_crash(self):
        """Test dat ontbrekend send attribuut niet crasht."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []
                # Geen send attribuut

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 6 stemmen op vrijdag (drempel gehaald)
        votes = {str(i): {"vrijdag": ["om 19:00 uur"]} for i in range(100, 106)}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            # Mag niet crashen
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Assert: safe_call NIET aangeroepen (want geen send)
        mock_call.assert_not_awaited()

    async def test_notify_voters_safe_call_exception_returns_early(self):
        """Test dat exception in safe_call wordt afgehandeld."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 6 stemmen op vrijdag (drempel gehaald)
        votes = {str(i): {"vrijdag": ["om 19:00 uur"]} for i in range(100, 106)}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        async def fake_safe_call(*args, **kwargs):
            raise RuntimeError("boom")

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", side_effect=fake_safe_call),
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            # Mag niet crashen, functie keert terug
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

    async def test_notify_voters_deny_channel_names_within_function(self):
        """Test dat DENY_CHANNEL_NAMES binnen notify_voters_if_avond_gaat_door wordt gecontroleerd."""

        class Channel:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10, "general")]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 6 stemmen
        votes = {str(i): {"vrijdag": ["om 19:00 uur"]} for i in range(100, 106)}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(os.environ, {"DENY_CHANNEL_NAMES": "general"}, clear=False),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Assert: safe_call NIET aangeroepen (kanaal geskipt door DENY)
        mock_call.assert_not_awaited()

    async def test_notify_voters_allow_per_channel_no_poll_skip(self):
        """Test dat ALLOW_FROM_PER_CHANNEL_ONLY=true en geen poll → skip."""

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        votes = {str(i): {"vrijdag": ["om 19:00 uur"]} for i in range(100, 106)}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return None  # Geen polls

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Assert: safe_call NIET aangeroepen (geen poll → skip)
        mock_call.assert_not_awaited()

    # --- Extra tests voor notify_non_voters ---

    async def test_notify_non_voters_channel_without_guild_returns_false(self):
        """Test commando-modus: channel zonder guild → False."""

        class Channel:
            def __init__(self, id):
                self.id = id
                # Geen guild attribuut

        channel = Channel(10)

        result = await scheduler.notify_non_voters(
            None, "vrijdag", cast(discord.TextChannel, channel)
        )

        # Assert: False teruggegeven
        self.assertFalse(result)

    async def test_notify_non_voters_scheduler_mode_deny_channel(self):
        """Test scheduler-modus met DENY_CHANNEL_NAMES."""

        class Channel:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10, "general")]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        with (
            patch.object(scheduler, "load_votes", return_value={}),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.dict(os.environ, {"DENY_CHANNEL_NAMES": "general"}, clear=False),
        ):
            result = await scheduler.notify_non_voters(bot, "vrijdag")

        # Assert: False (geen berichten verstuurd)
        self.assertFalse(result)
        mock_call.assert_not_awaited()

    async def test_notify_non_voters_scheduler_mode_allow_and_no_polls(self):
        """Test scheduler-modus: ALLOW_FROM_PER_CHANNEL_ONLY=true en geen polls → skip."""

        class Channel:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self.members = []
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10, "dmk")]

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(_cid, _key):
            return None  # Geen polls

        with (
            patch.object(scheduler, "load_votes", return_value={}),
            patch.object(scheduler, "safe_call", new_callable=AsyncMock) as mock_call,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            result = await scheduler.notify_non_voters(bot, "vrijdag")

        # Assert: False (geen berichten verstuurd)
        self.assertFalse(result)
        mock_call.assert_not_awaited()

    async def test_notify_non_voters_safe_call_exception_swallowed(self):
        """Test dat safe_call exception wordt geslikt."""

        class Member:
            def __init__(self, id):
                self.id = id
                self.bot = False
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, guild):
                self.id = id
                self.guild = guild
                self.members = [Member(100), Member(200)]
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

        guild = Guild(1)
        channel = Channel(10, guild)

        # User 100 heeft gestemd, 200 niet
        votes = {"100": {"vrijdag": ["om 19:00 uur"]}}

        async def fake_nonvoter_notification(*_args, **_kwargs):
            raise RuntimeError("boom")

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "get_setting", return_value={"modus": "deadline", "tijd": "18:00"}
            ),
            patch.object(scheduler, "send_non_voter_notification", side_effect=fake_nonvoter_notification),
        ):
            # Mag niet crashen, functie slikt de exception
            result = await scheduler.notify_non_voters(
                None, "vrijdag", cast(discord.TextChannel, channel)
            )

        # Assert: False returned because send failed, but no crash
        self.assertFalse(result)

    async def test_notify_voters_if_avond_gaat_door_with_participant_list_members_only(
        self,
    ):
        """Doorgaan-notificatie met deelnemerslijst: alleen leden."""

        class Member:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self.display_name = name
                self.global_name = name
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = [
                    Member(100, "Mario"),
                    Member(101, "Luigi"),
                    Member(102, "Peach"),
                    Member(103, "Daisy"),
                    Member(104, "Rosalina"),
                    Member(105, "Toad"),
                ]
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

            def get_member(self, member_id):
                channel = self.text_channels[0]
                for m in channel.members:
                    if m.id == member_id:
                        return m
                return None

            async def fetch_member(self, member_id):
                return self.get_member(member_id)

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 6 stemmen op vrijdag (drempel gehaald) - alleen leden
        votes = {str(i): {"vrijdag": ["om 19:00 uur"]} for i in range(100, 106)}

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_persistent_mention", new_callable=AsyncMock
            ) as mock_persistent,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Verify notification was sent
        mock_persistent.assert_awaited_once()

        # Check the message content
        args, kwargs = mock_persistent.call_args
        mentions_arg = args[1] if len(args) > 1 else kwargs.get("mentions", "")
        text_arg = args[2] if len(args) > 2 else kwargs.get("text", "")

        # All members should be mentioned
        for i in range(100, 106):
            self.assertIn(f"<@{i}>", mentions_arg)

        # Text should include participant count and list
        self.assertIn("Totaal 6 deelnemers:", text_arg)
        # Check voor Hammertime in plaats van "om 19:00"
        self.assertIn("De DMK-avond van vrijdag om <t:", text_arg)
        self.assertIn(":t> gaat door!", text_arg)

    async def test_notify_voters_if_avond_gaat_door_with_guests_only(self):
        """Doorgaan-notificatie: alleen gasten (host afwezig)."""

        class Member:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self.display_name = name
                self.global_name = name
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = [
                    Member(100, "Mario"),
                    Member(101, "Luigi"),
                    Member(102, "Peach"),
                    Member(103, "Daisy"),
                    Member(104, "Rosalina"),
                    Member(105, "Toad"),
                ]
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

            def get_member(self, member_id):
                channel = self.text_channels[0]
                for m in channel.members:
                    if m.id == member_id:
                        return m
                return None

            async def fetch_member(self, member_id):
                return self.get_member(member_id)

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # 6 gasten stemmen (host stemt niet) - 6 unieke owners, drempel gehaald
        votes = {
            "100_guest::Bowser": {"vrijdag": ["om 20:30 uur"]},
            "101_guest::Wario": {"vrijdag": ["om 20:30 uur"]},
            "102_guest::Waluigi": {"vrijdag": ["om 20:30 uur"]},
            "103_guest::Koopa Troopa": {"vrijdag": ["om 20:30 uur"]},
            "104_guest::Lakitu": {"vrijdag": ["om 20:30 uur"]},
            "105_guest::Shy Guy": {"vrijdag": ["om 20:30 uur"]},
        }

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_persistent_mention", new_callable=AsyncMock
            ) as mock_persistent,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Verify notification was sent
        mock_persistent.assert_awaited_once()

        # Check the message content
        args, kwargs = mock_persistent.call_args
        mentions_arg = args[1] if len(args) > 1 else kwargs.get("mentions", "")
        text_arg = args[2] if len(args) > 2 else kwargs.get("text", "")

        # No member mentions (only guests voted)
        self.assertEqual(mentions_arg, "")

        # Text should include all guests with "(gast)" suffix
        self.assertIn("Totaal 6 deelnemers:", text_arg)
        self.assertIn("Bowser (gast)", text_arg)
        self.assertIn("Wario (gast)", text_arg)
        self.assertIn("Waluigi (gast)", text_arg)
        # Check voor Hammertime in plaats van "om 20:30"
        self.assertIn("De DMK-avond van vrijdag om <t:", text_arg)
        self.assertIn(":t> gaat door!", text_arg)

    async def test_notify_voters_if_avond_gaat_door_with_members_and_guests(self):
        """Doorgaan-notificatie: leden + gasten gemengd."""

        class Member:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self.display_name = name
                self.global_name = name
                self.mention = f"<@{id}>"

        class Channel:
            def __init__(self, id, name="dmk"):
                self.id = id
                self.name = name
                self.members = [
                    Member(100, "Mario"),
                    Member(101, "Luigi"),
                    Member(102, "Peach"),
                    Member(103, "Daisy"),
                    Member(104, "Rosalina"),
                    Member(105, "Toad"),
                ]
                self.send = AsyncMock()

        class Guild:
            def __init__(self, id):
                self.id = id

            @property
            def text_channels(self):
                return [Channel(10)]

            def get_member(self, member_id):
                channel = self.text_channels[0]
                for m in channel.members:
                    if m.id == member_id:
                        return m
                return None

            async def fetch_member(self, member_id):
                return self.get_member(member_id)

        class Bot:
            def __init__(self):
                self.guilds = [Guild(1)]

        bot = Bot()

        # Gemengd: 4 leden + 5 gasten = 9 deelnemers (6 unieke owners)
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},  # Mario stemt
            "100_guest::GastVanMario": {"vrijdag": ["om 19:00 uur"]},  # Gast van Mario
            "101": {"vrijdag": ["om 19:00 uur"]},  # Luigi stemt
            "102": {"vrijdag": ["om 19:00 uur"]},  # Peach stemt
            "102_guest::GastVanPeach1": {
                "vrijdag": ["om 19:00 uur"]
            },  # Gast 1 van Peach
            "102_guest::GastVanPeach2": {
                "vrijdag": ["om 19:00 uur"]
            },  # Gast 2 van Peach
            "103": {"vrijdag": ["om 19:00 uur"]},  # Daisy stemt
            "104_guest::GastVanRosalina": {
                "vrijdag": ["om 19:00 uur"]
            },  # Gast van Rosalina (Rosalina stemt niet)
            "105_guest::GastVanToad": {
                "vrijdag": ["om 19:00 uur"]
            },  # Gast van Toad (Toad stemt niet)
        }

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999

        with (
            patch.object(scheduler, "load_votes", return_value=votes),
            patch.object(
                scheduler, "send_persistent_mention", new_callable=AsyncMock
            ) as mock_persistent,
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_voters_if_avond_gaat_door(bot, "vrijdag")

        # Verify notification was sent
        mock_persistent.assert_awaited_once()

        # Check the message content
        args, kwargs = mock_persistent.call_args
        mentions_arg = args[1] if len(args) > 1 else kwargs.get("mentions", "")
        text_arg = args[2] if len(args) > 2 else kwargs.get("text", "")

        # Members should be mentioned (Mario, Luigi, Peach, Daisy voted)
        self.assertIn("<@100>", mentions_arg)  # Mario
        self.assertIn("<@101>", mentions_arg)  # Luigi
        self.assertIn("<@102>", mentions_arg)  # Peach
        self.assertIn("<@103>", mentions_arg)  # Daisy

        # Text should include total count (4 members + 5 guests = 9)
        self.assertIn("Totaal 9 deelnemers:", text_arg)

        # Text should include members with mentions
        self.assertIn("<@100>", text_arg)
        self.assertIn("<@101>", text_arg)
        self.assertIn("<@102>", text_arg)
        self.assertIn("<@103>", text_arg)

        # Text should include guests with "(gast)" suffix
        self.assertIn("GastVanMario (gast)", text_arg)
        self.assertIn("GastVanPeach1 (gast)", text_arg)
        self.assertIn("GastVanPeach2 (gast)", text_arg)
        self.assertIn("GastVanRosalina (gast)", text_arg)
        self.assertIn("GastVanToad (gast)", text_arg)

        # Main message should be present with Hammertime
        self.assertIn("De DMK-avond van vrijdag om <t:", text_arg)
        self.assertIn(":t> gaat door!", text_arg)
