# apps/utils/celebration_gif.py
"""Beheer van celebration GIF selectie met gewogen randomizer."""

import json
import os
from typing import Any


TENOR_LINKS_FILE = "tenor-links.json"


def _load_tenor_links() -> list[dict[str, Any]]:
    """Laad Tenor links uit JSON bestand."""
    if not os.path.exists(TENOR_LINKS_FILE):
        return []

    try:
        with open(TENOR_LINKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # pragma: no cover
        return []


def _save_tenor_links(links: list[dict[str, Any]]) -> None:
    """Sla Tenor links op naar JSON bestand."""
    try:
        with open(TENOR_LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(links, f, indent=4, ensure_ascii=False)
    except Exception:  # pragma: no cover
        pass


def get_celebration_gif_url() -> str | None:
    """
    Selecteer een celebration GIF URL met gewogen selectie.
    Nintendo URLs worden 3x vaker gebruikt dan non-Nintendo URLs.
    Retourneert de URL met de laagste count binnen de gewichtsgroep.
    """
    links = _load_tenor_links()
    if not links:
        return None

    # Splits in Nintendo en non-Nintendo
    nintendo_links = [link for link in links if link.get("nintendo") == "yes"]
    non_nintendo_links = [link for link in links if link.get("nintendo") == "no"]

    if not nintendo_links and not non_nintendo_links:
        return None

    # Bereken gemiddelde counts
    nintendo_avg = sum(link.get("count", 0) for link in nintendo_links) / len(nintendo_links) if nintendo_links else 0
    non_nintendo_avg = sum(link.get("count", 0) for link in non_nintendo_links) / len(non_nintendo_links) if non_nintendo_links else 0

    # Gewogen selectie: Nintendo moet 3x vaker gebruikt worden
    # Als Nintendo gemiddeld >= 3x non-Nintendo count, kies non-Nintendo
    # Anders kies Nintendo (inclusief gelijke gemiddelden -> Nintendo krijgt voorkeur)
    if nintendo_links and (not non_nintendo_links or nintendo_avg <= non_nintendo_avg * 3):
        selected_pool = nintendo_links
    elif non_nintendo_links:
        selected_pool = non_nintendo_links
    else:
        selected_pool = nintendo_links  # Fallback

    # Selecteer URL met laagste count uit de gekozen pool
    selected = min(selected_pool, key=lambda x: x.get("count", 0))

    # Increment count
    selected["count"] = selected.get("count", 0) + 1

    # Sla wijzigingen op
    _save_tenor_links(links)

    return selected.get("url")
