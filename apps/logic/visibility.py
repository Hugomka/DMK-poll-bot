# apps/logic/visibility.py

from datetime import datetime, time

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_settings import get_setting

# We call a private helper to detect if a setting is explicitly stored.
# This keeps behaviour minimal: only enforce deadline on buttons
# when an admin actually set it for this channel/day.
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
    """Return True if there is an explicit entry stored for this channel/day.
    We do NOT want to treat the in-code default ('deadline', 18:00) as explicit
    for button visibility rules.
    """
    if _load_settings_data is None:
        return False
    try:
        data = _load_settings_data() or {}
        ch = data.get(str(channel_id), {})
        return dag in ch
    except Exception:
        return False


def is_vote_button_visible(channel_id: int, dag: str, tijd: str, now: datetime) -> bool:
    """Bepaalt of een stemknop zichtbaar is (alleen knoplogica, niet aantallen).

    Regels:
    - Dag in verleden: onzichtbaar
    - Dag in toekomst: zichtbaar
    - Zelfde dag:
        * Als er voor deze dag/kanaal **expliciet** 'deadline' is ingesteld en het is >= deadline:
          ALLE knoppen uit (admin-keuze)
        * Normale tijden: zichtbaar tot eigen tijd (19:00 / 20:30 / 23:30)
        * Specials ('misschien', 'niet meedoen'): zichtbaar zolang er nog een komend tijdslot is
    """
    if dag not in WEEKDAG_INDEX:
        return False

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
