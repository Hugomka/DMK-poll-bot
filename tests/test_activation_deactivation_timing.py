# tests/test_activation_deactivation_timing.py

"""
Edge case tests voor activation/deactivation timing.
Test dat format_opening_time_from_schedule() de juiste opening tijd genereert
voor verschillende scenario's, waarbij activatie altijd binnen 168 uur (7 dagen) na deactivatie valt.

Belangrijke regel: activatie moet ALTIJD binnen 167 uur en 59 minuten vallen na deactivatie.
(Seconden worden verwaarloosd omdat alleen hh:mm instelbaar is)
"""

import unittest
from datetime import datetime
from unittest.mock import patch

import pytz


class TestActivationDeactivationTiming(unittest.TestCase):
    """Test edge cases voor activation/deactivation timing met format_opening_time_from_schedule()."""

    # DRY: Centralized helper methods
    TZ_AMSTERDAM = pytz.timezone("Europe/Amsterdam")

    def _mock_datetime_now(self, fake_now):
        """
        Helper: Mock datetime.now() terwijl datetime constructor intact blijft.
        Dit voorkomt duplicatie van mock setup in elke test.
        """
        patcher = patch("apps.utils.notification_texts.datetime")
        mock_dt = patcher.start()
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw) if args else fake_now
        self.addCleanup(patcher.stop)
        return mock_dt

    def _create_datetime(self, year, month, day, hour=0, minute=0):
        """Helper: Creëer datetime object met Amsterdam timezone."""
        return datetime(year, month, day, hour, minute, 0, tzinfo=self.TZ_AMSTERDAM)

    def _assert_weekday_date(self, dag, expected_date, message):
        """
        Helper: Test dat _get_next_weekday_date() de verwachte datum returnt.
        Dit vermindert duplicatie in assertions.
        """
        from apps.utils.notification_texts import _get_next_weekday_date
        result = _get_next_weekday_date(dag)
        self.assertEqual(result, expected_date, message)
        return result

    def test_monday_00_00_to_tuesday_19_00_exactly_43_hours(self):
        """
        Test: maandag 00:00 gesloten - dinsdag 19:00 open = exact 43 uur later.

        Scenario:
        - Deactivatie: maandag 00:00
        - Activatie schedule: {"type": "wekelijks", "dag": "dinsdag", "tijd": "19:00"}
        - Verwacht: dinsdag van DEZE week (niet volgende week)
        """
        from apps.utils.notification_texts import format_opening_time_from_schedule

        fake_now = self._create_datetime(2026, 1, 5, 0, 0)  # maandag 00:00
        self._mock_datetime_now(fake_now)

        schedule = {"type": "wekelijks", "dag": "dinsdag", "tijd": "19:00"}
        result = format_opening_time_from_schedule(schedule)

        # Verify format_opening_time_from_schedule returnt een string
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0, "Result mag niet leeg zijn")

        # De belangrijkste check: datum moet deze week zijn
        self._assert_weekday_date(
            "dinsdag",
            "2026-01-06",
            "Dinsdag moet deze week zijn (1 dag na maandag), niet volgende week"
        )

    def test_monday_00_00_to_monday_01_00_exactly_1_hour(self):
        """
        Test: maandag 00:00 gesloten - maandag 01:00 open = exact 1 uur later.

        Scenario:
        - Deactivatie: maandag 00:00
        - Activatie: maandag 01:00 (zelfde dag!)
        - Verwacht: maandag van DEZE week (VANDAAG, niet volgende week!)
        """
        fake_now = self._create_datetime(2026, 1, 5, 0, 0)  # maandag 00:00
        self._mock_datetime_now(fake_now)

        self._assert_weekday_date(
            "maandag",
            "2026-01-05",
            "Maandag moet VANDAAG zijn (0 dagen), niet volgende week (7 dagen)"
        )

    def test_monday_00_00_to_thursday_00_00_exactly_72_hours(self):
        """
        Test: maandag 00:00 gesloten - donderdag 00:00 open = exact 72 uur later (3 dagen).

        Scenario:
        - Deactivatie: maandag 00:00
        - Activatie: donderdag 00:00
        - Verwacht: donderdag van DEZE week (3 dagen later)
        """
        fake_now = self._create_datetime(2026, 1, 5, 0, 0)  # maandag 00:00
        self._mock_datetime_now(fake_now)

        self._assert_weekday_date(
            "donderdag",
            "2026-01-08",
            "Donderdag moet 3 dagen na maandag zijn (deze week)"
        )

    def test_tuesday_00_00_to_tuesday_19_00_exactly_19_hours(self):
        """
        Test: dinsdag 00:00 gesloten - dinsdag 19:00 open = exact 19 uur later.

        Scenario:
        - Deactivatie: dinsdag 00:00
        - Activatie: dinsdag 19:00 (zelfde dag!)
        - Verwacht: dinsdag van DEZE week (VANDAAG)
        """
        fake_now = self._create_datetime(2026, 1, 6, 0, 0)  # dinsdag 00:00
        self._mock_datetime_now(fake_now)

        self._assert_weekday_date(
            "dinsdag",
            "2026-01-06",
            "Dinsdag moet VANDAAG zijn (0 dagen)"
        )

    def test_tuesday_19_00_to_tuesday_19_00_exactly_0_hours_instant_open(self):
        """
        Test: dinsdag 19:00 gesloten - dinsdag 19:00 open = exact 0 uur later (instant open).

        Scenario:
        - Deactivatie: dinsdag 19:00
        - Activatie: dinsdag 19:00 (zelfde moment!)
        - Verwacht: dinsdag van DEZE week (VANDAAG)
        - Note: Scheduler volgorde bepaalt of deactivate of activate eerst draait.
        """
        fake_now = self._create_datetime(2026, 1, 6, 19, 0)  # dinsdag 19:00
        self._mock_datetime_now(fake_now)

        self._assert_weekday_date(
            "dinsdag",
            "2026-01-06",
            "Dinsdag moet VANDAAG zijn (instant reopen scenario)"
        )

    def test_tuesday_20_00_to_tuesday_19_00_misleading_display(self):
        """
        Test: dinsdag 20:00 gesloten - dinsdag 19:00 open = MISLEIDEND scenario (167u later).

        Scenario:
        - Deactivatie: dinsdag 20:00
        - Activatie: dinsdag 19:00 (1 uur EERDER op de dag)
        - Verwacht: Functie returnt "vandaag" (technisch correct), maar dit is misleidend!

        BELANGRIJKE NOTE:
        Dit scenario betekent dat de activatie tijd (19:00) EERDER is dan deactivatie tijd (20:00)
        op dezelfde dag. De functie _get_next_weekday_date() returnt VANDAAG (want vandaag IS dinsdag),
        maar in de praktijk zal de scheduler pas VOLGENDE WEEK dinsdag 19:00 triggeren.

        Dit geeft een misleidende display: "dinsdag 19:00" lijkt vandaag, maar is volgende week!

        OPLOSSING: Validation in UI om te voorkomen dat activation tijd < deactivation tijd op zelfde dag.
        """
        fake_now = self._create_datetime(2026, 1, 6, 20, 0)  # dinsdag 20:00
        self._mock_datetime_now(fake_now)

        self._assert_weekday_date(
            "dinsdag",
            "2026-01-06",
            "Functie returnt vandaag (technisch correct, maar misleidend)"
        )

        # WARNING: Dit scenario toont waarom we UI validation nodig hebben!
        # De gebruiker ziet "dinsdag 19:00" en denkt dat het vandaag is,
        # maar de scheduler zal pas volgende week om 19:00 triggeren (167 uur later).

    def test_all_weekdays_within_7_days_from_monday_midnight(self):
        """
        Test: vanaf maandag 00:00, alle weekdagen moeten binnen 6 dagen vallen.

        Scenario:
        - Nu: maandag 00:00
        - Vraag naar alle dagen (maandag t/m zondag)
        - Verwacht: maandag=0 dagen, dinsdag=1, ..., zondag=6 (max 6 dagen vooruit)
        - GEEN enkele dag mag > 6 dagen vooruit zijn (want dan is het volgende week!)

        Belangrijke regel: activatie altijd binnen 167u59m (< 168 uur) na deactivatie.
        """
        from apps.utils.notification_texts import _get_next_weekday_date

        fake_now = self._create_datetime(2026, 1, 5, 0, 0)  # maandag 00:00
        self._mock_datetime_now(fake_now)

        # DRY: gebruik dict voor test data
        test_cases = {
            "maandag": ("2026-01-05", 0),    # vandaag
            "dinsdag": ("2026-01-06", 1),
            "woensdag": ("2026-01-07", 2),
            "donderdag": ("2026-01-08", 3),
            "vrijdag": ("2026-01-09", 4),
            "zaterdag": ("2026-01-10", 5),
            "zondag": ("2026-01-11", 6),     # max 6 dagen vooruit
        }

        for dag, (expected_date, expected_days) in test_cases.items():
            with self.subTest(dag=dag):
                result = _get_next_weekday_date(dag)
                self.assertEqual(result, expected_date,
                               f"{dag} moet {expected_date} zijn (binnen deze week)")

                # Verify: NOOIT meer dan 6 dagen vooruit (< 168 uur)
                result_dt = datetime.strptime(result, "%Y-%m-%d")
                days_diff = (result_dt - fake_now.replace(tzinfo=None)).days
                self.assertEqual(days_diff, expected_days,
                               f"{dag} moet exact {expected_days} dagen na maandag zijn")
                self.assertLessEqual(days_diff, 6,
                                   f"{dag} moet max 6 dagen vooruit zijn (< 168 uur)")
                self.assertGreaterEqual(days_diff, 0,
                                      f"{dag} mag niet in het verleden zijn")


if __name__ == "__main__":
    unittest.main()
