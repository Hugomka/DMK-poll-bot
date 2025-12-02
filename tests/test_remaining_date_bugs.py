# tests/test_remaining_date_bugs.py
"""Test om te bewijzen of er nog verborgen datum bugs zijn in message builder fallback."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_settings import set_poll_option_state
from tests.base import BaseTestCase


class TestPollMessageButtonLabelDates(BaseTestCase):
    """Test dat poll message button labels correcte datums gebruiken."""

    async def test_poll_message_button_labels_use_correct_dates(self):
        """Test dat button labels in poll berichten correcte datums gebruiken."""
        # Dinsdag 2 december 2025, 07:35
        tuesday = datetime(2025, 12, 2, 7, 35, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        channel_id = 12345
        guild_id = 99999

        # Enable donderdag
        set_poll_option_state(channel_id, "donderdag", "19:00", True)
        set_poll_option_state(channel_id, "donderdag", "20:30", True)

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            # Bouw poll bericht voor donderdag (zonder datum_iso parameter - trigger fallback)
            message = await build_poll_message_for_day_async(
                "donderdag",
                guild_id=guild_id,
                channel_id=channel_id,
                datum_iso=None,  # Dit triggert de fallback naar _get_next_weekday_date_iso
                hide_counts=False  # Toon timestamps in buttons
            )

            # Verwacht: donderdag 4 december 2025 timestamps
            # 4 december 2025 19:00 = timestamp 1764871200
            # 4 december 2025 20:30 = timestamp 1764876600

            # Check dat button labels de juiste timestamps bevatten
            self.assertTrue(
                "1764871200" in message or "1764876600" in message,
                f"Expected 4 december timestamps in poll message: {message}"
            )

            # Check dat het NIET 27 november is (verkeerde datum)
            # 27 november 2025 19:00 = timestamp 1764266400
            # 27 november 2025 20:30 = timestamp 1764271800
            self.assertNotIn("1764266400", message,
                f"Should not contain 27 november 19:00 timestamp in: {message}")
            self.assertNotIn("1764271800", message,
                f"Should not contain 27 november 20:30 timestamp in: {message}")


if __name__ == "__main__":
    import unittest
    unittest.main()
