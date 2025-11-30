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
            result = _get_next_weekday_date("invaliddag")
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

    def test_get_next_weekday_date_for_monday_on_tuesday(self):
        """Test dat maandag op dinsdag de aankomende maandag retourneert."""
        # Dinsdag 5 november 2024, 14:00 (voor 20:00)
        # Poll-periode: di 29 okt 20:00 - di 5 nov 20:00
        # Maandag in deze periode: 4 november
        tuesday = datetime(2024, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("maandag")
            self.assertEqual(result, "04-11")  # 4 november

    def test_get_next_weekday_date_for_tuesday_on_tuesday(self):
        """Test dat dinsdag op dinsdag de volgende dinsdag retourneert."""
        # Dinsdag 5 november 2024, 14:00 (voor 20:00)
        # Poll-periode: di 29 okt 20:00 - di 5 nov 20:00
        # Dinsdag in deze periode: 5 november
        tuesday = datetime(2024, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("dinsdag")
            self.assertEqual(result, "05-11")  # 5 november

    def test_get_next_weekday_date_for_wednesday_on_tuesday(self):
        """Test dat woensdag op dinsdag de aankomende woensdag retourneert."""
        # Dinsdag 5 november 2024, 14:00
        # Poll-periode: di 29 okt 20:00 - di 5 nov 20:00
        # Woensdag in deze periode: 6 november
        tuesday = datetime(2024, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("woensdag")
            self.assertEqual(result, "30-10")  # 30 oktober (van huidige periode)

    def test_get_next_weekday_date_for_thursday_on_tuesday(self):
        """Test dat donderdag op dinsdag de aankomende donderdag retourneert."""
        # Dinsdag 5 november 2024, 14:00
        # Poll-periode: di 29 okt 20:00 - di 5 nov 20:00
        # Donderdag in deze periode: 31 oktober
        tuesday = datetime(2024, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday
            result = _get_next_weekday_date("donderdag")
            self.assertEqual(result, "31-10")  # 31 oktober


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

            # Verwacht "DMK-poll voor Vrijdag (07-11):"
            self.assertIn("Vrijdag (07-11)", message)

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

            self.assertIn("(07-11)", vrijdag_msg)
            self.assertIn("(08-11)", zaterdag_msg)
            self.assertIn("(09-11)", zondag_msg)

    async def test_build_message_with_pauze_includes_date(self):
        """Test dat gepauzeerd bericht ook datum bevat."""
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            message = await build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=100, pauze=True
            )

            # Verwacht "DMK-poll voor Vrijdag (07-11): - (Gepauzeerd)"
            self.assertIn("Vrijdag (07-11)", message)
            self.assertIn("Gepauzeerd", message)

    async def test_build_message_shows_dates_for_all_weekdays(self):
        """Test dat alle weekdagen (maandag t/m zondag) datums tonen."""
        # Dinsdag 5 november 2024, 14:00 (voor 20:00)
        # Poll-periode: di 29 okt 20:00 - di 5 nov 20:00
        tuesday = datetime(2024, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            # Verwachte datums voor alle dagen van deze poll-periode
            expected_dates = {
                "maandag": "04-11",  # Ma 4 nov
                "dinsdag": "05-11",  # Di 5 nov
                "woensdag": "30-10",  # Wo 30 okt
                "donderdag": "31-10",  # Do 31 okt
                "vrijdag": "01-11",  # Vr 1 nov
                "zaterdag": "02-11",  # Za 2 nov
                "zondag": "03-11",  # Zo 3 nov
            }

            for dag, expected_date in expected_dates.items():
                message = await build_poll_message_for_day_async(
                    dag, guild_id=1, channel_id=100
                )
                self.assertIn(
                    f"{dag.capitalize()} ({expected_date})",
                    message,
                    f"{dag} should show date {expected_date}",
                )
