# apps/entities/poll_option.py

import json
import os

from discord import ButtonStyle

OPTIONS_FILE = "poll_options.json"

# Standaardoptie (als JSON ontbreekt of stuk is)
_DEFAULTS = [
    {"dag": "vrijdag", "tijd": "om 19:00 uur", "emoji": "🔴"},
    {"dag": "vrijdag", "tijd": "om 20:30 uur", "emoji": "🟠"},
    {"dag": "vrijdag", "tijd": "misschien", "emoji": "Ⓜ️"},
    {"dag": "vrijdag", "tijd": "niet meedoen", "emoji": "❌"},
    {"dag": "zaterdag", "tijd": "om 19:00 uur", "emoji": "🟡"},
    {"dag": "zaterdag", "tijd": "om 20:30 uur", "emoji": "⚪"},
    {"dag": "zaterdag", "tijd": "misschien", "emoji": "Ⓜ️"},
    {"dag": "zaterdag", "tijd": "niet meedoen", "emoji": "❌"},
    {"dag": "zondag", "tijd": "om 19:00 uur", "emoji": "🟢"},
    {"dag": "zondag", "tijd": "om 20:30 uur", "emoji": "🔵"},
    {"dag": "zondag", "tijd": "misschien", "emoji": "Ⓜ️"},
    {"dag": "zondag", "tijd": "niet meedoen", "emoji": "❌"},
]

# Map internal tijd keys to i18n TIME_LABELS keys
_TIJD_TO_I18N_KEY = {
    "om 19:00 uur": "19:00",
    "om 20:30 uur": "20:30",
    "misschien": "maybe",
    "niet meedoen": "not_joining",
}


class PollOption:
    def __init__(
        self,
        dag: str,
        tijd: str,
        emoji: str,
        stijl=ButtonStyle.secondary,
        channel_id: int = 0,
    ):
        self.dag = dag
        self.tijd = tijd
        self.emoji = emoji
        self.stijl = stijl
        self._channel_id = channel_id
        # Generate localized label
        self.label = self._make_label()

    def _make_label(self) -> str:
        """Generate localized button label."""
        from apps.utils.i18n import get_day_name, get_time_label

        dag_display = get_day_name(self._channel_id, self.dag).capitalize()
        # Map internal tijd to i18n key
        tijd_key = _TIJD_TO_I18N_KEY.get(self.tijd, self.tijd)
        tijd_display = get_time_label(self._channel_id, tijd_key)
        return f"{self.emoji} {dag_display} {tijd_display}"


def _load_raw_options():
    if not os.path.exists(OPTIONS_FILE):
        return list(_DEFAULTS)
    try:
        with open(OPTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Eenvoudige validatie
        ok = [
            o
            for o in data
            if isinstance(o, dict) and "dag" in o and "tijd" in o and "emoji" in o
        ]
        return ok if ok else list(_DEFAULTS)
    except Exception:  # pragma: no cover
        return list(_DEFAULTS)


def get_poll_options(channel_id: int = 0) -> list[PollOption]:
    """Live inladen bij elke aanroep, with localized labels."""
    items = _load_raw_options()
    return [
        PollOption(o["dag"], o["tijd"], o["emoji"], channel_id=channel_id)
        for o in items
    ]


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
