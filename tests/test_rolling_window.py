# tests/test_rolling_window.py
"""Tests voor rolling window met dag_als_vandaag parameter."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.utils.message_builder import get_rolling_window_days
from tests.base import BaseTestCase


class TestRollingWindowWithDagAlsVandaag(BaseTestCase):
    """Test rolling window met dag_als_vandaag parameter."""

    def test_dag_als_vandaag_looks_forward_not_backward(self):
        """Test dat dag_als_vandaag vooruit kijkt naar de volgende occurrence, niet terug."""
        # Maandag 1 december 2025, 14:00
        monday = datetime(2025, 12, 1, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = monday

            # Gebruik dinsdag als "vandaag"
            dagen_info = get_rolling_window_days(dag_als_vandaag="dinsdag")

            # Verwacht:
            # - offset -1: maandag 1 dec (is_past=True)
            # - offset 0: dinsdag 2 dec (is_today=True) <- VOORUIT, niet terug naar 25 nov
            # - offset +1 t/m +5: woensdag 3 t/m zondag 7 dec

            # Check dat dinsdag 2 december "today" is (niet 25 november)
            today_item = next((d for d in dagen_info if d["is_today"]), None)
            self.assertIsNotNone(today_item)
            assert today_item is not None  # Type narrowing for Pylance
            self.assertEqual(today_item["dag"], "dinsdag")
            self.assertEqual(today_item["datum"].day, 2)
            self.assertEqual(today_item["datum"].month, 12)

            # Check dat zondag in de toekomst ligt (7 december, niet 30 november)
            zondag_item = next((d for d in dagen_info if d["dag"] == "zondag"), None)
            self.assertIsNotNone(zondag_item)
            assert zondag_item is not None  # Type narrowing for Pylance
            self.assertEqual(zondag_item["dag"], "zondag")
            self.assertEqual(zondag_item["datum"].day, 7)
            self.assertEqual(zondag_item["datum"].month, 12)
            self.assertTrue(zondag_item["is_future"])

    def test_dag_als_vandaag_on_same_day_uses_today(self):
        """Test dat als vandaag al de gekozen dag is, vandaag wordt gebruikt."""
        # Dinsdag 2 december 2025, 14:00
        tuesday = datetime(2025, 12, 2, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            # Gebruik dinsdag als "vandaag" (terwijl het al dinsdag is)
            dagen_info = get_rolling_window_days(dag_als_vandaag="dinsdag")

            # Verwacht: dinsdag 2 december is "today"
            today_item = next((d for d in dagen_info if d["is_today"]), None)
            self.assertIsNotNone(today_item)
            assert today_item is not None  # Type narrowing for Pylance
            self.assertEqual(today_item["dag"], "dinsdag")
            self.assertEqual(today_item["datum"].day, 2)
            self.assertEqual(today_item["datum"].month, 12)

    def test_dag_als_vandaag_none_uses_real_today(self):
        """Test dat dag_als_vandaag=None de echte vandaag gebruikt."""
        # Maandag 1 december 2025, 14:00
        monday = datetime(2025, 12, 1, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = monday

            # Geen dag_als_vandaag parameter
            dagen_info = get_rolling_window_days(dag_als_vandaag=None)

            # Verwacht: maandag 1 december is "today"
            today_item = next((d for d in dagen_info if d["is_today"]), None)
            self.assertIsNotNone(today_item)
            assert today_item is not None  # Type narrowing for Pylance
            self.assertEqual(today_item["dag"], "maandag")
            self.assertEqual(today_item["datum"].day, 1)
            self.assertEqual(today_item["datum"].month, 12)

    def test_dag_als_vandaag_covers_all_seven_days(self):
        """Test dat rolling window altijd 7 dagen bevat."""
        # Maandag 1 december 2025, 14:00
        monday = datetime(2025, 12, 1, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = monday

            dagen_info = get_rolling_window_days(dag_als_vandaag="woensdag")

            # Verwacht: exact 7 dagen
            self.assertEqual(len(dagen_info), 7)

            # Check dat we exact 1 is_past, 1 is_today, en 5 is_future hebben
            past_count = sum(1 for d in dagen_info if d["is_past"])
            today_count = sum(1 for d in dagen_info if d["is_today"])
            future_count = sum(1 for d in dagen_info if d["is_future"])

            self.assertEqual(past_count, 1)
            self.assertEqual(today_count, 1)
            self.assertEqual(future_count, 5)
