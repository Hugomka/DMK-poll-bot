# apps/utils/archive.py

import csv
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pytz

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_storage import load_votes

ARCHIVE_DIR = "archive"
ARCHIVE_CSV = os.path.join(ARCHIVE_DIR, "dmk_archive.csv")

VOLGORDE = ["om 19:00 uur", "om 20:30 uur", "misschien", "niet meedoen"]
DAGEN = []
for o in get_poll_options():
    if o.dag not in DAGEN and o.dag in ["vrijdag", "zaterdag", "zondag"]:
        DAGEN.append(o.dag)


def _ensure_dir():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _sanitize_id(value: int | str) -> str:
    """Sanitize guild/channel ID voor veilige bestandsnaam."""
    s = str(value).strip()
    # Alleen cijfers en underscores toestaan
    return "".join(c if c.isdigit() or c == "_" else "_" for c in s)


def get_archive_path_scoped(
    guild_id: Optional[int | str] = None, channel_id: Optional[int | str] = None
) -> str:
    """
    Pad naar CSV-archief.
    - Zonder guild/channel → legacy pad: ARCHIVE_CSV
    - Met beide IDs → per-kanaal pad: archive/dmk_archive_<guild>_<channel>.csv
    """
    if guild_id is None or channel_id is None:
        return ARCHIVE_CSV
    gid = _sanitize_id(guild_id)
    cid = _sanitize_id(channel_id)
    return os.path.join(ARCHIVE_DIR, f"dmk_archive_{gid}_{cid}.csv")


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


# === SCOPED ARCHIVE FUNCTIONS (PER GUILD+CHANNEL) met backward compat ===


async def append_week_snapshot_scoped(
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
    now: Optional[datetime] = None,
) -> None:
    """
    Schrijf 1 rij naar CSV met week+datums+tellingen.
    Backward compat:
      - Zonder guild/channel → gebruik globale ARCHIVE_CSV (legacy tests).
      - Sommige oude tests roepen append_week_snapshot_scoped(<now>) aan:
        detecteer dat en verschuif argumenten.
    """
    # Back-compat: eerste arg kan 'now' zijn
    if isinstance(guild_id, datetime) and channel_id is None and now is None:
        now = guild_id
        guild_id = None
        channel_id = None
    _ensure_dir()
    if now is None:
        now = datetime.now(pytz.timezone("Europe/Amsterdam"))

    # Zonder IDs: legacy pad + lege telling is prima voor tests
    votes = (
        await load_votes(guild_id, channel_id)
        if (guild_id is not None and channel_id is not None)
        else {}
    )
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

    csv_path = get_archive_path_scoped(guild_id, channel_id)
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(header)
        w.writerow(row)


def archive_exists_scoped(
    guild_id: Optional[int | str] = None, channel_id: Optional[int | str] = None
) -> bool:
    """Bestaat het archief? Zonder IDs → legacy pad."""
    return os.path.exists(get_archive_path_scoped(guild_id, channel_id))


def create_archive(
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
    delimiter: str = ",",
) -> Optional[bytes]:
    """
    Genereer CSV archief met gespecificeerde delimiter.

    Args:
        guild_id: Guild ID voor scoped archief
        channel_id: Channel ID voor scoped archief
        delimiter: CSV delimiter ("," of ";")

    Returns:
        CSV data als bytes, of None als archief niet bestaat
    """
    if not archive_exists_scoped(guild_id, channel_id):
        return None

    csv_path = get_archive_path_scoped(guild_id, channel_id)

    # Lees originele CSV (altijd met komma delimiter)
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",")
        rows = list(reader)

    if not rows:
        return None

    # Herschrijf met gewenste delimiter
    output = []
    for row in rows:
        output.append(delimiter.join(str(cell) for cell in row))

    return "\n".join(output).encode("utf-8")


def generate_csv_preview(
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
    delimiter: str = ",",
    max_lines: int = 5,
) -> str:
    """
    Genereer preview van eerste N regels van CSV archief.

    Args:
        guild_id: Guild ID voor scoped archief
        channel_id: Channel ID voor scoped archief
        delimiter: CSV delimiter ("," of ";")
        max_lines: Maximum aantal regels (default 5)

    Returns:
        Preview string voor codeblock
    """
    csv_data = create_archive(guild_id, channel_id, delimiter)
    if not csv_data:
        return "Geen archief beschikbaar."

    lines = csv_data.decode("utf-8").split("\n")
    preview_lines = lines[:max_lines]

    return "\n".join(preview_lines)


def open_archive_bytes_scoped(
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
) -> Tuple[Optional[str], Optional[bytes]]:
    """Open archief als bytes. Zonder IDs → legacy bestandsnaam."""
    if not archive_exists_scoped(guild_id, channel_id):
        return None, None
    csv_path = get_archive_path_scoped(guild_id, channel_id)
    if guild_id is None or channel_id is None:
        filename = "dmk_archive.csv"
    else:
        filename = (
            f"dmk_archive_{_sanitize_id(guild_id)}_{_sanitize_id(channel_id)}.csv"
        )
    with open(csv_path, "rb") as f:
        data = f.read()
    return (filename, data)


def delete_archive_scoped(
    guild_id: Optional[int | str] = None, channel_id: Optional[int | str] = None
) -> bool:
    """Verwijder archief. Zonder IDs → legacy pad."""
    if archive_exists_scoped(guild_id, channel_id):
        os.remove(get_archive_path_scoped(guild_id, channel_id))
        return True
    return False
