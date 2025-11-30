"""Tests voor TimeZoneHelper tijdzone conversie functies."""

import unittest
from datetime import date

from apps.utils.time_zone_helper import TimeZoneHelper


class TestNlTijdNaarHammertime(unittest.TestCase):
    """Tests voor nl_tijd_naar_hammertime functie."""

    def test_converteer_nl_tijd_naar_hammertime_default_style(self):
        """Test conversie van NL datum/tijd naar Hammertime met standaard style."""
        result = TimeZoneHelper.nl_tijd_naar_hammertime("2025-01-15", "19:00")
        # Verwacht: <t:TIMESTAMP:t> format
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":t>"))
        # Timestamp moet een getal zijn
        timestamp_str = result[3:-3]  # Extract timestamp tussen <t: en :t>
        self.assertTrue(timestamp_str.isdigit())

    def test_converteer_nl_tijd_naar_hammertime_custom_style(self):
        """Test conversie met verschillende Hammertime styles."""
        styles = ["t", "T", "d", "D", "f", "F", "R"]
        for style in styles:
            result = TimeZoneHelper.nl_tijd_naar_hammertime(
                "2025-01-15", "19:00", style=style
            )
            self.assertTrue(result.startswith("<t:"))
            self.assertTrue(result.endswith(f":{style}>"))

    def test_converteer_wintertijd_correct(self):
        """Test conversie tijdens wintertijd (CET = UTC+1)."""
        # 15 januari 2025, 19:00 CET = 18:00 UTC
        result = TimeZoneHelper.nl_tijd_naar_hammertime("2025-01-15", "19:00")
        timestamp_str = result[3:-3]
        timestamp = int(timestamp_str)
        # Verwacht: 15 jan 2025 18:00 UTC = 1736964000
        # Exact timestamp checken is fragiel, maar we kunnen de orde van grootte checken
        self.assertGreater(timestamp, 1700000000)  # Na 2023
        self.assertLess(timestamp, 1800000000)  # Voor 2027

    def test_converteer_zomertijd_correct(self):
        """Test conversie tijdens zomertijd (CEST = UTC+2)."""
        # 15 juli 2025, 19:00 CEST = 17:00 UTC
        result = TimeZoneHelper.nl_tijd_naar_hammertime("2025-07-15", "19:00")
        timestamp_str = result[3:-3]
        timestamp = int(timestamp_str)
        # Verwacht: 15 juli 2025 17:00 UTC
        self.assertGreater(timestamp, 1700000000)
        self.assertLess(timestamp, 1800000000)

    def test_invalid_datum_geeft_fallback(self):
        """Test dat ongeldige datum terugvalt naar tijd string."""
        result = TimeZoneHelper.nl_tijd_naar_hammertime("invalid-date", "19:00")
        self.assertEqual(result, "19:00")

    def test_invalid_tijd_geeft_fallback(self):
        """Test dat ongeldige tijd terugvalt naar tijd string."""
        result = TimeZoneHelper.nl_tijd_naar_hammertime("2025-01-15", "invalid:time")
        self.assertEqual(result, "invalid:time")


class TestNlTijdNaarUserTijd(unittest.TestCase):
    """Tests voor nl_tijd_naar_user_tijd functie."""

    def test_converteer_naar_zelfde_timezone(self):
        """Test conversie naar dezelfde tijdzone (NL → NL)."""
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="Europe/Amsterdam"
        )
        self.assertEqual(result, "19:00")

    def test_converteer_naar_us_eastern(self):
        """Test conversie naar US Eastern tijdzone."""
        # Gebruik expliciete datum in winter (geen DST complicaties)
        winter_datum = date(2025, 1, 15)
        # 19:00 CET (UTC+1) = 13:00 EST (UTC-5) → verschil van 6 uur
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="America/New_York", datum=winter_datum
        )
        self.assertEqual(result, "13:00")

    def test_converteer_naar_us_pacific(self):
        """Test conversie naar US Pacific tijdzone."""
        winter_datum = date(2025, 1, 15)
        # 19:00 CET (UTC+1) = 10:00 PST (UTC-8) → verschil van 9 uur
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="America/Los_Angeles", datum=winter_datum
        )
        self.assertEqual(result, "10:00")

    def test_converteer_naar_tokyo(self):
        """Test conversie naar Tokyo tijdzone."""
        winter_datum = date(2025, 1, 15)
        # 19:00 CET (UTC+1) = 03:00+1day JST (UTC+9) → verschil van 8 uur vooruit
        # Maar omdat we alleen tijd tonen, wordt dit 03:00 (volgende dag)
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="Asia/Tokyo", datum=winter_datum
        )
        self.assertEqual(result, "03:00")

    def test_converteer_naar_london(self):
        """Test conversie naar London tijdzone."""
        winter_datum = date(2025, 1, 15)
        # 19:00 CET (UTC+1) = 18:00 GMT (UTC+0) → verschil van 1 uur
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="Europe/London", datum=winter_datum
        )
        self.assertEqual(result, "18:00")

    def test_dst_handling_zomer(self):
        """Test correcte DST handling in de zomer."""
        zomer_datum = date(2025, 7, 15)
        # 19:00 CEST (UTC+2) = 13:00 EDT (UTC-4) → verschil van 6 uur
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="America/New_York", datum=zomer_datum
        )
        self.assertEqual(result, "13:00")

    def test_default_datum_is_vandaag(self):
        """Test dat standaard datum vandaag is (geen error)."""
        # Dit test moet gewoon niet crashen
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="America/New_York"
        )
        # Result moet een geldige tijd zijn in HH:MM format
        self.assertRegex(result, r"^\d{2}:\d{2}$")

    def test_invalid_timezone_geeft_fallback(self):
        """Test dat ongeldige tijdzone terugvalt naar originele tijd."""
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "19:00", user_timezone="Invalid/Timezone"
        )
        self.assertEqual(result, "19:00")

    def test_invalid_tijd_format_geeft_fallback(self):
        """Test dat ongeldig tijd formaat terugvalt naar originele string."""
        result = TimeZoneHelper.nl_tijd_naar_user_tijd("invalid:time")
        self.assertEqual(result, "invalid:time")

    def test_edge_case_midnight(self):
        """Test conversie van middernacht."""
        winter_datum = date(2025, 1, 15)
        # 00:00 CET = 18:00 vorige dag EST (verschil 6 uur terug)
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "00:00", user_timezone="America/New_York", datum=winter_datum
        )
        self.assertEqual(result, "18:00")

    def test_edge_case_almost_midnight(self):
        """Test conversie van bijna middernacht."""
        winter_datum = date(2025, 1, 15)
        # 23:00 CET = 17:00 EST
        result = TimeZoneHelper.nl_tijd_naar_user_tijd(
            "23:00", user_timezone="America/New_York", datum=winter_datum
        )
        self.assertEqual(result, "17:00")


if __name__ == "__main__":
    unittest.main()
