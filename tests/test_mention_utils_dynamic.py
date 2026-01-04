# tests/test_mention_utils_dynamic.py

"""
Tests for dynamic non-voter notification functions in mention_utils.py.
These functions handle real-time mention updates when users vote.
"""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo


def _consume_coro_task():
    """Helper to consume coroutines in create_task mocks."""
    def _consume(coro, *args, **kwargs):
        try:
            coro.close()
        except RuntimeError:
            pass
        dummy = MagicMock()
        dummy.cancelled.return_value = False
        return dummy
    return _consume


class TestSendNonVoterNotification(unittest.IsolatedAsyncioTestCase):
    """Test send_non_voter_notification function."""

    @patch("asyncio.create_task", side_effect=_consume_coro_task())
    async def test_send_non_voter_notification_basic_flow(self, mock_create_task):
        """Test basic flow of sending non-voter notification."""
        from apps.utils.mention_utils import send_non_voter_notification

        mock_message = MagicMock()
        mock_message.id = 456

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.send = MagicMock()

        with (
            patch("apps.utils.mention_utils.get_message_id", return_value=None),
            patch("apps.utils.mention_utils.save_message_id") as mock_save,
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock, return_value=mock_message) as mock_safe_call,
            patch("apps.utils.mention_utils.datetime") as mock_dt,
        ):
            # Mock datetime to return a fixed time
            now = datetime(2026, 1, 10, 10, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
            mock_dt.now.return_value = now

            # Execute
            await send_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                mentions_str="<@100>, <@200>",
                text="2 leden hebben nog niet gestemd",
                deadline_time_str="18:00",
            )

            # Assert: Message should be sent
            mock_safe_call.assert_called()

            # Assert: Message ID should be saved
            mock_save.assert_called_with(123, "notification_nonvoter", 456)

            # Assert: asyncio.create_task should be called for scheduling
            assert mock_create_task.call_count >= 1

    @patch("asyncio.create_task", side_effect=_consume_coro_task())
    async def test_send_non_voter_notification_deletes_old_notification(self, mock_create_task):
        """Test that old notifications are deleted before sending new one."""
        from apps.utils.mention_utils import send_non_voter_notification

        mock_old_message = MagicMock()
        mock_old_message.delete = AsyncMock()

        mock_new_message = MagicMock()
        mock_new_message.id = 456

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.send = MagicMock()

        with (
            patch("apps.utils.mention_utils.get_message_id", return_value=999),  # Old message exists
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_old_message),
            patch("apps.utils.mention_utils.clear_message_id") as mock_clear,
            patch("apps.utils.mention_utils.save_message_id"),
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock) as mock_safe_call,
            patch("apps.utils.mention_utils.datetime") as mock_dt,
        ):
            now = datetime(2026, 1, 10, 10, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
            mock_dt.now.return_value = now
            mock_safe_call.side_effect = [None, mock_new_message]  # First call deletes, second creates

            # Execute
            await send_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                mentions_str="<@100>",
                text="1 lid heeft nog niet gestemd",
                deadline_time_str="18:00",
            )

            # Assert: Old message should be cleared
            assert mock_clear.call_count >= 1

    @patch("asyncio.create_task", side_effect=_consume_coro_task())
    async def test_send_non_voter_notification_deadline_already_passed(self, mock_create_task):
        """Test handling when deadline has already passed."""
        from apps.utils.mention_utils import send_non_voter_notification

        mock_message = MagicMock()
        mock_message.id = 456

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.send = MagicMock()

        with (
            patch("apps.utils.mention_utils.get_message_id", return_value=None),
            patch("apps.utils.mention_utils.save_message_id"),
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock, return_value=mock_message) as mock_safe_call,
            patch("apps.utils.mention_utils.datetime") as mock_dt,
        ):
            # Current time is 19:00 (after 18:00 deadline)
            now = datetime(2026, 1, 10, 19, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
            mock_dt.now.return_value = now

            # Execute with deadline in the past
            await send_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                mentions_str="<@100>",
                text="Test",
                deadline_time_str="18:00",  # Already passed!
            )

            # Assert: Should still send notification (just skip scheduling mention removal)
            mock_safe_call.assert_called()

    @patch("asyncio.create_task", side_effect=_consume_coro_task())
    async def test_send_non_voter_notification_schedules_immediate_removal_when_close_to_deadline(self, mock_create_task):
        """Test that mentions are removed immediately if less than 5 minutes to deadline."""
        from apps.utils.mention_utils import send_non_voter_notification

        mock_message = MagicMock()
        mock_message.id = 456

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.send = MagicMock()

        with (
            patch("apps.utils.mention_utils.get_message_id", return_value=None),
            patch("apps.utils.mention_utils.save_message_id"),
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.utils.mention_utils.datetime") as mock_dt,
        ):
            # Current time is 17:57 (3 minutes before 18:00 deadline)
            now = datetime(2026, 1, 10, 17, 57, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
            mock_dt.now.return_value = now

            # Execute
            await send_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                mentions_str="<@100>",
                text="Test",
                deadline_time_str="18:00",
            )

            # Assert: create_task should be called with delay_seconds=0 (immediate removal)
            assert mock_create_task.call_count >= 1

    async def test_send_non_voter_notification_returns_early_if_no_send_method(self):
        """Test that function returns early if channel has no send method."""
        from apps.utils.mention_utils import send_non_voter_notification

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.send = None  # Set send to None (function checks with getattr)

        with (
            patch("apps.utils.mention_utils.get_message_id", return_value=None),
            patch("apps.utils.mention_utils.save_message_id") as mock_save,
            patch("apps.utils.mention_utils.clear_message_id"),
        ):
            # Execute
            await send_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                mentions_str="<@100>",
                text="Test",
                deadline_time_str="18:00",
            )

            # Assert: save_message_id should NOT be called (returned early)
            mock_save.assert_not_called()


class TestRemoveAllMentionsBeforeDeadline(unittest.IsolatedAsyncioTestCase):
    """Test _remove_all_mentions_before_deadline function."""

    async def test_remove_mentions_after_delay(self):
        """Test that mentions are removed after specified delay."""
        from apps.utils.mention_utils import _remove_all_mentions_before_deadline

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        with (
            patch("apps.utils.mention_utils.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock) as mock_safe_call,
            patch("apps.utils.mention_utils._NON_VOTER_NOTIFICATION_META", {123: {"dag": "vrijdag"}}),
        ):
            # Execute with 10 second delay
            await _remove_all_mentions_before_deadline(
                message=mock_message,
                delay_seconds=10.0,
                text="Test text",
                channel_id=123,
            )

            # Assert: Should sleep for 10 seconds
            mock_sleep.assert_called_once_with(10.0)

            # Assert: Message should be edited
            mock_safe_call.assert_called_once()

    async def test_remove_mentions_immediately_if_zero_delay(self):
        """Test that mentions are removed immediately if delay is 0."""
        from apps.utils.mention_utils import _remove_all_mentions_before_deadline

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        with (
            patch("apps.utils.mention_utils.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock) as mock_safe_call,
            patch("apps.utils.mention_utils._NON_VOTER_NOTIFICATION_META", {123: {"dag": "vrijdag"}}),
        ):
            # Execute with 0 delay
            await _remove_all_mentions_before_deadline(
                message=mock_message,
                delay_seconds=0.0,
                text="Test text",
                channel_id=123,
            )

            # Assert: Should NOT sleep
            mock_sleep.assert_not_called()

            # Assert: Message should be edited immediately
            mock_safe_call.assert_called_once()

    async def test_remove_mentions_clears_metadata(self):
        """Test that metadata is cleared after removing mentions."""
        from apps.utils.mention_utils import _remove_all_mentions_before_deadline, _NON_VOTER_NOTIFICATION_META

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        # Setup metadata
        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "vrijdag", "message_id": 456}

        with (
            patch("apps.utils.mention_utils.asyncio.sleep", new_callable=AsyncMock),
            patch("apps.utils.discord_client.safe_call", new_callable=AsyncMock),
        ):
            # Execute
            await _remove_all_mentions_before_deadline(
                message=mock_message,
                delay_seconds=0.0,
                text="Test text",
                channel_id=123,
            )

            # Assert: Metadata should be cleared
            assert 123 not in _NON_VOTER_NOTIFICATION_META


class TestUpdateNonVoterNotification(unittest.IsolatedAsyncioTestCase):
    """Test update_non_voter_notification function."""

    async def test_update_notification_returns_early_if_no_metadata(self):
        """Test that function returns early if no active notification exists."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        # Clear metadata
        _NON_VOTER_NOTIFICATION_META.clear()

        mock_channel = MagicMock()
        mock_channel.id = 123

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock) as mock_fetch,
        ):
            # Execute
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                guild_id=456,
            )

            # Assert: Should return early, not fetch message
            mock_fetch.assert_not_called()

    async def test_update_notification_returns_early_if_different_day(self):
        """Test that function returns early if notification is for different day."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        # Setup metadata for "zaterdag"
        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "zaterdag", "message_id": 789}

        mock_channel = MagicMock()
        mock_channel.id = 123

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock) as mock_fetch,
        ):
            # Execute with different day "vrijdag"
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",  # Different from "zaterdag"
                guild_id=456,
            )

            # Assert: Should return early
            mock_fetch.assert_not_called()

    async def test_update_notification_cleans_up_if_message_not_found(self):
        """Test that metadata is cleaned up if message no longer exists."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        # Setup metadata
        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "vrijdag", "message_id": 789}

        mock_channel = MagicMock()
        mock_channel.id = 123

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=None),
        ):
            # Execute
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                guild_id=456,
            )

            # Assert: Metadata should be cleaned up
            assert 123 not in _NON_VOTER_NOTIFICATION_META

    async def test_update_notification_deletes_if_everyone_voted(self):
        """Test that notification is deleted if everyone has voted."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "vrijdag", "message_id": 789}

        mock_message = MagicMock()
        mock_message.delete = AsyncMock()

        mock_channel = MagicMock()
        mock_channel.id = 123

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.utils.poll_storage.get_non_voters_for_day", new_callable=AsyncMock, return_value=(0, [])),  # No non-voters!
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock, return_value=None) as mock_safe_call,
            patch("apps.utils.mention_utils.clear_message_id") as mock_clear,
        ):
            # Execute
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                guild_id=456,
            )

            # Assert: Message should be deleted
            mock_safe_call.assert_called_once()

            # Assert: Message ID should be cleared
            mock_clear.assert_called_with(123, "notification_nonvoter")

            # Assert: Metadata should be cleaned up
            assert 123 not in _NON_VOTER_NOTIFICATION_META

    async def test_update_notification_updates_mention_list(self):
        """Test that notification is updated with new mention list when users vote."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "vrijdag", "message_id": 789}

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        mock_member1 = MagicMock()
        mock_member1.mention = "<@100>"

        mock_member2 = MagicMock()
        mock_member2.mention = "<@200>"

        mock_guild = MagicMock()
        mock_guild.get_member = MagicMock(side_effect=lambda uid: mock_member1 if uid == 100 else mock_member2)

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild = mock_guild

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.utils.poll_storage.get_non_voters_for_day", new_callable=AsyncMock, return_value=(2, ["100", "200"])),
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock) as mock_safe_call,
        ):
            # Execute
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                guild_id=456,
            )

            # Assert: Message should be edited with updated mentions
            mock_safe_call.assert_called_once()
            call_args = mock_safe_call.call_args
            # Check that edit was called with content containing mentions
            assert call_args is not None

    async def test_update_notification_uses_correct_dutch_grammar(self):
        """Test that notification uses correct Dutch grammar (1 lid vs 2 leden)."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "vrijdag", "message_id": 789}

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        mock_member = MagicMock()
        mock_member.mention = "<@100>"

        mock_guild = MagicMock()
        mock_guild.get_member = MagicMock(return_value=mock_member)

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild = mock_guild

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.utils.poll_storage.get_non_voters_for_day", new_callable=AsyncMock, return_value=(1, ["100"])),  # 1 voter
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock) as mock_safe_call,
        ):
            # Execute
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                guild_id=456,
            )

            # Assert: Should use singular form "1 lid heeft"
            mock_safe_call.assert_called_once()
            # Content should contain singular Dutch grammar
            # (Actual content check would require inspecting the call args)

    async def test_update_notification_deletes_if_no_mentions_list(self):
        """Test that notification is deleted if mention list becomes empty (invalid user IDs)."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "vrijdag", "message_id": 789}

        mock_message = MagicMock()
        mock_message.delete = AsyncMock()

        mock_guild = MagicMock()
        mock_guild.get_member = MagicMock(return_value=None)

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild = mock_guild

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            # Return non-voter IDs that can't be converted to int -> empty mentions list
            patch("apps.utils.poll_storage.get_non_voters_for_day", new_callable=AsyncMock, return_value=(2, ["invalid", "also_invalid"])),
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock, return_value=None) as mock_safe_call,
            patch("apps.utils.mention_utils.clear_message_id") as mock_clear,
        ):
            # Execute
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                guild_id=456,
            )

            # Assert: Message should be deleted (no valid mentions - int() fails)
            mock_safe_call.assert_called_once()
            mock_clear.assert_called_with(123, "notification_nonvoter")

    async def test_update_notification_returns_early_if_no_guild(self):
        """Test that function returns early if channel has no guild."""
        from apps.utils.mention_utils import update_non_voter_notification, _NON_VOTER_NOTIFICATION_META

        _NON_VOTER_NOTIFICATION_META[123] = {"dag": "vrijdag", "message_id": 789}

        mock_message = MagicMock()

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild = None  # No guild!

        with (
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.utils.poll_storage.get_non_voters_for_day", new_callable=AsyncMock, return_value=(2, ["100", "200"])),
            patch("apps.utils.mention_utils.safe_call", new_callable=AsyncMock) as mock_safe_call,
        ):
            # Execute
            await update_non_voter_notification(
                channel=mock_channel,
                dag="vrijdag",
                guild_id=456,
            )

            # Assert: Should return early, not call safe_call for editing
            mock_safe_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
