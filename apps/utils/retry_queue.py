"""
Retry queue voor mislukte misschien conversies.

Slaat gefaalde conversies op en probeert ze opnieuw tot 2 uur is verstreken.
"""

import json
import os
from datetime import datetime, timedelta

import pytz

RETRY_QUEUE_FILE = "data/retry_queue.json"
RETRY_TIMEOUT_HOURS = 2


def _ensure_dir():
    """Zorg dat data directory bestaat."""
    os.makedirs("data", exist_ok=True)


def _load_retry_queue() -> dict:
    """Laad retry queue uit JSON file."""
    _ensure_dir()
    if not os.path.exists(RETRY_QUEUE_FILE):
        return {}
    try:
        with open(RETRY_QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # pragma: no cover
        return {}


def _save_retry_queue(queue: dict):
    """Sla retry queue op naar JSON file."""
    _ensure_dir()
    try:
        with open(RETRY_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    except Exception:  # pragma: no cover
        pass


def add_failed_conversion(guild_id: str, channel_id: str, user_id: str, dag: str):
    """
    Voeg mislukte misschien conversie toe aan retry queue.

    Args:
        guild_id: Guild ID als string
        channel_id: Channel ID als string
        user_id: User ID als string
        dag: Dag van de week (bijv. "vrijdag")
    """
    queue = _load_retry_queue()

    # Unieke key per conversie
    key = f"conversion:{guild_id}:{channel_id}:{user_id}:{dag}"

    # Alleen toevoegen als nog niet in queue (voorkom duplicaten)
    if key not in queue:
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        queue[key] = {
            "type": "conversion",
            "guild_id": guild_id,
            "channel_id": channel_id,
            "user_id": user_id,
            "dag": dag,
            "first_attempt": now.isoformat(),
            "retry_count": 0,
        }
        _save_retry_queue(queue)


def add_failed_reset(guild_id: str, channel_id: str):
    """
    Voeg mislukte vote reset toe aan retry queue.

    Args:
        guild_id: Guild ID als string
        channel_id: Channel ID als string
    """
    queue = _load_retry_queue()

    # Unieke key per reset (geen user_id/dag want reset is voor hele kanaal)
    key = f"reset:{guild_id}:{channel_id}"

    # Alleen toevoegen als nog niet in queue (voorkom duplicaten)
    if key not in queue:
        tz = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(tz)
        queue[key] = {
            "type": "reset",
            "guild_id": guild_id,
            "channel_id": channel_id,
            "first_attempt": now.isoformat(),
            "retry_count": 0,
        }
        _save_retry_queue(queue)


def get_pending_conversions() -> list[dict]:
    """
    Haal alle pending conversies op die opnieuw geprobeerd moeten worden.

    Returns:
        List van dicts met: guild_id, channel_id, user_id, dag, first_attempt, retry_count, key
    """
    queue = _load_retry_queue()
    result = []

    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz)

    for key, data in queue.items():
        try:
            first_attempt = datetime.fromisoformat(data["first_attempt"])
            if first_attempt.tzinfo is None:
                first_attempt = tz.localize(first_attempt)

            # Check of timeout is verstreken (2 uur)
            elapsed = now - first_attempt
            if elapsed < timedelta(hours=RETRY_TIMEOUT_HOURS):
                # Nog binnen timeout - probeer opnieuw
                result.append({**data, "key": key, "elapsed_seconds": elapsed.total_seconds()})
        except Exception:  # pragma: no cover
            # Skip ongeldige entries
            continue

    return result


def get_expired_conversions() -> list[dict]:
    """
    Haal alle conversies op die timeout hebben bereikt (>2 uur).

    Returns:
        List van dicts met: guild_id, channel_id, user_id, dag, first_attempt, retry_count, key
    """
    queue = _load_retry_queue()
    result = []

    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz)

    for key, data in queue.items():
        try:
            first_attempt = datetime.fromisoformat(data["first_attempt"])
            if first_attempt.tzinfo is None:
                first_attempt = tz.localize(first_attempt)

            # Check of timeout is verstreken (2 uur)
            elapsed = now - first_attempt
            if elapsed >= timedelta(hours=RETRY_TIMEOUT_HOURS):
                # Timeout bereikt - stuur error message
                result.append({**data, "key": key, "elapsed_seconds": elapsed.total_seconds()})
        except Exception:  # pragma: no cover
            # Skip ongeldige entries
            continue

    return result


def remove_from_queue(key: str):
    """
    Verwijder conversie uit retry queue (na success of timeout).

    Args:
        key: Unieke key (guild_id:channel_id:user_id:dag)
    """
    queue = _load_retry_queue()
    if key in queue:
        del queue[key]
        _save_retry_queue(queue)


def increment_retry_count(key: str):
    """
    Verhoog retry count voor deze conversie.

    Args:
        key: Unieke key (guild_id:channel_id:user_id:dag)
    """
    queue = _load_retry_queue()
    if key in queue:
        queue[key]["retry_count"] = queue[key].get("retry_count", 0) + 1
        _save_retry_queue(queue)


def clear_retry_queue():
    """Verwijder alle entries uit retry queue (voor testing)."""
    _ensure_dir()
    try:
        with open(RETRY_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    except Exception:  # pragma: no cover
        pass
