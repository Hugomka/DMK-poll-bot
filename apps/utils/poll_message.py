import json
import os
import discord
from discord import Embed
from datetime import datetime, timezone

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

async def update_poll_message(channel):
    message_id = get_message_id(channel.id)
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=build_poll_embed())
        except discord.NotFound:
            print(f"⚠️ Pollbericht niet gevonden voor channel {channel.id}, ID {message_id}. Verwijder ID.")
            clear_message_id(channel.id)  # Verwijder fout ID uit JSON
        except Exception as e:
            print(f"❌ Fout bij updaten van pollbericht: {e}")
    else:
        print("ℹ️ Geen bestaand pollbericht om te updaten.")

def build_poll_embed(votes: dict) -> Embed:
    embed = Embed(
        title="🗳️ DMK-poll deze week",
        description="Stem op de tijden waarop je beschikbaar bent voor DMK 16 races!",
        color=0x00AAFF,
        timestamp=datetime.now(timezone.utc)
    )

    for dag in ["vrijdag", "zaterdag", "zondag"]:
        stemmen_1900 = sum(1 for v in votes.values() if dag in v and "19:00" in v[dag])
        stemmen_2030 = sum(1 for v in votes.values() if dag in v and "20:30" in v[dag])
        embed.add_field(
            name=f"📅 {dag.capitalize()}",
            value=f"🕖 19:00 uur — **{stemmen_1900} stemmen**\n🕤 20:30 uur — **{stemmen_2030} stemmen**",
            inline=False
        )

    embed.set_footer(text="Laatste update")
    return embed