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
# - reset_votes() -> None
# - add_guest_votes(owner_user_id, dag, tijd, namen, guild_id, channel_id) -> (list[str], list[str])
# - remove_guest_votes(owner_user_id, dag, tijd, namen, guild_id, channel_id) -> (list[str], list[str])

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
    except json.JSONDecodeError:
        print("⚠️ votes.json is beschadigd. Ik zet 'm terug naar leeg {}.")
        return {}


async def _write_json(path: str, data: Dict[str, Any]) -> None:
    def _write():
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

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
    if uid in scoped and tijd in scoped[uid].get(dag, []):
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


async def reset_votes() -> None:
    """Reset ALLE stemmen van alle guilds/channels."""
    async with _VOTES_LOCK:
        await _write_json(get_votes_path(), {})


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
        if s:
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
            except ValueError:
                nietgevonden.append(naam)

            if not scoped[key][dag]:
                del scoped[key][dag]
            if not scoped[key]:
                del scoped[key]
        else:
            nietgevonden.append(naam)

    await save_votes_scoped(gid, cid, scoped)
    return verwijderd, nietgevonden
