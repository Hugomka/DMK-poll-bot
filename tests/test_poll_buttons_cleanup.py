# tests/test_poll_buttons_cleanup.py

"""
Tests for _cleanup_outdated_messages_for_channel function in poll_buttons.py.
This function handles smart cleanup of outdated poll messages when users click the Stemmen button.
"""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytz


class TestCleanupOutdatedMessages(unittest.IsolatedAsyncioTestCase):
    """Test _cleanup_outdated_messages_for_channel function."""

    async def test_skip_cleanup_when_all_messages_recent(self):
        """Test that cleanup is skipped when all poll messages are recent (after reset threshold)."""
        from apps.ui.poll_buttons import _cleanup_outdated_messages_for_channel

        # Setup: Create mock channel and messages
        TZ = pytz.timezone("Europe/Amsterdam")
        now = datetime(2026, 1, 6, 10, 0, 0, tzinfo=TZ)  # Tuesday 10:00

        # Calculate reset threshold (last Sunday 20:30)
        datetime(2026, 1, 4, 20, 30, 0, tzinfo=TZ)  # Sunday 20:30

        # Create mock message that's AFTER reset threshold (recent)
        mock_message = MagicMock()
        mock_message.created_at = datetime(2026, 1, 5, 10, 0, 0, tzinfo=TZ)  # Monday (after Sunday 20:30)
        mock_message.author.id = 999

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild.me.id = 999

        with (
            patch("apps.ui.poll_buttons.datetime") as mock_dt,
            patch("apps.utils.poll_message.get_message_id", return_value=456),
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.ui.poll_buttons.safe_call", new_callable=AsyncMock) as mock_safe_call,
        ):
            # Mock datetime.now() to return our test time
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else now

            # Execute
            await _cleanup_outdated_messages_for_channel(mock_channel, 123)

            # Assert: safe_call should NOT be called (no cleanup needed)
            # The function returns early when no cleanup is needed
            mock_safe_call.assert_not_called()

    async def test_cleanup_triggered_when_message_outdated(self):
        """Test that cleanup is triggered when poll message is outdated (before reset threshold)."""
        from apps.ui.poll_buttons import _cleanup_outdated_messages_for_channel

        TZ = pytz.timezone("Europe/Amsterdam")
        now = datetime(2026, 1, 6, 10, 0, 0, tzinfo=TZ)  # Tuesday 10:00

        # Create mock message that's BEFORE reset threshold (outdated)
        mock_message = MagicMock()
        mock_message.created_at = datetime(2025, 12, 28, 10, 0, 0, tzinfo=TZ)  # Last week (outdated!)
        mock_message.author.id = 999

        # Mock bot messages in channel history
        mock_bot_message1 = MagicMock()
        mock_bot_message1.author.id = 999
        mock_bot_message1.delete = AsyncMock()

        mock_bot_message2 = MagicMock()
        mock_bot_message2.author.id = 999
        mock_bot_message2.delete = AsyncMock()

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild.me.id = 999
        mock_channel.send = AsyncMock(return_value=MagicMock(id=789))

        # Mock async iterator for channel.history()
        async def mock_history_iter(*args, **kwargs):
            yield mock_bot_message1
            yield mock_bot_message2

        mock_channel.history = MagicMock(return_value=MagicMock(__aiter__=lambda self: mock_history_iter()))

        with (
            patch("apps.ui.poll_buttons.datetime") as mock_dt,
            patch("apps.utils.poll_message.get_message_id", return_value=456),
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.ui.poll_buttons.safe_call", new_callable=AsyncMock) as mock_safe_call,
            patch("apps.ui.poll_buttons.clear_message_id") as mock_clear,
            patch("apps.utils.poll_message.save_message_id"),
            patch("apps.utils.poll_settings.get_enabled_rolling_window_days", return_value=[]),
            patch("apps.commands.poll_lifecycle._load_opening_message", return_value="Welcome"),
            patch("apps.utils.poll_message.create_notification_message", new_callable=AsyncMock),
        ):
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else now

            # Execute
            await _cleanup_outdated_messages_for_channel(mock_channel, 123)

            # Assert: safe_call should be called for message deletion
            assert mock_safe_call.call_count > 0

            # Assert: clear_message_id should be called for cleanup
            assert mock_clear.call_count > 0

    async def test_cleanup_triggered_when_message_not_found(self):
        """Test that cleanup is triggered when saved message ID doesn't exist anymore."""
        from apps.ui.poll_buttons import _cleanup_outdated_messages_for_channel

        TZ = pytz.timezone("Europe/Amsterdam")
        now = datetime(2026, 1, 6, 10, 0, 0, tzinfo=TZ)

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild.me.id = 999
        mock_channel.send = AsyncMock(return_value=MagicMock(id=789))

        # Mock async iterator for channel.history() - empty
        async def mock_history_iter(*args, **kwargs):
            return
            yield  # Empty history

        mock_channel.history = MagicMock(return_value=MagicMock(__aiter__=lambda self: mock_history_iter()))

        with (
            patch("apps.ui.poll_buttons.datetime") as mock_dt,
            patch("apps.utils.poll_message.get_message_id", return_value=456),
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=None),  # Message not found!
            patch("apps.ui.poll_buttons.safe_call", new_callable=AsyncMock),
            patch("apps.ui.poll_buttons.clear_message_id") as mock_clear,
            patch("apps.utils.poll_message.save_message_id"),
            patch("apps.utils.poll_settings.get_enabled_rolling_window_days", return_value=[]),
            patch("apps.commands.poll_lifecycle._load_opening_message", return_value="Welcome"),
            patch("apps.utils.poll_message.create_notification_message", new_callable=AsyncMock),
        ):
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else now

            # Execute
            await _cleanup_outdated_messages_for_channel(mock_channel, 123)

            # Assert: cleanup should be triggered (message not found = needs cleanup)
            # clear_message_id should be called
            assert mock_clear.call_count > 0

    async def test_cleanup_handles_exception_gracefully(self):
        """Test that cleanup handles exceptions gracefully and proceeds with cleanup."""
        from apps.ui.poll_buttons import _cleanup_outdated_messages_for_channel

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild.me.id = 999
        mock_channel.send = AsyncMock(return_value=MagicMock(id=789))

        # Mock async iterator for channel.history()
        async def mock_history_iter(*args, **kwargs):
            return
            yield

        mock_channel.history = MagicMock(return_value=MagicMock(__aiter__=lambda self: mock_history_iter()))

        with (
            patch("apps.utils.poll_message.get_message_id", side_effect=Exception("Test error")),
            patch("apps.ui.poll_buttons.clear_message_id"),
            patch("apps.utils.poll_message.save_message_id"),
            patch("apps.utils.poll_settings.get_enabled_rolling_window_days", return_value=[]),
            patch("apps.commands.poll_lifecycle._load_opening_message", return_value="Welcome"),
            patch("apps.utils.poll_message.create_notification_message", new_callable=AsyncMock),
        ):
            # Execute - should not raise exception
            await _cleanup_outdated_messages_for_channel(mock_channel, 123)

            # Assert: Function completes without crashing
            # (No assertion needed, test passes if no exception is raised)

    async def test_cleanup_skips_if_no_history_method(self):
        """Test that cleanup safely returns if channel has no history method."""
        from apps.ui.poll_buttons import _cleanup_outdated_messages_for_channel

        TZ = pytz.timezone("Europe/Amsterdam")
        now = datetime(2026, 1, 6, 10, 0, 0, tzinfo=TZ)

        # Create mock message that's outdated (triggers cleanup)
        mock_message = MagicMock()
        mock_message.created_at = datetime(2025, 12, 28, 10, 0, 0, tzinfo=TZ)

        # Channel WITHOUT history method
        mock_channel = MagicMock()
        mock_channel.id = 123
        del mock_channel.history  # Remove history attribute

        with (
            patch("apps.ui.poll_buttons.datetime") as mock_dt,
            patch("apps.utils.poll_message.get_message_id", return_value=456),
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.ui.poll_buttons.safe_call", new_callable=AsyncMock),
        ):
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else now

            # Execute - should return early without errors
            await _cleanup_outdated_messages_for_channel(mock_channel, 123)

            # Function should return early, not attempt cleanup
            # (No specific assertion, test passes if no exception)

    async def test_cleanup_recreates_messages_correctly(self):
        """Test that cleanup recreates all poll messages correctly."""
        from apps.ui.poll_buttons import _cleanup_outdated_messages_for_channel

        TZ = pytz.timezone("Europe/Amsterdam")
        now = datetime(2026, 1, 6, 10, 0, 0, tzinfo=TZ)

        # Create outdated message
        mock_message = MagicMock()
        mock_message.created_at = datetime(2025, 12, 28, 10, 0, 0, tzinfo=TZ)
        mock_message.author.id = 999

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild.me.id = 999
        mock_channel.guild.id = "456"
        mock_channel.send = AsyncMock(return_value=MagicMock(id=789))

        # Mock async iterator for channel.history()
        async def mock_history_iter(*args, **kwargs):
            return
            yield

        mock_channel.history = MagicMock(return_value=MagicMock(__aiter__=lambda self: mock_history_iter()))

        dagen_info = [
            {"dag": "vrijdag", "datum_iso": "2026-01-10"},
            {"dag": "zaterdag", "datum_iso": "2026-01-11"},
        ]

        with (
            patch("apps.ui.poll_buttons.datetime") as mock_dt,
            patch("apps.utils.poll_message.get_message_id", return_value=456),
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.ui.poll_buttons.safe_call", new_callable=AsyncMock),
            patch("apps.ui.poll_buttons.clear_message_id"),
            patch("apps.utils.poll_message.save_message_id") as mock_save,
            patch("apps.utils.poll_settings.get_enabled_rolling_window_days", return_value=dagen_info),
            patch("apps.commands.poll_lifecycle._load_opening_message", return_value="Welcome to DMK-poll"),
            patch("apps.utils.message_builder.build_poll_message_for_day_async", new_callable=AsyncMock, return_value="Poll content"),
            patch("apps.utils.poll_settings.is_paused", return_value=False),
            patch("apps.utils.poll_message.create_notification_message", new_callable=AsyncMock),
        ):
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else now

            # Execute
            await _cleanup_outdated_messages_for_channel(mock_channel, 123)

            # Assert: save_message_id should be called for opening, days, and stemmen button
            # Opening (1) + 2 days (2) + Stemmen button (1) = 4 calls
            assert mock_save.call_count >= 3  # At least opening + stemmen + notification

    async def test_cleanup_handles_recreation_error_gracefully(self):
        """Test that cleanup handles errors during message recreation gracefully."""
        from apps.ui.poll_buttons import _cleanup_outdated_messages_for_channel

        TZ = pytz.timezone("Europe/Amsterdam")
        now = datetime(2026, 1, 6, 10, 0, 0, tzinfo=TZ)

        mock_message = MagicMock()
        mock_message.created_at = datetime(2025, 12, 28, 10, 0, 0, tzinfo=TZ)
        mock_message.author.id = 999

        mock_channel = MagicMock()
        mock_channel.id = 123
        mock_channel.guild.me.id = 999

        async def mock_history_iter(*args, **kwargs):
            return
            yield

        mock_channel.history = MagicMock(return_value=MagicMock(__aiter__=lambda self: mock_history_iter()))

        with (
            patch("apps.ui.poll_buttons.datetime") as mock_dt,
            patch("apps.utils.poll_message.get_message_id", return_value=456),
            patch("apps.utils.discord_client.fetch_message_or_none", new_callable=AsyncMock, return_value=mock_message),
            patch("apps.ui.poll_buttons.safe_call", new_callable=AsyncMock),
            patch("apps.ui.poll_buttons.clear_message_id"),
            patch("apps.utils.poll_message.save_message_id"),
            patch("apps.utils.poll_settings.get_enabled_rolling_window_days", side_effect=Exception("Recreation error")),
        ):
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else now

            # Execute - should not raise exception
            await _cleanup_outdated_messages_for_channel(mock_channel, 123)

            # Function should handle error gracefully (print warning)
            # Test passes if no exception is raised


if __name__ == "__main__":
    unittest.main()
