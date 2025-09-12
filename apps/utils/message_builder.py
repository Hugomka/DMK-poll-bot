# apps/utils/message_builder.py

import discord

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_storage import get_counts_for_day


async def build_poll_message_for_day_async(
    dag: str,
    guild_id: int | str,
    channel_id: int | str,
    hide_counts: bool = True,
    pauze: bool = False,
    guild: discord.Guild | None = None,
) -> str:
    """
    Bouwt de tekst van het pollbericht voor één dag, GESCOPED per guild+channel.

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - guild_id: Discord guild ID (server)
    - channel_id: Discord channel ID (tekstkanaal)
    - hide_counts: verberg aantallen (True/False)
    - pauze: voeg marker toe in de titel
    - guild: optioneel, voor mentions in andere helpers
    """
    title = f"**DMK-poll voor {dag.capitalize()}**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n\n"

    # Filter opties voor deze dag
    opties = [o for o in get_poll_options() if o.dag == dag]
    if not opties:
        message += "_(geen opties gevonden)_"
        return message

    # Aantallen per tijd (scoped), tenzij verborgen
    counts = {} if hide_counts else await get_counts_for_day(dag, guild_id, channel_id)

    for opt in opties:
        label = f"{opt.emoji} {opt.tijd}"

        if hide_counts:
            message += f"{label} (stemmen verborgen)\n"
        else:
            n = int(counts.get(opt.tijd, 0))
            message += f"{label} ({n} stemmen)\n"

    return message


# Helper: groepeer leden en gasten (voor status + toggle)
async def build_grouped_names_for(
    dag: str, tijd: str, guild: discord.Guild | None, all_votes: dict
) -> tuple[int, str]:
    """
    Retourneert (totaal_stemmen, tekst) waarbij tekst bv. is:
      @Owner (@Owner: Gast1, Gast2), @AndereOwner, (@NogIemand: GastA)

    Regels:
    - @Owner alleen als eigenaar zelf stemt
    - (@Owner: ...) als alleen gasten van die eigenaar stemmen
    - Als 'guild' None is of members niet gevonden worden, worden mentions overgeslagen waar nodig.
    """
    if not all_votes:
        return 0, ""

    groepen: dict[str, dict] = {}

    for raw_id, user_votes in all_votes.items():
        try:
            tijden = user_votes.get(dag, [])
            if not isinstance(tijden, list) or tijd not in tijden:
                continue

            # Gast-key: "<ownerId>_guest::<gastnaam>"
            if isinstance(raw_id, str) and "_guest::" in raw_id:
                owner_id, guest_name = raw_id.split("_guest::", 1)
                guest_name = (guest_name or "Gast").strip()

                mention = "Gast"
                if guild:
                    try:
                        owner_member = guild.get_member(
                            int(owner_id)
                        ) or await guild.fetch_member(int(owner_id))
                        if owner_member:
                            mention = owner_member.mention
                    except Exception:
                        pass

                g = groepen.setdefault(
                    owner_id, {"voted": False, "guests": [], "mention": mention}
                )
                g["guests"].append(guest_name)

            else:
                # Normale stemmer (lid)
                mention = None
                if guild:
                    try:
                        member = guild.get_member(
                            int(raw_id)
                        ) or await guild.fetch_member(int(raw_id))
                        if member:
                            mention = member.mention
                    except Exception:
                        pass

                key = str(raw_id)
                g = groepen.setdefault(
                    key, {"voted": False, "guests": [], "mention": mention or "Lid"}
                )
                g["voted"] = True

        except Exception:
            # Onbekende of niet-parsbare id; negeren
            continue

    # Totaal = leden die stemden + alle gasten
    totaal = sum(1 for g in groepen.values() if g["voted"]) + sum(
        len(g["guests"]) for g in groepen.values()
    )

    def fmt(g: dict) -> str:
        mention = g.get("mention") or "Lid"
        guests = g.get("guests") or []
        voted = bool(g.get("voted"))

        if guests and voted:
            # @Owner (@Owner: a, b)
            return f"{mention} ({mention}: {', '.join(guests)})"
        elif guests:
            # (@Owner: a, b)
            return f"({mention}: {', '.join(guests)})"
        else:
            # @Owner
            return f"{mention}"

    tekst = ", ".join(
        fmt(g) for g in groepen.values() if g.get("voted") or g.get("guests")
    )

    return totaal, tekst
