# apps/utils/message_builder.py

from datetime import datetime, timedelta
from typing import Any

import discord
import pytz

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_settings import get_setting
from apps.utils.poll_storage import (
    get_counts_for_day,
    load_votes,
)
from apps.utils.poll_storage import (
    get_non_voters_for_day as get_non_voters_from_storage,
)
from apps.utils.time_zone_helper import TimeZoneHelper


def get_rolling_window_days(dag_als_vandaag: str | None = None) -> list[dict[str, Any]]:
    """
    Bereken rolling window van 7 dagen: 1 dag terug + vandaag + 5 dagen vooruit.

    Args:
        dag_als_vandaag: Optioneel, welke dag als "vandaag" beschouwen (bijv. "dinsdag").
                        Als None, gebruik echte vandaag.

    Returns:
        List van dicts met keys: 'dag' (naam), 'datum' (datetime object), 'is_past', 'is_today', 'is_future'

    Voorbeeld op maandag 1 december:
        - 1 terug: zondag 30 nov
        - vandaag: maandag 1 dec
        - 5 vooruit: dinsdag 2 dec, woensdag 3 dec, donderdag 4 dec, vrijdag 5 dec, zaterdag 6 dec
    """
    from apps.utils.constants import DAG_MAPPING, DAG_NAMEN

    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # Bepaal "vandaag" datum
    if dag_als_vandaag:
        target_weekday = DAG_MAPPING.get(dag_als_vandaag.lower())
        if target_weekday is None:
            # Fallback naar echte vandaag
            today = now
        else:
            # Bereken de volgende occurrence van deze dag (of vandaag als het die dag is)
            days_diff = (target_weekday - now.weekday()) % 7
            if days_diff == 0:
                # Vandaag is al die dag
                today = now
            else:
                # Ga vooruit naar die dag
                today = now + timedelta(days=days_diff)
    else:
        today = now

    # Bereken window: -1 dag tot +5 dagen
    window = []
    for offset in range(-1, 6):  # -1, 0, 1, 2, 3, 4, 5
        datum = today + timedelta(days=offset)
        weekday = datum.weekday()
        dag_naam = DAG_NAMEN[weekday]

        window.append({
            "dag": dag_naam,
            "datum": datum,
            "is_past": offset < 0,
            "is_today": offset == 0,
            "is_future": offset > 0,
        })

    return window


def _get_weekday_date_for_rolling_window(dag: str, dag_als_vandaag: str | None = None) -> str:
    """
    Bereken datum voor een specifieke dag binnen de rolling window in YYYY-MM-DD formaat.

    Args:
        dag: De weekdag naam (bijv. "vrijdag")
        dag_als_vandaag: Optioneel, welke dag als "vandaag" beschouwen

    Returns:
        ISO datum string (YYYY-MM-DD) of lege string bij fout
    """
    window = get_rolling_window_days(dag_als_vandaag)

    for day_info in window:
        if day_info["dag"] == dag.lower():
            return day_info["datum"].strftime("%Y-%m-%d")

    # Niet gevonden in window (zou niet moeten gebeuren)
    return ""


def _get_next_weekday_date(dag: str) -> str:
    """
    Bereken datum voor elke dag van de week van de huidige poll-periode in DD-MM formaat.

    De poll-periode loopt van dinsdag 20:00 tot de volgende dinsdag 20:00.
    Datums blijven stabiel gedurende de hele periode en updaten alleen na dinsdag 20:00.

    Dit zorgt ervoor dat de datums consistent blijven, ongeacht bot-restarts of andere events.
    """
    from apps.utils.constants import DAG_MAPPING

    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz)

    target_weekday = DAG_MAPPING.get(dag.lower())
    if target_weekday is None:
        return ""

    # Bereken de laatste dinsdag 20:00 (start van huidige poll-periode)
    days_since_tuesday = (now.weekday() - 1) % 7  # 1 = dinsdag
    last_tuesday = (now - timedelta(days=days_since_tuesday)).replace(
        hour=20, minute=0, second=0, microsecond=0
    )

    # Als we nog niet voorbij dinsdag 20:00 zijn, gebruik de dinsdag van vorige week
    if now < last_tuesday:
        last_tuesday -= timedelta(days=7)

    # Bereken de doeldag vanaf de laatste dinsdag 20:00
    days_ahead = (target_weekday - last_tuesday.weekday()) % 7

    # Als days_ahead 0 is, betekent dit dinsdag → vrijdag/zaterdag/zondag dezelfde week
    if days_ahead == 0:
        days_ahead = 7

    target_date = last_tuesday + timedelta(days=days_ahead)

    return target_date.strftime("%d-%m")


async def build_poll_message_for_day_async(
    dag: str,
    guild_id: int | str,
    channel_id: int | str,
    hide_counts: bool = True,
    hide_ghosts: bool = False,
    pauze: bool = False,
    guild: discord.Guild | None = None,
    channel: Any = None,
    datum_iso: str | None = None,
) -> str:
    """
    Bouwt de tekst van het pollbericht voor één dag, GESCOPED per guild+channel.

    Parameters:
    - dag: 'maandag' | 'dinsdag' | 'woensdag' | 'donderdag' | 'vrijdag' | 'zaterdag' | 'zondag'
    - guild_id: Discord guild ID (server)
    - channel_id: Discord channel ID (tekstkanaal)
    - hide_counts: verberg stemaantallen (True/False)
    - hide_ghosts: verberg niet-gestemd aantallen (True/False)
    - pauze: voeg marker toe in de titel
    - guild: optioneel, voor mentions in andere helpers
    - channel: optioneel, voor niet-stemmers tracking
    - datum_iso: optioneel, YYYY-MM-DD datum (voor rolling window). Als None, gebruik oude logica.
    """
    # Genereer Hammertime voor de datum (18:00 = deadline tijd)
    if datum_iso is None:
        # Fallback: gebruik rolling window om correcte datum te krijgen
        dagen_info = get_rolling_window_days(dag_als_vandaag=None)
        for day_info in dagen_info:
            if day_info["dag"] == dag.lower():
                datum_iso = day_info["datum"].strftime("%Y-%m-%d")
                break
        # Dag moet altijd in rolling window zitten - als niet, dan is er een bug
        if datum_iso is None:
            raise ValueError(
                f"Dag '{dag}' niet gevonden in rolling window. "
                f"Dit zou niet moeten gebeuren - bug in get_rolling_window_days()."
            )

    datum_hammertime = TimeZoneHelper.nl_tijd_naar_hammertime(
        datum_iso, "18:00", style="D"  # D = long date format (bijv. "28 november 2025")
    )
    title = f"**DMK-poll voor {dag.capitalize()} ({datum_hammertime}):**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n"

    # Gebruik de hide_counts en hide_ghosts parameters direct
    # De caller (poll_message.py) roept al should_hide_counts() aan
    # die de deadline-tijd checkt (bijv. vrijdag 18:00)
    effective_hide_counts = hide_counts
    effective_hide_ghosts = hide_ghosts

    # Filter opties voor deze dag
    all_opties = [o for o in get_poll_options() if o.dag == dag]

    # Filter opties op basis van poll option settings
    from apps.utils.poll_settings import get_poll_option_state

    opties = []
    for opt in all_opties:
        # Skip tijd-opties die disabled zijn (19:00 of 20:30)
        if opt.tijd in ["om 19:00 uur", "om 20:30 uur"]:
            tijd_short = "19:00" if "19:00" in opt.tijd else "20:30"
            if not get_poll_option_state(int(channel_id), dag, tijd_short):
                continue  # Skip deze optie

        opties.append(opt)

    if not opties:
        message += "_(geen opties gevonden)_"
        return message

    # Aantallen per tijd (scoped), tenzij verborgen
    # Voor verleden dagen: altijd counts ophalen (effective_hide_counts is False)
    counts = {} if effective_hide_counts else await get_counts_for_day(dag, guild_id, channel_id)

    # Bepaal of we in deadline-modus zitten (voor misschien-filtering)
    setting = get_setting(int(channel_id), dag) or {}
    is_deadline_mode = isinstance(setting, dict) and setting.get("modus") == "deadline"

    # Bereken datum voor Hammertime conversie (gebruik datum_iso parameter als beschikbaar)
    # Als niet beschikbaar, haal op uit rolling window
    if datum_iso is None:
        dagen_info = get_rolling_window_days(dag_als_vandaag=None)
        for day_info in dagen_info:
            if day_info["dag"] == dag.lower():
                datum_iso = day_info["datum"].strftime("%Y-%m-%d")
                break
        # Dag moet altijd in rolling window zitten - als niet, dan is er een bug
        if datum_iso is None:
            raise ValueError(
                f"Dag '{dag}' niet gevonden in rolling window. "
                f"Dit zou niet moeten gebeuren - bug in get_rolling_window_days()."
            )

    for opt in opties:
        # Filter "misschien" uit resultaten in deadline-modus:
        # - Bij verborgen counts: toont toch alleen "(stemmen verborgen)", geen meerwaarde
        # - Na deadline: toont toch alleen "(0 stemmen)", geen meerwaarde
        if is_deadline_mode and opt.tijd == "misschien":
            continue

        # Converteer tijd naar Hammertime voor 19:00 en 20:30
        if opt.tijd == "om 19:00 uur":
            tijd_display = TimeZoneHelper.nl_tijd_naar_hammertime(
                datum_iso, "19:00", style="t"
            )
            label = f"{opt.emoji} Om {tijd_display} uur"
        elif opt.tijd == "om 20:30 uur":
            tijd_display = TimeZoneHelper.nl_tijd_naar_hammertime(
                datum_iso, "20:30", style="t"
            )
            label = f"{opt.emoji} Om {tijd_display} uur"
        else:
            # Voor "misschien", "niet meedoen", etc.: geen Hammertime
            label = f"{opt.emoji} {opt.tijd.capitalize()}"

        if effective_hide_counts:
            message += f"{label} (stemmen verborgen)\n"
        else:
            n = int(counts.get(opt.tijd, 0))
            message += f"{label} ({n} stemmen)\n"

    # Voeg niet-stemmers toe (tenzij verborgen via hide_ghosts)
    # Voor verleden dagen: altijd niet-stemmers tonen (effective_hide_ghosts is False)
    if guild and channel and not effective_hide_ghosts:
        all_votes = await load_votes(guild_id, channel_id)
        non_voter_count, _ = await get_non_voters_for_day(
            dag, guild, channel, all_votes
        )

        if non_voter_count == 0:
            message += "🎉 Iedereen heeft gestemd! - *Fantastisch dat jullie allemaal hebben gestemd! Bedankt!*\n"
        else:
            message += f"👻 Niet gestemd ({non_voter_count} personen)\n"

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
                    except Exception:  # pragma: no cover
                        pass

                participants.append(
                    {
                        "type": "member",
                        "id": str(raw_id),
                        "display_name": display_name,
                        "mention": mention,
                    }
                )

        except Exception:  # pragma: no cover
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

    Tries to use stored non-voters first, falls back to calculating from channel members.

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - guild: Discord guild (server)
    - channel: Discord channel (for member access and display names)
    - all_votes: Dictionary met alle stemmen (used for fallback calculation)

    Retourneert:
    - (count, text) waarbij text bv. is: "@Naam1, @Naam2, @Naam3"

    Regels:
    - Tries to retrieve non-voters from storage
    - Falls back to calculating from channel members if not in storage
    - Display names are fetched from guild members
    """
    if not channel or not guild:
        return 0, ""

    guild_id = getattr(guild, "id", None)
    channel_id = getattr(channel, "id", None)

    if guild_id is None or channel_id is None:
        return 0, ""

    # Try to get non-voter IDs from storage
    try:
        count, non_voter_ids = await get_non_voters_from_storage(
            dag, guild_id, channel_id
        )

        # If we have stored non-voters, use them
        if count > 0 and non_voter_ids:
            # Build display names for non-voters
            non_voters: list[str] = []

            for member_id in non_voter_ids:
                try:
                    member = guild.get_member(
                        int(member_id)
                    ) or await guild.fetch_member(int(member_id))
                    if member:
                        display = (
                            getattr(member, "display_name", None)
                            or getattr(member, "global_name", None)
                            or getattr(member, "name", "Lid")
                        )
                        non_voters.append(f"@{display}")
                except Exception:  # pragma: no cover
                    # If member not found, skip
                    continue

            count = len(non_voters)
            text = ", ".join(non_voters) if non_voters else ""

            return count, text
    except Exception:  # pragma: no cover
        # If storage fails, fall through to legacy calculation
        pass

    # Fallback: calculate non-voters from channel members (legacy behavior)
    # Verzamel IDs die voor deze dag hebben gestemd (inclusief gasten via hun owner)
    voted_ids: set[str] = set()
    for uid, per_dag in all_votes.items():
        try:
            # Skip non-voter entries (they're not actual votes)
            if isinstance(uid, str) and uid.startswith("_non_voter::"):
                continue

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


async def get_was_misschien_for_day(
    dag: str,
    guild: discord.Guild | None,
    guild_id: int | str,
    channel_id: int | str,
) -> tuple[int, str]:
    """
    Retourneert (aantal_was_misschien, tekst) voor een specifieke dag.

    Parameters:
    - dag: 'vrijdag' | 'zaterdag' | 'zondag'
    - guild: Discord guild (server) voor het ophalen van display names
    - guild_id: Discord guild ID
    - channel_id: Discord channel ID

    Retourneert:
    - (count, text) waarbij text bv. is: "@Naam1, @Naam2"
    """
    from apps.utils.poll_storage import get_was_misschien_user_ids

    try:
        user_ids = await get_was_misschien_user_ids(dag, guild_id, channel_id)

        if not user_ids:
            return 0, ""

        # Bouw display names voor was_misschien gebruikers
        names: list[str] = []

        for member_id in user_ids:
            if guild:
                try:
                    member = guild.get_member(
                        int(member_id)
                    ) or await guild.fetch_member(int(member_id))
                    if member:
                        display = (
                            getattr(member, "display_name", None)
                            or getattr(member, "global_name", None)
                            or getattr(member, "name", "Lid")
                        )
                        names.append(f"@{display}")
                except Exception:  # pragma: no cover
                    # Lid niet gevonden, skip
                    continue
            else:
                # Geen guild, gebruik ID als fallback
                names.append(f"<@{member_id}>")

        count = len(names)
        text = ", ".join(names) if names else ""

        return count, text
    except Exception:  # pragma: no cover
        return 0, ""
