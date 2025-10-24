# apps/utils/poll_settings.py

import json
import os
from datetime import datetime, time

SETTINGS_FILE = os.getenv("SETTINGS_FILE", "poll_settings.json")

DAYS_INDEX = {
    "maandag": 0,
    "dinsdag": 1,
    "woensdag": 2,
    "donderdag": 3,
    "vrijdag": 4,
    "zaterdag": 5,
    "zondag": 6,
}


def _load_data():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:  # pragma: no cover
                pass
    return {}


def _save_data(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_setting(channel_id: int, dag: str):
    """
    Geef de instelling voor zichtbaarheid en tijdstip terug.
    Standaard: {'modus': 'deadline', 'tijd': '18:00'}.
    """
    data = _load_data()
    return data.get(str(channel_id), {}).get(
        dag, {"modus": "deadline", "tijd": "18:00"}
    )


def set_visibility(channel_id: int, dag: str, modus: str, tijd: str = "18:00"):
    """Zet expliciet 'altijd' of 'deadline' zichtbaarheid met tijd."""
    data = _load_data()
    kanaal = data.setdefault(str(channel_id), {})
    if modus == "altijd":
        instelling = {"modus": "altijd", "tijd": "18:00"}
    else:
        instelling = {"modus": "deadline", "tijd": tijd}
    kanaal[dag] = instelling
    _save_data(data)
    return instelling


def should_hide_counts(channel_id: int, dag: str, now: datetime) -> bool:
    instelling = get_setting(channel_id, dag)
    if instelling["modus"] == "altijd":
        return False

    # Deadline-uur:minuut
    tijd_str = instelling.get("tijd", "18:00")
    try:
        uur, minuut = map(int, tijd_str.split(":"))
    except ValueError:  # pragma: no cover
        uur, minuut = 18, 0

    target_idx = DAYS_INDEX.get(dag)
    if target_idx is None:
        return False  # Onbekende dag

    huidige_idx = now.weekday()

    # Vóór de dag → verbergen
    if huidige_idx < target_idx:
        return True
    # Na de dag → tonen
    if huidige_idx > target_idx:
        return False

    # Zelfde dag: verbergen tot de deadline-tijd
    deadline = time(uur, minuut)
    return now.time() < deadline


def is_paused(channel_id: int) -> bool:
    data = _load_data()
    return bool(data.get(str(channel_id), {}).get("__paused__", False))


def set_paused(channel_id: int, value: bool) -> bool:
    data = _load_data()
    ch = data.setdefault(str(channel_id), {})
    ch["__paused__"] = bool(value)
    _save_data(data)
    return ch["__paused__"]


def toggle_paused(channel_id: int) -> bool:
    return set_paused(channel_id, not is_paused(channel_id))


def reset_settings() -> None:
    """Verwijdert alle zichtbaarheid- en pauze-instellingen."""
    if os.path.exists(SETTINGS_FILE):
        os.remove(SETTINGS_FILE)


# ========================================================================
# Scheduling Functions for Poll Activation
# ========================================================================


def get_scheduled_activation(channel_id: int) -> dict | None:
    """
    Haal de geplande activatie-instellingen op voor een kanaal.

    Returns:
        Dict met scheduling info of None als er geen schema is.
        Format: {
            'type': 'datum' | 'wekelijks',
            'datum': 'YYYY-MM-DD' (alleen voor type='datum'),
            'dag': 'maandag' t/m 'zondag' (alleen voor type='wekelijks'),
            'tijd': 'HH:mm'
        }
    """
    data = _load_data()
    return data.get(str(channel_id), {}).get("__scheduled_activation__")


def set_scheduled_activation(
    channel_id: int,
    activation_type: str,
    tijd: str,
    dag: str | None = None,
    datum: str | None = None,
) -> dict:
    """
    Stel een geplande activatie in voor een kanaal.

    Args:
        channel_id: Het kanaal ID
        activation_type: 'datum' (eenmalig) of 'wekelijks'
        tijd: Tijd in HH:mm formaat
        dag: Weekdag naam (voor wekelijks), optioneel
        datum: Datum in YYYY-MM-DD formaat (voor datum), optioneel

    Returns:
        De opgeslagen schedule configuratie
    """
    data = _load_data()
    ch = data.setdefault(str(channel_id), {})

    schedule: dict = {
        "type": activation_type,
        "tijd": tijd,
    }

    if activation_type == "datum" and datum:
        schedule["datum"] = datum
    elif activation_type == "wekelijks" and dag:
        schedule["dag"] = dag

    ch["__scheduled_activation__"] = schedule
    _save_data(data)
    return schedule


def clear_scheduled_activation(channel_id: int) -> None:
    """Verwijder de geplande activatie voor een kanaal."""
    data = _load_data()
    ch = data.get(str(channel_id), {})
    if "__scheduled_activation__" in ch:
        del ch["__scheduled_activation__"]
        _save_data(data)
