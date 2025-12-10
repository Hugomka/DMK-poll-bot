# tests/test_pollberichten.py

from datetime import datetime, timedelta

from apps.utils.poll_message import build_poll_message_for_day_async
from tests.base import BaseTestCase


class TestPollBerichten(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_pollbericht_zonder_stemmen(self):
        bericht = await build_poll_message_for_day_async(
            "vrijdag", 1, 123, hide_counts=False, pauze=False
        )
        self.assertIn("vrijdag", bericht.lower())
        self.assertIn("0 stemmen", bericht)

    async def test_pollbericht_met_pauze(self):
        bericht = await build_poll_message_for_day_async(
            "zaterdag", 1, 123, hide_counts=False, pauze=True
        )
        self.assertIn("gepauzeerd", bericht.lower())

    async def test_pollbericht_verbergt_aantallen(self):
        # Gebruik zondag van de huidige week (realistisch voor DMK-poll-bot)
        # Bot werkt met huidige week (maandag t/m zondag), datum kan in verleden/toekomst zijn
        now = datetime.now()
        days_since_monday = now.weekday()  # 0=maandag, 6=zondag
        monday_this_week = now - timedelta(days=days_since_monday)
        sunday_this_week = monday_this_week + timedelta(days=6)  # Zondag = +6 dagen
        sunday_date = sunday_this_week.strftime("%Y-%m-%d")
        bericht = await build_poll_message_for_day_async(
            "zondag", 1, 123, hide_counts=True, pauze=False, datum_iso=sunday_date
        )
        self.assertIn("stemmen verborgen", bericht.lower())

    async def test_pollbericht_met_geen_opties(self):
        from unittest.mock import patch

        with patch("apps.utils.message_builder.get_poll_options", return_value=[]):
            bericht = await build_poll_message_for_day_async(
                "vrijdag", 1, 123, hide_counts=False, pauze=False
            )
            self.assertIn("geen opties gevonden", bericht.lower())
