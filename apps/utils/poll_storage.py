# apps\utils\poll_storage.py

import json, os, asyncio
from typing import Dict, Any
from apps.entities.poll_option import get_poll_options, is_valid_option

VOTES_FILE = "votes.json"
SPECIALS = {"misschien", "niet meedoen"}

# 1 lock voor veilig schrijven/lezen
_VOTES_LOCK = asyncio.Lock()

async def _read_json(path: str) -> Dict[str, Any]:
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
    def _write():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    await asyncio.to_thread(_write)

# Publiek async API
async def load_votes() -> Dict[str, Any]:
    async with _VOTES_LOCK:
        return await _read_json(VOTES_FILE)

async def save_votes(data: Dict[str, Any]) -> None:
    async with _VOTES_LOCK:
        await _write_json(VOTES_FILE, data)

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
