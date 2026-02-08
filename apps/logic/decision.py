# apps/logic/decision.py

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from apps.utils.i18n import t
from apps.utils.poll_settings import should_hide_counts
from apps.utils.poll_storage import get_counts_for_day, get_counts_for_day_scoped

# Alleen deze twee tijden doen mee aan de beslissing
T19 = "om 19:00 uur"
T2030 = "om 20:30 uur"
MIN_STEMMEN = 6  # Drempel voor "gaat door"


async def build_decision_line(
    guild_id: int | str,
    channel_id: int | str,
    dag: str,
    now: datetime | None = None,
    channel: Any = None,
) -> str | None:
    """
    Geeft 1 regel terug die onder het pollbericht kan.
    Regels:
    - Beslissing alleen tonen op de dag zelf ná de deadline (niet erna voor andere dagen).
    - ≥6 stemmen nodig. Meeste stemmen wint. Bij gelijkspel wint 20:30.
    - Als drempel niet gehaald: duidelijk melden dat het niet doorgaat.
    - Voor de deadline (op de dag zelf): aankondigen dat beslissing om <tijd> komt.
    - Op dagen vóór de dag zelf: niets tonen.
    """
    now = now or datetime.now(ZoneInfo("Europe/Amsterdam"))

    # Voor/na de deadline bepalen met bestaande logica:
    # should_hide_counts == True  -> vóór deadline
    # should_hide_counts == False -> ná deadline (of niet in deadline-modus)
    chan_int: int = int(channel_id) if not isinstance(channel_id, int) else channel_id
    voor_deadline = should_hide_counts(chan_int, dag, now)

    # Check of het vandaag die dag is; anders geen tekst
    WEEKDAG_INDEX = {
        "maandag": 0,
        "dinsdag": 1,
        "woensdag": 2,
        "donderdag": 3,
        "vrijdag": 4,
        "zaterdag": 5,
        "zondag": 6,
    }
    if dag not in WEEKDAG_INDEX:
        return None
    if now.weekday() != WEEKDAG_INDEX[dag]:
        return None

    # Op de dag zelf maar vóór deadline → aankondigen
    if voor_deadline:
        return t(chan_int, "NOTIFICATIONS.decision_pending")

    # Ná de deadline → echte beslissing tonen (gescope per guild en channel)
    # Use category-scoped counts for dual language support
    if channel:
        from apps.utils.poll_settings import get_vote_scope_channels

        scope_ids = get_vote_scope_channels(channel)
        if len(scope_ids) > 1:
            # Multiple channels share votes - use aggregated counts
            counts = await get_counts_for_day_scoped(dag, guild_id, scope_ids)
        else:
            counts = await get_counts_for_day(dag, guild_id, channel_id)
    else:
        counts = await get_counts_for_day(dag, guild_id, channel_id)
    c19 = counts.get(T19, 0)
    c2030 = counts.get(T2030, 0)

    if c19 < MIN_STEMMEN and c2030 < MIN_STEMMEN:
        return t(chan_int, "NOTIFICATIONS.decision_not_happening")

    # Winnaar bepalen (gelijk → 20:30)
    if c2030 >= max(c19, MIN_STEMMEN):
        return t(chan_int, "NOTIFICATIONS.decision_happening_2030", count=c2030)
    elif c19 >= MIN_STEMMEN:
        return t(chan_int, "NOTIFICATIONS.decision_happening_1900", count=c19)
    else:  # pragma: no cover
        return t(chan_int, "NOTIFICATIONS.decision_not_happening")
