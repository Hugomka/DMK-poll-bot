"""
Geïntegreerde test suite voor archief datum berekening logica.

Test verschillende scenario's:
1. Basis datum berekening voor verschillende weekdagen
2. Reset op verschillende dagen (maandag t/m zondag)
3. ISO weeknummer berekening
4. Directe test van _week_dates_eu() functie

Voer uit met: py tests/test_archive_dates.py
"""
from datetime import datetime
import pytz
import sys

sys.path.insert(0, ".")
from apps.utils.archive import _week_dates_eu


def test_week_dates_eu_function():
    """Test de daadwerkelijke _week_dates_eu() functie uit archive.py."""
    # Test cases: (test_datum, verwachte_vrijdag, verwachte_zaterdag, verwachte_zondag, verwachte_week)
    test_cases = [
        ("2025-11-10", "2025-11-07", "2025-11-08", "2025-11-09", "2025-W45"),  # Maandag
        ("2025-11-11", "2025-11-07", "2025-11-08", "2025-11-09", "2025-W45"),  # Dinsdag (reset dag)
        ("2025-11-12", "2025-11-07", "2025-11-08", "2025-11-09", "2025-W45"),  # Woensdag
        ("2025-11-13", "2025-11-07", "2025-11-08", "2025-11-09", "2025-W45"),  # Donderdag
        ("2025-11-07", "2025-10-31", "2025-11-01", "2025-11-02", "2025-W44"),  # Vrijdag -> VORIG weekend
        ("2025-11-08", "2025-10-31", "2025-11-01", "2025-11-02", "2025-W44"),  # Zaterdag -> VORIG weekend
        ("2025-11-09", "2025-10-31", "2025-11-01", "2025-11-02", "2025-W44"),  # Zondag -> VORIG weekend
    ]

    for test_date_str, exp_fri, exp_sat, exp_sun, exp_week in test_cases:
        # Parse test datum
        test_date = datetime.strptime(test_date_str, "%Y-%m-%d")
        test_date = pytz.timezone("Europe/Amsterdam").localize(test_date)

        # Haal resultaten op
        week, fri, sat, sun = _week_dates_eu(test_date)

        # Assert correctheid
        assert week == exp_week, f"Week mismatch voor {test_date_str}: verwacht {exp_week}, kreeg {week}"
        assert fri == exp_fri, f"Vrijdag mismatch voor {test_date_str}: verwacht {exp_fri}, kreeg {fri}"
        assert sat == exp_sat, f"Zaterdag mismatch voor {test_date_str}: verwacht {exp_sat}, kreeg {sat}"
        assert sun == exp_sun, f"Zondag mismatch voor {test_date_str}: verwacht {exp_sun}, kreeg {sun}"


def test_different_reset_days():
    """Test dat archief logica werkt voor verschillende reset dagen."""
    scenarios = [
        ("MAANDAG", datetime(2025, 11, 10, 20, 0), ("2025-11-07", "2025-11-08", "2025-11-09", "2025-W45")),
        ("DINSDAG", datetime(2025, 11, 11, 20, 0), ("2025-11-07", "2025-11-08", "2025-11-09", "2025-W45")),
        ("WOENSDAG", datetime(2025, 11, 12, 20, 0), ("2025-11-07", "2025-11-08", "2025-11-09", "2025-W45")),
        ("DONDERDAG", datetime(2025, 11, 13, 20, 0), ("2025-11-07", "2025-11-08", "2025-11-09", "2025-W45")),
        ("VRIJDAG", datetime(2025, 11, 7, 20, 0), ("2025-10-31", "2025-11-01", "2025-11-02", "2025-W44")),
    ]

    for day_name, reset_time, expected in scenarios:
        reset_time = pytz.timezone("Europe/Amsterdam").localize(reset_time)
        week, fri, sat, sun = _week_dates_eu(reset_time)

        exp_fri, exp_sat, exp_sun, exp_week = expected

        # Assert correctheid
        assert week == exp_week, f"Week mismatch voor {day_name}: verwacht {exp_week}, kreeg {week}"
        assert fri == exp_fri, f"Vrijdag mismatch voor {day_name}: verwacht {exp_fri}, kreeg {fri}"
        assert sat == exp_sat, f"Zaterdag mismatch voor {day_name}: verwacht {exp_sat}, kreeg {sat}"
        assert sun == exp_sun, f"Zondag mismatch voor {day_name}: verwacht {exp_sun}, kreeg {sun}"


def test_week_numbers():
    """Test ISO weeknummer berekening voor november 2025."""
    # Verwachte week nummers voor november 2025
    expected_weeks = {
        3: 45,
        4: 45,
        5: 45,
        6: 45,
        7: 45,  # Vrijdag 7 nov = W45
        8: 45,  # Zaterdag 8 nov = W45
        9: 45,  # Zondag 9 nov = W45
        10: 46,  # Maandag 10 nov = W46 (nieuwe week start)
        11: 46,
        12: 46,
        13: 46,
        14: 46,
        15: 46,
        16: 46,
    }

    for day in range(3, 17):
        d = datetime(2025, 11, day)
        iso = d.isocalendar()
        expected = expected_weeks[day]

        # Assert correctheid
        assert iso.week == expected, f"Week nummer mismatch voor {d.strftime('%Y-%m-%d')}: verwacht W{expected:02d}, kreeg W{iso.week:02d}"
