# tests/test_scheduler_retry_operations.py
#
# Integration tests voor Scheduler Retry Operations

import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytz

from apps import scheduler
from apps.utils import retry_queue
from tests.base import BaseTestCase


class TestSchedulerRetryOperations(BaseTestCase):
    """Integration tests voor retry_failed_operations scheduler job."""

    def setUp(self):
        """Setup temp retry queue file."""
        super().setUp()
        self.temp_retry_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_retry_queue.json", encoding="utf-8"
        )
        self.temp_retry_file.close()

        self.original_retry_file = retry_queue.RETRY_QUEUE_FILE
        retry_queue.RETRY_QUEUE_FILE = self.temp_retry_file.name

        # Clear queue
        retry_queue.clear_retry_queue()

    def tearDown(self):
        """Cleanup."""
        retry_queue.RETRY_QUEUE_FILE = self.original_retry_file
        try:
            import os
            os.remove(self.temp_retry_file.name)
        except FileNotFoundError:
            pass
        super().tearDown()

    async def test_retry_pending_conversion_success(self):
        """Test retry pending conversion - success pad."""
        # Add pending conversion to queue
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_minute_ago = now - timedelta(minutes=1)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = one_minute_ago
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

        # Mock bot
        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(id=10, guild=guild)
        bot.guilds = [guild]

        with (
            patch.object(scheduler, "get_channels", return_value=[channel]),
            patch(
                "apps.utils.poll_storage.remove_vote", new_callable=AsyncMock
            ) as mock_remove,
            patch("apps.utils.poll_storage.add_vote", new_callable=AsyncMock) as mock_add,
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_update,
        ):
            await scheduler.retry_failed_operations(bot)

        # Verify conversion calls
        mock_remove.assert_awaited_once_with("100", "vrijdag", "misschien", "1", "10")
        mock_add.assert_awaited_once_with("100", "vrijdag", "niet meedoen", "1", "10")
        mock_update.assert_awaited_once()

        # Verify removed from queue
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

    async def test_retry_pending_conversion_fails(self):
        """Test retry pending conversion - conversie faalt, increment retry count."""
        # Add pending conversion
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_minute_ago = now - timedelta(minutes=1)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = one_minute_ago
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

        bot = SimpleNamespace(guilds=[])

        with (
            patch.object(scheduler, "get_channels", return_value=[]),
            patch(
                "apps.utils.poll_storage.remove_vote",
                new_callable=AsyncMock,
                side_effect=Exception("Vote removal failed"),
            ),
        ):
            await scheduler.retry_failed_operations(bot)

        # Verify retry count incremented
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 1)
        key = "conversion:1:10:100:vrijdag"
        self.assertIn(key, queue)
        self.assertEqual(queue[key]["retry_count"], 1)

    async def test_retry_pending_reset_success(self):
        """Test retry pending reset - success pad."""
        # Add pending reset
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_minute_ago = now - timedelta(minutes=1)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = one_minute_ago
            retry_queue.add_failed_reset("1", "10")

        bot = SimpleNamespace(guilds=[])

        with patch(
            "apps.utils.poll_storage.reset_votes_scoped", new_callable=AsyncMock
        ) as mock_reset:
            await scheduler.retry_failed_operations(bot)

        # Verify reset called
        mock_reset.assert_awaited_once_with("1", "10")

        # Verify removed from queue
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

    async def test_retry_pending_reset_fails(self):
        """Test retry pending reset - reset faalt, increment retry count."""
        # Add pending reset
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_minute_ago = now - timedelta(minutes=1)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = one_minute_ago
            retry_queue.add_failed_reset("1", "10")

        bot = SimpleNamespace(guilds=[])

        with patch(
            "apps.utils.poll_storage.reset_votes_scoped",
            new_callable=AsyncMock,
            side_effect=Exception("Reset failed"),
        ):
            await scheduler.retry_failed_operations(bot)

        # Verify retry count incremented
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 1)
        key = "reset:1:10"
        self.assertIn(key, queue)
        self.assertEqual(queue[key]["retry_count"], 1)

    async def test_expired_conversion_error_message_sent(self):
        """Test expired conversion - error message gestuurd naar Discord."""
        # Add expired conversion (3 hours ago)
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        three_hours_ago = now - timedelta(hours=3)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = three_hours_ago
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

            # Set retry count
            queue = retry_queue._load_retry_queue()
            queue["conversion:1:10:100:vrijdag"]["retry_count"] = 5
            retry_queue._save_retry_queue(queue)

        # Mock bot
        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        mock_send = AsyncMock()
        channel = SimpleNamespace(id=10, guild=guild, send=mock_send)
        bot.guilds = [guild]

        with patch.object(scheduler, "get_channels", return_value=[channel]):
            await scheduler.retry_failed_operations(bot)

        # Verify error message sent
        mock_send.assert_awaited_once()
        call_args = mock_send.call_args
        message = call_args[0][0]

        self.assertIn("⚠️", message)
        self.assertIn("misschien conversie", message)
        self.assertIn("<@100>", message)
        self.assertIn("vrijdag", message)
        self.assertIn("6x", message)  # retry_count + 1

        # Verify removed from queue
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

    async def test_expired_reset_error_message_sent(self):
        """Test expired reset - error message gestuurd naar Discord."""
        # Add expired reset
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        three_hours_ago = now - timedelta(hours=3)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = three_hours_ago
            retry_queue.add_failed_reset("1", "10")

            # Set retry count
            queue = retry_queue._load_retry_queue()
            queue["reset:1:10"]["retry_count"] = 3
            retry_queue._save_retry_queue(queue)

        # Mock bot
        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        mock_send = AsyncMock()
        channel = SimpleNamespace(id=10, guild=guild, send=mock_send)
        bot.guilds = [guild]

        with patch.object(scheduler, "get_channels", return_value=[channel]):
            await scheduler.retry_failed_operations(bot)

        # Verify error message sent
        mock_send.assert_awaited_once()
        call_args = mock_send.call_args
        message = call_args[0][0]

        self.assertIn("⚠️", message)
        self.assertIn("vote reset", message)
        self.assertIn("4x", message)  # retry_count + 1

        # Verify removed from queue
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

    async def test_expired_channel_not_found(self):
        """Test expired operation - channel niet gevonden, queue wel cleaned up."""
        # Add expired conversion
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        three_hours_ago = now - timedelta(hours=3)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = three_hours_ago
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

        bot = SimpleNamespace(guilds=[])

        with patch.object(scheduler, "get_channels", return_value=[]):
            await scheduler.retry_failed_operations(bot)

        # Verify removed from queue (cleanup)
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

    async def test_expired_send_fails(self):
        """Test expired operation - send faalt, queue wel cleaned up."""
        # Add expired conversion
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        three_hours_ago = now - timedelta(hours=3)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = three_hours_ago
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

        # Mock bot with send that fails
        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        mock_send = AsyncMock(side_effect=Exception("Send failed"))
        channel = SimpleNamespace(id=10, guild=guild, send=mock_send)
        bot.guilds = [guild]

        with patch.object(scheduler, "get_channels", return_value=[channel]):
            await scheduler.retry_failed_operations(bot)

        # Verify removed from queue (exception caught)
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

    async def test_empty_queues(self):
        """Test retry_failed_operations met lege queues."""
        bot = SimpleNamespace(guilds=[])

        # Should not raise error
        await scheduler.retry_failed_operations(bot)

        # Queue should still be empty
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

    async def test_mixed_operations(self):
        """Test retry_failed_operations met mixed pending en expired operations."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_minute_ago = now - timedelta(minutes=1)
        three_hours_ago = now - timedelta(hours=3)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            # Add pending conversion
            mock_dt.now.return_value = one_minute_ago
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

            # Add pending reset
            retry_queue.add_failed_reset("1", "10")

            # Add expired conversion
            mock_dt.now.return_value = three_hours_ago
            retry_queue.add_failed_conversion("1", "10", "200", "zaterdag")

            # Add expired reset
            retry_queue.add_failed_reset("1", "11")

        # Mock bot
        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        mock_send = AsyncMock()
        channel = SimpleNamespace(id=10, guild=guild, send=mock_send)
        channel11 = SimpleNamespace(id=11, guild=guild, send=mock_send)
        bot.guilds = [guild]

        with (
            patch.object(scheduler, "get_channels", return_value=[channel, channel11]),
            patch("apps.utils.poll_storage.remove_vote", new_callable=AsyncMock),
            patch("apps.utils.poll_storage.add_vote", new_callable=AsyncMock),
            patch("apps.utils.poll_storage.reset_votes_scoped", new_callable=AsyncMock),
            patch.object(scheduler, "schedule_poll_update", new_callable=AsyncMock),
        ):
            await scheduler.retry_failed_operations(bot)

        # Verify all operations processed (queue should be empty)
        queue = retry_queue._load_retry_queue()
        self.assertEqual(len(queue), 0)

        # Verify error messages sent (2 expired operations)
        self.assertEqual(mock_send.call_count, 2)


if __name__ == "__main__":
    import unittest

    unittest.main()
