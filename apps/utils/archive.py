# apps/utils/archive.py

import os
import csv
import pytz
from datetime import datetime, timedelta
from typing import Tuple

from apps.utils.poll_storage import load_votes
from apps.entities.poll_option import get_poll_options

ARCHIVE_DIR = "archive"
ARCHIVE_CSV = os.path.join(ARCHIVE_DIR, "dmk_archive.csv")

VOLGORDE = ["om 19:00 uur", "om 20:30 uur", "misschien", "niet meedoen"]
DAGEN = []
for o in get_poll_options():
    if o.dag not in DAGEN and o.dag in ["vrijdag", "zaterdag", "zondag"]:
        DAGEN.append(o.dag)


def _ensure_dir():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _empty_counts():
    return {dag: {k: 0 for k in VOLGORDE} for dag in DAGEN}


def _build_counts_from_votes(votes: dict):
    telling = _empty_counts()
    for per_dag in votes.values():
        for dag, keuzes in per_dag.items():
            if dag not in telling:
                continue
            for tijd in keuzes:
                if tijd in telling[dag]:
                    telling[dag][tijd] += 1
    return telling


def _week_dates_eu(now):
    """Geef (week, datum_vrijdag, datum_zaterdag, datum_zondag) als YYYY-MM-DD."""
    if now.tzinfo is None:
        now = pytz.timezone("Europe/Amsterdam").localize(now)

    def last_weekday(now_dt, target_weekday):
        delta = (now_dt.weekday() - target_weekday) % 7
        return (now_dt - timedelta(days=delta)).date()

    vr = last_weekday(now, 4)
    za = last_weekday(now, 5)
    zo = last_weekday(now, 6)

    week = vr.isocalendar().week
    return (week, vr.isoformat(), za.isoformat(), zo.isoformat())


async def append_week_snapshot(now=None) -> None:
    """
    Schrijf 1 rij naar CSV met week + datums + aantallen per dag/optie.
    Roep dit A L T I J D aan vóór reset_votes().
    """
    _ensure_dir()
    if now is None:
        now = datetime.now(pytz.timezone("Europe/Amsterdam"))

    votes = await load_votes()
    telling = _build_counts_from_votes(votes)
    week, vr, za, zo = _week_dates_eu(now)

    header = [
        "week",
        "datum_vrijdag",
        "datum_zaterdag",
        "datum_zondag",
        "vr_19",
        "vr_2030",
        "vr_misschien",
        "vr_niet",
        "za_19",
        "za_2030",
        "za_misschien",
        "za_niet",
        "zo_19",
        "zo_2030",
        "zo_misschien",
        "zo_niet",
    ]
    row = [
        week,
        vr,
        za,
        zo,
        telling["vrijdag"]["om 19:00 uur"],
        telling["vrijdag"]["om 20:30 uur"],
        telling["vrijdag"]["misschien"],
        telling["vrijdag"]["niet meedoen"],
        telling["zaterdag"]["om 19:00 uur"],
        telling["zaterdag"]["om 20:30 uur"],
        telling["zaterdag"]["misschien"],
        telling["zaterdag"]["niet meedoen"],
        telling["zondag"]["om 19:00 uur"],
        telling["zondag"]["om 20:30 uur"],
        telling["zondag"]["misschien"],
        telling["zondag"]["niet meedoen"],
    ]

    write_header = not os.path.exists(ARCHIVE_CSV)
    with open(ARCHIVE_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(header)
        w.writerow(row)


def archive_exists() -> bool:
    return os.path.exists(ARCHIVE_CSV)


def open_archive_bytes() -> Tuple[str, bytes] | Tuple[None, None]:
    if not archive_exists():
        return None, None
    with open(ARCHIVE_CSV, "rb") as f:
        data = f.read()
    return ("dmk_archive.csv", data)


def delete_archive() -> bool:
    if archive_exists():
        os.remove(ARCHIVE_CSV)
        return True
    return False
