# apps/utils/period_dates.py

from datetime import datetime, timedelta

import pytz

# Amsterdam timezone
TZ = pytz.timezone("Europe/Amsterdam")


def get_period_for_day(dag: str) -> str:
    """
    Bepaal tot welke periode een dag behoort.

    Args:
        dag: Weekdag naam ("maandag" t/m "zondag")

    Returns:
        "ma-do" voor maandag t/m donderdag
        "vr-zo" voor vrijdag t/m zondag
    """
    ma_do_dagen = ["maandag", "dinsdag", "woensdag", "donderdag"]
    vr_zo_dagen = ["vrijdag", "zaterdag", "zondag"]

    dag_lower = dag.lower()
    if dag_lower in ma_do_dagen:
        return "ma-do"
    elif dag_lower in vr_zo_dagen:
        return "vr-zo"
    else:
        raise ValueError(f"Ongeldige dag: {dag}")


def get_period_days(period: str, reference_date: datetime | None = None) -> dict[str, str]:
    """
    Bereken de datums voor alle dagen in een periode.

    Args:
        period: "vr-zo" of "ma-do"
        reference_date: Optionele referentiedatum (defaults to now in Amsterdam timezone)

    Returns:
        Dict mapping dag naar datum_iso: {"vrijdag": "2026-01-10", ...}

    Logica:
    - vr-zo: Altijd de vrijdag van de huidige ISO week (maandag = start van week)
      - Ma t/m zo: alle dagen binnen dezelfde ISO week tonen dezelfde vrijdag
      - Reset op maandag 00:00: datums springen naar de volgende week
    - ma-do: DEZE week tijdens ma-do dagen, VOLGENDE week tijdens vr-zo dagen
      - Ma t/m do: toon maandag van DEZE week
      - Vr t/m zo: toon maandag van VOLGENDE week
      - Reset op vrijdag 00:00: datums springen naar de volgende week

    Voorbeelden:
    - Vandaag = maandag 5 januari 2026 (of 6/7/8 januari):
      - ma-do: 5 t/m 8 januari (deze week)
      - vr-zo: 9 t/m 11 januari (deze week)
    - Vandaag = vrijdag 9 januari 2026 (of 10/11 januari):
      - vr-zo: 9 t/m 11 januari (deze week)
      - ma-do: 12 t/m 15 januari (volgende week)
    - Vandaag = maandag 12 januari 2026 (of 13/14/15 januari):
      - ma-do: 12 t/m 15 januari (deze week)
      - vr-zo: 16 t/m 18 januari (deze week)
    """
    if reference_date is None:
        reference_date = datetime.now(TZ)
    elif reference_date.tzinfo is None:
        # Zet timezone als niet aanwezig
        reference_date = reference_date.replace(tzinfo=TZ)
    else:
        # Converteer naar Amsterdam timezone
        reference_date = reference_date.astimezone(TZ)

    # Zet tijd op 00:00 voor consistente datumberekening
    reference_date = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "vr-zo":
        # Vind de vrijdag van de huidige ISO week (maandag = start van week)
        # Dit geeft consistent de vr-zo datums voor de huidige week totdat maandag 00:00 reset
        # vrijdag = weekday 4 (ma=0, di=1, wo=2, do=3, vr=4, za=5, zo=6)
        current_weekday = reference_date.weekday()

        # Bereken dagen terug naar de maandag van deze week
        days_since_monday = current_weekday  # ma=0, di=1, ..., zo=6
        week_start = reference_date - timedelta(days=days_since_monday)

        # Vrijdag is 4 dagen na maandag
        friday = week_start + timedelta(days=4)

        return {
            "vrijdag": friday.strftime("%Y-%m-%d"),
            "zaterdag": (friday + timedelta(days=1)).strftime("%Y-%m-%d"),
            "zondag": (friday + timedelta(days=2)).strftime("%Y-%m-%d"),
        }

    elif period == "ma-do":
        # Ma-do period shows dates based on when the poll is ACTIVE (voting period):
        # - Voting period is Friday-Sunday (when you vote FOR ma-do events)
        # - Reset happens at Friday 00:00
        # - During Monday-Thursday: show THIS week's dates (the events are happening/happened)
        # - During Friday-Sunday: show NEXT week's dates (voting for upcoming events)
        #
        # maandag = weekday 0, vrijdag = weekday 4
        current_weekday = reference_date.weekday()

        # Bereken dagen terug naar de maandag van deze week
        days_since_monday = current_weekday
        this_week_monday = reference_date - timedelta(days=days_since_monday)

        # Ma (0) t/m do (3): toon DEZE week (de events zijn nu/waren recent)
        # Vr (4), za (5), zo (6): toon VOLGENDE week (voting voor toekomstige events)
        if current_weekday >= 4:
            # Vrijdag, zaterdag, zondag: toon VOLGENDE week
            monday = this_week_monday + timedelta(days=7)
        else:
            # Maandag t/m donderdag: toon DEZE week
            monday = this_week_monday

        return {
            "maandag": monday.strftime("%Y-%m-%d"),
            "dinsdag": (monday + timedelta(days=1)).strftime("%Y-%m-%d"),
            "woensdag": (monday + timedelta(days=2)).strftime("%Y-%m-%d"),
            "donderdag": (monday + timedelta(days=3)).strftime("%Y-%m-%d"),
        }

    else:
        raise ValueError(f"Ongeldige periode: {period}. Gebruik 'vr-zo' of 'ma-do'.")
