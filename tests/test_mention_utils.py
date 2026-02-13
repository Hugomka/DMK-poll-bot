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
    @patch("apps.utils.mention_utils.clear_message_id")
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
        mock_clear_msg_id,
        mock_create_task,
    ):
        """Test that temporary mention deletes ALL previous notifications (temp, persistent, legacy)."""
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

        # Verify old messages were deleted for all notification types (3 calls: temp, persistent, legacy)
        assert mock_fetch.call_count == 3, "Should fetch messages for all 3 notification keys"
        assert mock_clear_msg_id.call_count == 3, "Should clear all 3 message IDs"
        # safe_call is used for: delete (3x) + send (1x) = 4 calls
        assert mock_safe_call.call_count == 4, "Should delete 3 old messages and send 1 new"

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
    @patch("apps.utils.mention_utils.clear_message_id")
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
        mock_clear_msg_id,
        mock_create_task,
    ):
        """Test persistent mention deletes ALL previous notifications (temp, persistent, legacy)."""
        mock_create_task.side_effect = _consume_coro_task()

        # Mock previous message exists for all notification types
        old_msg = MagicMock()
        old_msg.delete = AsyncMock()
        mock_get_msg_id.return_value = 999  # Return same ID for all keys
        mock_fetch.return_value = old_msg

        # Mock new message
        new_msg = MagicMock()
        new_msg.id = 123
        mock_safe_call.return_value = new_msg

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        await send_persistent_mention(channel, "@user1", "Test")

        # Verify old messages were deleted for all notification types (3 calls: temp, persistent, legacy)
        assert mock_fetch.call_count == 3, "Should fetch messages for all 3 notification keys"
        assert mock_clear_msg_id.call_count == 3, "Should clear all 3 message IDs"
        # safe_call is used for: delete (3x) + send (1x) = 4 calls
        assert mock_safe_call.call_count == 4, "Should delete 3 old messages and send 1 new"

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
            mock_message, 5.0, "<@111>, <@222>", "Please vote!", mock_view, True, 123
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
    @patch("apps.utils.mention_utils.clear_message_id")
    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_only_one_notification_exists_at_a_time(
        self, mock_safe_call, mock_get_msg_id, mock_save_msg_id, mock_clear_msg_id, mock_create_task
    ):
        """Test that only ONE notification message exists at a time (all old notifications are deleted)."""
        mock_create_task.side_effect = _consume_coro_task()

        # Mock that there's no previous message initially
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

        # Verify persistent key was used for saving
        persistent_call = mock_save_msg_id.call_args
        self.assertEqual(persistent_call[0], (456, "notification_persistent", 222))

        # Verify all 3 notification keys were checked for cleanup
        assert mock_get_msg_id.call_count == 3, "Should check all 3 notification keys"

        # Reset mocks
        mock_save_msg_id.reset_mock()
        mock_get_msg_id.reset_mock()
        mock_clear_msg_id.reset_mock()

        # Now send temporary mention - it should DELETE the persistent one
        mock_safe_call.return_value = mock_temp_msg
        mock_get_msg_id.return_value = 222  # The persistent message exists
        await send_temporary_mention(channel, "@user2", "Temporary message")

        # Verify temp key was used for the NEW message
        temp_call = mock_save_msg_id.call_args
        self.assertEqual(temp_call[0], (456, "notification_temp", 111))

        # Verify ALL notification keys were checked and cleared (ensuring only ONE notification)
        assert mock_get_msg_id.call_count == 3, "Should check all 3 notification keys"
        assert mock_clear_msg_id.call_count == 3, "Should clear all 3 notification keys to ensure only one notification"

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

        # NEW BEHAVIOR: Temporary mentions NOW DELETE ALL notification types
        # to ensure only ONE notification exists at a time
        # This test is kept for documentation but behavior has changed


class UpdateNotificationRemoveMentionTestCase(unittest.IsolatedAsyncioTestCase):
    """Test update_notification_remove_mention function."""

    @patch("apps.utils.mention_utils.get_message_id")
    async def test_no_message_id_returns_early(self, mock_get_msg_id):
        """No stored message ID → early return without fetching."""
        from apps.utils.mention_utils import update_notification_remove_mention

        mock_get_msg_id.return_value = None
        channel = MagicMock()
        channel.id = 456

        await update_notification_remove_mention(channel, user_id=111)

        mock_get_msg_id.assert_called_once_with(456, "notification_temp")

    @patch("apps.utils.mention_utils.clear_message_id")
    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.get_message_id")
    async def test_message_not_found_clears_id(self, mock_get_msg_id, mock_fetch, mock_clear):
        """Message no longer exists → clear stored ID and return."""
        from apps.utils.mention_utils import update_notification_remove_mention

        mock_get_msg_id.return_value = 999
        mock_fetch.return_value = None

        channel = MagicMock()
        channel.id = 456

        await update_notification_remove_mention(channel, user_id=111)

        mock_clear.assert_called_once_with(456, "notification_temp")

    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.get_message_id")
    async def test_empty_content_returns_early(self, mock_get_msg_id, mock_fetch):
        """Message has no content → return without editing."""
        from apps.utils.mention_utils import update_notification_remove_mention

        mock_get_msg_id.return_value = 999
        msg = MagicMock()
        msg.content = ""
        mock_fetch.return_value = msg

        channel = MagicMock()
        channel.id = 456

        await update_notification_remove_mention(channel, user_id=111)

    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.get_message_id")
    async def test_user_not_mentioned_returns_early(self, mock_get_msg_id, mock_fetch):
        """User not in message content → return without editing."""
        from apps.utils.mention_utils import update_notification_remove_mention

        mock_get_msg_id.return_value = 999
        msg = MagicMock()
        msg.content = ":mega: Notificatie:\n<@222>, <@333>\nPlease vote!"
        mock_fetch.return_value = msg

        channel = MagicMock()
        channel.id = 456

        await update_notification_remove_mention(channel, user_id=111)

        # Message should NOT have been edited (user 111 not mentioned)
        msg.edit.assert_not_called()

    @patch("apps.utils.mention_utils.safe_call")
    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.get_message_id")
    async def test_remove_one_mention_others_remain(self, mock_get_msg_id, mock_fetch, mock_safe_call):
        """Remove one user's mention, others remain → edit message."""
        from apps.utils.mention_utils import update_notification_remove_mention

        mock_get_msg_id.return_value = 999
        msg = MagicMock()
        msg.content = ":mega: Notificatie:\n<@111>, <@222>\nPlease vote!"
        msg.edit = AsyncMock()
        mock_fetch.return_value = msg

        channel = MagicMock()
        channel.id = 456

        await update_notification_remove_mention(channel, user_id=111)

        # Message should be edited with user 111 removed
        mock_safe_call.assert_called_once()
        call_kwargs = mock_safe_call.call_args[1]
        new_content = call_kwargs["content"]
        self.assertNotIn("<@111>", new_content)
        self.assertIn("<@222>", new_content)

    @patch("apps.utils.mention_utils.clear_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.get_message_id")
    async def test_remove_last_mention_deletes_message(
        self, mock_get_msg_id, mock_fetch, mock_safe_call, mock_clear
    ):
        """Remove the last mention → delete entire message."""
        from apps.utils.mention_utils import update_notification_remove_mention

        mock_get_msg_id.return_value = 999
        msg = MagicMock()
        msg.content = ":mega: Notificatie:\n<@111>\nPlease vote!"
        msg.delete = AsyncMock()
        mock_fetch.return_value = msg

        channel = MagicMock()
        channel.id = 456

        await update_notification_remove_mention(channel, user_id=111)

        # Message should be deleted (no mentions left)
        mock_safe_call.assert_called_once_with(msg.delete)
        mock_clear.assert_called_once_with(456, "notification_temp")

    @patch("apps.utils.mention_utils.safe_call")
    @patch("apps.utils.discord_client.fetch_message_or_none")
    @patch("apps.utils.mention_utils.get_message_id")
    async def test_remove_mention_with_nick_format(self, mock_get_msg_id, mock_fetch, mock_safe_call):
        """Remove mention with nickname format <@!user_id>."""
        from apps.utils.mention_utils import update_notification_remove_mention

        mock_get_msg_id.return_value = 999
        msg = MagicMock()
        msg.content = ":mega: Notificatie:\n<@!111>, <@222>\nPlease vote!"
        msg.edit = AsyncMock()
        mock_fetch.return_value = msg

        channel = MagicMock()
        channel.id = 456

        await update_notification_remove_mention(channel, user_id=111)

        mock_safe_call.assert_called_once()
        new_content = mock_safe_call.call_args[1]["content"]
        self.assertNotIn("<@!111>", new_content)
        self.assertIn("<@222>", new_content)


class SendTemporaryMentionEdgeCasesTestCase(unittest.IsolatedAsyncioTestCase):
    """Test edge cases for send_temporary_mention."""

    async def test_no_send_method_returns_early(self):
        """Channel without send method → return without sending."""
        channel = MagicMock(spec=[])  # No send attribute
        channel.id = 456

        await send_temporary_mention(channel, "@user1", "Vote!")

    @patch("apps.utils.mention_utils.save_message_id")
    @patch("apps.utils.mention_utils.get_message_id")
    @patch("apps.utils.mention_utils.safe_call")
    async def test_safe_call_returns_none(self, mock_safe_call, mock_get_msg_id, mock_save_msg_id):
        """safe_call returns None (send failed) → no tasks scheduled."""
        mock_get_msg_id.return_value = None
        mock_safe_call.return_value = None

        channel = MagicMock()
        channel.id = 456
        channel.send = AsyncMock()

        await send_temporary_mention(channel, "@user1", "Vote!")

        # save_message_id should NOT have been called
        mock_save_msg_id.assert_not_called()


if __name__ == "__main__":
    unittest.main()
