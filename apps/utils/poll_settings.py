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


def is_slot_past_deadline(channel_id: int, dag: str, tijd: str, now: datetime) -> bool:
    """
    Bepaalt of een tijdslot voorbij de deadline is (voor guest votes).

    Een slot is "past deadline" als:
    - De dag al voorbij is, OF
    - Het is dezelfde dag EN de starttijd van het slot is al geweest

    Args:
        channel_id: Discord channel ID
        dag: Dagnaam (e.g., 'vrijdag', 'zaterdag')
        tijd: Tijdslot string (e.g., 'om 19:00 uur' of '19:00')
        now: Huidige datetime

    Returns:
        True als het slot al voorbij is, anders False
    """
    target_idx = DAYS_INDEX.get(dag.lower())
    if target_idx is None:
        return False  # Onbekende dag

    huidige_idx = now.weekday()

    # Als de dag al voorbij is deze week → past deadline
    if huidige_idx > target_idx:
        return True

    # Als de dag nog moet komen → niet past deadline
    if huidige_idx < target_idx:
        return False

    # Zelfde dag: check of de starttijd van het slot al geweest is
    # Extraheer uur en minuut uit tijd string (bijv. "om 19:00 uur" -> 19, 0)
    tijd_clean = tijd.replace("om ", "").replace(" uur", "").strip()
    try:
        uur, minuut = map(int, tijd_clean.split(":"))
    except ValueError:
        return False  # Kan tijd niet parsen

    slot_time = time(uur, minuut)
    return now.time() >= slot_time


def should_hide_counts(channel_id: int, dag: str, now: datetime) -> bool:
    """
    Bepaalt of stemaantallen verborgen moeten worden.

    Gebruikt period-based date calculation om te bepalen of de deadline is gepasseerd.
    Counts worden verborgen vóór de deadline en getoond na de deadline.
    """
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

    # Haal de datum op voor deze dag vanuit het period systeem
    from apps.utils.period_dates import get_period_for_day, get_period_days

    try:
        period = get_period_for_day(dag)
        period_dates = get_period_days(period, now)
        datum_iso = period_dates.get(dag.lower())

        if datum_iso is None:
            # Fallback naar oude logica als datum niet gevonden
            target_idx = DAYS_INDEX.get(dag)
            if target_idx is None:
                return False
            huidige_idx = now.weekday()
            if huidige_idx < target_idx:
                return True
            if huidige_idx > target_idx:
                return False
            deadline = time(uur, minuut)
            return now.time() < deadline

        # Parse de datum
        from datetime import datetime as dt_class
        dag_date = dt_class.strptime(datum_iso, "%Y-%m-%d").date()
        now_date = now.date()

        # Vóór de dag → verbergen (deadline nog niet gepasseerd)
        if now_date < dag_date:
            return True
        # Na de dag → tonen (deadline gepasseerd)
        if now_date > dag_date:
            return False

        # Zelfde dag: verbergen tot deadline, tonen na deadline
        deadline = time(uur, minuut)
        return now.time() < deadline

    except Exception:  # pragma: no cover
        # Fallback naar oude weekday-based logica bij fouten
        target_idx = DAYS_INDEX.get(dag)
        if target_idx is None:
            return False
        huidige_idx = now.weekday()
        if huidige_idx < target_idx:
            return True
        if huidige_idx > target_idx:
            return False
        deadline = time(uur, minuut)
        return now.time() < deadline


def should_hide_ghosts(channel_id: int, dag: str, now: datetime) -> bool:
    """
    Bepaalt of ghostaantallen (niet gestemd) verborgen moeten worden.

    Gebruikt period-based date calculation om te bepalen of de deadline is gepasseerd.
    Ghosts worden verborgen vóór de deadline en getoond na de deadline.
    """
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

    # Haal de datum op voor deze dag vanuit het period systeem
    from apps.utils.period_dates import get_period_for_day, get_period_days

    try:
        period = get_period_for_day(dag)
        period_dates = get_period_days(period, now)
        datum_iso = period_dates.get(dag.lower())

        if datum_iso is None:
            # Fallback naar oude logica als datum niet gevonden
            target_idx = DAYS_INDEX.get(dag)
            if target_idx is None:
                return False
            huidige_idx = now.weekday()
            if huidige_idx < target_idx:
                return True
            if huidige_idx > target_idx:
                return False
            deadline = time(uur, minuut)
            return now.time() < deadline

        # Parse de datum
        from datetime import datetime as dt_class
        dag_date = dt_class.strptime(datum_iso, "%Y-%m-%d").date()
        now_date = now.date()

        # Vóór de dag → verbergen (deadline nog niet gepasseerd)
        if now_date < dag_date:
            return True
        # Na de dag → tonen (deadline gepasseerd)
        if now_date > dag_date:
            return False

        # Zelfde dag: verbergen tot deadline, tonen na deadline
        deadline = time(uur, minuut)
        return now.time() < deadline

    except Exception:  # pragma: no cover
        # Fallback naar oude weekday-based logica bij fouten
        target_idx = DAYS_INDEX.get(dag)
        if target_idx is None:
            return False
        huidige_idx = now.weekday()
        if huidige_idx < target_idx:
            return True
        if huidige_idx > target_idx:
            return False
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
# Language Settings (per channel)
# ========================================================================

SUPPORTED_LANGUAGES = {"nl", "en"}
DEFAULT_LANGUAGE = "nl"


def get_language(channel_id: int) -> str:
    """
    Get language preference for a channel.

    Returns:
        Language code ('nl' or 'en'), default: 'nl'
    """
    data = _load_data()
    return data.get(str(channel_id), {}).get("__language__", DEFAULT_LANGUAGE)


def set_language(channel_id: int, language: str) -> str:
    """
    Set language preference for a channel.

    Args:
        channel_id: The channel ID
        language: 'nl' or 'en'

    Returns:
        The new language setting

    Raises:
        ValueError: If language is not supported
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: {language}. Supported: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    data = _load_data()
    ch = data.setdefault(str(channel_id), {})
    ch["__language__"] = language
    _save_data(data)
    return language


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


def set_notification_setting(channel_id: int, key: str, enabled: bool) -> None:
    """
    Zet een specifieke notificatie instelling aan of uit.

    Args:
        channel_id: Het kanaal ID
        key: poll_opened | poll_reset | poll_closed | reminders |
             thursday_reminder | misschien | doorgaan | celebration
        enabled: True = enabled, False = disabled
    """
    data = _load_data()
    ch = data.setdefault(str(channel_id), {})
    notif_states = ch.setdefault("__notification_states__", {})

    # Als __notification_states__ leeg is (eerste keer), initialiseer alles expliciet
    if not notif_states:
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
        notif_states.update(defaults)

    notif_states[key] = enabled
    _save_data(data)


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


def get_reminder_time(channel_id: int) -> str:
    """
    Haal de reminder tijd op voor ghost notifications (niet-stemmers).

    Returns:
        Tijd string in formaat "HH:MM", default: "16:00"
    """
    data = _load_data()
    ch_data = data.get(str(channel_id), {})
    return ch_data.get("__reminder_time__", "16:00")


def set_reminder_time(channel_id: int, tijd: str) -> None:
    """
    Stel reminder tijd in voor ghost notifications (niet-stemmers).

    Args:
        channel_id: Het kanaal ID
        tijd: Tijd string in formaat "HH:MM" (bijv. "16:00")
    """
    data = _load_data()
    ch_data = data.setdefault(str(channel_id), {})
    ch_data["__reminder_time__"] = tijd
    _save_data(data)


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


# ========================================================================
# Category-Based Vote Scope (Dual Language Support)
# ========================================================================


def get_activated_channels_in_category(guild, category_id: int) -> list[int]:
    """
    Return list of channel IDs in this category that have active polls.

    A channel is considered active if:
    - It's in the specified category
    - It's not permanently disabled (via /dmk-poll-stopzetten)
    - It has settings and is not paused

    Args:
        guild: Discord guild object
        category_id: The Discord category ID

    Returns:
        List of channel IDs with active polls in this category
    """
    from apps.utils.poll_message import is_channel_disabled

    activated = []
    for channel in guild.text_channels:
        if channel.category_id != category_id:
            continue
        if is_channel_disabled(channel.id):
            continue
        # Check if channel has been activated (has poll settings and not paused)
        settings = _load_data().get(str(channel.id), {})
        if settings and not settings.get("__paused__", True):
            activated.append(channel.id)
    return activated


def get_vote_scope_channels(channel) -> list[int]:
    """
    Get all channel IDs that share votes with this channel.

    Returns [channel.id] for standalone channels (no category or only one active
    channel in category).
    Returns all activated channel IDs in the same category for linked channels.

    Args:
        channel: Discord TextChannel object

    Returns:
        List of channel IDs that share votes
    """
    channel_id = getattr(channel, "id", None)
    if channel_id is None:
        return []  # Invalid channel object

    category_id = getattr(channel, "category_id", None)
    if not category_id:
        return [channel_id]  # No category = standalone

    guild = getattr(channel, "guild", None)
    if not guild:
        return [channel_id]

    # Get all activated channels in this category
    linked = get_activated_channels_in_category(guild, category_id)

    # Only share votes if there are multiple active channels
    return linked if len(linked) > 1 else [channel_id]


# Settings that should be synced across linked channels in the same category.
# Everything except __language__ which is intentionally per-channel for dual language support.
SYNCED_SETTINGS = [
    "__poll_options__",
    "__period_settings__",
    "__reminder_time__",
    "__notification_states__",
    "__paused__",
    "__scheduled_activation__",
]


def sync_settings_to_category(channel) -> None:
    """
    Sync all shared settings from this channel to all linked channels in the category.

    When settings are changed in one channel, this function copies them to all other
    channels in the same category that share votes. This ensures consistent behavior
    across language variants.

    Settings synced: poll options, period settings, reminder time, notification states,
    paused state, and scheduled activation.

    Settings NOT synced: language (intentionally different per channel).

    Args:
        channel: Discord TextChannel object
    """
    scope_ids = get_vote_scope_channels(channel)
    if len(scope_ids) <= 1:
        return  # No other channels to sync

    channel_id = getattr(channel, "id", None)
    if channel_id is None:
        return

    source_id = str(channel_id)
    data = _load_data()
    source_settings = data.get(source_id, {})

    if not source_settings:
        return

    for cid in scope_ids:
        if cid != channel_id:
            target_id = str(cid)
            if target_id not in data:
                data[target_id] = {}
            for key in SYNCED_SETTINGS:
                if key in source_settings:
                    value = source_settings[key]
                    # Deep copy dicts, shallow copy other values
                    data[target_id][key] = value.copy() if isinstance(value, dict) else value

    _save_data(data)


# Backwards compatibility alias
sync_poll_options_to_category = sync_settings_to_category


def get_enabled_period_days(
    channel_id: int, reference_date: datetime | None = None
) -> list[dict[str, str]]:
    """
    Geef lijst van enabled dagen terug voor alle enabled periodes.

    Args:
        channel_id: Het kanaal ID
        reference_date: Optionele referentiedatum (defaults to now)

    Returns:
        Lijst van dicts met 'dag' (naam) en 'datum_iso' (YYYY-MM-DD) voor enabled dagen

    Voorbeeld: [
        {'dag': 'vrijdag', 'datum_iso': '2026-01-09'},
        {'dag': 'zaterdag', 'datum_iso': '2026-01-10'},
        {'dag': 'zondag', 'datum_iso': '2026-01-11'},
    ]
    """
    from apps.utils.period_dates import TZ, get_period_days

    now = reference_date or datetime.now(TZ)
    enabled_days = []

    # Check beide periodes
    for period in ["vr-zo", "ma-do"]:
        settings = get_period_settings(channel_id, period)
        if not settings.get("enabled", False):
            continue  # Skip disabled periods

        # Skip periodes waarvan de poll nog niet geopend is
        if not is_period_currently_open(settings, now):
            continue

        # Haal datums voor deze periode op
        period_dates = get_period_days(period, now)

        # Filter op enabled dagen (volgens poll option settings)
        for dag, datum_iso in period_dates.items():
            if not is_day_completely_disabled(channel_id, dag):
                enabled_days.append({
                    "dag": dag,
                    "datum_iso": datum_iso,
                })

    # Sorteer op datum (chronologisch) zodat de polls in de juiste volgorde verschijnen
    enabled_days.sort(key=lambda x: x["datum_iso"])

    return enabled_days


# Weekdag-index voor minuten-berekening (ma=0 t/m zo=6)
_WEEKDAG_INDEX = {
    "maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3,
    "vrijdag": 4, "zaterdag": 5, "zondag": 6,
}


def is_period_currently_open(settings: dict, now: datetime) -> bool:
    """
    Bepaal of een periode momenteel geopend is op basis van open/close instellingen.

    Converteert open_day/open_time en close_day/close_time naar "minuten sinds
    maandag 00:00" en checkt of *now* binnen het venster valt.
    Bij wrap-around (open > close): actief als now >= open OR now < close.
    """
    open_day = settings.get("open_day", "")
    open_time = settings.get("open_time", "00:00")
    close_day = settings.get("close_day", "")
    close_time = settings.get("close_time", "00:00")

    if open_day not in _WEEKDAG_INDEX or close_day not in _WEEKDAG_INDEX:
        return False

    def _to_week_minutes(day_name: str, time_str: str) -> int:
        day_idx = _WEEKDAG_INDEX[day_name]
        try:
            h, m = (int(x) for x in time_str.split(":", 1))
        except (ValueError, TypeError):
            h, m = 0, 0
        return day_idx * 24 * 60 + h * 60 + m

    open_min = _to_week_minutes(open_day, open_time)
    close_min = _to_week_minutes(close_day, close_time)
    now_min = now.weekday() * 24 * 60 + now.hour * 60 + now.minute

    if open_min < close_min:
        # Geen wrap-around: open_min <= now < close_min
        return open_min <= now_min < close_min
    else:
        # Wrap-around: now >= open_min OR now < close_min
        return now_min >= open_min or now_min < close_min


# ========================================================================
# Period Settings (Two-Period Poll System)
# ========================================================================


def get_period_settings(channel_id: int, period: str) -> dict:
    """
    Haal de period-instellingen op voor een kanaal.

    Args:
        channel_id: Het kanaal ID
        period: "vr-zo" of "ma-do"

    Returns:
        Dict met keys: enabled, close_day, close_time, open_day, open_time
        Default voor vr-zo: {enabled: True, close_day: "maandag", close_time: "00:00", open_day: "dinsdag", open_time: "20:00"}
        Default voor ma-do: {enabled: False, close_day: "vrijdag", close_time: "00:00", open_day: "vrijdag", open_time: "20:00"}
    """
    if period not in ["vr-zo", "ma-do"]:
        raise ValueError(f"Ongeldige periode: {period}. Gebruik 'vr-zo' of 'ma-do'.")

    data = _load_data()
    ch_data = data.get(str(channel_id), {})
    period_settings = ch_data.get("__period_settings__", {})

    # Defaults per periode
    defaults = {
        "vr-zo": {
            "enabled": True,
            "close_day": "maandag",
            "close_time": "00:00",
            "open_day": "dinsdag",
            "open_time": "20:00",
        },
        "ma-do": {
            "enabled": False,
            "close_day": "vrijdag",
            "close_time": "00:00",
            "open_day": "vrijdag",
            "open_time": "20:00",
        },
    }

    return period_settings.get(period, defaults[period]).copy()


def set_period_settings(
    channel_id: int,
    period: str,
    enabled: bool | None = None,
    close_day: str | None = None,
    close_time: str | None = None,
    open_day: str | None = None,
    open_time: str | None = None,
) -> dict:
    """
    Stel de period-instellingen in voor een kanaal.

    Args:
        channel_id: Het kanaal ID
        period: "vr-zo" of "ma-do"
        enabled: Optioneel, of deze periode enabled is
        close_day: Optioneel, dag waarop poll sluit/reset
        close_time: Optioneel, tijd waarop poll sluit/reset (HH:MM)
        open_day: Optioneel, dag waarop poll opent
        open_time: Optioneel, tijd waarop poll opent (HH:MM)

    Returns:
        De bijgewerkte period settings

    Raises:
        ValueError: Als validatie faalt
    """
    if period not in ["vr-zo", "ma-do"]:
        raise ValueError(f"Ongeldige periode: {period}. Gebruik 'vr-zo' of 'ma-do'.")

    # Haal huidige settings op
    current_settings = get_period_settings(channel_id, period)

    # Update alleen opgegeven velden
    if enabled is not None:
        current_settings["enabled"] = enabled
    if close_day is not None:
        current_settings["close_day"] = close_day.lower()
    if close_time is not None:
        current_settings["close_time"] = close_time
    if open_day is not None:
        current_settings["open_day"] = open_day.lower()
    if open_time is not None:
        current_settings["open_time"] = open_time

    # Validatie: close_time moet vóór open_time zijn (op dezelfde dag)
    if current_settings["close_day"] == current_settings["open_day"]:
        try:
            close_h, close_m = map(int, current_settings["close_time"].split(":"))
            open_h, open_m = map(int, current_settings["open_time"].split(":"))
            close_minutes = close_h * 60 + close_m
            open_minutes = open_h * 60 + open_m

            if close_minutes >= open_minutes:
                raise ValueError(
                    f"Sluitingstijd ({current_settings['close_time']}) moet vóór openingstijd ({current_settings['open_time']}) zijn op dezelfde dag."
                )
        except (ValueError, AttributeError) as e:
            if "invalid literal" in str(e) or "split" in str(e):
                raise ValueError("Ongeldige tijdnotatie. Gebruik HH:MM formaat.")
            raise

    # Sla op
    data = _load_data()
    ch = data.setdefault(str(channel_id), {})
    period_settings = ch.setdefault("__period_settings__", {})
    period_settings[period] = current_settings

    _save_data(data)
    return current_settings.copy()


def get_enabled_periods(channel_id: int) -> list[str]:
    """
    Haal lijst van enabled periodes op.

    Args:
        channel_id: Het kanaal ID

    Returns:
        Lijst van enabled periodes, bijv: ["vr-zo"] of ["ma-do"] of ["vr-zo", "ma-do"]
    """
    enabled = []

    for period in ["vr-zo", "ma-do"]:
        settings = get_period_settings(channel_id, period)
        if settings.get("enabled", False):
            enabled.append(period)

    return enabled


def migrate_channel_to_periods(channel_id: int) -> bool:
    """
    Migreer een kanaal van oude activation/deactivation settings naar nieuwe period settings.
    
    Args:
        channel_id: Het kanaal ID
        
    Returns:
        True als migratie succesvol was, False als al gemigreerd of geen oude settings
    """
    data = _load_data()
    ch_key = str(channel_id)
    
    if ch_key not in data:
        return False
    
    ch = data[ch_key]
    
    # Check of al gemigreerd
    if "__period_settings__" in ch:
        return False  # Al gemigreerd
    
    # Bepaal welke periodes enabled moeten zijn op basis van enabled dagen
    poll_options = ch.get("__poll_options__", {})
    
    vr_zo_days = ["vrijdag", "zaterdag", "zondag"]
    ma_do_days = ["maandag", "dinsdag", "woensdag", "donderdag"]
    
    vr_zo_enabled = any(
        poll_options.get(f"{dag}_{tijd}", False)
        for dag in vr_zo_days
        for tijd in ["19:00", "20:30"]
    )
    
    ma_do_enabled = any(
        poll_options.get(f"{dag}_{tijd}", False)
        for dag in ma_do_days
        for tijd in ["19:00", "20:30"]
    )
    
    # Als geen enkele dag enabled is, zet vr-zo enabled (default)
    if not vr_zo_enabled and not ma_do_enabled:
        vr_zo_enabled = True
    
    # Migreer oude activation/deactivation settings naar vr-zo periode
    old_activation = ch.get("__scheduled_activation__", {})
    old_deactivation = ch.get("__scheduled_deactivation__", {})
    
    # Creëer nieuwe period settings
    ch["__period_settings__"] = {
        "vr-zo": {
            "enabled": vr_zo_enabled,
            "close_day": old_deactivation.get("dag", "maandag"),
            "close_time": old_deactivation.get("tijd", "00:00"),
            "open_day": old_activation.get("dag", "dinsdag"),
            "open_time": old_activation.get("tijd", "20:00"),
        },
        "ma-do": {
            "enabled": ma_do_enabled,
            "close_day": "vrijdag",
            "close_time": "00:00",
            "open_day": "vrijdag",
            "open_time": "20:00",
        }
    }
    
    # Verwijder oude settings
    ch.pop("__scheduled_activation__", None)
    ch.pop("__scheduled_deactivation__", None)
    
    data[ch_key] = ch
    _save_data(data)
    
    return True


def migrate_all_channels_to_periods() -> dict[str, int]:
    """
    Migreer alle kanalen naar het nieuwe period systeem.
    
    Returns:
        Dict met statistieken: {"migrated": aantal, "already_migrated": aantal, "total": aantal}
    """
    data = _load_data()
    stats = {"migrated": 0, "already_migrated": 0, "total": 0}
    
    for ch_key in data.keys():
        if ch_key == "defaults":
            continue
            
        try:
            channel_id = int(ch_key)
            stats["total"] += 1
            
            if migrate_channel_to_periods(channel_id):
                stats["migrated"] += 1
            else:
                stats["already_migrated"] += 1
        except (ValueError, TypeError):
            # Skip invalid channel IDs
            continue
    
    return stats
