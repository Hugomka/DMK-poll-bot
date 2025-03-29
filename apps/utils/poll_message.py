import json
import os

MESSAGE_FILE = "poll_message.json"

def save_message_id(channel_id, message_id):
    data = {}
    if os.path.exists(MESSAGE_FILE):
        with open(MESSAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[str(channel_id)] = message_id
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_message_id(channel_id):
    if not os.path.exists(MESSAGE_FILE):
        return None
    with open(MESSAGE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get(str(channel_id))
