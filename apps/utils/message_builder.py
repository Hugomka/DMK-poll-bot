# apps/utils/message_builder.py

from typing import Any

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
    title = f"**DMK-poll voor {dag.capitalize()}:**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n"

    # Filter opties voor deze dag
    opties = [o for o in get_poll_options() if o.dag == dag]
    if not opties:
        message += "_(geen opties gevonden)_"
        return message

    # Aantallen per tijd (scoped), tenzij verborgen
    counts = {} if hide_counts else await get_counts_for_day(dag, guild_id, channel_id)

    for opt in opties:
        # Filter "misschien" uit resultaten wanneer counts verborgen zijn
        # (toont toch alleen "(stemmen verborgen)", geen meerwaarde)
        if hide_counts and opt.tijd == "misschien":
            continue

        label = f"{opt.emoji} {opt.tijd}"

        if hide_counts:
            message += f"{label} (stemmen verborgen)\n"
        else:
            n = int(counts.get(opt.tijd, 0))
            message += f"{label} ({n} stemmen)\n"

    return f"{message}\u200b"


# Helper: groepeer leden en gasten (voor status + toggle)
async def build_grouped_names_for(
    dag: str, tijd: str, guild: discord.Guild | None, all_votes: dict
) -> tuple[int, str]:
    """
    Retourneert (totaal_stemmen, tekst) waarbij tekst bv. is:
      @Owner (@Owner: Bowser, Wario), @AndereOwner, (@NogIemand: GastA)

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
                            # Gebruik displaynaam in plaats van mention
                            display = (
                                getattr(owner_member, "display_name", None)
                                or getattr(owner_member, "global_name", None)
                                or getattr(owner_member, "name", "Lid")
                            )
                            mention = f"@{display}"
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
                            # Gebruik displaynaam in plaats van mention
                            display = (
                                getattr(member, "display_name", None)
                                or getattr(member, "global_name", None)
                                or getattr(member, "name", "Lid")
                            )
                            mention = f"@{display}"
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


async def build_doorgaan_participant_list(
    dag: str,
    tijd: str,
    guild: discord.Guild | None,
    all_votes: dict,
    channel_member_ids: dict[str, Any],
) -> tuple[int, str, str]:
    """
    Bouw een deelnemerslijst voor de doorgaan-notificatie.

    Retourneert (totaal_deelnemers, mentions_str, participant_list) waarbij:
    - totaal_deelnemers: aantal stemmen (leden + gasten)
    - mentions_str: spatie-gescheiden Discord mentions voor leden (voor notificatie)
    - participant_list: geformatteerde lijst zoals "@Naam1, @Naam2, Naam3 (gast), @Naam4"

    Regels:
    - Leden krijgen een ping (@mention) in beide strings
    - Gasten krijgen geen ping, worden getoond als "Naam (gast)"
    - Gasten worden getoond ook als hun host afwezig is
    """
    if not all_votes:
        return 0, "", ""

    # Verzamel alle deelnemers (members + guests)
    participants: list[dict] = []

    # Track owner IDs voor gastenkoppeling
    owner_guests: dict[str, list[str]] = {}

    for raw_id, user_votes in all_votes.items():
        try:
            tijden = user_votes.get(dag, [])
            if not isinstance(tijden, list) or tijd not in tijden:
                continue

            # Gast-key: "<ownerId>_guest::<gastnaam>"
            if isinstance(raw_id, str) and "_guest::" in raw_id:
                owner_id, guest_name = raw_id.split("_guest::", 1)
                guest_name = (guest_name or "Gast").strip()

                # Verzamel gasten per owner
                if owner_id not in owner_guests:
                    owner_guests[owner_id] = []
                owner_guests[owner_id].append(guest_name)

            else:
                # Normale stemmer (lid)
                member = None
                mention = None
                display_name = "Lid"

                if guild:
                    try:
                        member = channel_member_ids.get(
                            str(raw_id)
                        ) or guild.get_member(int(raw_id))
                        if not member:
                            member = await guild.fetch_member(int(raw_id))

                        if member:
                            display_name = (
                                getattr(member, "display_name", None)
                                or getattr(member, "global_name", None)
                                or getattr(member, "name", "Lid")
                            )
                            mention = getattr(member, "mention", None)
                    except Exception:
                        pass

                participants.append(
                    {
                        "type": "member",
                        "id": str(raw_id),
                        "display_name": display_name,
                        "mention": mention,
                    }
                )

        except Exception:
            # Onbekende of niet-parsbare id; negeren
            continue

    # Voeg alle gasten toe aan de deelnemerslijst
    for owner_id, guests in owner_guests.items():
        for guest_name in guests:
            participants.append(
                {"type": "guest", "id": owner_id, "guest_name": guest_name}
            )

    # Totaal aantal deelnemers
    totaal = len(participants)

    # Bouw mentions_str (alleen voor leden met toegang tot channel)
    mentions: list[str] = []
    for p in participants:
        if p["type"] == "member" and p.get("mention"):
            mentions.append(p["mention"])

    mentions_str = " ".join(mentions) if mentions else ""

    # Bouw participant_list
    participant_parts: list[str] = []
    for p in participants:
        if p["type"] == "member":
            # Gebruik mention als beschikbaar, anders display_name met @
            if p.get("mention"):
                participant_parts.append(p["mention"])
            else:
                participant_parts.append(f"@{p['display_name']}")
        else:
            # Gast: "Naam (gast)"
            participant_parts.append(f"{p['guest_name']} (gast)")

    participant_list = ", ".join(participant_parts) if participant_parts else ""

    return totaal, mentions_str, participant_list


async def get_non_voters_for_day(
    dag: str,
    guild: discord.Guild | None,
    channel: Any,
    all_votes: dict,
) -> tuple[int, str]:
    """
    Retourneert (aantal_niet_stemmers, tekst) voor een specifieke dag.

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - guild: Discord guild (server)
    - channel: Discord channel (voor toegang tot members)
    - all_votes: Dictionary met alle stemmen (van load_votes)

    Retourneert:
    - (count, text) waarbij text bv. is: "@Naam1, @Naam2, @Naam3"

    Regels:
    - Alleen leden die toegang hebben tot het kanaal worden meegenomen
    - Bots worden uitgefilterd
    - Gasten worden via hun owner-ID gekoppeld
    - Als een lid (of gast van dat lid) heeft gestemd, wordt het lid niet als niet-stemmer getoond
    """
    if not channel or not guild:
        return 0, ""

    # Verzamel IDs die voor deze dag hebben gestemd (inclusief gasten via hun owner)
    voted_ids: set[str] = set()
    for uid, per_dag in all_votes.items():
        try:
            tijden = (per_dag or {}).get(dag, [])
            if isinstance(tijden, list) and tijden:
                # Extract owner ID (handle guests)
                actual_uid = (
                    uid.split("_guest::", 1)[0]
                    if isinstance(uid, str) and "_guest::" in uid
                    else uid
                )
                voted_ids.add(str(actual_uid))
        except Exception:  # pragma: no cover
            continue

    # Alleen leden die toegang hebben tot dit specifieke kanaal
    members = getattr(channel, "members", [])
    non_voters: list[str] = []

    for member in members:
        # Skip bots
        if getattr(member, "bot", False):
            continue

        # Check of dit lid heeft gestemd
        member_id = str(getattr(member, "id", ""))
        if member_id not in voted_ids:
            # Gebruik displaynaam in plaats van mention (consistent met build_grouped_names_for)
            display = (
                getattr(member, "display_name", None)
                or getattr(member, "global_name", None)
                or getattr(member, "name", "Lid")
            )
            non_voters.append(f"@{display}")

    count = len(non_voters)
    text = ", ".join(non_voters) if non_voters else ""

    return count, text
