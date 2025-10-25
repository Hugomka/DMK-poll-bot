# tests/test_scheduler_misschien_flow.py
#
# Unit tests voor Misschien Confirmation Flow (17:00-18:00)

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from apps import scheduler
from tests.base import BaseTestCase


class TestSchedulerMisschienFlow(BaseTestCase):
    """Tests voor Misschien notification en conversie flow."""

    async def test_notify_misschien_voters_basic(self):
        """Test notify_misschien_voters vindt misschien voters en stuurt notificatie."""

        # Mock setup
        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
                SimpleNamespace(id=200, bot=False, mention="<@200>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft "misschien" gestemd, user 200 heeft "om 19:00 uur" gestemd
        votes = {
            "100": {"vrijdag": ["misschien"]},
            "200": {"vrijdag": ["om 19:00 uur"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(
                scheduler, "load_votes", new_callable=AsyncMock, return_value=votes
            ),
            patch.object(
                scheduler,
                "calculate_leading_time",
                new_callable=AsyncMock,
                return_value="19:00",
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_misschien_voters(bot, "vrijdag")

        # Assert: send_temporary_mention aangeroepen met button
        mock_mention.assert_awaited_once()
        args, kwargs = mock_mention.call_args

        # Check mentions bevat user 100 (misschien voter)
        mentions = kwargs.get("mentions", args[1] if len(args) > 1 else "")
        self.assertIn("<@100>", mentions)
        self.assertNotIn("<@200>", mentions)  # User 200 heeft al gestemd

        # Check button parameters
        self.assertTrue(kwargs.get("show_button", False))
        self.assertEqual(kwargs.get("dag", ""), "vrijdag")
        self.assertEqual(kwargs.get("leading_time", ""), "19:00")

    async def test_notify_misschien_voters_no_misschien_voters(self):
        """Test notify_misschien_voters stuurt niks als er geen misschien voters zijn."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft al gestemd voor een tijd
        votes = {
            "100": {"vrijdag": ["om 19:00 uur"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(
                scheduler, "load_votes", new_callable=AsyncMock, return_value=votes
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_misschien_voters(bot, "vrijdag")

        # Assert: geen notificatie verstuurd
        mock_mention.assert_not_awaited()

    async def test_notify_misschien_voters_no_leading_time(self):
        """Test notify_misschien_voters skipt als er geen duidelijke winnaar is."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft misschien gestemd
        votes = {
            "100": {"vrijdag": ["misschien"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(
                scheduler, "load_votes", new_callable=AsyncMock, return_value=votes
            ),
            patch.object(
                scheduler,
                "calculate_leading_time",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_misschien_voters(bot, "vrijdag")

        # Assert: geen notificatie als er geen leading time is
        mock_mention.assert_not_awaited()

    async def test_convert_remaining_misschien_converts_to_niet_meedoen(self):
        """Test convert_remaining_misschien converteert misschien naar niet meedoen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
        )
        bot.guilds = [guild]

        # User 100 heeft nog steeds misschien
        votes = {
            "100": {"vrijdag": ["misschien"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        mock_remove = AsyncMock()
        mock_add = AsyncMock()

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(
                scheduler, "load_votes", new_callable=AsyncMock, return_value=votes
            ),
            patch("apps.utils.poll_storage.remove_vote", mock_remove),
            patch("apps.utils.poll_storage.add_vote", mock_add),
            patch.object(scheduler, "schedule_poll_update", new_callable=AsyncMock),
            patch(
                "apps.utils.poll_message.update_notification_message",
                new_callable=AsyncMock,
            ),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.convert_remaining_misschien(bot, "vrijdag")

        # Assert: remove_vote aangeroepen voor "misschien"
        mock_remove.assert_awaited_once()
        remove_args = mock_remove.call_args[0]
        self.assertEqual(remove_args[0], "100")  # user_id
        self.assertEqual(remove_args[1], "vrijdag")  # dag
        self.assertEqual(remove_args[2], "misschien")  # tijd

        # Assert: add_vote aangeroepen voor "niet meedoen"
        mock_add.assert_awaited_once()
        add_args = mock_add.call_args[0]
        self.assertEqual(add_args[0], "100")  # user_id
        self.assertEqual(add_args[1], "vrijdag")  # dag
        self.assertEqual(add_args[2], "niet meedoen")  # tijd

    async def test_convert_remaining_misschien_clears_button(self):
        """Test convert_remaining_misschien verwijdert notificatiebericht."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
        )
        bot.guilds = [guild]

        # Geen misschien voters, maar check of notification wordt verwijderd
        votes = {}

        def fake_get_channels(g):
            return [channel] if g == guild else []

        mock_fetch_message = AsyncMock()
        mock_message = MagicMock()
        mock_message.delete = AsyncMock()
        mock_fetch_message.return_value = mock_message
        mock_safe_call = AsyncMock()

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(
                scheduler, "load_votes", new_callable=AsyncMock, return_value=votes
            ),
            patch(
                "apps.utils.discord_client.fetch_message_or_none", mock_fetch_message
            ),
            patch.object(scheduler, "safe_call", mock_safe_call),
            patch.object(scheduler, "clear_message_id") as mock_clear,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.convert_remaining_misschien(bot, "vrijdag")

        # Assert: notification bericht werd opgehaald en verwijderd
        mock_fetch_message.assert_awaited_once_with(channel, 999)
        mock_safe_call.assert_awaited_once()
        mock_clear.assert_called_once_with(10, "notification")

    async def test_notify_misschien_voters_handles_guest_votes(self):
        """Test notify_misschien_voters extraheert eigenaar van gastenstemmen correct."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft misschien gestemd, inclusief als gast
        votes = {
            "100": {"vrijdag": ["misschien"]},
            "100_guest::Mario": {"vrijdag": ["misschien"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(
                scheduler, "load_votes", new_callable=AsyncMock, return_value=votes
            ),
            patch.object(
                scheduler,
                "calculate_leading_time",
                new_callable=AsyncMock,
                return_value="19:00",
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_misschien_voters(bot, "vrijdag")

        # Assert: mention bevat user 100 slechts één keer (niet dubbel voor gast)
        mock_mention.assert_awaited_once()
        args, kwargs = mock_mention.call_args
        mentions = kwargs.get("mentions", args[1] if len(args) > 1 else "")

        # Count occurrences of <@100>
        count = mentions.count("<@100>")
        self.assertEqual(
            count, 1, f"Expected <@100> to appear once, but found {count} times"
        )
