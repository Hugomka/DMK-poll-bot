import json
import os

VOTE_FILE = "votes.json"

def load_votes():
    if not os.path.exists(VOTE_FILE):
        return {}
    with open(VOTE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_votes(data):
    with open(VOTE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_vote(user_id, dag, tijd):
    votes = load_votes()
    user_id = str(user_id)

    if user_id not in votes:
        votes[user_id] = {"vrijdag": [], "zaterdag": [], "zondag": []}

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
    return votes.get(str(user_id), {"vrijdag": [], "zaterdag": [], "zondag": []})
