# apps/utils/poll_storage.py

import asyncio
import json
import os
from typing import (
    Any,
    Dict,
    Optional,
)  # Optional alleen nodig als je < Python 3.10 draait

from apps.entities.poll_option import get_poll_options, is_valid_option

SPECIALS = {"misschien", "niet meedoen"}

# 1 lock voor veilig schrijven/lezen
_VOTES_LOCK = asyncio.Lock()


def get_votes_path() -> str:
    return os.getenv("VOTES_FILE", "votes.json")


# Gebruik Optional[str] (of str | None op 3.10+)
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
        print("⚠️ votes.json is corrupt. Ik zet 'm terug naar leeg {}.")
        return {}


async def _write_json(path: str, data: Dict[str, Any]) -> None:
    """
    Schrijf de stemmen veilig weg door eerst naar een tijdelijk bestand te schrijven.
    Daarna vervang je het oude bestand in één stap.
    """

    def _write():
        # schrijf naar een tijdelijke file
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # zorg dat alles op schijf staat
        # vervang de oude file atomisch
        os.replace(tmp_path, path)

    await asyncio.to_thread(_write)


# Publiek async API
async def load_votes() -> Dict[str, Any]:
    async with _VOTES_LOCK:
        return await _read_json(get_votes_path())


async def save_votes(data: Dict[str, Any]) -> None:
    async with _VOTES_LOCK:
        await _write_json(get_votes_path(), data)


def _empty_days() -> Dict[str, list]:
    unieke_dagen = {opt.dag for opt in get_poll_options()}
    return {dag: [] for dag in unieke_dagen}


async def get_user_votes(user_id: str) -> Dict[str, list]:
    votes = await load_votes()
    return votes.get(str(user_id), _empty_days())


async def add_vote(user_id: str, dag: str, tijd: str) -> None:
    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in add_vote: {dag}, {tijd}")
        return
    user_id = str(user_id)
    votes = await load_votes()
    if user_id not in votes:
        votes[user_id] = _empty_days()
    if tijd not in votes[user_id].get(dag, []):
        votes[user_id][dag].append(tijd)
    await save_votes(votes)


async def toggle_vote(user_id: str, dag: str, tijd: str) -> list:
    votes = await load_votes()
    user = votes.setdefault(user_id, _empty_days())
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
    await save_votes(votes)
    return day_votes


async def remove_vote(user_id: str, dag: str, tijd: str) -> None:
    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in remove_vote: {dag}, {tijd}")
        return
    user_id = str(user_id)
    votes = await load_votes()
    if user_id in votes and tijd in votes[user_id].get(dag, []):
        votes[user_id][dag].remove(tijd)
        await save_votes(votes)


async def get_counts_for_day(dag: str) -> Dict[str, int]:
    """Telt in 1 keer alle opties van deze dag (minder I/O)."""
    votes = await load_votes()
    counts: Dict[str, int] = {}
    for o in get_poll_options():
        if o.dag != dag:
            continue
        c = 0
        for per_user in votes.values():
            tijden = per_user.get(dag, [])
            if isinstance(tijden, list) and o.tijd in tijden:
                c += 1
        counts[o.tijd] = c
    return counts


async def get_votes_for_option(dag: str, tijd: str) -> int:
    # optioneel, maar we gebruiken liever get_counts_for_day in 1 I/O
    counts = await get_counts_for_day(dag)
    return counts.get(tijd, 0)


async def reset_votes() -> None:
    await save_votes({})


# === GASTEN ===============================================================


def _sanitize_guest_name(name: str) -> str:
    # trim + simpele sanitisatie: vervang scheidingstekens door spatie, collapse spaces
    raw = (
        name.strip()
        .replace("_", " ")
        .replace("|", " ")
        .replace(";", " ")
        .replace(",", " ")
    )
    # alleen zichtbare chars, kort houden
    cleaned = " ".join(raw.split())
    return cleaned[:40] if cleaned else "Gast"


def _guest_id(owner_user_id: int | str, guest_name: str) -> str:
    return f"{owner_user_id}_guest::{guest_name}"


async def add_guest_votes(
    owner_user_id: int | str, dag: str, tijd: str, namen: list[str]
) -> tuple[list[str], list[str]]:
    """
    Maakt voor elke gastnaam een eigen 'virtuele user' key aan en zet daar de stem.
    Return: (toegevoegd, overgeslagen)
    - overgeslagen als die exacte gastnaam al bestond voor die eigenaar en dag/tijd.
    """
    from apps.entities.poll_option import is_valid_option

    if not is_valid_option(dag, tijd):
        return ([], namen or [])

    # normaliseer en filter lege
    norm = []
    for n in namen or []:
        s = _sanitize_guest_name(n)
        if s:
            norm.append(s)

    votes = await load_votes()
    toegevoegd, overgeslagen = [], []

    for naam in norm:
        gid = _guest_id(owner_user_id, naam)
        per_dag = votes.get(gid, {})
        bestaande = per_dag.get(dag, [])

        if tijd in bestaande:
            overgeslagen.append(naam)
            continue

        nieuw = set(bestaande)
        nieuw.add(tijd)
        per_dag[dag] = sorted(nieuw)
        votes[gid] = per_dag
        toegevoegd.append(naam)

    await save_votes(votes)
    return (toegevoegd, overgeslagen)


async def remove_guest_votes(
    owner_id: int, dag: str, tijd: str, namen: list[str]
) -> tuple[list[str], list[str]]:
    """
    Verwijder gaststemmen voor een bepaalde owner, dag en tijd.
    :param owner_id: Discord user ID van de eigenaar
    :param dag: bv. 'vrijdag'
    :param tijd: bv. 'om 20:30 uur'
    :param namen: lijst van gastnamen die verwijderd moeten worden
    :return: (verwijderd, nietgevonden)
    """
    votes = await load_votes()
    verwijderd, nietgevonden = [], []

    for naam in namen:
        key = f"{owner_id}_guest::{naam}"
        if key in votes and tijd in votes[key].get(dag, []):
            # haal tijd uit de stemmenlijst van deze gast
            try:
                votes[key][dag].remove(tijd)
                verwijderd.append(naam)
            except ValueError:
                nietgevonden.append(naam)

            # als gast helemaal leeg is → opschonen
            if not votes[key][dag]:
                del votes[key][dag]
            if not votes[key]:
                del votes[key]
        else:
            nietgevonden.append(naam)

    await save_votes(votes)
    return verwijderd, nietgevonden
