# tests/test_mention_utils.py

"""
Tests for mention utility functions (temporary and persistent mentions).
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.utils.mention_utils import (
    _delete_message_after_delay,
    _remove_mentions_after_delay,
    _remove_persistent_mentions_after_delay,
    send_persistent_mention,
    send_temporary_mention,
)


def _consume_coro_task():
    """
    Returns a side_effect for asyncio.create_task that safely closes the
    coroutine to avoid 'was never awaited' warnings during tests.
    """

    def _consume(coro, *args, **kwargs):
        try:
            coro.close()
        except RuntimeError:
            pass
        dummy = MagicMock()
        dummy.cancelled.return_value = False
        return dummy

    return _consume


class TemporaryMentionTestCase(unittest.IsolatedAsyncioTestCase):
    """Test temporary mention functionality."""

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_send_temporary_mention_basic(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_create_task
    ):
        """Test that temporary mention sends new message and schedules tasks."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_get_msg_id.return_value = None  # No previous message

        # Mock sent message
        mock_message = MagicMock()
        mock_message.id = 123
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        mentions = "@user1, @user2"
        text = "Please vote!"

        await send_temporary_mention(channel, mentions, text, delay=5.0)

        # Verify message was sent
        mock_safe_call.assert_called_once()
        call_args = mock_safe_call.call_args[0]
        self.assertEqual(call_args[0], channel.send)
        # Verify content includes mentions and text
        content = mock_safe_call.call_args[1]["content"]
        self.assertIn(mentions, content)
        self.assertIn(text, content)

        # Verify message ID was saved
        mock_save_msg_id.assert_called_once_with(456, "notification", 123)

        # Verify two tasks were created (privacy removal and auto-delete)
        self.assertEqual(mock_create_task.call_count, 2)

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_send_temporary_mention_deletes_previous(
        self,
        mock_safe_call,
        mock_fetch,
        mock_get_msg_id,
        mock_save_msg_id,
        mock_create_task,
    ):
        """Test that temporary mention deletes previous notification."""
        mock_create_task.side_effect = _consume_coro_task()

        # Mock previous message exists
        old_msg = MagicMock()
        old_msg.delete = AsyncMock()
        mock_get_msg_id.return_value = 999
        mock_fetch.return_value = old_msg

        # Mock new message
        new_msg = MagicMock()
        new_msg.id = 123
        mock_safe_call.return_value = new_msg

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        await send_temporary_mention(channel, "@user1", "Vote now!")

        # Verify old message was fetched and deleted
        mock_fetch.assert_called_once()
        self.assertEqual(mock_safe_call.call_count, 2)  # delete + send

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_send_temporary_mention_with_button(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_create_task
    ):
        """Test temporary mention with Stem Nu button."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_get_msg_id.return_value = None

        mock_message = MagicMock()
        mock_message.id = 123
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        await send_temporary_mention(
            channel,
            "@user1",
            "Vote now!",
            delay=5.0,
            show_button=True,
            dag="vrijdag",
            leading_time="19:00",
        )

        # Verify message was sent with button view
        mock_safe_call.assert_called_once()
        self.assertIsNotNone(mock_safe_call.call_args[1].get("view"))

        # Verify two tasks were created
        self.assertEqual(mock_create_task.call_count, 2)


class PersistentMentionTestCase(unittest.IsolatedAsyncioTestCase):
    """Test persistent mention functionality."""

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_send_persistent_mention_schedules_tasks(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_create_task
    ):
        """Test persistent mention schedules privacy removal and auto-delete."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_get_msg_id.return_value = None

        # Mock sent message
        mock_message = MagicMock()
        mock_message.id = 123
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        result = await send_persistent_mention(channel, "@user1 Test message")

        # Verify message was sent
        self.assertEqual(result, mock_message)
        mock_safe_call.assert_called_once()

        # Verify message ID was saved
        mock_save_msg_id.assert_called_once_with(456, "notification", 123)

        # Verify two tasks were scheduled (privacy removal + 5 hour delete)
        self.assertEqual(mock_create_task.call_count, 2)

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_send_persistent_mention_deletes_previous(
        self,
        mock_safe_call,
        mock_fetch,
        mock_get_msg_id,
        mock_save_msg_id,
        mock_create_task,
    ):
        """Test persistent mention deletes previous notification."""
        mock_create_task.side_effect = _consume_coro_task()

        # Mock previous message exists
        old_msg = MagicMock()
        old_msg.delete = AsyncMock()
        mock_get_msg_id.return_value = 999
        mock_fetch.return_value = old_msg

        # Mock new message
        new_msg = MagicMock()
        new_msg.id = 123
        mock_safe_call.return_value = new_msg

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        await send_persistent_mention(channel, "@user1 Test")

        # Verify old message was deleted
        mock_fetch.assert_called_once()
        self.assertEqual(mock_safe_call.call_count, 2)  # delete + send

    async def test_send_persistent_mention_no_send_method(self):
        """Test persistent mention with channel that has no send method."""
        channel = MagicMock(spec=[])  # No send attribute

        result = await send_persistent_mention(channel, "@user1 Test")

        # Should return None
        self.assertIsNone(result)

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_send_persistent_mention_returns_none_on_failure(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_create_task
    ):
        """Test persistent mention returns None when safe_call fails."""
        mock_get_msg_id.return_value = None
        mock_safe_call.return_value = None

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        result = await send_persistent_mention(channel, "@user1 Test")

        self.assertIsNone(result)


class RemoveMentionsTestCase(unittest.IsolatedAsyncioTestCase):
    """Test mention removal functionality."""

    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_remove_mentions_after_delay(self, mock_safe_call, mock_sleep):
        """Test that mentions are removed after delay."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        mock_view = MagicMock()

        await _remove_mentions_after_delay(
            mock_message, 5.0, "Please vote!", mock_view, True
        )

        # Verify sleep was called
        mock_sleep.assert_called_once_with(5.0)

        # Verify message was edited
        mock_safe_call.assert_called_once()
        call_kwargs = mock_safe_call.call_args[1]
        self.assertIn("content", call_kwargs)
        self.assertIn("Please vote!", call_kwargs["content"])
        self.assertEqual(call_kwargs["view"], mock_view)

    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_remove_persistent_mentions(self, mock_safe_call, mock_sleep):
        """Test that persistent mentions are removed."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "<@123456> <@!789012> Please respond"
        mock_message.edit = AsyncMock()

        await _remove_persistent_mentions_after_delay(mock_message, 5.0)

        # Verify sleep was called
        mock_sleep.assert_called_once_with(5.0)

        # Verify safe_call was called with edit function and cleaned content
        mock_safe_call.assert_called_once()
        call_kwargs = mock_safe_call.call_args[1]
        self.assertIn("content", call_kwargs)
        cleaned_content = call_kwargs["content"]
        self.assertIn("Please respond", cleaned_content)
        self.assertNotIn("<@123456>", cleaned_content)
        self.assertNotIn("<@!789012>", cleaned_content)

    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_remove_mentions_removes_role_mentions(
        self, mock_safe_call, mock_sleep
    ):
        """Test that cleanup removes role mentions."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "<@&123456> Important announcement"
        mock_message.edit = AsyncMock()

        await _remove_persistent_mentions_after_delay(mock_message, 5.0)

        mock_safe_call.assert_called_once()
        # Verify role mention was removed
        call_args = str(mock_safe_call.call_args)
        self.assertNotIn("<@&", call_args)

    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_remove_mentions_removes_everyone_here(
        self, mock_safe_call, mock_sleep
    ):
        """Test that cleanup removes @everyone and @here mentions."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = "@everyone @here Important message"
        mock_message.edit = AsyncMock()

        await _remove_persistent_mentions_after_delay(mock_message, 5.0)

        mock_safe_call.assert_called_once()
        # Verify @everyone and @here were removed
        call_args = str(mock_safe_call.call_args)
        self.assertNotIn("@everyone", call_args)
        self.assertNotIn("@here", call_args)


class DeleteMessageTestCase(unittest.IsolatedAsyncioTestCase):
    """Test message deletion functionality."""

    @patch("apps.utils.poll_message.clear_message_id")
    @patch("asyncio.sleep")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_delete_message_after_delay(
        self, mock_safe_call, mock_sleep, mock_clear
    ):
        """Test that message is deleted after delay."""
        mock_sleep.return_value = AsyncMock()
        mock_safe_call.return_value = AsyncMock()

        mock_message = MagicMock()
        mock_message.delete = AsyncMock()

        await _delete_message_after_delay(mock_message, 3600.0, 456)

        # Verify sleep was called
        mock_sleep.assert_called_once_with(3600.0)

        # Verify message was deleted
        mock_safe_call.assert_called_once()

        # Verify message ID was cleared
        mock_clear.assert_called_once_with(456, "notification")


if __name__ == "__main__":
    unittest.main()
