import json
import os

POLL_MESSAGE_FILE = "poll_message.json"

def save_message_id(channel_id, message_id):
    data = {}
    if os.path.exists(POLL_MESSAGE_FILE):
        with open(POLL_MESSAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[str(channel_id)] = message_id
    with open(POLL_MESSAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_message_id(channel_id):
    if os.path.exists(POLL_MESSAGE_FILE):
        with open(POLL_MESSAGE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("message_id_per_channel", {}).get(str(channel_id))
    return None

def clear_message_id(channel_id):
    if os.path.exists(POLL_MESSAGE_FILE):
        with open(POLL_MESSAGE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}

    data["message_id_per_channel"] = data.get("message_id_per_channel", {})
    data["message_id_per_channel"].pop(str(channel_id), None)

    with open(POLL_MESSAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)