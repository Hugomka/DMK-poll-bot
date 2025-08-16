# apps\utils\poll_settings.py

import json
import os
from datetime import datetime, time


SETTINGS_FILE = "poll_settings.json"

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
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {}

def _save_data(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def get_setting(channel_id: int, dag: str):
    """Geef de instelling voor zichtbaarheid en tijdstip terug.
       Standaard: {'modus': 'altijd', 'tijd': '18:00'}."""
    data = _load_data()
    return (
        data.get(str(channel_id), {})
            .get(dag, {'modus': 'altijd', 'tijd': '18:00'})
    )

def toggle_visibility(channel_id: int, dag: str, tijd: str = '18:00'):
    """Schakel tussen 'altijd' en 'deadline'. Bij omschakeling naar 'deadline'
       wordt het tijdstip opgeslagen."""
    data = _load_data()
    kanaal = data.setdefault(str(channel_id), {})
    instelling = kanaal.get(dag, {'modus': 'altijd', 'tijd': '18:00'})
    if instelling['modus'] == 'altijd':
        instelling = {'modus': 'deadline', 'tijd': tijd}
    else:
        instelling = {'modus': 'altijd', 'tijd': '18:00'}
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
    except ValueError:
        uur, minuut = 18, 0

    target_idx = DAYS_INDEX.get(dag)
    if target_idx is None:
        return False  # onbekende dag

    huidige_idx = now.weekday()

    # vóór de dag → verbergen
    if huidige_idx < target_idx:
        return True
    # na de dag → tonen
    if huidige_idx > target_idx:
        return False

    # zelfde dag: verbergen tot de deadline-tijd
    deadline = time(uur, minuut)  # gebruik datetime.time-klasse die we importeerden
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

