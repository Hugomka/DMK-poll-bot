# apps/logic/decision.py

from datetime import datetime
from zoneinfo import ZoneInfo

from apps.utils.poll_settings import should_hide_counts
from apps.utils.poll_storage import get_counts_for_day

# Alleen deze twee tijden doen mee aan de beslissing
T19 = "om 19:00 uur"
T2030 = "om 20:30 uur"
MIN_STEMMEN = 6  # drempel voor “gaat door”


async def build_decision_line(
    guild_id: int | str,
    channel_id: int | str,
    dag: str,
    now: datetime | None = None,
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
        return "⏳ Beslissing komt **om 18:00**."

    # Ná de deadline → echte beslissing tonen (gescope per guild+channel)
    counts = await get_counts_for_day(dag, guild_id, channel_id)
    c19 = counts.get(T19, 0)
    c2030 = counts.get(T2030, 0)

    if c19 < MIN_STEMMEN and c2030 < MIN_STEMMEN:
        return "🚫 **Gaat niet door** (te weinig stemmen)."

    # Winnaar bepalen (gelijk → 20:30)
    if c2030 >= max(c19, MIN_STEMMEN):
        return f"🏁 **Vanavond om 20:30 gaat door!** ({c2030} stemmen)"
    elif c19 >= MIN_STEMMEN:
        return f"🏁 **Vanavond om 19:00 gaat door!** ({c19} stemmen)"
    else:
        return "🚫 **Gaat niet door** (te weinig stemmen)."
