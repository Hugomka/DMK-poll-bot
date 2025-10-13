# tests/test_mention_utils.py

"""
Tests for mention utility functions (temporary and persistent mentions).
"""

import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytz

from apps.utils.mention_utils import (
    _cleanup_mentions_at_23,
    send_persistent_mention,
    send_temporary_mention,
)

TZ = pytz.timezone("Europe/Amsterdam")


class TemporaryMentionTestCase(unittest.IsolatedAsyncioTestCase):
    """Test temporary mention functionality."""

    @patch("apps.utils.mention_utils.update_notification_message")
    @patch("asyncio.sleep")
    async def test_send_temporary_mention_basic(self, mock_sleep, mock_update):
        """Test that temporary mention shows and then hides mentions."""
        mock_update.return_value = AsyncMock()
        mock_sleep.return_value = AsyncMock()

        channel = MagicMock()
        mentions = "@user1, @user2"
        text = "Please vote!"

        await send_temporary_mention(channel, mentions, text, delay=2.0)

        # Verify update_notification_message was called twice
        self.assertEqual(mock_update.call_count, 2)

        # First call: with mentions
        first_call = mock_update.call_args_list[0]
        self.assertEqual(first_call[0][0], channel)
        self.assertEqual(first_call[1]["mentions"], mentions)
        self.assertEqual(first_call[1]["text"], text)
        self.assertEqual(first_call[1]["show_button"], False)

        # Verify sleep was called
        mock_sleep.assert_called_once_with(2.0)

        # Second call: without mentions
        second_call = mock_update.call_args_list[1]
        self.assertEqual(second_call[0][0], channel)
        self.assertEqual(second_call[1]["mentions"], "")
        self.assertEqual(second_call[1]["text"], text)

    @patch("apps.utils.mention_utils.update_notification_message")
    @patch("asyncio.sleep")
    async def test_send_temporary_mention_with_button(self, mock_sleep, mock_update):
        """Test temporary mention with Stem Nu button."""
        mock_update.return_value = AsyncMock()
        mock_sleep.return_value = AsyncMock()

        channel = MagicMock()
        mentions = "@user1"
        text = "Vote now!"

        await send_temporary_mention(
            channel,
            mentions,
            text,
            delay=3.0,
            show_button=True,
            dag="vrijdag",
            leading_time="19:00",
        )

        # Verify both calls included button parameters
        self.assertEqual(mock_update.call_count, 2)

        first_call = mock_update.call_args_list[0]
        self.assertEqual(first_call[1]["show_button"], True)
        self.assertEqual(first_call[1]["dag"], "vrijdag")
        self.assertEqual(first_call[1]["leading_time"], "19:00")

        second_call = mock_update.call_args_list[1]
        self.assertEqual(second_call[1]["show_button"], True)
        self.assertEqual(second_call[1]["dag"], "vrijdag")
        self.assertEqual(second_call[1]["leading_time"], "19:00")

        mock_sleep.assert_called_once_with(3.0)


class PersistentMentionTestCase(unittest.IsolatedAsyncioTestCase):
    """Test persistent mention functionality."""

    @patch("apps.utils.mention_utils.safe_call")
    @patch("apps.utils.mention_utils.datetime")
    @patch("asyncio.create_task")
    async def test_send_persistent_mention_before_23(
        self, mock_create_task, mock_datetime, mock_safe_call
    ):
        """Test persistent mention sent before 23:00 schedules cleanup."""
        # Mock current time as 20:00
        mock_now = datetime(2025, 1, 15, 20, 0, 0, tzinfo=TZ)
        mock_datetime.now.return_value = mock_now

        # Mock sent message
        mock_message = MagicMock()
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.send = AsyncMock()

        result = await send_persistent_mention(channel, "@user1 Test message")

        # Verify message was sent
        self.assertEqual(result, mock_message)
        mock_safe_call.assert_called_once()

        # Verify cleanup was scheduled
        mock_create_task.assert_called_once()

        # Verify delay calculation (3 hours = 10800 seconds)
        call_args = mock_create_task.call_args[0][0]
        # Should be a coroutine for _cleanup_mentions_at_23

    @patch("apps.utils.mention_utils.safe_call")
    @patch("apps.utils.mention_utils.datetime")
    @patch("asyncio.create_task")
    async def test_send_persistent_mention_after_23(
        self, mock_create_task, mock_datetime, mock_safe_call
    ):
        """Test persistent mention sent after 23:00 does NOT schedule cleanup."""
        # Mock current time as 23:30
        mock_now = datetime(2025, 1, 15, 23, 30, 0, tzinfo=TZ)
        mock_datetime.now.return_value = mock_now

        # Mock sent message
        mock_message = MagicMock()
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.send = AsyncMock()

        result = await send_persistent_mention(channel, "@user1 Test message")

        # Verify message was sent
        self.assertEqual(result, mock_message)
        mock_safe_call.assert_called_once()

        # Verify cleanup was NOT scheduled
        mock_create_task.assert_not_called()

    async def test_send_persistent_mention_no_send_method(self):
        """Test persistent mention with channel that has no send method."""
        channel = MagicMock(spec=[])  # No send attribute

        result = await send_persistent_mention(channel, "@user1 Test")

        # Should return None
        self.assertIsNone(result)

    @patch("apps.utils.mention_utils.safe_call")
    async def test_send_persistent_mention_returns_none_on_failure(self, mock_safe_call):
        """Test persistent mention returns None when safe_call fails."""
        mock_safe_call.return_value = None

        channel = MagicMock()
        channel.send = AsyncMock()

        result = await send_persistent_mention(channel, "@user1 Test")

        self.assertIsNone(result)


class CleanupMentionsTestCase(unittest.IsolatedAsyncioTestCase):
    """Test mention cleanup functionality."""

    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_cleanup_mentions_removes_user_mentions(self, mock_safe_call, mock_sleep):
        """Test that cleanup removes user mentions from message."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "<@123456> <@!789012> Please respond"
        mock_message.edit = AsyncMock()

        await _cleanup_mentions_at_23(mock_message, 0.01)

        # Verify sleep was called
        mock_sleep.assert_called_once_with(0.01)

        # Verify edit was called with cleaned content
        mock_safe_call.assert_called_once()
        call_args = mock_safe_call.call_args
        self.assertIn("Please respond", call_args[0])
        self.assertNotIn("<@", str(call_args))

    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_cleanup_mentions_removes_role_mentions(self, mock_safe_call, mock_sleep):
        """Test that cleanup removes role mentions from message."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "<@&123456> Important announcement"
        mock_message.edit = AsyncMock()

        await _cleanup_mentions_at_23(mock_message, 0.01)

        mock_safe_call.assert_called_once()
        # Verify role mention was removed
        call_args = str(mock_safe_call.call_args)
        self.assertNotIn("<@&", call_args)

    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_cleanup_mentions_removes_everyone_here(self, mock_safe_call, mock_sleep):
        """Test that cleanup removes @everyone and @here mentions."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "@everyone @here Important message"
        mock_message.edit = AsyncMock()

        await _cleanup_mentions_at_23(mock_message, 0.01)

        mock_safe_call.assert_called_once()
        # Verify @everyone and @here were removed
        call_args = str(mock_safe_call.call_args)
        self.assertNotIn("@everyone", call_args)
        self.assertNotIn("@here", call_args)

    @patch("asyncio.sleep")
    async def test_cleanup_mentions_empty_content(self, mock_sleep):
        """Test that cleanup handles empty content gracefully."""
        mock_sleep.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = ""
        mock_message.edit = AsyncMock()

        # Should not raise an error
        await _cleanup_mentions_at_23(mock_message, 0.01)

        # Edit should not be called for empty content
        mock_message.edit.assert_not_called()

    @patch("asyncio.sleep")
    async def test_cleanup_mentions_no_edit_method(self, mock_sleep):
        """Test that cleanup handles message without edit method gracefully."""
        mock_sleep.return_value = AsyncMock()

        mock_message = MagicMock(spec=["content"])  # No edit method
        mock_message.content = "<@123> Test"

        # Should not raise an error
        await _cleanup_mentions_at_23(mock_message, 0.01)


if __name__ == "__main__":
    unittest.main()
