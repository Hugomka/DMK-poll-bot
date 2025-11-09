# apps/utils/notification_texts.py
#
# Centrale opslagplaats voor alle notificatieteksten in DMK-poll-bot
# DRY principe: alle teksten op één plek voor makkelijk onderhoud

from datetime import datetime
from typing import NamedTuple


class NotificationText(NamedTuple):
    """Notificatietekst met naam en content."""

    name: str  # Korte beschrijving voor dropdown
    content: str  # Volledige notificatietekst


def get_text_herinnering_dag(dag: str, non_voters: list[str] | None = None) -> str:
    """Herinnering voor specifieke dag met optioneel aantal niet-stemmers."""
    if non_voters:
        count = len(non_voters)
        count_text = f"**{count} {'lid' if count == 1 else 'leden'}** {'heeft' if count == 1 else 'hebben'} nog niet gestemd. "
    else:
        count_text = ""

    return (
        f" DMK-poll - **{dag}**\n"
        f"{count_text}Als je nog niet gestemd hebt voor **{dag}**, doe dat dan a.u.b. zo snel mogelijk."
    )


def get_text_herinnering_weekend(non_voters: list[str] | None = None) -> str:
    """Herinnering voor het weekend met optioneel aantal niet-stemmers."""
    if non_voters:
        count = len(non_voters)
        count_text = f"**{count} {'lid' if count == 1 else 'leden'}** {'heeft' if count == 1 else 'hebben'} nog niet gestemd. "
    else:
        count_text = ""

    return (
        f"DMK-poll - herinnering\n"
        f"{count_text}Als je nog niet gestemd hebt voor dit weekend, doe dat dan a.u.b. zo snel mogelijk."
    )


def get_text_poll_gesloten(opening_time="dinsdag om 20:00 uur") -> str:
    """Poll gesloten tekst met opening tijd. Default is dinsdag 20:00 (zie poll_settings defaults)."""
    return (
        f"Deze poll is gesloten en gaat pas **{opening_time}** weer open. "
        "Dank voor je deelname."
    )


# Alle standaard notificatieteksten
NOTIFICATION_TEXTS = [
    NotificationText(
        name="Poll geopend",
        content="De DMK-poll-bot is zojuist aangezet. Veel plezier met de stemmen! 🎮",
    ),
    NotificationText(
        name="Poll gereset",
        content="De poll is zojuist gereset voor het nieuwe weekend. Je kunt weer stemmen. Veel plezier!",
    ),
    NotificationText(name="Poll gesloten", content=get_text_poll_gesloten()),
    NotificationText(
        name="Herinnering vrijdag", content=get_text_herinnering_dag("vrijdag")
    ),
    NotificationText(
        name="Herinnering zaterdag", content=get_text_herinnering_dag("zaterdag")
    ),
    NotificationText(
        name="Herinnering zondag", content=get_text_herinnering_dag("zondag")
    ),
    NotificationText(
        name="Herinnering weekend", content=get_text_herinnering_weekend()
    ),
    NotificationText(
        name="Felicitatie (iedereen gestemd)",
        content="🎉 Geweldig! Iedereen heeft gestemd!\nBedankt voor jullie inzet dit weekend!",
    ),
]


def get_notification_by_name(name: str) -> NotificationText | None:
    """Zoek notificatietekst op naam."""
    for notif in NOTIFICATION_TEXTS:
        if notif.name == name:
            return notif
    return None


def get_all_notification_names() -> list[str]:
    """Geef lijst van alle notificatienamen voor dropdown."""
    return [notif.name for notif in NOTIFICATION_TEXTS]


def format_opening_time_from_schedule(schedule: dict | None) -> str:
    """Formatteer opening tijd vanaf activation schedule. DRY functie - gedefinieerd op 1 plek, overal hergebruikt."""
    if not schedule:
        return "dinsdag om 20:00 uur"  # Default

    weekday_names = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]

    act_type = schedule.get("type")
    act_tijd = schedule.get("tijd", "20:00")

    if act_type == "datum":
        act_datum = schedule.get("datum", "")
        try:
            datum_obj = datetime.strptime(act_datum, "%Y-%m-%d")
            datum_display = datum_obj.strftime("%d-%m-%Y")
            dag_naam = weekday_names[datum_obj.weekday()]
            return f"{dag_naam} {datum_display} om {act_tijd}"
        except Exception:
            return f"{act_datum} om {act_tijd}"
    elif act_type == "wekelijks":
        act_dag = schedule.get("dag", "dinsdag")
        return f"{act_dag} om {act_tijd}"

    return "dinsdag om 20:00 uur"  # Fallback


def format_notification_text(text: str, **kwargs) -> str:
    """Formatteer notificatietekst door placeholders te vervangen met echte waarden."""
    try:
        return text.format(**kwargs)
    except KeyError:
        # Als placeholder ontbreekt, return origineel
        return text
