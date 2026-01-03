# apps/utils/notification_texts.py
#
# Centrale opslagplaats voor alle notificatieteksten in DMK-poll-bot
# DRY principe: alle teksten op één plek voor makkelijk onderhoud

from datetime import datetime
from typing import NamedTuple

from apps.utils.time_zone_helper import TimeZoneHelper


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


def _get_next_tuesday_hammertime() -> str:
    """Bereken volgende dinsdag 20:00 in Hammertime format."""
    from datetime import timedelta
    import pytz

    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz)

    # Bereken dagen tot volgende dinsdag (1 = dinsdag)
    days_until_tuesday = (1 - now.weekday()) % 7
    if days_until_tuesday == 0 and now.hour >= 20:
        days_until_tuesday = 7

    next_tuesday = now + timedelta(days=days_until_tuesday)
    next_tuesday_iso = next_tuesday.strftime("%Y-%m-%d")

    return TimeZoneHelper.nl_tijd_naar_hammertime(next_tuesday_iso, "20:00", style="F")


def _get_next_weekday_date(dag: str) -> str:
    """
    Bereken datum voor volgende occurrence van een weekdag in YYYY-MM-DD formaat.
    Als het vandaag de gevraagde dag is, return VANDAAG (niet volgende week).
    Dit zorgt ervoor dat activation binnen 7 dagen na deactivation valt.
    """
    from datetime import timedelta
    import pytz

    from apps.utils.constants import DAG_MAPPING

    target_weekday = DAG_MAPPING.get(dag.lower())
    if target_weekday is None:
        raise ValueError(f"Ongeldige dag: {dag}")

    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz)

    # Bereken dagen tot volgende occurrence
    days_ahead = (target_weekday - now.weekday()) % 7
    # Als days_ahead == 0, betekent het VANDAAG - return vandaag, niet volgende week!
    # Dit zorgt ervoor dat activatie altijd binnen 7 dagen na deactivatie valt.

    target_date = now + timedelta(days=days_ahead)
    return target_date.strftime("%Y-%m-%d")


def get_text_poll_gesloten(opening_time: str | None = None) -> str:
    """Poll gesloten tekst met opening tijd. Default is volgende dinsdag 20:00 in Hammertime."""
    if opening_time is None:
        opening_time = _get_next_tuesday_hammertime()
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
    """Formatteer opening tijd vanaf activation schedule met Hammertime. DRY functie - gedefinieerd op 1 plek, overal hergebruikt."""
    if not schedule:
        # Default: volgende dinsdag 20:00 in Hammertime
        return _get_next_tuesday_hammertime()

    act_type = schedule.get("type")
    act_tijd = schedule.get("tijd", "20:00")

    if act_type == "datum":
        act_datum = schedule.get("datum", "")
        # Converteer specifieke datum naar Hammertime
        hammertime = TimeZoneHelper.nl_tijd_naar_hammertime(
            act_datum, act_tijd, style="F"  # F = volledige datum en tijd
        )
        # Als conversie faalt, geeft TimeZoneHelper de tijd terug als fallback
        # We moeten dit detecteren en de volledige fallback string maken
        if not hammertime.startswith("<t:"):
            return f"{act_datum} om {act_tijd}"
        return hammertime
    elif act_type == "wekelijks":
        act_dag = schedule.get("dag", "dinsdag")
        # Voor wekelijkse schema's: bereken volgende occurrence en gebruik Hammertime
        try:
            next_date = _get_next_weekday_date(act_dag)
            hammertime = TimeZoneHelper.nl_tijd_naar_hammertime(
                next_date, act_tijd, style="F"
            )
            return hammertime
        except Exception:
            return f"{act_dag} om {act_tijd}"

    return _get_next_tuesday_hammertime()  # Fallback


def format_notification_text(text: str, **kwargs) -> str:
    """Formatteer notificatietekst door placeholders te vervangen met echte waarden."""
    try:
        return text.format(**kwargs)
    except KeyError:
        # Als placeholder ontbreekt, return origineel
        return text
