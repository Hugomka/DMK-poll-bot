#!/usr/bin/env python
"""
One-time migration script to update all existing archive CSV files
to include the new niet_gestemd and was_misschien columns,
and convert old week numbers to ISO week format.

Run this script once to migrate all archive files:
    py migrate_archives.py

Supported CSV versions:
- V1 (16 columns): no niet_gestemd, no was_misschien, old week format
- V2 (19 columns): has niet_gestemd, no was_misschien, old week format
- V3 (22 columns): has niet_gestemd and was_misschien, old week format
- V4 (22 columns): has niet_gestemd and was_misschien, ISO week format (YYYY-Www)
"""

import csv
import os
from datetime import datetime


def _convert_week_to_iso(week_str: str, friday_date: str) -> str:
    """
    Convert old week number to ISO week format (YYYY-Www).
    """
    # Als week al ISO format heeft (bevat '-'), return as-is
    if "-" in week_str:
        return week_str

    try:
        # Parse friday date to get year
        friday = datetime.strptime(friday_date, "%Y-%m-%d")
        year = friday.isocalendar().year
        week = int(week_str)

        # Format as ISO week: YYYY-Www
        return f"{year}-W{week:02d}"
    except (ValueError, AttributeError):
        # Als conversie faalt, return origineel + warning
        print(
            f"    [WARNING] Could not convert week '{week_str}' with date '{friday_date}', keeping original"
        )
        return week_str


def migrate_csv_file(csv_path: str) -> bool:
    """
    Migrate a single CSV file to the newest format (V4 - 22 columns with ISO week format).

    Supported CSV versions:
    - V1 (16 columns): no niet_gestemd, no was_misschien, old week format
    - V2 (19 columns): has niet_gestemd, no was_misschien, old week format
    - V3 (22 columns): has niet_gestemd and was_misschien, old week format
    - V4 (22 columns): has niet_gestemd and was_misschien, ISO week format (current)

    Returns True if migration was performed, False if file was already migrated or doesn't exist.
    """
    if not os.path.exists(csv_path):
        return False

    # Read existing CSV
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return False

    existing_header = rows[0]

    # Check if already has V3/V4 columns AND ISO week format
    has_v3_columns = "vr_was_misschien" in existing_header

    # Check if week format is already ISO (check first data row)
    has_iso_week = False
    if len(rows) > 1 and rows[1]:
        week_value = rows[1][0]
        has_iso_week = "-W" in week_value  # ISO format contains "-W"

    if has_v3_columns and has_iso_week:
        print(f"  [OK] Already migrated to V4: {csv_path}")
        return False

    # V4 header with niet_gestemd and was_misschien columns
    new_header = [
        "week",
        "datum_vrijdag",
        "datum_zaterdag",
        "datum_zondag",
        "vr_19",
        "vr_2030",
        "vr_misschien",
        "vr_was_misschien",
        "vr_niet",
        "vr_niet_gestemd",
        "za_19",
        "za_2030",
        "za_misschien",
        "za_was_misschien",
        "za_niet",
        "za_niet_gestemd",
        "zo_19",
        "zo_2030",
        "zo_misschien",
        "zo_was_misschien",
        "zo_niet",
        "zo_niet_gestemd",
    ]

    # Update header
    rows[0] = new_header

    # Migrate data rows
    migrated_count = 0
    week_converted_count = 0

    for i in range(1, len(rows)):
        old_row = rows[i]

        # Skip empty rows
        if not old_row or len(old_row) < 4:
            continue

        if len(old_row) >= 22 and has_v3_columns:
            # V3 format: alleen week conversie nodig
            old_week = old_row[0]
            friday_date = old_row[1]
            new_week = _convert_week_to_iso(old_week, friday_date)

            if new_week != old_week:
                old_row[0] = new_week
                week_converted_count += 1

            rows[i] = old_row
            migrated_count += 1
        elif len(old_row) >= 19:
            # V2 format with niet_gestemd (19 columns)
            # Migrate to V4: Add was_misschien columns + convert week format
            old_week = old_row[0]
            friday_date = old_row[1]
            new_week = _convert_week_to_iso(old_week, friday_date)

            if new_week != old_week:
                week_converted_count += 1

            new_row = [
                new_week,  # week (converted to ISO)
                old_row[1],  # datum_vrijdag
                old_row[2],  # datum_zaterdag
                old_row[3],  # datum_zondag
                old_row[4],  # vr_19
                old_row[5],  # vr_2030
                old_row[6],  # vr_misschien
                "",  # vr_was_misschien (V4 - empty = data not tracked)
                old_row[7],  # vr_niet
                old_row[8],  # vr_niet_gestemd
                old_row[9],  # za_19
                old_row[10],  # za_2030
                old_row[11],  # za_misschien
                "",  # za_was_misschien (V4 - empty = data not tracked)
                old_row[12],  # za_niet
                old_row[13],  # za_niet_gestemd
                old_row[14],  # zo_19
                old_row[15],  # zo_2030
                old_row[16],  # zo_misschien
                "",  # zo_was_misschien (V4 - empty = data not tracked)
                old_row[17],  # zo_niet
                old_row[18],  # zo_niet_gestemd
            ]
            rows[i] = new_row
            migrated_count += 1
        elif len(old_row) >= 16:
            # V1 format without niet_gestemd (16 columns)
            # Migrate to V4: Add both niet_gestemd and was_misschien columns + convert week format
            old_week = old_row[0]
            friday_date = old_row[1]
            new_week = _convert_week_to_iso(old_week, friday_date)

            if new_week != old_week:
                week_converted_count += 1

            new_row = [
                new_week,  # week (converted to ISO)
                old_row[1],  # datum_vrijdag
                old_row[2],  # datum_zaterdag
                old_row[3],  # datum_zondag
                old_row[4],  # vr_19
                old_row[5],  # vr_2030
                old_row[6],  # vr_misschien
                "",  # vr_was_misschien (V4 - empty = data not tracked)
                old_row[7],  # vr_niet
                "",  # vr_niet_gestemd (V4 - empty = data not tracked)
                old_row[8],  # za_19
                old_row[9],  # za_2030
                old_row[10],  # za_misschien
                "",  # za_was_misschien (V4 - empty = data not tracked)
                old_row[11],  # za_niet
                "",  # za_niet_gestemd (V4 - empty = data not tracked)
                old_row[12],  # zo_19
                old_row[13],  # zo_2030
                old_row[14],  # zo_misschien
                "",  # zo_was_misschien (V4 - empty = data not tracked)
                old_row[15],  # zo_niet
                "",  # zo_niet_gestemd (V4 - empty = data not tracked)
            ]
            rows[i] = new_row
            migrated_count += 1

    # Write migrated CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)

    if week_converted_count > 0:
        print(
            f"  [OK] Migrated {migrated_count} rows ({week_converted_count} weeks converted to ISO format): {csv_path}"
        )
    else:
        print(f"  [OK] Migrated {migrated_count} rows: {csv_path}")
    return True


def find_archive_files() -> list[str]:
    """Find all archive CSV files in the archives directory."""
    archive_files = []

    # Look for poll_archive.csv (legacy global file)
    if os.path.exists("poll_archive.csv"):
        archive_files.append("poll_archive.csv")

    # Look for scoped archives in archives/ and archive/ directories
    for archives_dir in ["archives", "archive"]:
        if os.path.exists(archives_dir) and os.path.isdir(archives_dir):
            for root, _, files in os.walk(archives_dir):
                for file in files:
                    if file.endswith(".csv"):
                        archive_files.append(os.path.join(root, file))

    return archive_files


def main():
    print("=" * 70)
    print("Archive CSV Migration Tool - V4")
    print("=" * 70)
    print("\nThis script will migrate all archive CSV files to V4 format:")
    print("  1. Add niet_gestemd columns (if missing)")
    print("     - vr_niet_gestemd, za_niet_gestemd, zo_niet_gestemd")
    print("  2. Add was_misschien columns (if missing)")
    print("     - vr_was_misschien, za_was_misschien, zo_was_misschien")
    print("  3. Convert old week numbers to ISO format")
    print("     - Old: 44")
    print("     - New: 2025-W44")
    print("\nOld data will be preserved with EMPTY values for new columns.")
    print("(Empty = data was not tracked in those weeks)")
    print()

    # Find all archive files
    archive_files = find_archive_files()

    if not archive_files:
        print("No archive files found. Nothing to migrate.")
        return

    print(f"Found {len(archive_files)} archive file(s):\n")
    for file in archive_files:
        print(f"  - {file}")

    print("\nStarting migration...\n")

    migrated = 0
    already_migrated = 0

    for csv_path in archive_files:
        try:
            if migrate_csv_file(csv_path):
                migrated += 1
            else:
                already_migrated += 1
        except Exception as e:
            print(f"  [ERROR] Error migrating {csv_path}: {e}")

    print("\n" + "=" * 70)
    print("Migration Complete!")
    print("=" * 70)
    print(f"  Files migrated: {migrated}")
    print(f"  Already migrated: {already_migrated}")
    print(f"  Total files: {len(archive_files)}")
    print()


if __name__ == "__main__":
    main()
