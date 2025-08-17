# apps/logic/visibility.py

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apps.utils.poll_settings import get_setting, should_hide_counts
from apps.entities.poll_option import get_poll_options

WEEKDAG_INDEX = {
    "maandag": 0,
    "dinsdag": 1,
    "woensdag": 2,
    "donderdag": 3,
    "vrijdag": 4,
    "zaterdag": 5,
    "zondag": 6
}

TIJD_LABELS = {
    "om 19:00 uur": (19, 0),
    "om 20:30 uur": (20, 30),
    "om 23:30 uur": (23, 30),
}


def is_vote_button_visible(channel_id: int, dag: str, tijd: str, now: datetime) -> bool:
    setting = get_setting(channel_id, dag)

    if dag not in WEEKDAG_INDEX:
        return False

    doel_idx = WEEKDAG_INDEX[dag]
    huidige_idx = now.weekday()
    verschil = (huidige_idx - doel_idx) % 7
    stemdatum = now.date() - timedelta(days=verschil)

    if setting["modus"] == "deadline":
        if should_hide_counts(channel_id, dag, now) is False:
            return False
        else:
            return True

    # → Tijd bepalen voor dit tijdslot
    if tijd in TIJD_LABELS:
        stem_uur, stem_min = TIJD_LABELS[tijd]
    else:
        # Specials: gebruik hoogste bekende tijd voor deze dag
        dag_tijden = [t for o in get_poll_options() if o.dag == dag and o.tijd in TIJD_LABELS for t in [TIJD_LABELS[o.tijd]]]
        if not dag_tijden:
            return False
        stem_uur, stem_min = max(dag_tijden)

    sluitmoment = datetime.combine(stemdatum, datetime.min.time(), tzinfo=ZoneInfo("Europe/Amsterdam"))
    sluitmoment = sluitmoment.replace(hour=stem_uur, minute=stem_min)

    return now < sluitmoment
