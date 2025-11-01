# apps/utils/archive.py

import csv
import os
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

import pytz

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_storage import (
    get_non_voters_for_day,
    get_was_misschien_count,
    load_votes,
)

ARCHIVE_DIR = "archive"
ARCHIVE_CSV = os.path.join(ARCHIVE_DIR, "dmk_archive.csv")

VOLGORDE = ["om 19:00 uur", "om 20:30 uur", "misschien", "was misschien", "niet meedoen", "niet gestemd"]
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


async def _build_counts_from_votes(
    votes: dict,
    channel: Any = None,
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
):
    """
    Bouw tellingen voor alle opties inclusief niet-stemmers.

    Parameters:
    - votes: Dictionary met alle stemmen
    - channel: Discord channel (kept for compatibility, not used)
    - guild_id: Guild ID for retrieving stored non-voters
    - channel_id: Channel ID for retrieving stored non-voters

    Returns:
    - Dictionary met tellingen per dag en optie
    """
    telling = _empty_counts()

    # Tel gewone stemmen
    for per_dag in votes.values():
        for dag, keuzes in per_dag.items():
            if dag not in telling:
                continue
            for tijd in keuzes:
                if tijd in telling[dag]:
                    telling[dag][tijd] += 1

    # Tel niet-stemmers per dag (from storage)
    if guild_id is not None and channel_id is not None:
        for dag in DAGEN:
            non_voter_count = await _count_non_voters(
                dag, votes, channel, guild_id, channel_id
            )
            telling[dag]["niet gestemd"] = non_voter_count

            # Get was_misschien count (from storage)
            was_misschien_count = await get_was_misschien_count(dag, guild_id, channel_id)
            telling[dag]["was misschien"] = was_misschien_count

    return telling


async def _count_non_voters(
    dag: str,
    votes: dict,
    channel: Any = None,
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
) -> int:
    """
    Tel aantal niet-stemmers voor een specifieke dag.

    Tries to use stored non-voters from poll_storage, falls back to calculating from channel.

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - votes: Dictionary met alle stemmen (used for fallback calculation)
    - channel: Discord channel (used for fallback calculation)
    - guild_id: Guild ID for retrieving stored non-voters
    - channel_id: Channel ID for retrieving stored non-voters

    Returns:
    - Aantal niet-stemmers
    """
    # Try to get count from storage first
    if guild_id is not None and channel_id is not None:
        try:
            count, _ = await get_non_voters_for_day(dag, guild_id, channel_id)
            if count > 0:
                return count
        except Exception:  # pragma: no cover
            pass

    # Fallback: calculate from channel members (legacy behavior)
    if not channel:
        return 0

    # Verzamel IDs die voor deze dag hebben gestemd (inclusief gasten via hun owner)
    voted_ids: set[str] = set()
    for uid, per_dag in votes.items():
        try:
            # Skip non-voter entries
            if isinstance(uid, str) and uid.startswith("_non_voter::"):
                continue

            tijden = (per_dag or {}).get(dag, [])
            if isinstance(tijden, list) and tijden:
                # Extract owner ID (handle guests)
                actual_uid = (
                    uid.split("_guest::", 1)[0]
                    if isinstance(uid, str) and "_guest::" in uid
                    else uid
                )
                voted_ids.add(str(actual_uid))
        except Exception:
            continue

    # Tel leden die toegang hebben tot dit specifieke kanaal (exclusief bots)
    members = getattr(channel, "members", [])
    total_members = 0

    for member in members:
        if getattr(member, "bot", False):
            continue
        total_members += 1

    # Aantal stemmers (alleen die ook toegang hebben tot het kanaal)
    voters_count = 0
    for member in members:
        if getattr(member, "bot", False):
            continue
        member_id = str(getattr(member, "id", ""))
        if member_id in voted_ids:
            voters_count += 1

    return total_members - voters_count


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
    channel: Any = None,
) -> None:
    """
    Schrijf 1 rij naar CSV met week+datums+tellingen+niet-stemmers.
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
    telling = await _build_counts_from_votes(votes, channel, guild_id, channel_id)
    week, vr, za, zo = _week_dates_eu(now)

    header = [
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
    row = [
        week,
        vr,
        za,
        zo,
        telling["vrijdag"]["om 19:00 uur"],
        telling["vrijdag"]["om 20:30 uur"],
        telling["vrijdag"]["misschien"],
        telling["vrijdag"]["was misschien"],
        telling["vrijdag"]["niet meedoen"],
        telling["vrijdag"]["niet gestemd"],
        telling["zaterdag"]["om 19:00 uur"],
        telling["zaterdag"]["om 20:30 uur"],
        telling["zaterdag"]["misschien"],
        telling["zaterdag"]["was misschien"],
        telling["zaterdag"]["niet meedoen"],
        telling["zaterdag"]["niet gestemd"],
        telling["zondag"]["om 19:00 uur"],
        telling["zondag"]["om 20:30 uur"],
        telling["zondag"]["misschien"],
        telling["zondag"]["was misschien"],
        telling["zondag"]["niet meedoen"],
        telling["zondag"]["niet gestemd"],
    ]

    csv_path = get_archive_path_scoped(guild_id, channel_id)

    # Check if we need to migrate/update the header
    if os.path.exists(csv_path):
        # Lees bestaande CSV
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if rows:
            existing_header = rows[0]
            # Check of nieuwe kolommen ontbreken
            if "vr_was_misschien" not in existing_header:
                # Migreer oude data naar nieuwe structuur
                # Supported CSV versions:
                # V1 (16 columns): no niet_gestemd, no was_misschien
                # V2 (19 columns): has niet_gestemd, no was_misschien
                # V3 (22 columns): has niet_gestemd and was_misschien (current)

                # Update header
                rows[0] = header

                # Voor elke data rij, voeg ontbrekende kolommen toe met lege waarde
                # Lege waarde = data niet beschikbaar (niet getrackt in die week)
                for i in range(1, len(rows)):
                    old_row = rows[i]

                    if len(old_row) >= 19:
                        # V2 format with niet_gestemd (19 columns)
                        # Migrate to V3: Add was_misschien columns after each misschien column
                        new_row = [
                            old_row[0],   # week
                            old_row[1],   # datum_vrijdag
                            old_row[2],   # datum_zaterdag
                            old_row[3],   # datum_zondag
                            old_row[4],   # vr_19
                            old_row[5],   # vr_2030
                            old_row[6],   # vr_misschien
                            "",           # vr_was_misschien (V3 - leeg = niet getrackt)
                            old_row[7],   # vr_niet
                            old_row[8],   # vr_niet_gestemd
                            old_row[9],   # za_19
                            old_row[10],  # za_2030
                            old_row[11],  # za_misschien
                            "",           # za_was_misschien (V3 - leeg = niet getrackt)
                            old_row[12],  # za_niet
                            old_row[13],  # za_niet_gestemd
                            old_row[14],  # zo_19
                            old_row[15],  # zo_2030
                            old_row[16],  # zo_misschien
                            "",           # zo_was_misschien (V3 - leeg = niet getrackt)
                            old_row[17],  # zo_niet
                            old_row[18],  # zo_niet_gestemd
                        ]
                        rows[i] = new_row
                    elif len(old_row) >= 16:
                        # V1 format without niet_gestemd (16 columns)
                        # Migrate to V3: Add both niet_gestemd and was_misschien columns
                        new_row = [
                            old_row[0],   # week
                            old_row[1],   # datum_vrijdag
                            old_row[2],   # datum_zaterdag
                            old_row[3],   # datum_zondag
                            old_row[4],   # vr_19
                            old_row[5],   # vr_2030
                            old_row[6],   # vr_misschien
                            "",           # vr_was_misschien (V3 - leeg = niet getrackt)
                            old_row[7],   # vr_niet
                            "",           # vr_niet_gestemd (V2/V3 - leeg = niet getrackt)
                            old_row[8],   # za_19
                            old_row[9],   # za_2030
                            old_row[10],  # za_misschien
                            "",           # za_was_misschien (V3 - leeg = niet getrackt)
                            old_row[11],  # za_niet
                            "",           # za_niet_gestemd (V2/V3 - leeg = niet getrackt)
                            old_row[12],  # zo_19
                            old_row[13],  # zo_2030
                            old_row[14],  # zo_misschien
                            "",           # zo_was_misschien (V3 - leeg = niet getrackt)
                            old_row[15],  # zo_niet
                            "",           # zo_niet_gestemd (V2/V3 - leeg = niet getrackt)
                        ]
                        rows[i] = new_row

                # Herschrijf bestand met nieuwe header + gemigreerde data
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerows(rows)

        # Append nieuwe rij
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(row)
    else:
        # Nieuw bestand: schrijf header + eerste rij
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
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
