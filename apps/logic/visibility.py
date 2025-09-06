from datetime import datetime, time

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_settings import get_setting, should_hide_counts

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


def is_vote_button_visible(channel_id: int, dag: str, tijd: str, now: datetime) -> bool:
    setting = get_setting(channel_id, dag)

    if dag not in WEEKDAG_INDEX:
        return False

    dag_index = WEEKDAG_INDEX[dag]
    now_index = now.weekday()

    # Deadline alleen op dag zelf vóór de ingestelde tijd
    if setting["modus"] == "deadline":
        if should_hide_counts(channel_id, dag, now) is False:
            return False
        else:
            return True

    # Bepaal of dag deze week nog komt
    if dag_index < now_index:
        return False
    elif dag_index > now_index:
        return True
    else:
        # Het is vandaag → controleer tijd
        if tijd in TIJD_LABELS:
            uur, minuut = TIJD_LABELS[tijd]
        else:
            # specials → check of ENIG TIJD nog in de toekomst is
            tijden = [
                TIJD_LABELS[o.tijd]
                for o in get_poll_options()
                if o.dag == dag and o.tijd in TIJD_LABELS
            ]
            if not tijden:
                return False
            return any(now.time() < time(u, m) for u, m in tijden)

        return now.time() < time(uur, minuut)
