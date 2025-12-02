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

# Standaard weekdagen voor DMK polls
WEEK_DAYS = [
    "maandag",
    "dinsdag",
    "woensdag",
    "donderdag",
    "vrijdag",
    "zaterdag",
    "zondag",
]


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


def _seed_defaults_if_missing() -> None:  # pragma: no cover
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


# ========================================================================
# Notification Settings (per channel)
# ========================================================================


def get_all_notification_states(channel_id: int) -> dict[str, bool]:
    """
    Haal alle notificatie states op voor UI.

    Returns:
        Dict met keys: poll_opened, poll_reset, poll_closed, reminders,
        thursday_reminder, misschien, doorgaan, celebration
    """
    data = _load_data()
    ch_data = data.get(str(channel_id), {})
    notif_data = ch_data.get("__notification_states__", {})

    # Default states
    defaults = {
        "poll_opened": True,
        "poll_reset": True,
        "poll_closed": True,
        "reminders": False,
        "thursday_reminder": False,
        "misschien": False,
        "doorgaan": True,
        "celebration": True,
    }

    # Merge met opgeslagen data
    return {key: notif_data.get(key, default) for key, default in defaults.items()}


def toggle_notification_setting(channel_id: int, key: str) -> bool:
    """
    Toggle een specifieke notificatie instelling.
    Bij eerste gebruik: initialiseer ALLE notificaties expliciet met defaults.

    Args:
        channel_id: Het kanaal ID
        key: poll_opened | poll_reset | poll_closed | reminders |
             thursday_reminder | misschien | doorgaan | celebration

    Returns:
        Nieuwe status (True = enabled, False = disabled)
    """
    data = _load_data()
    ch = data.setdefault(str(channel_id), {})
    notif_states = ch.setdefault("__notification_states__", {})

    # Als __notification_states__ leeg is (eerste keer), initialiseer alles expliciet
    if not notif_states:
        # Default states
        defaults = {
            "poll_opened": True,
            "poll_reset": True,
            "poll_closed": True,
            "reminders": False,
            "thursday_reminder": False,
            "misschien": False,
            "doorgaan": True,
            "celebration": True,
        }
        # Initialiseer alle notificaties met defaults
        notif_states.update(defaults)

    # Haal huidige status op (met default)
    current = get_all_notification_states(channel_id).get(key, False)

    # Toggle
    new_status = not current
    notif_states[key] = new_status

    _save_data(data)
    return new_status


def is_notification_enabled(channel_id: int, key: str) -> bool:
    """
    Check of een notificatie enabled is.

    Args:
        channel_id: Het kanaal ID
        key: poll_opened | poll_reset | poll_closed | reminders |
             thursday_reminder | misschien | doorgaan | celebration

    Returns:
        True als enabled, anders False
    """
    states = get_all_notification_states(channel_id)
    return states.get(key, False)


# ========================================================================
# Enabled Days Configuration (per channel)
# ========================================================================


def get_enabled_days(channel_id: int) -> list[str]:
    """
    Haal enabled dagen op voor een kanaal.

    Returns:
        List van dag-namen, default: ['vrijdag', 'zaterdag', 'zondag']
    """
    data = _load_data()
    ch_data = data.get(str(channel_id), {})
    enabled = ch_data.get("__enabled_days__")

    # Default: alleen weekend dagen (vrijdag, zaterdag, zondag)
    DEFAULT_ENABLED_DAYS = ["vrijdag", "zaterdag", "zondag"]

    if enabled is None:
        return DEFAULT_ENABLED_DAYS.copy()

    return enabled if isinstance(enabled, list) else DEFAULT_ENABLED_DAYS.copy()


def set_enabled_days(channel_id: int, dagen: list[str]) -> list[str]:
    """
    Stel enabled dagen in voor een kanaal.

    Args:
        channel_id: Het kanaal ID
        dagen: List van dag-namen (bijv. ['zondag'] of ['vrijdag', 'zaterdag', 'zondag'])

    Returns:
        De opgeslagen enabled days
    """
    # Validatie: alleen geldige weekdagen
    geldige_dagen = [
        "maandag",
        "dinsdag",
        "woensdag",
        "donderdag",
        "vrijdag",
        "zaterdag",
        "zondag",
    ]
    for dag in dagen:
        if dag.lower() not in geldige_dagen:
            raise ValueError(
                f"Ongeldige dag: {dag}. Gebruik: {', '.join(geldige_dagen)}"
            )

    data = _load_data()
    ch = data.setdefault(str(channel_id), {})
    ch["__enabled_days__"] = [dag.lower() for dag in dagen]
    _save_data(data)

    return ch["__enabled_days__"]


# ========================================================================
# Poll Options Settings (per channel, per dag+tijd combinatie)
# ========================================================================


def get_poll_option_state(channel_id: int, dag: str, tijd: str) -> bool:
    """
    Check of een specifieke poll optie enabled is.

    Args:
        channel_id: Het kanaal ID
        dag: 'maandag' t/m 'zondag'
        tijd: '19:00' | '20:30'

    Returns:
        True als enabled, False als disabled
    """
    data = _load_data()
    ch_data = data.get(str(channel_id), {})
    options = ch_data.get("__poll_options__", {})

    # Key format: "vrijdag_19:00" of "zaterdag_20:30"
    key = f"{dag.lower()}_{tijd}"

    # Default: alleen vrijdag, zaterdag, zondag enabled
    default_enabled = dag.lower() in ["vrijdag", "zaterdag", "zondag"]
    return options.get(key, default_enabled)


def set_poll_option_state(channel_id: int, dag: str, tijd: str, enabled: bool) -> bool:
    """
    Zet de status van een specifieke poll optie.
    Bij eerste gebruik: initialiseer ALLE opties expliciet met defaults.

    Args:
        channel_id: Het kanaal ID
        dag: 'vrijdag' | 'zaterdag' | 'zondag'
        tijd: '19:00' | '20:30'
        enabled: True = enabled, False = disabled

    Returns:
        De nieuwe status
    """
    data = _load_data()
    ch = data.setdefault(str(channel_id), {})
    options = ch.setdefault("__poll_options__", {})

    # Als __poll_options__ leeg is (eerste keer), initialiseer alles expliciet
    if not options:
        # Initialiseer alle 14 opties met defaults
        for day in WEEK_DAYS:
            for time in ["19:00", "20:30"]:
                key = f"{day}_{time}"
                # Default: alleen vrijdag, zaterdag, zondag enabled
                default_enabled = day in ["vrijdag", "zaterdag", "zondag"]
                options[key] = default_enabled

    # Nu de aangeklikte optie updaten
    key = f"{dag.lower()}_{tijd}"
    options[key] = enabled

    _save_data(data)
    return enabled


def toggle_poll_option(channel_id: int, dag: str, tijd: str) -> bool:
    """
    Toggle een poll optie aan/uit.

    Args:
        channel_id: Het kanaal ID
        dag: 'vrijdag' | 'zaterdag' | 'zondag'
        tijd: '19:00' | '20:30'

    Returns:
        De nieuwe status (True = enabled, False = disabled)
    """
    current = get_poll_option_state(channel_id, dag, tijd)
    return set_poll_option_state(channel_id, dag, tijd, not current)


def get_all_poll_options_state(channel_id: int) -> dict:
    """
    Haal de status van alle poll opties op.

    Returns:
        Dict met keys zoals "vrijdag_19:00" en values True/False
    """
    data = _load_data()
    ch_data = data.get(str(channel_id), {})
    options = ch_data.get("__poll_options__", {})

    # Return all 14 options met defaults (alleen weekend dagen enabled)
    result = {}
    for dag in WEEK_DAYS:
        for tijd in ["19:00", "20:30"]:
            key = f"{dag}_{tijd}"
            # Default: alleen vrijdag, zaterdag, zondag enabled
            default_enabled = dag in ["vrijdag", "zaterdag", "zondag"]
            result[key] = options.get(key, default_enabled)

    return result


def get_enabled_times_for_day(channel_id: int, dag: str) -> list[str]:
    """
    Haal de enabled tijden op voor een specifieke dag.

    Args:
        channel_id: Het kanaal ID
        dag: 'vrijdag' | 'zaterdag' | 'zondag'

    Returns:
        List van enabled tijden, bijv: ['om 19:00 uur', 'om 20:30 uur']
    """
    enabled_times = []

    if get_poll_option_state(channel_id, dag, "19:00"):
        enabled_times.append("om 19:00 uur")

    if get_poll_option_state(channel_id, dag, "20:30"):
        enabled_times.append("om 20:30 uur")

    return enabled_times


def is_day_completely_disabled(channel_id: int, dag: str) -> bool:
    """
    Check of een dag volledig disabled is (alle tijden uit).

    Args:
        channel_id: Het kanaal ID
        dag: 'maandag' t/m 'zondag'

    Returns:
        True als alle tijdslots voor deze dag disabled zijn, anders False
    """
    from apps.entities.poll_option import get_poll_options

    # Haal alle poll opties op voor deze dag
    day_options = [opt for opt in get_poll_options() if opt.dag == dag]

    # Als er geen opties zijn voor deze dag, check de standaard tijden (backwards compatibility)
    if not day_options:
        # Fallback naar hardcoded tijden voor backwards compatibility
        has_19 = get_poll_option_state(channel_id, dag, "19:00")
        has_2030 = get_poll_option_state(channel_id, dag, "20:30")
        return not has_19 and not has_2030

    # Check of er minstens één tijd enabled is voor deze dag
    # We moeten zowel long form ("om 19:00 uur") als short form ("19:00") checken
    data = _load_data()
    ch_data = data.get(str(channel_id), {})
    options_data = ch_data.get("__poll_options__", {})

    has_enabled = False
    for opt in day_options:
        # Skip special options zoals "misschien" en "niet meedoen"
        if opt.tijd in ["misschien", "niet meedoen"]:
            continue

        # Extract short form (bijv. "om 19:00 uur" -> "19:00")
        short_form = opt.tijd.replace("om ", "").replace(" uur", "").strip()

        # Check beide keys
        key_long = f"{dag.lower()}_{opt.tijd}"
        key_short = f"{dag.lower()}_{short_form}"

        # Kijk of één van de twee keys een expliciete setting heeft
        if key_long in options_data:
            if options_data[key_long]:
                has_enabled = True
                break
        elif key_short in options_data:
            if options_data[key_short]:
                has_enabled = True
                break
        else:
            # Geen expliciete setting, gebruik default
            # Default: alleen vrijdag, zaterdag, zondag enabled
            if dag.lower() in ["vrijdag", "zaterdag", "zondag"]:
                has_enabled = True
                break

    return not has_enabled


def get_enabled_poll_days(channel_id: int) -> list[str]:
    """
    Geef lijst van enabled dagen terug (waar minstens één tijd enabled is).

    Args:
        channel_id: Het kanaal ID

    Returns:
        Lijst van enabled dagen (bijv. ['vrijdag', 'zondag'])
    """
    return [dag for dag in WEEK_DAYS if not is_day_completely_disabled(channel_id, dag)]


def get_enabled_rolling_window_days(
    channel_id: int, dag_als_vandaag: str | None = None
) -> list[dict[str, str]]:
    """
    Geef lijst van enabled dagen terug binnen rolling window (1 terug + vandaag + 5 vooruit).

    Args:
        channel_id: Het kanaal ID
        dag_als_vandaag: Optioneel, welke dag als "vandaag" beschouwen

    Returns:
        Lijst van dicts met 'dag' (naam) en 'datum_iso' (YYYY-MM-DD) voor enabled dagen binnen window

    Voorbeeld: [
        {'dag': 'zondag', 'datum_iso': '2024-11-30', 'is_past': True, 'is_today': False, 'is_future': False},
        {'dag': 'maandag', 'datum_iso': '2024-12-01', 'is_past': False, 'is_today': True, 'is_future': False},
        {'dag': 'dinsdag', 'datum_iso': '2024-12-02', 'is_past': False, 'is_today': False, 'is_future': True},
        ...
    ]
    """
    from apps.utils.message_builder import get_rolling_window_days

    # Haal rolling window op
    window = get_rolling_window_days(dag_als_vandaag)

    # Filter op enabled dagen (volgens poll option settings)
    enabled_days = []
    for day_info in window:
        dag = day_info["dag"]
        if not is_day_completely_disabled(channel_id, dag):
            enabled_days.append({
                "dag": dag,
                "datum_iso": day_info["datum"].strftime("%Y-%m-%d"),
                "is_past": day_info["is_past"],
                "is_today": day_info["is_today"],
                "is_future": day_info["is_future"],
            })

    return enabled_days
