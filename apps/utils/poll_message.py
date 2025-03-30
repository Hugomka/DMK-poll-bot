import json
import os
import discord
from apps.utils.message_builder import build_poll_message

POLL_MESSAGE_FILE = "poll_message.json"

def save_message_id(channel_id, message_id):
    file_path = POLL_MESSAGE_FILE
    data = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Bestand is corrupt. Nieuw bestand wordt aangemaakt.")
                data = {}
    if "message_id_per_channel" not in data:
        data["message_id_per_channel"] = {}
    data["message_id_per_channel"][str(channel_id)] = message_id
    with open(file_path, 'w', encoding='utf-8') as f:
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

async def update_poll_message(channel, user_id=None):
    message_id = get_message_id(channel.id)
    if message_id:
        try:
            from apps.ui.poll_buttons import PollButtonView
            message = await channel.fetch_message(message_id)
            content = build_poll_message()
            view = PollButtonView(user_id) if user_id else None
            await message.edit(content=content, view=view)
        except discord.NotFound:
            clear_message_id(channel.id)
        except Exception as e:
            print(f"❌ Fout bij updaten van pollbericht: {e}")
    else:
        print("ℹ️ Geen bestaand pollbericht om te updaten.")