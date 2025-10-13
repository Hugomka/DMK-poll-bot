# tests/test_scheduler_pause.py

"""
Tests for pause functionality in scheduler tasks.
Verifies that all notification functions respect the pause state.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.scheduler import (
    convert_remaining_misschien,
    notify_misschien_voters,
    notify_non_voters,
    notify_non_voters_thursday,
    notify_voters_if_avond_gaat_door,
    update_all_polls,
)
from apps.utils.message_builder import build_poll_message_for_day_async


class SchedulerPauseTestCase(unittest.IsolatedAsyncioTestCase):
    """Test that pause blocks all scheduler notification functions."""

    def setUp(self):
        """Set up common mocks for all tests."""
        # Mock bot with guild and channel
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_channel = MagicMock()

        self.mock_guild.id = 123
        self.mock_channel.id = 456
        self.mock_channel.name = "test-channel"
        self.mock_channel.guild = self.mock_guild
        self.mock_channel.members = []
        self.mock_channel.send = AsyncMock()

        self.mock_guild.channels = [self.mock_channel]
        self.mock_bot.guilds = [self.mock_guild]

    @patch("apps.scheduler.is_paused")
    @patch("apps.scheduler.is_channel_disabled")
    @patch("apps.scheduler.get_channels")
    @patch("apps.scheduler.load_votes")
    @patch("apps.scheduler.log_job")
    async def test_notify_non_voters_thursday_skips_paused_channel(
        self, mock_log_job, mock_load_votes, mock_get_channels, mock_disabled, mock_paused
    ):
        """Test that notify_non_voters_thursday skips paused channels."""
        mock_get_channels.return_value = [self.mock_channel]
        mock_disabled.return_value = False
        mock_paused.return_value = True  # Channel is paused
        mock_load_votes.return_value = {}

        await notify_non_voters_thursday(self.mock_bot)

        # Verify send was never called because channel is paused
        self.mock_channel.send.assert_not_called()


    @patch("apps.scheduler.is_paused")
    @patch("apps.scheduler.is_channel_disabled")
    @patch("apps.scheduler.get_channels")
    @patch("apps.scheduler.get_message_id")
    @patch("apps.utils.poll_message.update_poll_message")
    @patch("apps.scheduler.log_job")
    async def test_update_all_polls_skips_paused_channel(
        self, mock_log_job, mock_update, mock_get_msg_id, mock_get_channels, mock_disabled, mock_paused
    ):
        """Test that update_all_polls skips paused channels."""
        mock_get_channels.return_value = [self.mock_channel]
        mock_disabled.return_value = False
        mock_paused.return_value = True  # Channel is paused
        mock_get_msg_id.return_value = 999  # Has poll message
        mock_update.return_value = AsyncMock()

        await update_all_polls(self.mock_bot)

        # Verify update_poll_message was never called because channel is paused
        mock_update.assert_not_called()

    @patch("apps.scheduler.is_paused")
    @patch("apps.scheduler.is_channel_disabled")
    @patch("apps.scheduler.get_channels")
    @patch("apps.scheduler.load_votes")
    async def test_notify_non_voters_skips_paused_channel_in_scheduler_mode(
        self, mock_load_votes, mock_get_channels, mock_disabled, mock_paused
    ):
        """Test that notify_non_voters skips paused channels in scheduler mode."""
        mock_get_channels.return_value = [self.mock_channel]
        mock_disabled.return_value = False
        mock_paused.return_value = True  # Channel is paused
        mock_load_votes.return_value = {}

        # Call without channel parameter = scheduler mode
        await notify_non_voters(self.mock_bot, channel=None)

        # Verify send was never called because channel is paused
        self.mock_channel.send.assert_not_called()


    @patch("apps.scheduler.is_paused")
    @patch("apps.scheduler.is_channel_disabled")
    @patch("apps.scheduler.get_channels")
    @patch("apps.scheduler.load_votes")
    @patch("apps.scheduler.log_job")
    async def test_notify_voters_if_avond_gaat_door_skips_paused_channel(
        self, mock_log_job, mock_load_votes, mock_get_channels, mock_disabled, mock_paused
    ):
        """Test that notify_voters_if_avond_gaat_door skips paused channels."""
        mock_get_channels.return_value = [self.mock_channel]
        mock_disabled.return_value = False
        mock_paused.return_value = True  # Channel is paused
        mock_load_votes.return_value = {}

        await notify_voters_if_avond_gaat_door(self.mock_bot, "vrijdag")

        # Verify send was never called because channel is paused
        self.mock_channel.send.assert_not_called()

    @patch("apps.scheduler.is_paused")
    @patch("apps.scheduler.is_channel_disabled")
    @patch("apps.scheduler.get_channels")
    @patch("apps.scheduler.load_votes")
    @patch("apps.scheduler.log_job")
    async def test_notify_misschien_voters_skips_paused_channel(
        self, mock_log_job, mock_load_votes, mock_get_channels, mock_disabled, mock_paused
    ):
        """Test that notify_misschien_voters skips paused channels."""
        mock_get_channels.return_value = [self.mock_channel]
        mock_disabled.return_value = False
        mock_paused.return_value = True  # Channel is paused
        mock_load_votes.return_value = {}

        await notify_misschien_voters(self.mock_bot, "vrijdag")

        # Verify send was never called because channel is paused
        self.mock_channel.send.assert_not_called()

    @patch("apps.scheduler.is_paused")
    @patch("apps.scheduler.is_channel_disabled")
    @patch("apps.scheduler.get_channels")
    @patch("apps.scheduler.load_votes")
    @patch("apps.scheduler.get_message_id")
    @patch("apps.scheduler.log_job")
    async def test_convert_remaining_misschien_skips_paused_channel(
        self,
        mock_log_job,
        mock_get_msg_id,
        mock_load_votes,
        mock_get_channels,
        mock_disabled,
        mock_paused,
    ):
        """Test that convert_remaining_misschien skips paused channels."""
        mock_get_channels.return_value = [self.mock_channel]
        mock_disabled.return_value = False
        mock_paused.return_value = True  # Channel is paused
        mock_get_msg_id.return_value = 999  # Has poll
        mock_load_votes.return_value = {}  # Empty votes, so nothing to convert anyway

        await convert_remaining_misschien(self.mock_bot, "vrijdag")

        # If not paused, load_votes would be called; since paused, it should still be called
        # but no further processing should happen (no saves, no updates)
        # The key assertion is that the channel was skipped due to pause
        mock_load_votes.assert_not_called()  # Not even loaded because channel is paused


class PollMessagePauseTestCase(unittest.IsolatedAsyncioTestCase):
    """Test that pause message is shown in poll embeds."""

    @patch("apps.utils.message_builder.get_counts_for_day")
    async def test_poll_message_shows_pause_indicator(self, mock_counts):
        """Test that poll message includes pause indicator when paused."""
        mock_counts.return_value = {}

        message = await build_poll_message_for_day_async(
            "vrijdag",
            guild_id=123,
            channel_id=456,
            hide_counts=False,
            pauze=True,
        )

        # Verify that the pause indicator is in the message
        self.assertIn("Gepauzeerd", message)
        self.assertIn("vrijdag", message.lower())

    @patch("apps.utils.message_builder.get_counts_for_day")
    async def test_poll_message_no_pause_indicator_when_not_paused(self, mock_counts):
        """Test that poll message does NOT include pause indicator when not paused."""
        mock_counts.return_value = {}

        message = await build_poll_message_for_day_async(
            "vrijdag",
            guild_id=123,
            channel_id=456,
            hide_counts=False,
            pauze=False,
        )

        # Verify that the pause indicator is NOT in the message
        self.assertNotIn("Gepauzeerd", message)
        self.assertIn("vrijdag", message.lower())


if __name__ == "__main__":
    unittest.main()
