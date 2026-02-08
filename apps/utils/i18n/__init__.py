# apps/utils/i18n/__init__.py
"""
Internationalization (i18n) module for DMK-poll-bot.

Usage:
    from apps.utils.i18n import t, get_day_name, get_time_label

    # Get translated text
    text = t(channel_id, "UI.vote_success")

    # Get translated day name
    dag = get_day_name(channel_id, "vrijdag")  # "vrijdag" (nl) or "Friday" (en)

    # With placeholders
    text = t(channel_id, "NOTIFICATIONS.reminder_day", dag="vrijdag", count_text="3 leden")
"""

from __future__ import annotations

from typing import Any

from apps.utils.poll_settings import get_language

from . import en, nl

LANGUAGES: dict[str, Any] = {
    "nl": nl,
    "en": en,
}

DEFAULT_LANGUAGE = "nl"

# Internal day name mapping (Dutch internal -> English key)
INTERNAL_DAY_TO_KEY = {
    "maandag": "monday",
    "dinsdag": "tuesday",
    "woensdag": "wednesday",
    "donderdag": "thursday",
    "vrijdag": "friday",
    "zaterdag": "saturday",
    "zondag": "sunday",
}


def _get_module(channel_id: int) -> Any:
    """Get the translation module for a channel."""
    lang = get_language(channel_id)
    return LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE])


def t(channel_id: int, key: str, **kwargs: Any) -> str:
    """
    Get translated text for a channel.

    Args:
        channel_id: The channel ID
        key: Dot-notation key like "UI.vote_success" or "NOTIFICATIONS.poll_opened"
        **kwargs: Placeholder values for .format()

    Returns:
        Translated string with placeholders filled in
    """
    module = _get_module(channel_id)

    # Parse dot-notation key (e.g., "UI.vote_success")
    parts = key.split(".", 1)
    if len(parts) != 2:
        return f"[INVALID KEY: {key}]"

    category, name = parts
    texts = getattr(module, category, None)

    if texts is None or not isinstance(texts, dict):
        # Fallback to Dutch
        texts = getattr(nl, category, {})

    text = texts.get(name)
    if text is None:
        # Try Dutch fallback
        fallback_texts = getattr(nl, category, {})
        text = fallback_texts.get(name, f"[MISSING: {key}]")

    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text

    return text


def get_day_name(channel_id: int, internal_name: str) -> str:
    """
    Convert internal Dutch day name to localized name.

    Args:
        channel_id: The channel ID
        internal_name: Internal day name (always Dutch: "maandag", "vrijdag", etc.)

    Returns:
        Localized day name
    """
    module = _get_module(channel_id)
    key = INTERNAL_DAY_TO_KEY.get(internal_name.lower(), internal_name)
    return module.DAY_NAMES.get(key, internal_name.capitalize())


def get_time_label(channel_id: int, internal_time: str) -> str:
    """
    Convert internal time to localized label.

    Args:
        channel_id: The channel ID
        internal_time: "om 19:00 uur", "om 20:30 uur", "misschien", or "niet meedoen"

    Returns:
        Localized time label
    """
    module = _get_module(channel_id)

    # Map internal Dutch time formats to translation keys
    time_map = {
        "om 19:00 uur": "19:00",
        "om 20:30 uur": "20:30",
        "misschien": "maybe",
        "niet meedoen": "not_joining",
    }
    key = time_map.get(internal_time, internal_time)
    return module.TIME_LABELS.get(key, internal_time)


def pluralize_nl(count: int, singular: str, plural: str) -> str:
    """Dutch pluralization helper."""
    return singular if count == 1 else plural


def get_count_text(channel_id: int, count: int) -> str:
    """
    Get 'X lid/leden heeft/hebben nog niet gestemd' text.

    Args:
        channel_id: The channel ID
        count: Number of non-voters

    Returns:
        Formatted count text with proper pluralization
    """
    lang = get_language(channel_id)

    if lang == "en":
        word = "member" if count == 1 else "members"
        verb = "has" if count == 1 else "have"
        return f"**{count} {word}** {verb} not voted yet. "
    else:
        word = "lid" if count == 1 else "leden"
        verb = "heeft" if count == 1 else "hebben"
        return f"**{count} {word}** {verb} nog niet gestemd. "


__all__ = [
    "t",
    "get_day_name",
    "get_time_label",
    "get_count_text",
    "get_language",
    "LANGUAGES",
]
