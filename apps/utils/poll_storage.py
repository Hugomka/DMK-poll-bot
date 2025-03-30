import json
import os

VOTES_FILE = "votes.json"

def load_votes():
    if not os.path.exists(VOTES_FILE):
        return {}
    with open(VOTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_votes(data):
    with open(VOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_vote(user_id, dag, tijd):
    votes = load_votes()
    user_id = str(user_id)

    if user_id not in votes:
        votes[user_id] = {"vrijdag": [], "zaterdag": [], "zondag": [], "misschien": [], "niet": []}

    if tijd not in votes[user_id].get(dag, []):
        votes[user_id][dag].append(tijd)

    save_votes(votes)

def remove_vote(user_id, dag, tijd):
    votes = load_votes()
    user_id = str(user_id)

    if user_id in votes and tijd in votes[user_id].get(dag, []):
        votes[user_id][dag].remove(tijd)
        save_votes(votes)

def get_votes_for_option(dag, tijd):
    votes = load_votes()
    count = 0
    for user_data in votes.values():
        if tijd in user_data.get(dag, []):
            count += 1
    return count

def get_user_votes(user_id):
    votes = load_votes()
    return votes.get(str(user_id), {"vrijdag": [], "zaterdag": [], "zondag": [], "misschien": [], "niet": []})

def reset_votes():
    with open(VOTES_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)
