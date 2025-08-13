import datetime
import discord
import json
import os
import pytz
from apps.entities.poll_option import POLL_OPTIONS
from apps.utils.message_builder import build_poll_message_for_day
from apps.utils.poll_settings import should_hide_counts

POLL_MESSAGE_FILE = "poll_message.json"

def _load_data():
    if os.path.exists(POLL_MESSAGE_FILE):
        with open(POLL_MESSAGE_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Bestand is corrupt. Nieuw bestand wordt aangemaakt.")
    return {}

def _save_data(data):
    with open(POLL_MESSAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def save_message_id(channel_id, dag, message_id):
    """
    Sla per kanaal en per dag het bericht‑ID op.
    """
    data = _load_data()
    channel_str = str(channel_id)
    data.setdefault("message_id_per_channel", {}).setdefault(channel_str, {})[dag] = message_id
    _save_data(data)

def get_message_id(channel_id, dag):
    """
    Haal het bericht‑ID op voor een kanaal en een specifieke dag.
    """
    data = _load_data()
    return (
        data.get("message_id_per_channel", {})
            .get(str(channel_id), {})
            .get(dag)
    )

def clear_message_id(channel_id, dag=None):
    """
    Verwijder het bericht‑ID. Als 'dag' None is, worden alle dagen voor dit kanaal verwijderd.
    """
    data = _load_data()
    channel_str = str(channel_id)
    if "message_id_per_channel" in data and channel_str in data["message_id_per_channel"]:
        if dag:
            data["message_id_per_channel"][channel_str].pop(dag, None)
        else:
            data["message_id_per_channel"].pop(channel_str, None)
        _save_data(data)

async def update_poll_message(channel, dag, user_id=None):
    """
    Werk het pollbericht voor een specifieke dag bij.
    """
    message_id = get_message_id(channel.id, dag)
    if not message_id:
        print(f"ℹ️ Geen pollbericht gevonden voor {dag}.")
        return

    try:
        message = await channel.fetch_message(message_id)

        from apps.ui.poll_buttons import PollButtonView

        # bepaal of aantallen verborgen moeten blijven
        now = datetime.datetime.now(pytz.timezone("Europe/Amsterdam"))
        hide_counts = should_hide_counts(channel.id, dag, now)

        # bouw de tekst op met of zonder aantal stemmen
        content = build_poll_message_for_day(dag, hide_counts=hide_counts)
        view = PollButtonView(dag, user_id) if user_id else PollButtonView(dag)

        await message.edit(content=content, view=view)
    except discord.NotFound:
        # Bericht bestaat niet meer → verwijder ID
        clear_message_id(channel.id, dag)
    except Exception as e:
        print(f"❌ Fout bij updaten van pollbericht voor {dag}: {e}")
