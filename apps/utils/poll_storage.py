import json
import os
from apps.entities.poll_option import POLL_OPTIONS

VOTES_FILE = "votes.json"
SPECIALS = {"misschien", "niet meedoen"}

def load_votes():
    if not os.path.exists(VOTES_FILE):
        return {}
    with open(VOTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_votes(data):
    with open(VOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_user_votes(user_id):
    votes = load_votes()
    unieke_dagen = {opt.dag for opt in POLL_OPTIONS}
    return votes.get(str(user_id), {dag: [] for dag in unieke_dagen})

def add_vote(user_id, dag, tijd):
    user_id = str(user_id)
    votes = load_votes()

    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in add_vote: {dag}, {tijd}")
        return

    if user_id not in votes:
        votes[user_id] = {opt.dag: [] for opt in POLL_OPTIONS}

    if tijd not in votes[user_id].get(dag, []):
        votes[user_id][dag].append(tijd)

    save_votes(votes)

def toggle_vote(user_id: str, dag: str, tijd: str):
    votes = load_votes()
    user = votes.setdefault(user_id, {})
    day_votes = user.setdefault(dag, [])

    # Validatie: bestaand optie?
    if not is_valid_option(dag, tijd):
        return day_votes  # negeer ongeldige input

    if tijd in SPECIALS:
        # Klik op 'misschien' of 'niet meedoen'
        if tijd in day_votes and all(v in SPECIALS for v in day_votes):
            # stond al aan, en er stond geen tijd → zet uit
            day_votes = [v for v in day_votes if v != tijd]
        else:
            # zet exclusief deze special aan → alle tijden en andere special uit
            day_votes = [tijd]
    else:
        # Klik op een tijdoptie (bijv. 'om 19:00 uur' / 'om 20:30 uur')
        # specials altijd uit bij tijdstem
        day_votes = [v for v in day_votes if v not in SPECIALS]
        if tijd in day_votes:
            # toggle uit
            day_votes = [v for v in day_votes if v != tijd]
        else:
            # toggle aan (meerdere tijden mogen)
            day_votes.append(tijd)

    user[dag] = day_votes
    save_votes(votes)
    return day_votes

def remove_vote(user_id, dag, tijd):
    user_id = str(user_id)
    votes = load_votes()

    if not is_valid_option(dag, tijd):
        print(f"⚠️ Ongeldige combinatie in remove_vote: {dag}, {tijd}")
        return

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

def is_valid_option(dag, tijd):
    return any(opt.dag == dag and opt.tijd == tijd for opt in POLL_OPTIONS)
