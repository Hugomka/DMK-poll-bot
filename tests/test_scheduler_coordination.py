# tests/test_scheduler_coordination.py
"""
Tests voor coördinatie tussen reset_polls en activate_scheduled_polls.

Voorkomt dubbele @everyone notificaties wanneer beide jobs gelijktijdig
draaien op dinsdag 20:00.
"""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytz

from apps import scheduler
from tests.base import BaseTestCase

TZ = pytz.timezone("Europe/Amsterdam")


class Channel:
    def __init__(self, id):
        self.id = id


class Guild:
    def __init__(self):
        self.id = 1

    @property
    def text_channels(self):
        return [Channel(10)]


class Bot:
    def __init__(self):
        self.guilds = [Guild()]


def fake_get_channels(guild):
    return guild.text_channels


class ResetSkipsActivatedChannelTestCase(BaseTestCase):
    """reset_polls slaat kanalen over die al door activate_scheduled_polls zijn afgehandeld."""

    async def test_reset_polls_skips_channel_already_activated(self):
        """Als activate_scheduled_polls kanaal 10 al heeft geactiveerd,
        moet reset_polls dat kanaal overslaan (geen dubbele @everyone)."""
        bot = Bot()
        state = {
            "activated_channels_this_reset": {"10": "2024-05-28T20:00:01"},
        }

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "reset_votes_scoped", new_callable=AsyncMock) as mock_rvs,
            patch.object(scheduler, "clear_message_id", side_effect=lambda *a: None),
            patch.object(scheduler, "send_temporary_mention", new_callable=AsyncMock) as mock_mention,
        ):
            result = await scheduler.reset_polls(bot)

        self.assertTrue(result)
        # reset_votes_scoped mag NIET aangeroepen zijn (activate deed dit al)
        mock_rvs.assert_not_awaited()
        # send_temporary_mention mag NIET aangeroepen zijn (geen dubbele @everyone)
        mock_mention.assert_not_awaited()

    async def test_reset_polls_proceeds_for_non_activated_channel(self):
        """Kanalen die NIET door activate_scheduled_polls zijn afgehandeld,
        worden normaal gereset."""
        bot = Bot()
        state = {
            "activated_channels_this_reset": {"99": "2024-05-28T20:00:01"},
        }

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "reset_votes_scoped", new_callable=AsyncMock) as mock_rvs,
            patch.object(scheduler, "clear_message_id", side_effect=lambda *a: None),
            patch.object(scheduler, "send_temporary_mention", new_callable=AsyncMock) as mock_mention,
        ):
            result = await scheduler.reset_polls(bot)

        self.assertTrue(result)
        mock_rvs.assert_awaited_once_with(1, 10)
        mock_mention.assert_awaited_once()

    async def test_reset_polls_clears_coordination_state(self):
        """reset_polls ruimt activated_channels_this_reset op na afloop."""
        bot = Bot()
        state = {
            "activated_channels_this_reset": {"10": "2024-05-28T20:00:01"},
        }
        written_states = []

        def capture_write(s):
            written_states.append(dict(s))

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state", side_effect=capture_write),
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "reset_votes_scoped", new_callable=AsyncMock),
            patch.object(scheduler, "clear_message_id", side_effect=lambda *a: None),
            patch.object(scheduler, "send_temporary_mention", new_callable=AsyncMock),
        ):
            await scheduler.reset_polls(bot)

        # Laatste geschreven state mag geen activated_channels_this_reset bevatten
        self.assertTrue(len(written_states) > 0)
        final_state = written_states[-1]
        self.assertNotIn("activated_channels_this_reset", final_state)
        self.assertIn("reset_polls", final_state)

    async def test_reset_polls_no_coordination_state_proceeds_normally(self):
        """Zonder activated_channels_this_reset (legacy/geen periods), reset normaal."""
        bot = Bot()
        state = {}  # Geen coördinatie-state

        with (
            patch.object(scheduler, "_within_reset_window", return_value=True),
            patch.object(scheduler, "_read_state", return_value=state),
            patch.object(scheduler, "_write_state", lambda s: None),
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "reset_votes_scoped", new_callable=AsyncMock) as mock_rvs,
            patch.object(scheduler, "clear_message_id", side_effect=lambda *a: None),
            patch.object(scheduler, "send_temporary_mention", new_callable=AsyncMock) as mock_mention,
        ):
            result = await scheduler.reset_polls(bot)

        self.assertTrue(result)
        mock_rvs.assert_awaited_once_with(1, 10)
        mock_mention.assert_awaited_once()
