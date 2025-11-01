#!/usr/bin/env python
"""
One-time migration script to update all existing archive CSV files
to include the new niet_gestemd columns.

Run this script once to migrate all archive files:
    python migrate_archives.py
"""

import csv
import os
from pathlib import Path


def migrate_csv_file(csv_path: str) -> bool:
    """
    Migrate a single CSV file from old format (16 columns) to new format (19 columns).

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

    # Check if already migrated
    if "vr_niet_gestemd" in existing_header:
        print(f"  [OK] Already migrated: {csv_path}")
        return False

    # New header with niet_gestemd columns
    new_header = [
        "week",
        "datum_vrijdag",
        "datum_zaterdag",
        "datum_zondag",
        "vr_19",
        "vr_2030",
        "vr_misschien",
        "vr_niet",
        "vr_niet_gestemd",
        "za_19",
        "za_2030",
        "za_misschien",
        "za_niet",
        "za_niet_gestemd",
        "zo_19",
        "zo_2030",
        "zo_misschien",
        "zo_niet",
        "zo_niet_gestemd",
    ]

    # Update header
    rows[0] = new_header

    # Migrate data rows
    migrated_count = 0
    for i in range(1, len(rows)):
        old_row = rows[i]
        if len(old_row) >= 16:  # Valid old row format
            # Build new row with niet_gestemd columns added as empty (data not available)
            new_row = [
                old_row[0],   # week
                old_row[1],   # datum_vrijdag
                old_row[2],   # datum_zaterdag
                old_row[3],   # datum_zondag
                old_row[4],   # vr_19
                old_row[5],   # vr_2030
                old_row[6],   # vr_misschien
                old_row[7],   # vr_niet
                "",           # vr_niet_gestemd (NEW - empty = data not tracked)
                old_row[8],   # za_19
                old_row[9],   # za_2030
                old_row[10],  # za_misschien
                old_row[11],  # za_niet
                "",           # za_niet_gestemd (NEW - empty = data not tracked)
                old_row[12],  # zo_19
                old_row[13],  # zo_2030
                old_row[14],  # zo_misschien
                old_row[15],  # zo_niet
                "",           # zo_niet_gestemd (NEW - empty = data not tracked)
            ]
            rows[i] = new_row
            migrated_count += 1

    # Write migrated CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)

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
    print("Archive CSV Migration Tool")
    print("=" * 70)
    print("\nThis script will migrate all archive CSV files to include the new")
    print("niet_gestemd columns (vr_niet_gestemd, za_niet_gestemd, zo_niet_gestemd).")
    print("\nOld data will be preserved with EMPTY values for niet_gestemd columns.")
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
