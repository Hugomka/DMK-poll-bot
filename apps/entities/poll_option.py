# apps/entities/poll_option.py
import json
import os
from discord import ButtonStyle

OPTIONS_FILE = "poll_options.json"

# Fallback (als JSON ontbreekt of stuk is)
_DEFAULTS = [
    {"dag": "vrijdag",  "tijd": "om 19:00 uur", "emoji": "🔴"},
    {"dag": "vrijdag",  "tijd": "om 20:30 uur", "emoji": "🟠"},
    {"dag": "vrijdag",  "tijd": "misschien",    "emoji": "Ⓜ️"},
    {"dag": "vrijdag",  "tijd": "niet meedoen", "emoji": "❌"},

    {"dag": "zaterdag", "tijd": "om 19:00 uur", "emoji": "🟡"},
    {"dag": "zaterdag", "tijd": "om 20:30 uur", "emoji": "⚪"},
    {"dag": "zaterdag", "tijd": "misschien",    "emoji": "Ⓜ️"},
    {"dag": "zaterdag", "tijd": "niet meedoen", "emoji": "❌"},

    {"dag": "zondag",   "tijd": "om 19:00 uur", "emoji": "🟢"},
    {"dag": "zondag",   "tijd": "om 20:30 uur", "emoji": "🔵"},
    {"dag": "zondag",   "tijd": "misschien",    "emoji": "Ⓜ️"},
    {"dag": "zondag",   "tijd": "niet meedoen", "emoji": "❌"},
]

class PollOption:
    def __init__(self, dag: str, tijd: str, emoji: str, stijl=ButtonStyle.secondary):
        self.dag = dag
        self.tijd = tijd
        self.emoji = emoji
        self.stijl = stijl
        self.label = f"{emoji} {dag.capitalize()} {tijd}"

def _load_raw_options():
    if not os.path.exists(OPTIONS_FILE):
        return list(_DEFAULTS)
    try:
        with open(OPTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # eenvoudige validatie
        ok = [o for o in data if isinstance(o, dict) and "dag" in o and "tijd" in o and "emoji" in o]
        return ok if ok else list(_DEFAULTS)
    except Exception:
        return list(_DEFAULTS)

def get_poll_options() -> list[PollOption]:
    if not os.path.exists(OPTIONS_FILE):
        return []
    with open(OPTIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [PollOption(**item) for item in data]

def is_valid_option(dag: str, tijd: str) -> bool:
    return any(o.dag == dag and o.tijd == tijd for o in get_poll_options())

def list_days() -> list[str]:
    """Unieke dagen in JSON-volgorde."""
    seen = set()
    days = []
    for o in _load_raw_options():
        d = o["dag"]
        if d not in seen:
            seen.add(d)
            days.append(d)
    return days

def is_valid_option(dag: str, tijd: str) -> bool:
    for o in _load_raw_options():
        if o["dag"] == dag and o["tijd"] == tijd:
            return True
    return False
