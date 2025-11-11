#!/usr/bin/env python
"""
EENMALIG MIGRATIESCRIPT om archief-datums te corrigeren die 7 dagen te laat zijn.

BELANGRIJK: Dit script moet maar ÉÉN KEER uitgevoerd worden!
Meerdere keren uitvoeren verschuift telkens weer 7 dagen terug.

Dit script:
- Leest alle archief CSV-bestanden
- Verschuift alle vrijdag/zaterdag/zondag datums 7 dagen terug
- Overschrijft de originele bestanden

Voer dit script eenmalig uit:
    py fix_archive_dates.py

Om eerst te testen zonder bestanden te wijzigen:
    py fix_archive_dates.py --dry-run
"""

import csv
import os
import sys
from datetime import datetime, timedelta


def shift_date_back_7_days(date_str: str) -> str:
    """
    Verschuif een datum 7 dagen terug.

    Args:
        date_str: Datum in formaat YYYY-MM-DD

    Returns:
        Nieuwe datum 7 dagen terug in formaat YYYY-MM-DD
    """
    if not date_str or date_str.strip() == "":
        return date_str

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        new_date = date_obj - timedelta(days=7)
        return new_date.strftime("%Y-%m-%d")
    except (ValueError, AttributeError) as e:
        print(f"    [WAARSCHUWING] Kon datum '{date_str}' niet parsen: {e}")
        return date_str


def get_iso_week_from_date(date_str: str) -> str:
    """
    Haal ISO weeknummer op uit een datum string.

    Args:
        date_str: Datum in formaat YYYY-MM-DD

    Returns:
        ISO week in formaat YYYY-Www (bijv. 2025-W45)
    """
    if not date_str or date_str.strip() == "":
        return ""

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        iso_calendar = date_obj.isocalendar()
        return f"{iso_calendar.year}-W{iso_calendar.week:02d}"
    except (ValueError, AttributeError) as e:
        print(f"    [WAARSCHUWING] Kon weeknummer niet ophalen uit '{date_str}': {e}")
        return ""


def fix_csv_dates(csv_path: str, dry_run: bool = False) -> bool:
    """
    Corrigeer datums in een enkel CSV-bestand door ze 7 dagen terug te zetten.
    Herberekent ook het ISO weeknummer op basis van de nieuwe vrijdagdatum.

    Args:
        csv_path: Pad naar het CSV-bestand
        dry_run: Als True, toon alleen wat gewijzigd zou worden zonder bestanden aan te passen

    Returns:
        True als wijzigingen gemaakt zijn, False anders
    """
    if not os.path.exists(csv_path):
        return False

    # Lees bestaande CSV
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows or len(rows) < 2:
        print(f"  [OVERSLAAN] Geen data rijen in {csv_path}")
        return False

    header = rows[0]

    # Vind datum kolom indices
    try:
        friday_idx = header.index("datum_vrijdag")
        saturday_idx = header.index("datum_zaterdag")
        sunday_idx = header.index("datum_zondag")
    except ValueError as e:
        print(f"  [FOUT] Ontbrekende datum kolommen in {csv_path}: {e}")
        return False

    # Houd wijzigingen bij
    changes_made = False
    changes_log = []

    # Corrigeer data rijen
    for i in range(1, len(rows)):
        row = rows[i]

        # Sla lege rijen over
        if not row or len(row) < 4:
            continue

        # Haal originele datums en week op
        old_week = row[0] if row else ""
        old_friday = row[friday_idx] if friday_idx < len(row) else ""
        old_saturday = row[saturday_idx] if saturday_idx < len(row) else ""
        old_sunday = row[sunday_idx] if sunday_idx < len(row) else ""

        # Verschuif datums 7 dagen terug
        new_friday = shift_date_back_7_days(old_friday)
        new_saturday = shift_date_back_7_days(old_saturday)
        new_sunday = shift_date_back_7_days(old_sunday)

        # Bereken nieuw weeknummer op basis van nieuwe vrijdagdatum
        new_week = get_iso_week_from_date(new_friday)
        if not new_week:
            new_week = old_week  # Behoud oude week als berekening faalt

        # Check of er wijzigingen zijn gemaakt
        if (
            new_week != old_week
            or new_friday != old_friday
            or new_saturday != old_saturday
            or new_sunday != old_sunday
        ):

            changes_made = True

            log_msg = f"    Week {old_week}"
            if new_week != old_week:
                log_msg += f" -> {new_week}"
            log_msg += f": {old_friday},{old_saturday},{old_sunday} -> {new_friday},{new_saturday},{new_sunday}"
            changes_log.append(log_msg)

            # Update rij
            row[0] = new_week
            row[friday_idx] = new_friday
            row[saturday_idx] = new_saturday
            row[sunday_idx] = new_sunday
            rows[i] = row

    if changes_made:
        print(f"  [WIJZIGINGEN] {csv_path}")
        for log in changes_log:
            print(log)

        if not dry_run:
            # Schrijf gewijzigde CSV
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerows(rows)
            print("  [OPGESLAGEN] Bestand bijgewerkt\n")
        else:
            print("  [DRY-RUN] Bestand NIET gewijzigd (gebruik zonder --dry-run om toe te passen)\n")

        return True
    else:
        print(f"  [OK] Geen wijzigingen nodig voor {csv_path}")
        return False


def find_archive_files() -> list[str]:
    """Vind alle archief CSV-bestanden in de archives directory."""
    archive_files = []

    # Zoek naar poll_archive.csv (legacy globaal bestand)
    if os.path.exists("poll_archive.csv"):
        archive_files.append("poll_archive.csv")

    # Zoek naar scoped archieven in archives/ en archive/ directories
    for archives_dir in ["archives", "archive"]:
        if os.path.exists(archives_dir) and os.path.isdir(archives_dir):
            for root, _, files in os.walk(archives_dir):
                for file in files:
                    if file.endswith(".csv"):
                        archive_files.append(os.path.join(root, file))

    return archive_files


def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 70)
    print("Archief Datum Correctie Tool - EENMALIG GEBRUIK")
    print("=" * 70)
    print("\n" + "!" * 70)
    print("WAARSCHUWING: Dit script doet het volgende:")
    print("         1. Verschuift ALLE datums 7 dagen terug")
    print("         2. Herberekent weeknummers op basis van nieuwe vrijdagdatums")
    print("         Voer dit script maar ÉÉN KEER uit!")
    print("         Meerdere keren uitvoeren blijft datums telkens 7 dagen terugzetten!")
    print("!" * 70)
    print()

    if dry_run:
        print("[DRY-RUN MODUS] - Geen bestanden worden gewijzigd\n")
    else:
        print("Dit script zal je archief bestanden WIJZIGEN.")
        print("Het zal:")
        print("  - Alle datums 7 dagen terugzetten")
        print("  - Weeknummers herberekenen op basis van de gecorrigeerde vrijdagdatums")
        response = input("\nWeet je zeker dat je wilt doorgaan? (yes/no): ")
        if response.lower() not in ["yes", "y", "ja", "j"]:
            print("Afgebroken.")
            return
        print()

    # Vind alle archief bestanden
    archive_files = find_archive_files()

    if not archive_files:
        print("Geen archief bestanden gevonden. Niets te corrigeren.")
        return

    print(f"Gevonden {len(archive_files)} archief bestand(en):\n")
    for file in archive_files:
        print(f"  - {file}")

    print("\nBestanden verwerken...\n")

    files_changed = 0
    files_unchanged = 0

    for csv_path in archive_files:
        try:
            if fix_csv_dates(csv_path, dry_run=dry_run):
                files_changed += 1
            else:
                files_unchanged += 1
        except Exception as e:
            print(f"  [FOUT] Fout bij verwerken {csv_path}: {e}\n")

    print("=" * 70)
    print("Proces Voltooid!")
    print("=" * 70)
    print(f"  Bestanden gewijzigd: {files_changed}")
    print(f"  Bestanden ongewijzigd: {files_unchanged}")
    print(f"  Totaal bestanden: {len(archive_files)}")

    if dry_run:
        print("\n[DRY-RUN] Geen bestanden zijn daadwerkelijk gewijzigd.")
        print("Voer uit zonder --dry-run om wijzigingen toe te passen.")
    else:
        print("\nAlle datums zijn 7 dagen teruggeschoven.")
        print("BELANGRIJK: Voer dit script NIET opnieuw uit!")

    print()


if __name__ == "__main__":
    main()
