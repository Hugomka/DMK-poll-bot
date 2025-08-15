# apps\utils\poll_storage.py

import json, os
from apps.entities.poll_option import get_poll_options, is_valid_option

VOTES_FILE = "votes.json"
SPECIALS = {"misschien", "niet meedoen"}

def load_votes():
    if not os.path.exists(VOTES_FILE):
        return {}
    try:
        with open(VOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ votes.json is corrupt. Ik zet 'm terug naar leeg {}.")
        return {}

def save_votes(data):
    with open(VOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _empty_days():
    unieke_dagen = {opt.dag for opt in get_poll_options()}
    return {dag: [] for dag in unieke_dagen}

def get_user_votes(user_id):
    votes = load_votes()
    return votes.get(str(user_id), _empty_days())

def add_vote(user_id, dag, tijd):
    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in add_vote: {dag}, {tijd}")
        return
    user_id = str(user_id)
    votes = load_votes()
    if user_id not in votes:
        votes[user_id] = _empty_days()
    if tijd not in votes[user_id].get(dag, []):
        votes[user_id][dag].append(tijd)
    save_votes(votes)

def toggle_vote(user_id: str, dag: str, tijd: str):
    votes = load_votes()
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
    save_votes(votes)
    return day_votes

def remove_vote(user_id, dag, tijd):
    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in remove_vote: {dag}, {tijd}")
        return
    user_id = str(user_id)
    votes = load_votes()
    if user_id in votes and tijd in votes[user_id].get(dag, []):
        votes[user_id][dag].remove(tijd)
        save_votes(votes)

def get_votes_for_option(dag, tijd):
    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in get_votes_for_option: {dag}, {tijd}")
        return 0
    votes = load_votes()
    count = 0
    for v in votes.values():
        tijden = v.get(dag)
        if isinstance(tijden, list) and tijd in tijden:
            count += 1
    return count

def reset_votes():
    save_votes({})
