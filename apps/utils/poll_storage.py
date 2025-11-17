# apps/utils/poll_storage.py
#
# Scoped opslag van stemmen: per guild_id → per channel_id → per user_id.
# Geen legacy, geen migratie: dit bestand verwacht alleen de nieuwe structuur.
#
# Publieke API (async):
# - load_votes(guild_id: int|str | None = None, channel_id: int|str | None = None) -> dict
# - save_votes_scoped(guild_id, channel_id, scoped: dict) -> None
# - get_user_votes(user_id, guild_id, channel_id) -> dict
# - add_vote(user_id, dag, tijd, guild_id, channel_id) -> None
# - toggle_vote(user_id, dag, tijd, guild_id, channel_id) -> list
# - remove_vote(user_id, dag, tijd, guild_id, channel_id) -> None
# - get_counts_for_day(dag, guild_id, channel_id) -> dict[str, int]
# - get_votes_for_option(dag, tijd, guild_id, channel_id) -> int
# - calculate_leading_time(guild_id, channel_id, dag) -> str | None
# - reset_votes() -> None
# - reset_votes_scoped(guild_id, channel_id) -> None
# - add_guest_votes(owner_user_id, dag, tijd, namen, guild_id, channel_id) -> (list[str], list[str])
# - remove_guest_votes(owner_user_id, dag, tijd, namen, guild_id, channel_id) -> (list[str], list[str])
# - update_non_voters(guild_id, channel_id, channel) -> None
# - get_non_voters_for_day(dag, guild_id, channel_id) -> (int, list[str])

import asyncio
import json
import os
from typing import Any, Dict, Optional

from apps.entities.poll_option import get_poll_options, is_valid_option

SPECIALS = {"misschien", "niet meedoen"}

_VOTES_LOCK = asyncio.Lock()


def get_votes_path() -> str:
    return os.getenv("VOTES_FILE", "votes.json")


# -----------------------------
# Interne I/O helpers
# -----------------------------


async def _read_json(path: Optional[str] = None) -> Dict[str, Any]:
    path = path or get_votes_path()
    if not os.path.exists(path):
        return {}
    try:

        def _read():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        return await asyncio.to_thread(_read)
    except json.JSONDecodeError:  # pragma: no cover
        return {}


async def _write_json(path: str, data: Dict[str, Any]) -> None:
    def _write():
        import time
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Retry logic for Windows file locking issues
        max_retries = 5
        for attempt in range(max_retries):  # pragma: no branch
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:  # pragma: no cover
                if attempt < max_retries - 1:  # pragma: no cover
                    time.sleep(0.01 * (attempt + 1))  # Exponential backoff
                else:  # pragma: no cover
                    raise

    await asyncio.to_thread(_write)


def _ensure_root_structure(root: Dict[str, Any]) -> Dict[str, Any]:
    if "guilds" not in root or not isinstance(root.get("guilds"), dict):
        root["guilds"] = {}
    return root


def _ensure_guild_channel(root: Dict[str, Any], guild_id: str, channel_id: str) -> None:
    _ensure_root_structure(root)
    g = root["guilds"].setdefault(guild_id, {})
    g.setdefault("channels", {})
    g["channels"].setdefault(channel_id, {})


def _get_scoped(root: Dict[str, Any], guild_id: str, channel_id: str) -> Dict[str, Any]:
    g = root.get("guilds", {}).get(guild_id, {})
    ch = g.get("channels", {}).get(channel_id, {})
    return dict(ch) if isinstance(ch, dict) else {}


def _set_scoped(
    root: Dict[str, Any], guild_id: str, channel_id: str, scoped_dict: Dict[str, Any]
) -> None:
    _ensure_guild_channel(root, guild_id, channel_id)
    root["guilds"][guild_id]["channels"][channel_id] = dict(scoped_dict)


async def _get_root() -> Dict[str, Any]:
    return await _read_json(get_votes_path())


async def _save_root(root: Dict[str, Any]) -> None:
    await _write_json(get_votes_path(), root)


def _empty_days() -> Dict[str, list]:
    unieke_dagen = {opt.dag for opt in get_poll_options()}
    return {dag: [] for dag in unieke_dagen}


# -----------------------------
# Publieke API (scoped)
# -----------------------------


async def load_votes(
    guild_id: Optional[int | str] = None, channel_id: Optional[int | str] = None
) -> Dict[str, Any]:
    """
    Zonder scope → volledige root (met 'guilds').
    Met scope → map {user_id -> {dag: [tijden]}} in die guild+channel.
    """
    async with _VOTES_LOCK:
        root = await _get_root()
        if guild_id is None or channel_id is None:
            return root
        gid, cid = str(guild_id), str(channel_id)
        return _get_scoped(root, gid, cid)


async def save_votes_scoped(
    guild_id: int | str, channel_id: int | str, scoped: Dict[str, Any]
) -> None:
    async with _VOTES_LOCK:
        gid, cid = str(guild_id), str(channel_id)
        root = await _get_root()
        _set_scoped(root, gid, cid, scoped)
        await _save_root(root)


async def get_user_votes(
    user_id: str, guild_id: int | str, channel_id: int | str
) -> Dict[str, list]:
    scoped = await load_votes(guild_id, channel_id)
    return scoped.get(str(user_id), _empty_days())


async def add_vote(
    user_id: str, dag: str, tijd: str, guild_id: int | str, channel_id: int | str
) -> None:
    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in add_vote: {dag}, {tijd}")
        return
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)
    uid = str(user_id)
    user = scoped.setdefault(uid, _empty_days())
    if tijd not in user.get(dag, []):
        user.setdefault(dag, []).append(tijd)
    scoped[uid] = user
    await save_votes_scoped(gid, cid, scoped)


async def toggle_vote(
    user_id: str, dag: str, tijd: str, guild_id: int | str, channel_id: int | str
) -> list:
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)
    uid = str(user_id)
    user = scoped.setdefault(uid, _empty_days())
    if not is_valid_option(dag, tijd):
        return user.get(dag, [])

    day_votes = user.setdefault(dag, [])

    if tijd in SPECIALS:
        if tijd in day_votes and all(v in SPECIALS for v in day_votes):
            day_votes = [v for v in day_votes if v != tijd]
        else:
            day_votes = [tijd]
    else:
        day_votes = [v for v in day_votes if v not in SPECIALS]
        if tijd in day_votes:
            day_votes = [v for v in day_votes if v != tijd]
        else:
            day_votes.append(tijd)

    user[dag] = day_votes
    scoped[uid] = user
    await save_votes_scoped(gid, cid, scoped)
    return day_votes


async def remove_vote(
    user_id: str, dag: str, tijd: str, guild_id: int | str, channel_id: int | str
) -> None:
    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in remove_vote: {dag}, {tijd}")
        return
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)
    uid = str(user_id)
    if uid in scoped and tijd in scoped[uid].get(dag, []):  # pragma: no branch
        scoped[uid][dag].remove(tijd)
        await save_votes_scoped(gid, cid, scoped)


async def get_counts_for_day(
    dag: str, guild_id: int | str, channel_id: int | str
) -> Dict[str, int]:
    """Telt alle opties voor deze dag in de gegeven scope."""
    scoped = await load_votes(guild_id, channel_id)
    counts: Dict[str, int] = {}
    for o in get_poll_options():
        if o.dag != dag:
            continue
        c = 0
        for per_user in scoped.values():
            tijden = per_user.get(dag, [])
            if isinstance(tijden, list) and o.tijd in tijden:
                c += 1
        counts[o.tijd] = c
    return counts


async def get_votes_for_option(
    dag: str, tijd: str, guild_id: int | str, channel_id: int | str
) -> int:
    counts = await get_counts_for_day(dag, guild_id, channel_id)
    return counts.get(tijd, 0)


async def calculate_leading_time(
    guild_id: int | str, channel_id: int | str, dag: str
) -> str | None:
    """
    Bepaal de winnende tijd (19:00 of 20:30) voor een specifieke dag.

    Regels:
    - Alleen "om 19:00 uur" en "om 20:30 uur" doen mee
    - ❌ "niet meedoen" telt NIET mee (wordt uitgefilterd door get_counts_for_day)
    - Bij gelijkspel wint 20:30
    - Returns "19:00", "20:30", of None als er geen stemmen zijn

    Args:
        guild_id: Guild ID
        channel_id: Channel ID
        dag: De dag (vrijdag, zaterdag, zondag)

    Returns:
        "19:00", "20:30", of None als er geen stemmen zijn
    """
    T19 = "om 19:00 uur"
    T2030 = "om 20:30 uur"

    counts = await get_counts_for_day(dag, guild_id, channel_id)
    c19 = counts.get(T19, 0)
    c2030 = counts.get(T2030, 0)

    # Geen stemmen? Geen winnaar
    if c19 == 0 and c2030 == 0:
        return None

    # Bij gelijkspel of meer stemmen voor 20:30 → 20:30 wint
    if c2030 >= c19:
        return "20:30"
    else:
        return "19:00"


async def reset_votes() -> None:
    """Reset ALLE stemmen van alle guilds/channels."""
    async with _VOTES_LOCK:
        await _write_json(get_votes_path(), {})


async def reset_votes_scoped(guild_id: int | str, channel_id: int | str) -> None:
    """Reset stemmen voor één specifiek guild+channel."""
    async with _VOTES_LOCK:
        gid, cid = str(guild_id), str(channel_id)
        root = await _get_root()
        # Verwijder alleen deze channel uit de structuur
        try:
            if "guilds" in root and gid in root["guilds"]:
                guild_data = root["guilds"][gid]
                if "channels" in guild_data and cid in guild_data["channels"]:  # pragma: no branch
                    del guild_data["channels"][cid]
                    # Als guild geen channels meer heeft, verwijder de guild ook
                    if not guild_data.get("channels"):  # pragma: no branch
                        del root["guilds"][gid]
            await _save_root(root)
        except Exception:  # pragma: no cover
            # Bij fouten, val terug op lege dict voor dit kanaal
            _set_scoped(root, gid, cid, {})
            await _save_root(root)


# === GASTEN ===============================================================


def _sanitize_guest_name(name: str) -> str:
    raw = (
        name.strip()
        .replace("_", " ")
        .replace("|", " ")
        .replace(";", " ")
        .replace(",", " ")
    )
    cleaned = " ".join(raw.split())
    return cleaned[:40] if cleaned else "Gast"


def _guest_id(owner_user_id: int | str, guest_name: str) -> str:
    return f"{owner_user_id}_guest::{guest_name}"


async def add_guest_votes(
    owner_user_id: int | str,
    dag: str,
    tijd: str,
    namen: list[str],
    guild_id: int | str,
    channel_id: int | str,
) -> tuple[list[str], list[str]]:
    if not is_valid_option(dag, tijd):
        return ([], namen or [])

    norm = []
    for n in namen or []:
        s = _sanitize_guest_name(n)
        if s:  # pragma: no branch
            norm.append(s)

    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)
    toegevoegd, overgeslagen = [], []

    for naam in norm:
        key = _guest_id(owner_user_id, naam)
        per_dag = scoped.get(key, {})
        bestaande = per_dag.get(dag, [])

        if tijd in bestaande:
            overgeslagen.append(naam)
            continue

        nieuw = set(bestaande)
        nieuw.add(tijd)
        per_dag[dag] = sorted(list(nieuw))
        scoped[key] = per_dag
        toegevoegd.append(naam)

    await save_votes_scoped(gid, cid, scoped)
    return (toegevoegd, overgeslagen)


async def remove_guest_votes(
    owner_id: int | str,
    dag: str,
    tijd: str,
    namen: list[str],
    guild_id: int | str,
    channel_id: int | str,
) -> tuple[list[str], list[str]]:
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)
    verwijderd, nietgevonden = [], []

    for naam in namen or []:
        key = f"{owner_id}_guest::{naam}"
        if key in scoped and tijd in scoped[key].get(dag, []):
            try:
                scoped[key][dag].remove(tijd)
                verwijderd.append(naam)
            except ValueError:  # pragma: no cover
                nietgevonden.append(naam)

            if not scoped[key][dag]:
                del scoped[key][dag]
            if not scoped[key]:
                del scoped[key]
        else:
            nietgevonden.append(naam)

    await save_votes_scoped(gid, cid, scoped)
    return verwijderd, nietgevonden


# === WAS_MISSCHIEN TRACKING ===============================================


def _was_misschien_id(channel_id: int | str) -> str:
    """Generate ID for was_misschien tracking entry."""
    return f"_was_misschien::{channel_id}"


def _is_was_misschien_id(raw_id: str) -> bool:
    """Check if an ID represents a was_misschien tracking entry."""
    return isinstance(raw_id, str) and raw_id.startswith("_was_misschien::")


async def get_was_misschien_count(
    dag: str, guild_id: int | str, channel_id: int | str
) -> int:
    """
    Get the was_misschien count for a specific day.

    This tracks how many "misschien" votes were converted to "niet meedoen"
    when the deadline passed.

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - guild_id: Discord guild ID
    - channel_id: Discord channel ID

    Returns:
    - Count of was_misschien votes for this day
    """
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)

    tracking_id = _was_misschien_id(cid)
    if tracking_id in scoped:
        per_dag = scoped[tracking_id]
        if isinstance(per_dag, dict) and dag in per_dag:
            tijden = per_dag[dag]
            if isinstance(tijden, list) and len(tijden) > 0:
                # The count is stored as the first element
                try:
                    return int(tijden[0])
                except (ValueError, TypeError):  # pragma: no cover
                    return 0

    return 0


async def set_was_misschien_count(
    dag: str, count: int, guild_id: int | str, channel_id: int | str
) -> None:
    """
    Set the was_misschien count for a specific day.

    This is called when the deadline passes and "misschien" votes are
    converted to "niet meedoen".

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - count: Number of misschien votes that were converted
    - guild_id: Discord guild ID
    - channel_id: Discord channel ID
    """
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)

    tracking_id = _was_misschien_id(cid)
    if tracking_id not in scoped:
        scoped[tracking_id] = _empty_days()

    # Store the count as a list with a single element (to match the vote structure)
    scoped[tracking_id][dag] = [str(count)]

    await save_votes_scoped(gid, cid, scoped)


async def reset_was_misschien_counts(guild_id: int | str, channel_id: int | str) -> None:
    """
    Reset all was_misschien counts to 0.

    This is called when the poll is reset for a new week.

    Parameters:
    - guild_id: Discord guild ID
    - channel_id: Discord channel ID
    """
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)

    tracking_id = _was_misschien_id(cid)
    if tracking_id in scoped:
        del scoped[tracking_id]
        await save_votes_scoped(gid, cid, scoped)


# === NON-VOTERS TRACKING ===================================================


def _non_voter_id(user_id: int | str) -> str:
    """Generate ID for non-voter entry."""
    return f"_non_voter::{user_id}"


def _is_non_voter_id(raw_id: str) -> bool:
    """Check if an ID represents a non-voter."""
    return isinstance(raw_id, str) and raw_id.startswith("_non_voter::")


def _extract_user_id_from_non_voter(raw_id: str) -> str:
    """Extract user ID from non-voter ID."""
    if _is_non_voter_id(raw_id):
        return raw_id.split("_non_voter::", 1)[1]
    return raw_id


async def update_non_voters(
    guild_id: int | str, channel_id: int | str, channel
) -> None:
    """
    Update non-voters in storage based on channel members.

    This function:
    1. Gets all channel members (excluding bots)
    2. Checks who has voted (including via guests)
    3. Stores non-voters with special IDs in the votes structure

    Non-voters are stored per day with "niet gestemd" as their vote.

    Parameters:
    - guild_id: Discord guild ID
    - channel_id: Discord channel ID
    - channel: Discord channel object (to get members)
    """
    if not channel:
        return

    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)

    # Get all channel members (excluding bots)
    members = getattr(channel, "members", [])
    all_member_ids = set()

    for member in members:
        if getattr(member, "bot", False):
            continue
        member_id = str(getattr(member, "id", ""))
        if member_id:
            all_member_ids.add(member_id)

    # For each day, determine who voted and who didn't
    unieke_dagen = {opt.dag for opt in get_poll_options()}

    for dag in unieke_dagen:
        # Collect IDs that voted for this day (including guests via their owner)
        voted_ids: set[str] = set()

        for uid, per_dag in scoped.items():
            # Skip non-voter entries when checking who voted
            if _is_non_voter_id(uid):
                continue

            try:
                tijden = (per_dag or {}).get(dag, [])
                if isinstance(tijden, list) and tijden:
                    # Extract owner ID (handle guests)
                    actual_uid = (
                        uid.split("_guest::", 1)[0]
                        if isinstance(uid, str) and "_guest::" in uid
                        else uid
                    )
                    voted_ids.add(str(actual_uid))
            except Exception:  # pragma: no cover
                continue

        # Determine non-voters
        non_voter_ids = all_member_ids - voted_ids

        # Remove old non-voter entries for this day
        keys_to_remove = []
        for uid in scoped.keys():
            if _is_non_voter_id(uid):
                # Extract actual user ID
                actual_id = _extract_user_id_from_non_voter(uid)
                # If this member is no longer a non-voter, remove the entry
                if actual_id not in non_voter_ids:
                    if dag in scoped[uid]:
                        del scoped[uid][dag]
                    # If no more days, mark for removal
                    if not scoped[uid]:
                        keys_to_remove.append(uid)

        for key in keys_to_remove:
            del scoped[key]

        # Add/update non-voter entries for this day
        for member_id in non_voter_ids:
            non_voter_key = _non_voter_id(member_id)
            if non_voter_key not in scoped:
                scoped[non_voter_key] = _empty_days()
            scoped[non_voter_key][dag] = ["niet gestemd"]

    await save_votes_scoped(gid, cid, scoped)


async def get_non_voters_for_day(
    dag: str, guild_id: int | str, channel_id: int | str
) -> tuple[int, list[str]]:
    """
    Get non-voters for a specific day from storage.

    Returns:
    - (count, list of user_ids) of non-voters for this day

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - guild_id: Discord guild ID
    - channel_id: Discord channel ID
    """
    gid, cid = str(guild_id), str(channel_id)
    scoped = await load_votes(gid, cid)

    non_voter_ids = []

    for uid, per_dag in scoped.items():
        if not _is_non_voter_id(uid):
            continue

        try:
            tijden = (per_dag or {}).get(dag, [])
            if isinstance(tijden, list) and "niet gestemd" in tijden:
                # Extract actual user ID
                actual_id = _extract_user_id_from_non_voter(uid)
                non_voter_ids.append(actual_id)
        except Exception:  # pragma: no cover
            continue

    return len(non_voter_ids), non_voter_ids
