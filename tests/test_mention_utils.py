# tests/test_mention_utils.py

"""
Tests for mention utility functions (temporary and persistent mentions).
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.utils.mention_utils import (
    _delete_message_after_delay,
    _remove_mentions_after_delay,
    render_notification_content,
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


class RenderNotificationContentTestCase(unittest.TestCase):
    """Test render_notification_content function."""

    def test_render_with_all_parts(self):
        """Test rendering with all parts (heading, mentions, text, footer)."""
        result = render_notification_content(
            heading=":mega: Notificatie:",
            mentions="@user1 @user2",
            text="Please vote now!",
            footer="Thank you!",
        )
        self.assertEqual(
            result,
            ":mega: Notificatie:\n@user1 @user2\nPlease vote now!\nThank you!",
        )

    def test_render_without_mentions(self):
        """Test that empty mentions are omitted (no comma artifacts)."""
        result = render_notification_content(
            heading=":mega: Notificatie:",
            mentions=None,
            text="Please vote now!",
            footer=None,
        )
        self.assertEqual(result, ":mega: Notificatie:\nPlease vote now!")
        # Verify no empty lines or commas
        self.assertNotIn("\n\n", result)
        self.assertNotIn(", ,", result)

    def test_render_with_empty_string_mentions(self):
        """Test that empty string mentions are omitted."""
        result = render_notification_content(
            heading=":mega: Notificatie:",
            mentions="",
            text="Vote!",
            footer=None,
        )
        self.assertEqual(result, ":mega: Notificatie:\nVote!")

    def test_render_strips_whitespace(self):
        """Test that whitespace is properly stripped."""
        result = render_notification_content(
            heading=":mega: Notificatie:",
            mentions="  @user1  ",
            text="  Vote!  ",
            footer="  Thanks!  ",
        )
        self.assertEqual(result, ":mega: Notificatie:\n@user1\nVote!\nThanks!")

    def test_render_only_heading(self):
        """Test rendering with only heading."""
        result = render_notification_content(
            heading=":mega: Notificatie:",
            mentions=None,
            text=None,
            footer=None,
        )
        self.assertEqual(result, ":mega: Notificatie:")


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

        # Verify message ID was saved with correct key for temporary notification
        mock_save_msg_id.assert_called_once_with(456, "notification_temp", 123)

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
        """Test persistent mention schedules auto-delete only (no mention removal)."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_get_msg_id.return_value = None

        # Mock sent message
        mock_message = MagicMock()
        mock_message.id = 123
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        result = await send_persistent_mention(channel, "@user1", "Test message")

        # Verify message was sent
        self.assertEqual(result, mock_message)
        mock_safe_call.assert_called_once()

        # Verify content uses unified renderer (no comma artifacts)
        # safe_call is called with (channel.send, content)
        call_args = mock_safe_call.call_args
        # The content is passed as the first positional arg after the function
        if len(call_args[0]) > 1:
            content = call_args[0][1]
        else:
            # Or as keyword arg
            content = call_args[1].get("content", call_args[0][0])

        self.assertIn(":mega: Notificatie:", content)
        self.assertIn("@user1", content)
        self.assertIn("Test message", content)
        self.assertNotIn("\n\n", content)  # No empty lines

        # Verify message ID was saved with correct key for persistent notification
        mock_save_msg_id.assert_called_once_with(456, "notification_persistent", 123)

        # Verify only one task was scheduled (5 hour delete only, no mention removal)
        self.assertEqual(mock_create_task.call_count, 1)

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

        await send_persistent_mention(channel, "@user1", "Test")

        # Verify old message was deleted
        mock_fetch.assert_called_once()
        self.assertEqual(mock_safe_call.call_count, 2)  # delete + send

    async def test_send_persistent_mention_no_send_method(self):
        """Test persistent mention with channel that has no send method."""
        channel = MagicMock(spec=[])  # No send attribute

        result = await send_persistent_mention(channel, "@user1", "Test")

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

        result = await send_persistent_mention(channel, "@user1", "Test")

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

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_persistent_mentions_not_removed(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_create_task
    ):
        """Test that persistent mentions are NOT removed after 5 seconds."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_get_msg_id.return_value = None

        # Mock sent message
        mock_message = MagicMock()
        mock_message.id = 123
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        mentions = "@user1 @user2"
        text = "De avond gaat door!"

        result = await send_persistent_mention(channel, mentions, text)

        # Verify message was sent
        self.assertEqual(result, mock_message)
        mock_safe_call.assert_called_once()

        # Verify content includes mentions
        call_args = mock_safe_call.call_args
        if len(call_args[0]) > 1:
            content = call_args[0][1]
        else:
            content = call_args[1].get("content", call_args[0][0])

        self.assertIn(mentions, content)
        self.assertIn(text, content)

        # Verify only ONE task was created (auto-delete only, no mention removal)
        self.assertEqual(mock_create_task.call_count, 1)

        # Verify the task is for deletion (5 hours = 18000 seconds)
        task_call = mock_create_task.call_args[0][0]
        # The coroutine should be _delete_message_after_delay
        self.assertIn("_delete_message_after_delay", str(task_call))

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_persistent_mentions_kept_until_deletion(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_create_task
    ):
        """Test that persistent mentions remain visible until the 5-hour auto-delete."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_get_msg_id.return_value = None

        mock_message = MagicMock()
        mock_message.id = 123
        mock_safe_call.return_value = mock_message

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        mentions = "@guest1 @guest2 @regular"
        text = "Important announcement"

        await send_persistent_mention(channel, mentions, text)

        # Verify content has mentions (not removed)
        call_args = mock_safe_call.call_args
        if len(call_args[0]) > 1:
            content = call_args[0][1]
        else:
            content = call_args[1].get("content", call_args[0][0])

        # Mentions should be present in the original message
        self.assertIn("@guest1", content)
        self.assertIn("@guest2", content)
        self.assertIn("@regular", content)
        self.assertIn("Important announcement", content)

        # Only auto-delete task should be scheduled (not mention removal)
        self.assertEqual(mock_create_task.call_count, 1)


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

        await _delete_message_after_delay(mock_message, 3600.0, 456, "notification_temp")

        # Verify sleep was called
        mock_sleep.assert_called_once_with(3600.0)

        # Verify message was deleted
        mock_safe_call.assert_called_once()

        # Verify message ID was cleared with correct key
        mock_clear.assert_called_once_with(456, "notification_temp")


class SeparateKeyTestCase(unittest.IsolatedAsyncioTestCase):
    """Test that temporary and persistent notifications use separate keys."""

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_temporary_and_persistent_use_different_keys(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_create_task
    ):
        """Test that sending temporary mention doesn't affect persistent mention."""
        mock_create_task.side_effect = _consume_coro_task()

        # Mock that there's no previous message for either key
        mock_get_msg_id.return_value = None

        # Mock message creation
        mock_temp_msg = MagicMock()
        mock_temp_msg.id = 111
        mock_persistent_msg = MagicMock()
        mock_persistent_msg.id = 222

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        # Send persistent mention first
        mock_safe_call.return_value = mock_persistent_msg
        await send_persistent_mention(channel, "@user1", "Persistent message")

        # Verify persistent key was used
        persistent_call = mock_save_msg_id.call_args
        self.assertEqual(persistent_call[0], (456, "notification_persistent", 222))

        # Reset mocks
        mock_save_msg_id.reset_mock()
        mock_get_msg_id.reset_mock()

        # Now send temporary mention
        mock_safe_call.return_value = mock_temp_msg
        mock_get_msg_id.return_value = None  # No previous temp notification
        await send_temporary_mention(channel, "@user2", "Temporary message")

        # Verify temporary key was used
        temp_call = mock_save_msg_id.call_args
        self.assertEqual(temp_call[0], (456, "notification_temp", 111))

        # Verify get_message_id was called with temp key, not persistent
        mock_get_msg_id.assert_called_with(456, "notification_temp")

    @patch("asyncio.create_task")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_temporary_mention_does_not_delete_persistent(
        self,
        mock_safe_call,
        mock_fetch,
        mock_get_msg_id,
        mock_save_msg_id,
        mock_create_task,
    ):
        """Test that sending a temporary mention does not delete persistent mention."""
        mock_create_task.side_effect = _consume_coro_task()

        # Persistent message exists
        persistent_msg = MagicMock()
        persistent_msg.id = 999
        persistent_msg.delete = AsyncMock()

        # Setup get_message_id to return different values based on key
        def get_msg_side_effect(cid, key):
            if key == "notification_persistent":
                return 999  # Persistent message exists
            elif key == "notification_temp":
                return None  # No temp message yet
            return None

        mock_get_msg_id.side_effect = get_msg_side_effect

        # Mock new temp message
        new_temp_msg = MagicMock()
        new_temp_msg.id = 123
        mock_safe_call.return_value = new_temp_msg

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        # Send temporary mention
        await send_temporary_mention(channel, "@user1", "Vote now!")

        # Verify fetch was NOT called for persistent message
        # (only temp key should be checked)
        if mock_fetch.called:
            # If fetch was called, it should NOT be for the persistent message ID
            for call in mock_fetch.call_args_list:
                _, msg_id = call[0]
                self.assertNotEqual(msg_id, 999, "Temporary mention should not delete persistent message")


if __name__ == "__main__":
    unittest.main()
