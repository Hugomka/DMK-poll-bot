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
    """Zet expliciet 'altijd', 'deadline_show_ghosts' of 'deadline' zichtbaarheid met tijd."""
    data = _load_data()
    kanaal = data.setdefault(str(channel_id), {})
    if modus == "altijd":
        instelling = {"modus": "altijd", "tijd": "18:00"}
    elif modus == "deadline_show_ghosts":
        instelling = {"modus": "deadline_show_ghosts", "tijd": tijd}
    else:
        instelling = {"modus": "deadline", "tijd": tijd}
    kanaal[dag] = instelling
    _save_data(data)
    return instelling


def should_hide_counts(channel_id: int, dag: str, now: datetime) -> bool:
    """Bepaalt of stemaantallen verborgen moeten worden."""
    instelling = get_setting(channel_id, dag)
    if instelling["modus"] == "altijd":
        return False

    # Voor 'deadline' en 'deadline_show_ghosts': beide verbergen counts tot deadline
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


def should_hide_ghosts(channel_id: int, dag: str, now: datetime) -> bool:
    """Bepaalt of ghostaantallen (niet gestemd) verborgen moeten worden."""
    instelling = get_setting(channel_id, dag)

    # 'altijd': alles zichtbaar → ghosts tonen
    if instelling["modus"] == "altijd":
        return False

    # 'deadline_show_ghosts': counts verbergen, ghosts tonen → ghosts tonen
    if instelling["modus"] == "deadline_show_ghosts":
        return False

    # 'deadline': alles verbergen → ghosts ook verbergen tot deadline
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


# ========================================================================
# Scheduling Functions for Poll Deactivation (/dmk-poll-off)
# ========================================================================


def get_scheduled_deactivation(channel_id: int) -> dict | None:
    """
    Haal de geplande deactivatie-instellingen op voor een kanaal.

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
    return data.get(str(channel_id), {}).get("__scheduled_deactivation__")


def set_scheduled_deactivation(
    channel_id: int,
    activation_type: str,
    tijd: str,
    dag: str | None = None,
    datum: str | None = None,
) -> dict:
    """
    Stel een geplande deactivatie in voor een kanaal.

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

    ch["__scheduled_deactivation__"] = schedule
    _save_data(data)
    return schedule


def clear_scheduled_deactivation(channel_id: int) -> None:
    """Verwijder de geplande deactivatie voor een kanaal."""
    data = _load_data()
    ch = data.get(str(channel_id), {})
    if "__scheduled_deactivation__" in ch:
        del ch["__scheduled_deactivation__"]
        _save_data(data)


# ========================================================================
# Global Default Schedules
# ========================================================================


def get_default_activation() -> dict | None:
    """
    Haal de globale standaard activatie-instellingen op.

    Returns:
        Dict met scheduling info of None als er geen standaard is.
        Format: {
            'type': 'wekelijks',
            'dag': 'dinsdag',
            'tijd': '20:00'
        }
    """
    data = _load_data()
    return data.get("defaults", {}).get("activation")


def get_default_deactivation() -> dict | None:
    """
    Haal de globale standaard deactivatie-instellingen op.

    Returns:
        Dict met scheduling info of None als er geen standaard is.
        Format: {
            'type': 'wekelijks',
            'dag': 'maandag',
            'tijd': '00:00'
        }
    """
    data = _load_data()
    return data.get("defaults", {}).get("deactivation")


def set_default_activation(value: dict | None) -> None:
    """
    Stel de globale standaard activatie in.

    Args:
        value: Schedule dict of None om te verwijderen
    """
    data = _load_data()
    defaults = data.setdefault("defaults", {})
    if value is None:
        defaults.pop("activation", None)
    else:
        defaults["activation"] = value
    _save_data(data)


def set_default_deactivation(value: dict | None) -> None:
    """
    Stel de globale standaard deactivatie in.

    Args:
        value: Schedule dict of None om te verwijderen
    """
    data = _load_data()
    defaults = data.setdefault("defaults", {})
    if value is None:
        defaults.pop("deactivation", None)
    else:
        defaults["deactivation"] = value
    _save_data(data)


def _seed_defaults_if_missing() -> None:
    """
    Seed standaard schedules als ze nog niet bestaan.
    Alleen uitgevoerd wanneer SEED_DEFAULT_SCHEDULES=true.
    """
    seed_flag = os.getenv("SEED_DEFAULT_SCHEDULES", "true").lower()
    if seed_flag not in {"1", "true", "yes", "y"}:
        return

    data = _load_data()
    if "defaults" in data:
        # Defaults already exist, don't overwrite
        return

    defaults = {
        "activation": {"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"},
        "deactivation": {"type": "wekelijks", "dag": "maandag", "tijd": "00:00"},
    }
    data["defaults"] = defaults
    _save_data(data)


# Seed defaults on module load (non-destructive)
_seed_defaults_if_missing()


def get_effective_activation(channel_id: int) -> tuple[dict | None, bool]:
    """
    Haal de effectieve activatie-instellingen op voor een kanaal.

    Returns:
        Tuple van (schedule, is_default):
        - Als het kanaal een override heeft -> (override, False)
        - Anders -> (defaults.activation, True) of (None, False) als er geen default is
    """
    channel_schedule = get_scheduled_activation(channel_id)
    if channel_schedule is not None:
        return (channel_schedule, False)

    default_schedule = get_default_activation()
    if default_schedule is not None:
        return (default_schedule, True)

    return (None, False)


def get_effective_deactivation(channel_id: int) -> tuple[dict | None, bool]:
    """
    Haal de effectieve deactivatie-instellingen op voor een kanaal.

    Returns:
        Tuple van (schedule, is_default):
        - Als het kanaal een override heeft -> (override, False)
        - Anders -> (defaults.deactivation, True) of (None, False) als er geen default is
    """
    channel_schedule = get_scheduled_deactivation(channel_id)
    if channel_schedule is not None:
        return (channel_schedule, False)

    default_schedule = get_default_deactivation()
    if default_schedule is not None:
        return (default_schedule, True)

    return (None, False)
