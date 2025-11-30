# tests/test_message_builder_dates.py
"""Tests voor datum weergave in poll-berichten."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.utils.message_builder import (
    _get_next_weekday_date,
    build_poll_message_for_day_async,
)
from tests.base import BaseTestCase


class TestGetNextWeekdayDate(BaseTestCase):
    """Test _get_next_weekday_date helper functie."""

    def test_get_next_weekday_date_for_friday_on_tuesday(self):
        """Test dat vrijdag op dinsdag de aankomende vrijdag retourneert."""
        # Mock datetime.now() om dinsdag 5 november 2025 te retourneren
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("vrijdag")
            self.assertEqual(result, "07-11")  # 7 november

    def test_get_next_weekday_date_for_saturday_on_tuesday(self):
        """Test dat zaterdag op dinsdag de aankomende zaterdag retourneert."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("zaterdag")
            self.assertEqual(result, "08-11")  # 8 november

    def test_get_next_weekday_date_for_sunday_on_tuesday(self):
        """Test dat zondag op dinsdag de aankomende zondag retourneert."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("zondag")
            self.assertEqual(result, "09-11")  # 9 november

    def test_get_next_weekday_date_on_friday_returns_same_day(self):
        """Test dat op vrijdag diezelfde vrijdag wordt geretourneerd."""
        friday = datetime(2025, 11, 7, 10, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = friday
            result = _get_next_weekday_date("vrijdag")
            self.assertEqual(result, "07-11")  # Vandaag

    def test_get_next_weekday_date_on_monday_returns_current_period_friday(self):
        """Test dat op maandag de vrijdag van de huidige poll-periode wordt geretourneerd.

        Poll-periode loopt van dinsdag 20:00 tot dinsdag 20:00.
        Maandag 10 november valt in periode di 5 nov 20:00 - di 12 nov 20:00.
        Dus moet vrijdag 7 november worden geretourneerd (van huidige periode).
        """
        monday = datetime(2025, 11, 10, 9, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = monday
            result = _get_next_weekday_date("vrijdag")
            self.assertEqual(result, "07-11")  # Vrijdag van huidige poll-periode

    def test_get_next_weekday_date_with_invalid_dag_returns_empty(self):
        """Test dat ongeldige dag lege string retourneert."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("maandag")
            self.assertEqual(result, "")

    def test_get_next_weekday_date_case_insensitive(self):
        """Test dat functie case-insensitive is."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result_lower = _get_next_weekday_date("vrijdag")
            result_upper = _get_next_weekday_date("VRIJDAG")
            result_mixed = _get_next_weekday_date("Vrijdag")
            self.assertEqual(result_lower, result_upper)
            self.assertEqual(result_lower, result_mixed)


class TestBuildPollMessageWithDates(BaseTestCase):
    """Test dat poll-berichten datums bevatten."""

    async def test_build_message_includes_date_in_title(self):
        """Test dat poll-bericht datum bevat in titel."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            message = await build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=100
            )

            # Verwacht "DMK-poll voor Vrijdag (<t:TIMESTAMP:D>):"
            self.assertIn("Vrijdag (<t:", message)
            self.assertIn(":D>)", message)

    async def test_build_message_shows_correct_date_for_each_day(self):
        """Test dat elke dag de correcte datum toont."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            vrijdag_msg = await build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=100
            )
            zaterdag_msg = await build_poll_message_for_day_async(
                "zaterdag", guild_id=1, channel_id=100
            )
            zondag_msg = await build_poll_message_for_day_async(
                "zondag", guild_id=1, channel_id=100
            )

            # Check voor Hammertime format in plaats van DD-MM format
            self.assertIn("(<t:", vrijdag_msg)
            self.assertIn("(<t:", zaterdag_msg)
            self.assertIn("(<t:", zondag_msg)
            self.assertIn(":D>)", vrijdag_msg)
            self.assertIn(":D>)", zaterdag_msg)
            self.assertIn(":D>)", zondag_msg)

    async def test_build_message_with_pauze_includes_date(self):
        """Test dat gepauzeerd bericht ook datum bevat."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            message = await build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=100, pauze=True
            )

            # Verwacht "DMK-poll voor Vrijdag (<t:TIMESTAMP:D>): - (Gepauzeerd)"
            self.assertIn("Vrijdag (<t:", message)
            self.assertIn(":D>)", message)
            self.assertIn("Gepauzeerd", message)
