# apps/utils/tenor_sync.py
"""
Sync tenor-links.template.json naar tenor-links.json met behoud van counts.

Deze module synchroniseert de GIF lijst bij bot startup:
- Nieuwe GIFs uit template worden toegevoegd met count: 0
- Verwijderde GIFs uit template worden verwijderd uit runtime
- Bestaande GIFs behouden hun count waarde
"""

import json
import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)


class TenorLink(TypedDict):
    """Type definitie voor een Tenor GIF link."""

    url: str
    nintendo: str
    count: int


def needs_sync() -> bool:
    """
    Controleer of sync nodig is (verschil tussen template en runtime, exclusief counts).

    Returns:
        True als er nieuwe of verwijderde GIFs zijn, False als alleen counts verschillen
    """
    template_path = "tenor-links.template.json"
    runtime_path = "tenor-links.json"

    # Als runtime niet bestaat, sync is nodig
    if not os.path.exists(runtime_path):
        return True

    # Als template niet bestaat, geen sync mogelijk
    if not os.path.exists(template_path):
        return False

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_links: list[TenorLink] = json.load(f)
        with open(runtime_path, "r", encoding="utf-8") as f:
            runtime_links: list[TenorLink] = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Fout bij vergelijken template/runtime: {e}")
        return False

    # Vergelijk URL sets (negeer counts)
    template_urls = {link["url"] for link in template_links}
    runtime_urls = {link["url"] for link in runtime_links}

    # Sync nodig als er nieuwe of verwijderde GIFs zijn
    return template_urls != runtime_urls


def sync_tenor_links() -> None:
    """
    Sync tenor-links.template.json naar tenor-links.json met behoud van counts.

    Logic:
    1. Laad template (bron van waarheid voor GIF lijst)
    2. Laad runtime bestand (bevat counts)
    3. Merge: nieuwe GIFs toevoegen, oude counts behouden, verwijderde GIFs weghalen
    4. Sla gesynchroniseerde lijst op

    Als tenor-links.json niet bestaat, wordt deze automatisch aangemaakt vanuit template.
    """
    template_path = "tenor-links.template.json"
    runtime_path = "tenor-links.json"

    # Stap 1: Laad template (bron van waarheid)
    if not os.path.exists(template_path):
        logger.warning(
            f"{template_path} niet gevonden - sync overgeslagen. "
            "Maak eerst een template bestand aan."
        )
        return

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_links: list[TenorLink] = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Fout bij laden {template_path}: {e}")
        return

    # Stap 2: Laad runtime bestand (of maak leeg aan als niet bestaat)
    runtime_links: list[TenorLink] = []
    if os.path.exists(runtime_path):
        try:
            with open(runtime_path, "r", encoding="utf-8") as f:
                runtime_links = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(
                f"Fout bij laden {runtime_path}: {e} - bestand wordt opnieuw aangemaakt"
            )
            runtime_links = []
    else:
        # Runtime bestand bestaat niet - eerste keer, log dit
        logger.info(
            f"{runtime_path} niet gevonden - wordt aangemaakt vanuit template"
        )

    # Stap 3: Bouw counts lookup (URL -> count)
    counts_by_url = {link["url"]: link["count"] for link in runtime_links}

    # Stap 4: Merge - template is leidend, counts worden behouden
    synced_links: list[TenorLink] = []
    for template_link in template_links:
        url = template_link["url"]
        # Behoud bestaande count, of gebruik 0 voor nieuwe GIFs
        count = counts_by_url.get(url, 0)

        synced_links.append(
            {"url": url, "nintendo": template_link["nintendo"], "count": count}
        )

    # Stap 5: Log wijzigingen
    template_urls = {link["url"] for link in template_links}
    runtime_urls = {link["url"] for link in runtime_links}

    nieuwe_gifs = template_urls - runtime_urls
    verwijderde_gifs = runtime_urls - template_urls

    if nieuwe_gifs:
        logger.info(f"✅ {len(nieuwe_gifs)} nieuwe GIF(s) toegevoegd")
        for url in nieuwe_gifs:
            logger.debug(f"  + {url}")

    if verwijderde_gifs:
        logger.info(f"🗑️  {len(verwijderde_gifs)} GIF(s) verwijderd")
        for url in verwijderde_gifs:
            # Log count van verwijderde GIF (voor debug)
            old_count = counts_by_url.get(url, 0)
            logger.debug(f"  - {url} (had {old_count} uses)")

    if not nieuwe_gifs and not verwijderde_gifs:
        logger.info("✓ Tenor GIF lijst is up-to-date")

    # Stap 6: Sla gesynchroniseerde lijst op
    try:
        with open(runtime_path, "w", encoding="utf-8") as f:
            json.dump(synced_links, f, indent=4, ensure_ascii=False)
        logger.info(f"💾 {runtime_path} bijgewerkt ({len(synced_links)} GIFs)")
    except IOError as e:
        logger.error(f"Fout bij opslaan {runtime_path}: {e}")


def get_tenor_links() -> list[TenorLink]:
    """
    Haal de huidige tenor links op (runtime bestand).

    Returns:
        Lijst van tenor links met counts
    """
    runtime_path = "tenor-links.json"

    if not os.path.exists(runtime_path):
        logger.warning(f"{runtime_path} niet gevonden - sync wordt uitgevoerd")
        sync_tenor_links()

    try:
        with open(runtime_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Fout bij laden {runtime_path}: {e}")
        return []


def increment_gif_count(url: str) -> None:
    """
    Verhoog de count voor een specifieke GIF URL.

    Args:
        url: De Tenor GIF URL
    """
    runtime_path = "tenor-links.json"
    links = get_tenor_links()

    # Zoek de GIF en verhoog count
    for link in links:
        if link["url"] == url:
            link["count"] += 1
            break
    else:
        logger.warning(f"GIF URL niet gevonden in lijst: {url}")
        return

    # Sla op
    try:
        with open(runtime_path, "w", encoding="utf-8") as f:
            json.dump(links, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Fout bij opslaan {runtime_path}: {e}")
