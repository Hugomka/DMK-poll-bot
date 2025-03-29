import discord
from discord import Embed
from datetime import datetime, timezone
from apps.utils.poll_storage import get_votes_for_option
from apps.utils.poll_message import get_message_id, clear_message_id

def build_poll_message():
    dagen = ["vrijdag", "zaterdag", "zondag"]
    tijden = ["19:00", "20:30"]
    message = "**DMK-poll deze week**\n\n"

    for dag in dagen:
        count_19 = get_votes_for_option(dag, "19:00")
        count_20 = get_votes_for_option(dag, "20:30")

        doorgaat = None
        if count_19 >= 6 or count_20 >= 6:
            # Bepaal welke tijd doorgaat
            if count_20 >= count_19:
                doorgaat = "20:30"
            else:
                doorgaat = "19:00"

        message += f"{dag.capitalize()}:\n"
        for tijd in tijden:
            count = get_votes_for_option(dag, tijd)
            markering = " → Gaat door!" if tijd == doorgaat else ""
            message += f"- {tijd} uur ({count} stemmen){markering}\n"
        message += "\n"

    return message

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