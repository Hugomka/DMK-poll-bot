# tests/test_period_dates.py

import unittest
from datetime import datetime, timedelta

import pytz

from apps.utils.period_dates import get_period_days, get_period_for_day

TZ = pytz.timezone("Europe/Amsterdam")


class TestPeriodForDay(unittest.TestCase):
    """Test get_period_for_day() helper functie."""

    def test_maandag_is_ma_do(self):
        self.assertEqual(get_period_for_day("maandag"), "ma-do")

    def test_dinsdag_is_ma_do(self):
        self.assertEqual(get_period_for_day("dinsdag"), "ma-do")

    def test_woensdag_is_ma_do(self):
        self.assertEqual(get_period_for_day("woensdag"), "ma-do")

    def test_donderdag_is_ma_do(self):
        self.assertEqual(get_period_for_day("donderdag"), "ma-do")

    def test_vrijdag_is_vr_zo(self):
        self.assertEqual(get_period_for_day("vrijdag"), "vr-zo")

    def test_zaterdag_is_vr_zo(self):
        self.assertEqual(get_period_for_day("zaterdag"), "vr-zo")

    def test_zondag_is_vr_zo(self):
        self.assertEqual(get_period_for_day("zondag"), "vr-zo")

    def test_case_insensitive(self):
        """Test dat hoofdletters niet uitmaken."""
        self.assertEqual(get_period_for_day("MAANDAG"), "ma-do")
        self.assertEqual(get_period_for_day("Vrijdag"), "vr-zo")
        self.assertEqual(get_period_for_day("ZoNdAg"), "vr-zo")

    def test_invalid_day_raises_error(self):
        """Test dat ongeldige dag een error geeft."""
        with self.assertRaises(ValueError) as ctx:
            get_period_for_day("invalid")
        self.assertIn("Ongeldige dag", str(ctx.exception))


class TestPeriodDaysVrZo(unittest.TestCase):
    """Test get_period_days() voor vr-zo periode."""

    def test_vr_zo_from_monday(self):
        """Vanaf maandag: vr-zo van DEZE week (vrijdag t/m zondag)."""
        ref = datetime(2026, 1, 5, 12, 0, 0, tzinfo=TZ)  # maandag 5 jan 2026
        result = get_period_days("vr-zo", ref)

        self.assertEqual(result["vrijdag"], "2026-01-09")
        self.assertEqual(result["zaterdag"], "2026-01-10")
        self.assertEqual(result["zondag"], "2026-01-11")

    def test_vr_zo_from_tuesday(self):
        """Vanaf dinsdag: vr-zo van DEZE week."""
        ref = datetime(2026, 1, 6, 12, 0, 0, tzinfo=TZ)  # dinsdag 6 jan 2026
        result = get_period_days("vr-zo", ref)

        self.assertEqual(result["vrijdag"], "2026-01-09")
        self.assertEqual(result["zaterdag"], "2026-01-10")
        self.assertEqual(result["zondag"], "2026-01-11")

    def test_vr_zo_from_wednesday(self):
        """Vanaf woensdag: vr-zo van DEZE week."""
        ref = datetime(2026, 1, 7, 12, 0, 0, tzinfo=TZ)  # woensdag 7 jan 2026
        result = get_period_days("vr-zo", ref)

        self.assertEqual(result["vrijdag"], "2026-01-09")
        self.assertEqual(result["zaterdag"], "2026-01-10")
        self.assertEqual(result["zondag"], "2026-01-11")

    def test_vr_zo_from_thursday(self):
        """Vanaf donderdag: vr-zo van DEZE week."""
        ref = datetime(2026, 1, 8, 12, 0, 0, tzinfo=TZ)  # donderdag 8 jan 2026
        result = get_period_days("vr-zo", ref)

        self.assertEqual(result["vrijdag"], "2026-01-09")
        self.assertEqual(result["zaterdag"], "2026-01-10")
        self.assertEqual(result["zondag"], "2026-01-11")

    def test_vr_zo_from_friday(self):
        """Vanaf vrijdag: vr-zo van DEZE week (vandaag = vrijdag)."""
        ref = datetime(2026, 1, 9, 12, 0, 0, tzinfo=TZ)  # vrijdag 9 jan 2026
        result = get_period_days("vr-zo", ref)

        self.assertEqual(result["vrijdag"], "2026-01-09")
        self.assertEqual(result["zaterdag"], "2026-01-10")
        self.assertEqual(result["zondag"], "2026-01-11")

    def test_vr_zo_from_saturday(self):
        """Vanaf zaterdag: vr-zo van DEZE week (vrijdag was gisteren)."""
        ref = datetime(2026, 1, 10, 12, 0, 0, tzinfo=TZ)  # zaterdag 10 jan 2026
        result = get_period_days("vr-zo", ref)

        # Deze week: vrijdag 9 jan (gisteren), zaterdag 10 jan (vandaag), zondag 11 jan
        self.assertEqual(result["vrijdag"], "2026-01-09")
        self.assertEqual(result["zaterdag"], "2026-01-10")
        self.assertEqual(result["zondag"], "2026-01-11")

    def test_vr_zo_from_sunday(self):
        """Vanaf zondag: vr-zo van DEZE week (vrijdag was 2 dagen geleden)."""
        ref = datetime(2026, 1, 11, 12, 0, 0, tzinfo=TZ)  # zondag 11 jan 2026
        result = get_period_days("vr-zo", ref)

        # Deze week: vrijdag 9 jan, zaterdag 10 jan, zondag 11 jan (vandaag)
        self.assertEqual(result["vrijdag"], "2026-01-09")
        self.assertEqual(result["zaterdag"], "2026-01-10")
        self.assertEqual(result["zondag"], "2026-01-11")


class TestPeriodDaysMaDo(unittest.TestCase):
    """Test get_period_days() voor ma-do periode."""

    def test_ma_do_from_monday(self):
        """Vanaf maandag: ma-do van DEZE week."""
        ref = datetime(2026, 1, 5, 12, 0, 0, tzinfo=TZ)  # maandag 5 jan 2026
        result = get_period_days("ma-do", ref)

        # Deze week: maandag 5 t/m donderdag 8 jan
        self.assertEqual(result["maandag"], "2026-01-05")
        self.assertEqual(result["dinsdag"], "2026-01-06")
        self.assertEqual(result["woensdag"], "2026-01-07")
        self.assertEqual(result["donderdag"], "2026-01-08")

    def test_ma_do_from_tuesday(self):
        """Vanaf dinsdag: ma-do van DEZE week."""
        ref = datetime(2026, 1, 6, 12, 0, 0, tzinfo=TZ)  # dinsdag 6 jan 2026
        result = get_period_days("ma-do", ref)

        # Deze week: maandag 5 t/m donderdag 8 jan
        self.assertEqual(result["maandag"], "2026-01-05")
        self.assertEqual(result["dinsdag"], "2026-01-06")
        self.assertEqual(result["woensdag"], "2026-01-07")
        self.assertEqual(result["donderdag"], "2026-01-08")

    def test_ma_do_from_wednesday(self):
        """Vanaf woensdag: ma-do van DEZE week."""
        ref = datetime(2026, 1, 7, 12, 0, 0, tzinfo=TZ)  # woensdag 7 jan 2026
        result = get_period_days("ma-do", ref)

        # Deze week: maandag 5 t/m donderdag 8 jan
        self.assertEqual(result["maandag"], "2026-01-05")
        self.assertEqual(result["dinsdag"], "2026-01-06")
        self.assertEqual(result["woensdag"], "2026-01-07")
        self.assertEqual(result["donderdag"], "2026-01-08")

    def test_ma_do_from_thursday(self):
        """Vanaf donderdag: ma-do van DEZE week."""
        ref = datetime(2026, 1, 8, 12, 0, 0, tzinfo=TZ)  # donderdag 8 jan 2026
        result = get_period_days("ma-do", ref)

        # Deze week: maandag 5 t/m donderdag 8 jan
        self.assertEqual(result["maandag"], "2026-01-05")
        self.assertEqual(result["dinsdag"], "2026-01-06")
        self.assertEqual(result["woensdag"], "2026-01-07")
        self.assertEqual(result["donderdag"], "2026-01-08")

    def test_ma_do_from_friday(self):
        """Vanaf vrijdag: ma-do van VOLGENDE week (na reset op vrijdag 00:00)."""
        ref = datetime(2026, 1, 9, 12, 0, 0, tzinfo=TZ)  # vrijdag 9 jan 2026
        result = get_period_days("ma-do", ref)

        # Volgende week: maandag 12 t/m donderdag 15 jan
        self.assertEqual(result["maandag"], "2026-01-12")
        self.assertEqual(result["dinsdag"], "2026-01-13")
        self.assertEqual(result["woensdag"], "2026-01-14")
        self.assertEqual(result["donderdag"], "2026-01-15")

    def test_ma_do_from_saturday(self):
        """Vanaf zaterdag: ma-do van VOLGENDE week."""
        ref = datetime(2026, 1, 10, 12, 0, 0, tzinfo=TZ)  # zaterdag 10 jan 2026
        result = get_period_days("ma-do", ref)

        # Volgende week: maandag 12 t/m donderdag 15 jan
        self.assertEqual(result["maandag"], "2026-01-12")
        self.assertEqual(result["dinsdag"], "2026-01-13")
        self.assertEqual(result["woensdag"], "2026-01-14")
        self.assertEqual(result["donderdag"], "2026-01-15")

    def test_ma_do_from_sunday(self):
        """Vanaf zondag: ma-do van VOLGENDE week."""
        ref = datetime(2026, 1, 11, 12, 0, 0, tzinfo=TZ)  # zondag 11 jan 2026
        result = get_period_days("ma-do", ref)

        # Volgende week: maandag 12 t/m donderdag 15 jan
        self.assertEqual(result["maandag"], "2026-01-12")
        self.assertEqual(result["dinsdag"], "2026-01-13")
        self.assertEqual(result["woensdag"], "2026-01-14")
        self.assertEqual(result["donderdag"], "2026-01-15")


class TestPeriodDaysEdgeCases(unittest.TestCase):
    """Test edge cases voor get_period_days()."""

    def test_vr_zo_no_reference_date_uses_now(self):
        """Test dat None als reference_date de huidige tijd gebruikt."""
        result = get_period_days("vr-zo")

        # Check dat we 3 datums hebben
        self.assertEqual(len(result), 3)
        self.assertIn("vrijdag", result)
        self.assertIn("zaterdag", result)
        self.assertIn("zondag", result)

        # Check dat datums valid ISO formaat zijn
        for dag, datum_iso in result.items():
            # Parse moet slagen
            datetime.strptime(datum_iso, "%Y-%m-%d")

    def test_ma_do_no_reference_date_uses_now(self):
        """Test dat None als reference_date de huidige tijd gebruikt."""
        result = get_period_days("ma-do")

        # Check dat we 4 datums hebben
        self.assertEqual(len(result), 4)
        self.assertIn("maandag", result)
        self.assertIn("dinsdag", result)
        self.assertIn("woensdag", result)
        self.assertIn("donderdag", result)

        # Check dat datums valid ISO formaat zijn
        for dag, datum_iso in result.items():
            # Parse moet slagen
            datetime.strptime(datum_iso, "%Y-%m-%d")

    def test_invalid_period_raises_error(self):
        """Test dat ongeldige periode een error geeft."""
        ref = datetime(2026, 1, 5, 12, 0, 0, tzinfo=TZ)
        with self.assertRaises(ValueError) as ctx:
            get_period_days("invalid", ref)
        self.assertIn("Ongeldige periode", str(ctx.exception))

    def test_naive_datetime_gets_timezone(self):
        """Test dat naive datetime een timezone krijgt."""
        ref_naive = datetime(2026, 1, 5, 12, 0, 0)  # Geen timezone, maandag 5 jan
        result = get_period_days("vr-zo", ref_naive)

        # Week van ma 5 jan → vrijdag 9 jan
        self.assertEqual(result["vrijdag"], "2026-01-09")

    def test_utc_datetime_gets_converted(self):
        """Test dat UTC datetime geconverteerd wordt naar Amsterdam tijd."""
        ref_utc = datetime(2026, 1, 5, 23, 0, 0, tzinfo=pytz.UTC)  # 23:00 UTC = 00:00 CET
        result = get_period_days("vr-zo", ref_utc)

        # 23:00 UTC op maandag 5 jan = 00:00 CET op dinsdag 6 jan (Jan 6, 2026, 00:00:00)
        # Dinsdag 6 jan is in week die begon op maandag 5 jan → vrijdag 9 jan
        self.assertEqual(result["vrijdag"], "2026-01-09")

    def test_vr_zo_year_boundary(self):
        """Test vr-zo periode over jaargrens heen."""
        ref = datetime(2025, 12, 29, 12, 0, 0, tzinfo=TZ)  # maandag 29 dec 2025
        result = get_period_days("vr-zo", ref)

        # Week van ma 29 dec → vrijdag is 2 januari 2026
        self.assertEqual(result["vrijdag"], "2026-01-02")
        self.assertEqual(result["zaterdag"], "2026-01-03")
        self.assertEqual(result["zondag"], "2026-01-04")

    def test_ma_do_year_boundary(self):
        """Test ma-do periode over jaargrens heen."""
        ref = datetime(2025, 12, 29, 12, 0, 0, tzinfo=TZ)  # maandag 29 dec 2025
        result = get_period_days("ma-do", ref)

        # Maandag 29 dec → toon DEZE week (ma 29 dec t/m do 1 jan)
        self.assertEqual(result["maandag"], "2025-12-29")
        self.assertEqual(result["dinsdag"], "2025-12-30")
        self.assertEqual(result["woensdag"], "2025-12-31")
        self.assertEqual(result["donderdag"], "2026-01-01")


class TestPeriodDaysConsistency(unittest.TestCase):
    """Test consistentie van datums over een hele week heen."""

    def test_vr_zo_stable_during_ma_do_period(self):
        """Test dat vr-zo datums stabiel blijven tijdens ma-do periode (ma t/m do)."""
        # Maandag t/m donderdag moeten allemaal dezelfde vr-zo datums geven
        expected_friday = "2026-01-09"

        for day_offset in range(4):  # ma=0, di=1, wo=2, do=3
            ref = datetime(2026, 1, 5, 12, 0, 0, tzinfo=TZ) + timedelta(days=day_offset)
            result = get_period_days("vr-zo", ref)
            self.assertEqual(
                result["vrijdag"],
                expected_friday,
                f"Dag {day_offset}: verkeerde vrijdag datum",
            )

    def test_ma_do_stable_during_vr_zo_period(self):
        """Test dat ma-do datums stabiel blijven tijdens vr-zo periode (vr t/m zo)."""
        # Vrijdag t/m zondag moeten allemaal VOLGENDE week tonen
        expected_monday = "2026-01-12"  # Volgende week na 5-11 jan

        for day_offset in range(3):  # vr=0, za=1, zo=2
            ref = datetime(2026, 1, 9, 12, 0, 0, tzinfo=TZ) + timedelta(days=day_offset)
            result = get_period_days("ma-do", ref)
            self.assertEqual(
                result["maandag"],
                expected_monday,
                f"Dag {day_offset}: verkeerde maandag datum",
            )

    def test_ma_do_stable_during_ma_do_period(self):
        """Test dat ma-do datums stabiel blijven tijdens ma-do stemperiode (ma t/m do)."""
        # Maandag t/m donderdag moeten allemaal DEZE week tonen
        expected_monday = "2026-01-05"

        for day_offset in range(4):  # ma=0, di=1, wo=2, do=3
            ref = datetime(2026, 1, 5, 12, 0, 0, tzinfo=TZ) + timedelta(days=day_offset)
            result = get_period_days("ma-do", ref)
            self.assertEqual(
                result["maandag"],
                expected_monday,
                f"Dag {day_offset}: verkeerde maandag datum",
            )

    def test_dates_always_in_future_or_today(self):
        """Test dat datums correct zijn voor elke dag van de week."""
        # Test voor een hele week
        for day_offset in range(7):
            ref = datetime(2026, 1, 5, 12, 0, 0, tzinfo=TZ) + timedelta(days=day_offset)

            # Check vr-zo: altijd de vrijdag van de huidige ISO week
            vr_zo = get_period_days("vr-zo", ref)
            friday_date = datetime.strptime(vr_zo["vrijdag"], "%Y-%m-%d").replace(tzinfo=TZ)

            # Bereken de verwachte vrijdag (ISO week)
            days_since_monday = ref.weekday()
            expected_friday = ref - timedelta(days=days_since_monday) + timedelta(days=4)

            self.assertEqual(
                friday_date.date(),
                expected_friday.date(),
                f"vr-zo vrijdag onjuist op dag {day_offset}",
            )

            # Check ma-do: DEZE week voor ma-do, VOLGENDE week voor vr-zo
            ma_do = get_period_days("ma-do", ref)
            monday_date = datetime.strptime(ma_do["maandag"], "%Y-%m-%d").replace(tzinfo=TZ)

            # Bereken de verwachte maandag
            this_week_monday = ref - timedelta(days=days_since_monday)
            if ref.weekday() >= 4:
                # Vrijdag, zaterdag, zondag: volgende week
                expected_monday = this_week_monday + timedelta(days=7)
            else:
                # Maandag t/m donderdag: deze week
                expected_monday = this_week_monday

            self.assertEqual(
                monday_date.date(),
                expected_monday.date(),
                f"ma-do maandag onjuist op dag {day_offset}",
            )


if __name__ == "__main__":
    unittest.main()
