# tests/test_retry_queue.py
#
# Unit tests voor Retry Queue System

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pytz

from apps.utils import retry_queue


class TestRetryQueue(unittest.TestCase):
    """Tests voor retry queue system."""

    def setUp(self):
        """Setup temp file voor elke test."""
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_retry_queue.json", encoding="utf-8"
        )
        self.temp_file.close()

        # Patch RETRY_QUEUE_FILE constant
        self.original_file = retry_queue.RETRY_QUEUE_FILE
        retry_queue.RETRY_QUEUE_FILE = self.temp_file.name

    def tearDown(self):
        """Cleanup temp file."""
        retry_queue.RETRY_QUEUE_FILE = self.original_file
        try:
            os.remove(self.temp_file.name)
        except FileNotFoundError:
            pass

    def test_ensure_dir_creates_directory(self):
        """Test dat _ensure_dir() directory aanmaakt."""
        # _ensure_dir() creates "data" directory (hardcoded)
        # This test just verifies it doesn't crash
        retry_queue._ensure_dir()

        # Verify "data" directory exists
        self.assertTrue(os.path.exists("data"))

    def test_ensure_dir_existing_directory(self):
        """Test dat _ensure_dir() geen error geeft bij bestaande directory."""
        # Should not raise error
        retry_queue._ensure_dir()
        retry_queue._ensure_dir()  # Call twice

    def test_load_retry_queue_empty_when_no_file(self):
        """Test dat _load_retry_queue() empty dict returned als file niet bestaat."""
        os.remove(self.temp_file.name)
        queue = retry_queue._load_retry_queue()
        self.assertEqual(queue, {})

    def test_load_retry_queue_valid_file(self):
        """Test dat _load_retry_queue() queue laadt uit bestaande file."""
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "guild_id": "1",
                "channel_id": "10",
                "user_id": "100",
                "dag": "vrijdag",
                "first_attempt": "2025-12-13T18:00:00+01:00",
                "retry_count": 0,
            }
        }
        with open(self.temp_file.name, "w", encoding="utf-8") as f:
            json.dump(test_data, f)

        queue = retry_queue._load_retry_queue()
        self.assertEqual(queue, test_data)

    def test_load_retry_queue_corrupted_file(self):
        """Test dat _load_retry_queue() empty dict returned bij corrupte JSON."""
        with open(self.temp_file.name, "w", encoding="utf-8") as f:
            f.write("invalid json{{{")

        queue = retry_queue._load_retry_queue()
        self.assertEqual(queue, {})

    def test_save_retry_queue_success(self):
        """Test dat _save_retry_queue() queue opslaat naar file."""
        test_data = {"key1": {"value": "test"}}
        retry_queue._save_retry_queue(test_data)

        with open(self.temp_file.name, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data, test_data)

    def test_add_failed_conversion_new_entry(self):
        """Test dat add_failed_conversion() nieuwe conversie toevoegt aan queue."""
        tz = pytz.timezone("Europe/Amsterdam")
        fixed_time = datetime(2025, 12, 13, 18, 0, 0, tzinfo=tz)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time

            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

        queue = retry_queue._load_retry_queue()
        key = "conversion:1:10:100:vrijdag"

        self.assertIn(key, queue)
        self.assertEqual(queue[key]["type"], "conversion")
        self.assertEqual(queue[key]["guild_id"], "1")
        self.assertEqual(queue[key]["channel_id"], "10")
        self.assertEqual(queue[key]["user_id"], "100")
        self.assertEqual(queue[key]["dag"], "vrijdag")
        self.assertEqual(queue[key]["first_attempt"], fixed_time.isoformat())
        self.assertEqual(queue[key]["retry_count"], 0)

    def test_add_failed_conversion_skip_duplicate(self):
        """Test dat add_failed_conversion() duplicate entry skipt."""
        tz = pytz.timezone("Europe/Amsterdam")
        fixed_time1 = datetime(2025, 12, 13, 18, 0, 0, tzinfo=tz)
        fixed_time2 = datetime(2025, 12, 13, 19, 0, 0, tzinfo=tz)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time1
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

            # Try to add again with different time
            mock_dt.now.return_value = fixed_time2
            retry_queue.add_failed_conversion("1", "10", "100", "vrijdag")

        queue = retry_queue._load_retry_queue()
        key = "conversion:1:10:100:vrijdag"

        # Should still have original timestamp (not updated)
        self.assertEqual(queue[key]["first_attempt"], fixed_time1.isoformat())

    def test_add_failed_reset_new_entry(self):
        """Test dat add_failed_reset() nieuwe reset toevoegt aan queue."""
        tz = pytz.timezone("Europe/Amsterdam")
        fixed_time = datetime(2025, 12, 13, 0, 0, 0, tzinfo=tz)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time

            retry_queue.add_failed_reset("1", "10")

        queue = retry_queue._load_retry_queue()
        key = "reset:1:10"

        self.assertIn(key, queue)
        self.assertEqual(queue[key]["type"], "reset")
        self.assertEqual(queue[key]["guild_id"], "1")
        self.assertEqual(queue[key]["channel_id"], "10")
        self.assertNotIn("user_id", queue[key])  # Reset heeft geen user_id
        self.assertNotIn("dag", queue[key])  # Reset heeft geen dag
        self.assertEqual(queue[key]["first_attempt"], fixed_time.isoformat())
        self.assertEqual(queue[key]["retry_count"], 0)

    def test_add_failed_reset_skip_duplicate(self):
        """Test dat add_failed_reset() duplicate entry skipt."""
        tz = pytz.timezone("Europe/Amsterdam")
        fixed_time1 = datetime(2025, 12, 13, 0, 0, 0, tzinfo=tz)
        fixed_time2 = datetime(2025, 12, 13, 1, 0, 0, tzinfo=tz)

        with patch("apps.utils.retry_queue.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_time1
            retry_queue.add_failed_reset("1", "10")

            # Try to add again with different time
            mock_dt.now.return_value = fixed_time2
            retry_queue.add_failed_reset("1", "10")

        queue = retry_queue._load_retry_queue()
        key = "reset:1:10"

        # Should still have original timestamp
        self.assertEqual(queue[key]["first_attempt"], fixed_time1.isoformat())

    def test_get_pending_conversions_within_timeout(self):
        """Test dat get_pending_conversions() operations returned binnen 2 uur."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_hour_ago = now - timedelta(hours=1)

        # Add entry from 1 hour ago
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "guild_id": "1",
                "channel_id": "10",
                "user_id": "100",
                "dag": "vrijdag",
                "first_attempt": one_hour_ago.isoformat(),
                "retry_count": 2,
            }
        }
        retry_queue._save_retry_queue(test_data)

        pending = retry_queue.get_pending_conversions()

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["guild_id"], "1")
        self.assertEqual(pending[0]["channel_id"], "10")
        self.assertEqual(pending[0]["user_id"], "100")
        self.assertEqual(pending[0]["dag"], "vrijdag")
        self.assertEqual(pending[0]["retry_count"], 2)
        self.assertEqual(pending[0]["key"], "conversion:1:10:100:vrijdag")
        self.assertIn("elapsed_seconds", pending[0])

    def test_get_pending_conversions_filters_expired(self):
        """Test dat get_pending_conversions() expired operations filtert (>2 uur)."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        three_hours_ago = now - timedelta(hours=3)

        # Add expired entry
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "guild_id": "1",
                "channel_id": "10",
                "user_id": "100",
                "dag": "vrijdag",
                "first_attempt": three_hours_ago.isoformat(),
                "retry_count": 0,
            }
        }
        retry_queue._save_retry_queue(test_data)

        pending = retry_queue.get_pending_conversions()

        # Should not include expired entry
        self.assertEqual(len(pending), 0)

    def test_get_pending_conversions_handles_timezone_naive(self):
        """Test dat get_pending_conversions() timezone-naive datetimes handled."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_hour_ago_naive = (now - timedelta(hours=1)).replace(tzinfo=None)

        # Add entry with naive datetime
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "guild_id": "1",
                "channel_id": "10",
                "user_id": "100",
                "dag": "vrijdag",
                "first_attempt": one_hour_ago_naive.isoformat(),
                "retry_count": 0,
            }
        }
        retry_queue._save_retry_queue(test_data)

        pending = retry_queue.get_pending_conversions()

        # Should still work (localize naive datetime)
        self.assertEqual(len(pending), 1)

    def test_get_pending_conversions_skips_invalid_entries(self):
        """Test dat get_pending_conversions() invalid entries skipt."""
        # Add invalid entry (missing first_attempt)
        test_data = {
            "invalid_entry": {
                "type": "conversion",
                "guild_id": "1",
            }
        }
        retry_queue._save_retry_queue(test_data)

        pending = retry_queue.get_pending_conversions()

        # Should skip invalid entry
        self.assertEqual(len(pending), 0)

    def test_get_pending_conversions_includes_both_types(self):
        """Test dat get_pending_conversions() beide operation types returned."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_hour_ago = now - timedelta(hours=1)

        # Add both conversion and reset
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "guild_id": "1",
                "channel_id": "10",
                "user_id": "100",
                "dag": "vrijdag",
                "first_attempt": one_hour_ago.isoformat(),
                "retry_count": 0,
            },
            "reset:1:10": {
                "type": "reset",
                "guild_id": "1",
                "channel_id": "10",
                "first_attempt": one_hour_ago.isoformat(),
                "retry_count": 0,
            },
        }
        retry_queue._save_retry_queue(test_data)

        pending = retry_queue.get_pending_conversions()

        # Should include both types
        self.assertEqual(len(pending), 2)
        types = [p["type"] for p in pending]
        self.assertIn("conversion", types)
        self.assertIn("reset", types)

    def test_get_expired_conversions_returns_expired(self):
        """Test dat get_expired_conversions() expired operations returned (>2 uur)."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        three_hours_ago = now - timedelta(hours=3)

        # Add expired entry
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "guild_id": "1",
                "channel_id": "10",
                "user_id": "100",
                "dag": "vrijdag",
                "first_attempt": three_hours_ago.isoformat(),
                "retry_count": 5,
            }
        }
        retry_queue._save_retry_queue(test_data)

        expired = retry_queue.get_expired_conversions()

        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0]["guild_id"], "1")
        self.assertEqual(expired[0]["retry_count"], 5)
        self.assertEqual(expired[0]["key"], "conversion:1:10:100:vrijdag")

    def test_get_expired_conversions_filters_pending(self):
        """Test dat get_expired_conversions() pending operations filtert (<2 uur)."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        one_hour_ago = now - timedelta(hours=1)

        # Add pending entry
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "guild_id": "1",
                "channel_id": "10",
                "user_id": "100",
                "dag": "vrijdag",
                "first_attempt": one_hour_ago.isoformat(),
                "retry_count": 0,
            }
        }
        retry_queue._save_retry_queue(test_data)

        expired = retry_queue.get_expired_conversions()

        # Should not include pending entry
        self.assertEqual(len(expired), 0)

    def test_get_expired_conversions_handles_timezone_naive(self):
        """Test dat get_expired_conversions() timezone-naive datetimes handled."""
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        three_hours_ago_naive = (now - timedelta(hours=3)).replace(tzinfo=None)

        # Add expired entry with naive datetime
        test_data = {
            "reset:1:10": {
                "type": "reset",
                "guild_id": "1",
                "channel_id": "10",
                "first_attempt": three_hours_ago_naive.isoformat(),
                "retry_count": 0,
            }
        }
        retry_queue._save_retry_queue(test_data)

        expired = retry_queue.get_expired_conversions()

        # Should still work
        self.assertEqual(len(expired), 1)

    def test_get_expired_conversions_skips_invalid_entries(self):
        """Test dat get_expired_conversions() invalid entries skipt."""
        # Add invalid entry
        test_data = {
            "invalid_entry": {
                "type": "conversion",
            }
        }
        retry_queue._save_retry_queue(test_data)

        expired = retry_queue.get_expired_conversions()

        # Should skip invalid entry
        self.assertEqual(len(expired), 0)

    def test_remove_from_queue_existing_key(self):
        """Test dat remove_from_queue() bestaande key verwijderd."""
        test_data = {
            "conversion:1:10:100:vrijdag": {"type": "conversion"},
            "reset:1:10": {"type": "reset"},
        }
        retry_queue._save_retry_queue(test_data)

        retry_queue.remove_from_queue("conversion:1:10:100:vrijdag")

        queue = retry_queue._load_retry_queue()
        self.assertNotIn("conversion:1:10:100:vrijdag", queue)
        self.assertIn("reset:1:10", queue)  # Other entry still exists

    def test_remove_from_queue_non_existent_key(self):
        """Test dat remove_from_queue() geen error geeft bij non-existent key."""
        test_data = {"reset:1:10": {"type": "reset"}}
        retry_queue._save_retry_queue(test_data)

        # Should not raise error
        retry_queue.remove_from_queue("non_existent_key")

        queue = retry_queue._load_retry_queue()
        self.assertIn("reset:1:10", queue)  # Original entry still exists

    def test_increment_retry_count_existing_entry(self):
        """Test dat increment_retry_count() retry_count verhoogt."""
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                "retry_count": 3,
            }
        }
        retry_queue._save_retry_queue(test_data)

        retry_queue.increment_retry_count("conversion:1:10:100:vrijdag")

        queue = retry_queue._load_retry_queue()
        self.assertEqual(queue["conversion:1:10:100:vrijdag"]["retry_count"], 4)

    def test_increment_retry_count_missing_retry_count(self):
        """Test dat increment_retry_count() missing retry_count handled (default 0)."""
        test_data = {
            "conversion:1:10:100:vrijdag": {
                "type": "conversion",
                # No retry_count field
            }
        }
        retry_queue._save_retry_queue(test_data)

        retry_queue.increment_retry_count("conversion:1:10:100:vrijdag")

        queue = retry_queue._load_retry_queue()
        self.assertEqual(queue["conversion:1:10:100:vrijdag"]["retry_count"], 1)

    def test_increment_retry_count_non_existent_key(self):
        """Test dat increment_retry_count() geen error geeft bij non-existent key."""
        test_data = {"reset:1:10": {"type": "reset", "retry_count": 0}}
        retry_queue._save_retry_queue(test_data)

        # Should not raise error
        retry_queue.increment_retry_count("non_existent_key")

        queue = retry_queue._load_retry_queue()
        # Original entry unchanged
        self.assertEqual(queue["reset:1:10"]["retry_count"], 0)

    def test_clear_retry_queue(self):
        """Test dat clear_retry_queue() alle entries verwijderd."""
        test_data = {
            "conversion:1:10:100:vrijdag": {"type": "conversion"},
            "reset:1:10": {"type": "reset"},
        }
        retry_queue._save_retry_queue(test_data)

        retry_queue.clear_retry_queue()

        queue = retry_queue._load_retry_queue()
        self.assertEqual(queue, {})


if __name__ == "__main__":
    unittest.main()
