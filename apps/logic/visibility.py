# apps/logic/visibility.py

from datetime import date, datetime, time

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_settings import get_setting

# We roepen een interne helper aan om te bepalen of er een expliciete instelling is opgeslagen.
# Het standaardgedrag verbergt de stemknoppen wanneer het aantal zichtbare dagen kleiner is dan
# het aantal geplande poll‑dagen.
try:
    from apps.utils.poll_settings import (
        _load_data as _load_settings_data,  # type: ignore
    )
except Exception:  # pragma: no cover
    _load_settings_data = None  # type: ignore

WEEKDAG_INDEX = {
    "maandag": 0,
    "dinsdag": 1,
    "woensdag": 2,
    "donderdag": 3,
    "vrijdag": 4,
    "zaterdag": 5,
    "zondag": 6,
}

TIJD_LABELS = {
    "om 19:00 uur": (19, 0),
    "om 20:30 uur": (20, 30),
    "om 23:30 uur": (23, 30),
}


def _has_explicit_setting(channel_id: int, dag: str) -> bool:
    """
    Geef True terug als er een expliciete invoer is opgeslagen voor dit kanaal/deze dag.
    We willen de standaardwaarde in de code ('deadline', 18:00) NIET als expliciet beschouwen
    voor de zichtbaarheid van
    """
    if _load_settings_data is None:
        return False
    try:
        data = _load_settings_data() or {}
        ch = data.get(str(channel_id), {})
        return dag in ch
    except Exception:
        return False


def is_vote_button_visible(
    channel_id: int,
    dag: str,
    tijd: str,
    now: datetime,
    datum: date | None = None,
) -> bool:
    """
    Bepaalt of een stemknop zichtbaar is (alleen knoplogica, niet aantallen).

    Regels:
    - Dag in verleden: onzichtbaar
    - Dag in toekomst: zichtbaar
    - Zelfde dag:
        * Als er voor deze dag/kanaal **expliciet** 'deadline' is ingesteld en het is >= deadline:
          ALLE knoppen uit (admin-keuze)
        * Normale tijden: zichtbaar tot eigen tijd (19:00 / 20:30 / 23:30)
        * Specials ('misschien', 'niet meedoen'): zichtbaar zolang er nog een komend tijdslot is

    Als *datum* (de werkelijke kalenderdatum van de dag) is meegegeven, wordt die
    gebruikt voor de verleden/toekomst-check in plaats van weekdag-indices.  Dit is
    essentieel voor het twee-periodesysteem, waar ma-do dagen op vrijdag-zondag in
    de toekomst liggen ondanks een lagere weekdag-index.
    """
    if dag not in WEEKDAG_INDEX:
        return False

    # Vergelijk op werkelijke datum als die beschikbaar is
    if datum is not None:
        today = now.date()
        if datum < today:
            return False
        elif datum > today:
            return True
        # datum == today → doorvallen naar zelfde-dag-logica
    else:
        dag_index = WEEKDAG_INDEX[dag]
        now_index = now.weekday()

        # Voorbije dag → knoppen uit
        if dag_index < now_index:
            return False
        # Toekomstige dag → knoppen aan
        elif dag_index > now_index:
            return True

    # Zelfde dag → alleen deadline afdwingen als admin dit expliciet heeft gezet
    if _has_explicit_setting(channel_id, dag):
        try:
            setting = get_setting(channel_id, dag) or {}
        except Exception:
            setting = {}
        if isinstance(setting, dict) and setting.get("modus") == "deadline":
            tijd_str = str(setting.get("tijd", "18:00"))
            try:
                uur, minuut = [int(x) for x in tijd_str.split(":", 1)]
            except Exception:
                uur, minuut = 18, 0
            if now.time() >= time(uur, minuut):
                return False

    # Daarna de specifieke knoplogica voor vandaag
    if tijd in TIJD_LABELS:
        uur, minuut = TIJD_LABELS[tijd]
        return now.time() < time(uur, minuut)
    else:
        # specials → zichtbaar zolang er nog een tijdslot van vandaag in de toekomst ligt
        try:
            tijden = [
                TIJD_LABELS[o.tijd]
                for o in get_poll_options()
                if o.dag == dag and o.tijd in TIJD_LABELS
            ]
        except Exception:
            tijden = []
        if not tijden:
            return False
        return any(now.time() < time(u, m) for (u, m) in tijden)
