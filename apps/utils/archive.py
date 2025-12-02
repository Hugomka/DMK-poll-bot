# apps/utils/archive.py

import csv
import os
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

import pytz

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_settings import WEEK_DAYS
from apps.utils.poll_storage import (
    get_non_voters_for_day,
    get_was_misschien_count,
    load_votes,
)

ARCHIVE_DIR = "archive"
ARCHIVE_CSV = os.path.join(ARCHIVE_DIR, "dmk_archive.csv")

VOLGORDE = [
    "om 19:00 uur",
    "om 20:30 uur",
    "misschien",
    "was misschien",
    "niet meedoen",
    "niet gestemd",
]

# Weekday en weekend constanten voor dual archive systeem
WEEKEND_DAYS = ["vrijdag", "zaterdag", "zondag"]
WEEKDAY_DAYS = ["maandag", "dinsdag", "woensdag", "donderdag"]

DAGEN = []
for o in get_poll_options():
    if o.dag not in DAGEN and o.dag in WEEK_DAYS:
        DAGEN.append(o.dag)


def _ensure_dir():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _sanitize_id(value: int | str) -> str:
    """Sanitize guild/channel ID voor veilige bestandsnaam."""
    s = str(value).strip()
    # Alleen cijfers en underscores toestaan
    return "".join(c if c.isdigit() or c == "_" else "_" for c in s)


def get_archive_path_scoped(
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
    weekday: bool = False,
) -> str:
    """
    Pad naar CSV-archief.
    - Zonder guild/channel → legacy pad: ARCHIVE_CSV
    - Met beide IDs + weekday=False → weekend archief: archive/dmk_archive_<guild>_<channel>.csv
    - Met beide IDs + weekday=True → weekday archief: archive/dmk_archive_<guild>_<channel>_weekdays.csv
    """
    if guild_id is None or channel_id is None:
        return ARCHIVE_CSV
    gid = _sanitize_id(guild_id)
    cid = _sanitize_id(channel_id)
    suffix = "_weekdays" if weekday else ""
    return os.path.join(ARCHIVE_DIR, f"dmk_archive_{gid}_{cid}{suffix}.csv")


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
            was_misschien_count = await get_was_misschien_count(
                dag, guild_id, channel_id
            )
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
    """
    Geef (week, datum_vrijdag, datum_zaterdag, datum_zondag) als YYYY-MM-DD.

    Geeft het meest recente AFGERONDE weekend (vr-za-zo) dat VOOR nu plaatsvond.
    Dit zorgt ervoor dat we altijd de poll-periode archiveren die net eindigde,
    ongeacht wanneer de reset is gepland (maandag, dinsdag, woensdag, etc.).

    Belangrijk: Dit geeft altijd het VERLEDEN weekend, nooit het huidige/toekomstige.
    """
    if now.tzinfo is None:
        now = pytz.timezone("Europe/Amsterdam").localize(now)

    current_weekday = now.weekday()  # Maandag=0, Zondag=6

    # Bereken de meest recente vrijdag die in het verleden ligt
    # Vrijdag = weekdag 4
    if current_weekday >= 4:  # Vrijdag (4), Zaterdag (5), Zondag (6)
        # We zitten in het weekend of het is vrijdag - ga terug naar VORIGE vrijdag
        days_since_last_friday = (
            current_weekday - 4 + 7
        )  # Ga terug naar vorige week vrijdag
        vr = (now - timedelta(days=days_since_last_friday)).date()
    else:  # Maandag (0) t/m Donderdag (3)
        # Weekend is net afgelopen - gebruik afgelopen vrijdag
        days_since_last_friday = current_weekday + 3  # Ma:3, Di:4, Wo:5, Do:6
        vr = (now - timedelta(days=days_since_last_friday)).date()

    # Zaterdag en zondag volgen vrijdag
    za = vr + timedelta(days=1)
    zo = vr + timedelta(days=2)

    # ISO week format: YYYY-Www (bijvoorbeeld 2025-W45)
    iso_cal = vr.isocalendar()
    week = f"{iso_cal.year}-W{iso_cal.week:02d}"
    return (week, vr.isoformat(), za.isoformat(), zo.isoformat())


def _week_dates_weekdays(now):
    """
    Geef (week, datum_maandag, datum_dinsdag, datum_woensdag, datum_donderdag) als YYYY-MM-DD.

    Geeft de meest recente AFGERONDE weekdagen (ma-di-wo-do) die VOOR nu plaatsvonden.
    Dit zorgt ervoor dat we altijd de week archiveren die net eindigde.

    Belangrijk: Dit geeft altijd VERLEDEN weekdagen, nooit huidige/toekomstige.
    """
    if now.tzinfo is None:
        now = pytz.timezone("Europe/Amsterdam").localize(now)

    current_weekday = now.weekday()  # Maandag=0, Zondag=6

    # Bereken de meest recente maandag die in het verleden ligt
    # Maandag = weekdag 0
    if current_weekday == 0:
        # Het is maandag - ga terug naar VORIGE maandag
        days_since_last_monday = 7
    else:
        # Anders: gebruik de meest recente maandag
        days_since_last_monday = current_weekday

    ma = (now - timedelta(days=days_since_last_monday)).date()

    # Dinsdag, woensdag, donderdag volgen maandag
    di = ma + timedelta(days=1)
    wo = ma + timedelta(days=2)
    do = ma + timedelta(days=3)

    # ISO week format: YYYY-Www (gebruik maandag voor week nummer)
    iso_cal = ma.isocalendar()
    week = f"{iso_cal.year}-W{iso_cal.week:02d}"
    return (week, ma.isoformat(), di.isoformat(), wo.isoformat(), do.isoformat())


# === SCOPED ARCHIVE FUNCTIONS (PER GUILD+CHANNEL) met backward compat ===


async def _archive_weekend(
    telling: dict,
    guild_id: Optional[int | str],
    channel_id: Optional[int | str],
    now: datetime,
) -> None:
    """
    Archiveer weekend data (vrijdag, zaterdag, zondag) naar weekend CSV.
    Dit is het standaard archief dat altijd wordt gebruikt (backward compatible).
    """
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

    csv_path = get_archive_path_scoped(guild_id, channel_id, weekday=False)
    await _write_archive_csv(csv_path, header, row, week)


async def _archive_weekdays(
    telling: dict,
    guild_id: Optional[int | str],
    channel_id: Optional[int | str],
    now: datetime,
) -> None:
    """
    Archiveer weekday data (maandag, dinsdag, woensdag, donderdag) naar weekday CSV.
    Dit archief wordt alleen gebruikt als er weekday polls zijn ingeschakeld.
    """
    week, ma, di, wo, do = _week_dates_weekdays(now)

    header = [
        "week",
        "datum_maandag",
        "datum_dinsdag",
        "datum_woensdag",
        "datum_donderdag",
        "ma_19",
        "ma_2030",
        "ma_misschien",
        "ma_was_misschien",
        "ma_niet",
        "ma_niet_gestemd",
        "di_19",
        "di_2030",
        "di_misschien",
        "di_was_misschien",
        "di_niet",
        "di_niet_gestemd",
        "wo_19",
        "wo_2030",
        "wo_misschien",
        "wo_was_misschien",
        "wo_niet",
        "wo_niet_gestemd",
        "do_19",
        "do_2030",
        "do_misschien",
        "do_was_misschien",
        "do_niet",
        "do_niet_gestemd",
    ]
    row = [
        week,
        ma,
        di,
        wo,
        do,
        telling["maandag"]["om 19:00 uur"],
        telling["maandag"]["om 20:30 uur"],
        telling["maandag"]["misschien"],
        telling["maandag"]["was misschien"],
        telling["maandag"]["niet meedoen"],
        telling["maandag"]["niet gestemd"],
        telling["dinsdag"]["om 19:00 uur"],
        telling["dinsdag"]["om 20:30 uur"],
        telling["dinsdag"]["misschien"],
        telling["dinsdag"]["was misschien"],
        telling["dinsdag"]["niet meedoen"],
        telling["dinsdag"]["niet gestemd"],
        telling["woensdag"]["om 19:00 uur"],
        telling["woensdag"]["om 20:30 uur"],
        telling["woensdag"]["misschien"],
        telling["woensdag"]["was misschien"],
        telling["woensdag"]["niet meedoen"],
        telling["woensdag"]["niet gestemd"],
        telling["donderdag"]["om 19:00 uur"],
        telling["donderdag"]["om 20:30 uur"],
        telling["donderdag"]["misschien"],
        telling["donderdag"]["was misschien"],
        telling["donderdag"]["niet meedoen"],
        telling["donderdag"]["niet gestemd"],
    ]

    csv_path = get_archive_path_scoped(guild_id, channel_id, weekday=True)
    await _write_archive_csv(csv_path, header, row, week)


async def _write_archive_csv(
    csv_path: str, header: list, row: list, week: str
) -> None:
    """
    Helper functie om CSV archief te schrijven met header en data rij.
    Gebruikt voor zowel weekend als weekday archieven.
    Ondersteunt update van bestaande week of append van nieuwe week.

    Voor weekend archief: migreert automatisch van V1/V2 → V3 formaat.
    Voor weekday archief: altijd V1 formaat (nieuw).
    """
    if os.path.exists(csv_path):
        # Lees bestaande CSV
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if rows:
            existing_header = rows[0]

            # Migratie logica voor weekend archief (V1/V2 → V3)
            # Check: weekend archief heeft "vr_" kolommen, weekday heeft "ma_"
            is_weekend_archive = any("vr_" in col for col in existing_header)

            if is_weekend_archive and "vr_was_misschien" not in existing_header:
                # Migreer oude data naar nieuwe structuur
                # V1 (16 columns): no niet_gestemd, no was_misschien
                # V2 (19 columns): has niet_gestemd, no was_misschien
                # V3 (22 columns): has niet_gestemd and was_misschien (current)

                rows[0] = header  # Update header

                # Migreer data rijen
                for i in range(1, len(rows)):
                    old_row = rows[i]

                    if len(old_row) >= 19:
                        # V2 → V3: Add was_misschien columns
                        new_row = [
                            old_row[0],
                            old_row[1],
                            old_row[2],
                            old_row[3],
                            old_row[4],
                            old_row[5],
                            old_row[6],
                            "",  # vr_was_misschien
                            old_row[7],
                            old_row[8],
                            old_row[9],
                            old_row[10],
                            old_row[11],
                            "",  # za_was_misschien
                            old_row[12],
                            old_row[13],
                            old_row[14],
                            old_row[15],
                            old_row[16],
                            "",  # zo_was_misschien
                            old_row[17],
                            old_row[18],
                        ]
                        rows[i] = new_row
                    elif len(old_row) >= 16:
                        # V1 → V3: Add beide niet_gestemd en was_misschien
                        new_row = [
                            old_row[0],
                            old_row[1],
                            old_row[2],
                            old_row[3],
                            old_row[4],
                            old_row[5],
                            old_row[6],
                            "",  # vr_was_misschien
                            old_row[7],
                            "",  # vr_niet_gestemd
                            old_row[8],
                            old_row[9],
                            old_row[10],
                            "",  # za_was_misschien
                            old_row[11],
                            "",  # za_niet_gestemd
                            old_row[12],
                            old_row[13],
                            old_row[14],
                            "",  # zo_was_misschien
                            old_row[15],
                            "",  # zo_niet_gestemd
                        ]
                        rows[i] = new_row

            # Check of deze week al bestaat, zo ja: update die rij, anders: append
            week_exists = False
            for i in range(1, len(rows)):
                if rows[i] and rows[i][0] == week:
                    # Update bestaande rij voor deze week
                    rows[i] = row
                    week_exists = True
                    break

            if not week_exists:
                # Week bestaat nog niet, append nieuwe rij
                rows.append(row)

            # Herschrijf het hele bestand
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerows(rows)
        else:
            # Leeg bestand (geen header): schrijf header + eerste rij
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerow(row)
    else:
        # Nieuw bestand: schrijf header + eerste rij
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerow(row)


async def append_week_snapshot_scoped(
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
    now: Optional[datetime] = None,
    channel: Any = None,
) -> None:
    """
    Schrijf 1 rij naar CSV met week+datums+tellingen+niet-stemmers.

    Gebruikt dual archive systeem:
    - Weekend archief (vrijdag/zaterdag/zondag): altijd actief (backward compatible)
    - Weekday archief (maandag/dinsdag/woensdag/donderdag): alleen actief als weekday polls enabled zijn

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

    # Altijd weekend archief schrijven (backward compatible)
    await _archive_weekend(telling, guild_id, channel_id, now)

    # Alleen weekday archief schrijven als er weekday polls ingeschakeld zijn
    if guild_id is not None and channel_id is not None:
        # Import hier om circulaire import te voorkomen
        from apps.utils.poll_settings import get_enabled_poll_days

        enabled_days = get_enabled_poll_days(int(channel_id))
        weekday_enabled = any(day in enabled_days for day in WEEKDAY_DAYS)

        if weekday_enabled:
            await _archive_weekdays(telling, guild_id, channel_id, now)


def archive_exists_scoped(
    guild_id: Optional[int | str] = None, channel_id: Optional[int | str] = None
) -> bool:
    """Bestaat het archief? Zonder IDs → legacy pad."""
    return os.path.exists(get_archive_path_scoped(guild_id, channel_id))


def create_archive(
    guild_id: Optional[int | str] = None,
    channel_id: Optional[int | str] = None,
    delimiter: str = ",",
    weekday: bool = False,
) -> Optional[bytes]:
    """
    Genereer CSV archief met gespecificeerde delimiter.

    Args:
        guild_id: Guild ID voor scoped archief
        channel_id: Channel ID voor scoped archief
        delimiter: CSV delimiter ("," of ";")
        weekday: True voor weekday archief (ma-do), False voor weekend archief (vr-zo)

    Returns:
        CSV data als bytes, of None als archief niet bestaat
    """
    csv_path = get_archive_path_scoped(guild_id, channel_id, weekday=weekday)

    if not os.path.exists(csv_path):
        return None

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
    """Verwijder alle archieven (weekend + weekday). Zonder IDs → legacy pad."""
    deleted_any = False

    # Verwijder weekend archief
    weekend_path = get_archive_path_scoped(guild_id, channel_id, weekday=False)
    if os.path.exists(weekend_path):
        os.remove(weekend_path)
        deleted_any = True

    # Verwijder weekday archief (indien aanwezig)
    weekday_path = get_archive_path_scoped(guild_id, channel_id, weekday=True)
    if os.path.exists(weekday_path):
        os.remove(weekday_path)
        deleted_any = True

    return deleted_any
