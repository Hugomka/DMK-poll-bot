# tests/test_rolling_window_integration.py
"""Integratie tests voor rolling window met dmk-poll-on command."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.utils.poll_settings import get_enabled_rolling_window_days
from apps.utils.poll_message import set_dag_als_vandaag, get_dag_als_vandaag
from tests.base import BaseTestCase


class TestRollingWindowIntegration(BaseTestCase):
    """Test rolling window integratie met dmk-poll-on."""

    def test_dmk_poll_on_without_parameter_uses_current_day(self):
        """Test dat /dmk-poll-on zonder parameter de huidige dag gebruikt."""
        # Dinsdag 2 december 2025, 07:15
        tuesday = datetime(2025, 12, 2, 7, 15, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            # Simuleer: /dmk-poll-on wordt uitgevoerd zonder parameters
            # Dit moet de huidige dag (dinsdag) opslaan
            channel_id = 12345

            # Enable alle dagen voor deze test
            from apps.utils.poll_settings import set_poll_option_state
            for dag in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]:
                set_poll_option_state(channel_id, dag, "om 19:00 uur", True)
                set_poll_option_state(channel_id, dag, "om 20:30 uur", True)

            # Bepaal effective_dag_als_vandaag zoals de on command doet
            from apps.utils.constants import DAG_NAMEN
            effective_dag_als_vandaag = DAG_NAMEN[tuesday.weekday()]  # dinsdag

            # Sla op
            set_dag_als_vandaag(channel_id, effective_dag_als_vandaag)

            # Haal rolling window op
            dagen_info = get_enabled_rolling_window_days(channel_id, effective_dag_als_vandaag)

            # Verwacht: chronologische volgorde met correcte datums
            # -1: maandag 1 dec
            # 0: dinsdag 2 dec (today)
            # +1: woensdag 3 dec
            # +2: donderdag 4 dec
            # +3: vrijdag 5 dec
            # +4: zaterdag 6 dec
            # +5: zondag 7 dec

            self.assertEqual(len(dagen_info), 7)

            # Check maandag
            maandag = dagen_info[0]
            self.assertEqual(maandag["dag"], "maandag")
            self.assertEqual(maandag["datum_iso"], "2025-12-01")
            self.assertTrue(maandag["is_past"])

            # Check dinsdag (today)
            dinsdag = dagen_info[1]
            self.assertEqual(dinsdag["dag"], "dinsdag")
            self.assertEqual(dinsdag["datum_iso"], "2025-12-02")
            self.assertTrue(dinsdag["is_today"])

            # Check woensdag
            woensdag = dagen_info[2]
            self.assertEqual(woensdag["dag"], "woensdag")
            self.assertEqual(woensdag["datum_iso"], "2025-12-03")
            self.assertTrue(woensdag["is_future"])

            # Check donderdag - NIET 27 november!
            donderdag = dagen_info[3]
            self.assertEqual(donderdag["dag"], "donderdag")
            self.assertEqual(donderdag["datum_iso"], "2025-12-04")
            self.assertTrue(donderdag["is_future"])

            # Check zondag - NIET 30 november!
            zondag = dagen_info[6]
            self.assertEqual(zondag["dag"], "zondag")
            self.assertEqual(zondag["datum_iso"], "2025-12-07")
            self.assertTrue(zondag["is_future"])

    def test_dmk_poll_on_respects_old_saved_dag_als_vandaag(self):
        """Test dat oude opgeslagen dag_als_vandaag NIET wordt gebruikt als we nieuwe /dmk-poll-on doen."""
        # Dinsdag 2 december 2025, 07:15
        tuesday = datetime(2025, 12, 2, 7, 15, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        channel_id = 12345

        # Enable alle dagen voor deze test
        from apps.utils.poll_settings import set_poll_option_state
        for dag in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]:
            set_poll_option_state(channel_id, dag, "om 19:00 uur", True)
            set_poll_option_state(channel_id, dag, "om 20:30 uur", True)

        # Simuleer: er staat een oude waarde in de state (bijv. "donderdag")
        set_dag_als_vandaag(channel_id, "donderdag")

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = tuesday

            # Nu doen we /dmk-poll-on zonder parameters
            # Dit moet de oude waarde OVERSCHRIJVEN met de huidige dag
            from apps.utils.constants import DAG_NAMEN
            effective_dag_als_vandaag = DAG_NAMEN[tuesday.weekday()]  # dinsdag

            # Sla nieuwe waarde op (zoals de on command doet)
            set_dag_als_vandaag(channel_id, effective_dag_als_vandaag)

            # Haal opgeslagen waarde op
            saved_dag = get_dag_als_vandaag(channel_id)
            self.assertEqual(saved_dag, "dinsdag")  # NIET "donderdag"!

            # Haal rolling window op met de nieuwe waarde
            dagen_info = get_enabled_rolling_window_days(channel_id, effective_dag_als_vandaag)

            # Check dat donderdag 4 december is (niet 27 november)
            donderdag = next((d for d in dagen_info if d["dag"] == "donderdag"), None)
            self.assertIsNotNone(donderdag)
            assert donderdag is not None  # Type narrowing
            self.assertEqual(donderdag["datum_iso"], "2025-12-04")
            self.assertTrue(donderdag["is_future"])
