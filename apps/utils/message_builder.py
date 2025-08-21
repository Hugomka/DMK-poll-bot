# apps/utils/message_builder.py

import discord
from apps.entities.poll_option import get_poll_options
from apps.utils.poll_storage import get_counts_for_day, load_votes
from apps.utils.poll_settings import is_name_display_enabled

async def build_poll_message_for_day_async(
    dag: str,
    hide_counts: bool = False,
    pauze: bool = False,
    guild: discord.Guild | None = None
) -> str:
    title = f"**DMK-poll voor {dag.capitalize()}**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n\n"

    opties = [o for o in get_poll_options() if o.dag == dag]

    if not opties:
        message += "_(geen opties gevonden)_"
        return message

    counts = {} if hide_counts else await get_counts_for_day(dag)

    for option in opties:
        if hide_counts:
            message += f"{option.label} (stemmen verborgen)\n"
        else:
            n = counts.get(option.tijd, 0)
            regel = f"{option.label} ({n} stemmen)"
            message += regel + "\n"

    return message

# --- Helper: groepeer leden en gasten (voor status + toggle) ---
async def build_grouped_names_for(dag: str, tijd: str, guild: discord.Guild, all_votes: dict) -> tuple[int, str]:
    """
    Retourneert (totaal_stemmen, tekst) waarbij tekst er zo uitziet:
    @Owner (@Owner: Gast1, Gast2), @AndereOwner, (@NogIemand: GastA)
    - @Owner alleen als eigenaar zelf stemt
    - ( @Owner: ... ) als alleen gasten van die eigenaar stemmen
    """
    groepen: dict[str, dict] = {}
    for raw_id, user_votes in all_votes.items():
        if tijd not in user_votes.get(dag, []):
            continue
        try:
            if "_guest::" in raw_id:
                owner_id, guest_name = raw_id.split("_guest::", 1)
                owner_member = guild.get_member(int(owner_id)) or await guild.fetch_member(int(owner_id))
                key = owner_id
                g = groepen.setdefault(key, {"voted": False, "guests": [], "mention": owner_member.mention if owner_member else "Gast"})
                g["guests"].append((guest_name or "Gast").strip())
            else:
                member = guild.get_member(int(raw_id)) or await guild.fetch_member(int(raw_id))
                if member:
                    key = raw_id
                    g = groepen.setdefault(key, {"voted": False, "guests": [], "mention": member.mention})
                    g["voted"] = True
        except Exception:
            # onbekende of vertrokken leden negeren
            pass

    totaal = sum(1 for g in groepen.values() if g["voted"]) + sum(len(g["guests"]) for g in groepen.values())

    def fmt(g):
        if g["guests"] and g["voted"]:
            # @Owner (@Owner: a, b)
            return f"{g['mention']} ({g['mention']}: {', '.join(g['guests'])})"
        elif g["guests"]:
            # (@Owner: a, b)
            return f"({g['mention']}: {', '.join(g['guests'])})"
        else:
            # @Owner
            return f"{g['mention']}"

    tekst = ", ".join(fmt(g) for g in groepen.values() if (g["voted"] or g["guests"]))
    return totaal, tekst

