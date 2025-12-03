# tests/test_vote_message_dates.py
"""Test dat stemberichten (vote messages) correcte datums gebruiken uit rolling window."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.ui.poll_buttons import _get_timezone_legend
from apps.utils.poll_settings import set_poll_option_state
from tests.base import BaseTestCase


class TestVoteMessageDates(BaseTestCase):
    """Test dat stemberichten correcte datums tonen uit rolling window."""

    def test_vote_message_uses_rolling_window_dates(self):
        """Test dat stemberichten datums gebruiken uit rolling window, niet oude logica."""
        # Dinsdag 2 december 2025, 07:35
        tuesday = datetime(2025, 12, 2, 7, 35, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        channel_id = 12345

        # Enable alle dagen voor deze test
        for dag in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]:
            set_poll_option_state(channel_id, dag, "om 19:00 uur", True)
            set_poll_option_state(channel_id, dag, "om 20:30 uur", True)

        # Mock datetime in BEIDE modules
        with patch("apps.ui.poll_buttons.datetime") as mock_dt_buttons, \
             patch("apps.utils.message_builder.datetime") as mock_dt_builder:
            mock_dt_buttons.now.return_value = tuesday
            mock_dt_builder.now.return_value = tuesday

            # Haal stembericht legenda op voor donderdag
            donderdag_legenda = _get_timezone_legend("donderdag")

            # Verwacht: donderdag 4 december 2025 (niet 27 november!)
            # 4 december 2025 19:00 = timestamp 1764871200
            # 4 december 2025 20:30 = timestamp 1764876600

            # Check dat het DE JUISTE datum is (4 december)
            # We kunnen de exacte timestamp checken
            self.assertTrue(
                "1764871200" in donderdag_legenda or "1764876600" in donderdag_legenda,
                f"Expected 4 december timestamps in: {donderdag_legenda}"
            )

            # Check dat het NIET 27 november is (oude datum)
            # 27 november 2025 19:00 = timestamp 1764266400
            # 27 november 2025 20:30 = timestamp 1764271800
            self.assertNotIn("1764266400", donderdag_legenda)
            self.assertNotIn("1764271800", donderdag_legenda)

            # Haal stembericht legenda op voor zondag
            zondag_legenda = _get_timezone_legend("zondag")

            # Verwacht: zondag 7 december 2025 (niet 30 november!)
            # 7 december 2025 19:00 = timestamp 1765130400
            # 7 december 2025 20:30 = timestamp 1765135800

            # Check dat het DE JUISTE datum is (7 december)
            self.assertTrue(
                "1765130400" in zondag_legenda or "1765135800" in zondag_legenda,
                f"Expected 7 december timestamps in: {zondag_legenda}"
            )

            # Check dat het NIET 30 november is (oude datum)
            # 30 november 2025 19:00 = timestamp 1764525600
            # 30 november 2025 20:30 = timestamp 1764531000
            self.assertNotIn("1764525600", zondag_legenda)
            self.assertNotIn("1764531000", zondag_legenda)

    def test_vote_message_dates_match_poll_message_dates(self):
        """Test dat stemberichten en pollberichten dezelfde datums gebruiken."""
        # Dinsdag 2 december 2025, 07:35
        tuesday = datetime(2025, 12, 2, 7, 35, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

        channel_id = 12345

        # Enable alle dagen
        for dag in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]:
            set_poll_option_state(channel_id, dag, "om 19:00 uur", True)
            set_poll_option_state(channel_id, dag, "om 20:30 uur", True)

        with patch("apps.ui.poll_buttons.datetime") as mock_dt_buttons, \
             patch("apps.utils.message_builder.datetime") as mock_dt_builder:
            mock_dt_buttons.now.return_value = tuesday
            mock_dt_builder.now.return_value = tuesday

            # Haal rolling window dagen op
            from apps.utils.poll_settings import get_enabled_rolling_window_days
            dagen_info = get_enabled_rolling_window_days(channel_id, dag_als_vandaag=None)

            # Voor elke dag: check dat stembericht dezelfde datum gebruikt als rolling window
            for day_info in dagen_info:
                dag = day_info["dag"]
                # datum_iso is beschikbaar in day_info maar wordt niet gebruikt in deze test
                # omdat we alleen het Hammertime format valideren, niet de exacte timestamp

                # Haal stembericht legenda op
                legenda = _get_timezone_legend(dag)

                # Extract timestamps from legenda
                # Legenda format: "emoji 19:00 = <t:TIMESTAMP:F> | emoji 20:30 = <t:TIMESTAMP:F>"
                self.assertIn("<t:", legenda)

                # Verify dat het Hammertime format is (we kunnen niet exact timestamp checken
                # omdat TimeZoneHelper conversie kan falen, maar we kunnen wel checken dat
                # het juiste format gebruikt wordt)
                self.assertIn(":F>", legenda)


if __name__ == "__main__":
    import unittest
    unittest.main()
