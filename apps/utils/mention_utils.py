# apps/utils/mention_utils.py
#
# Helpers voor privacy-vriendelijke mentions in notificaties.
# - Tijdelijke mentions (2 seconden zichtbaar)
# - Persistente mentions (tot 23:00)

import asyncio
from datetime import datetime
from typing import Any, Optional

import pytz

from apps.utils.discord_client import safe_call
from apps.utils.poll_message import update_notification_message

TZ = pytz.timezone("Europe/Amsterdam")


async def send_temporary_mention(
    channel: Any,
    mentions: str,
    text: str,
    delay: float = 2.0,
    show_button: bool = False,
    dag: str = "",
    leading_time: str = "",
) -> None:
    """
    Stuur een tijdelijke mention via het notificatiebericht.

    De mentions verschijnen voor `delay` seconden (standaard 2),
    waarna ze automatisch worden verwijderd. Gebruikers ontvangen
    wel een notificatie op hun apparaat.

    Args:
        channel: Het Discord kanaal object
        mentions: Mentions string, bijv. "@user1, @user2"
        text: De tekst die onder de mentions verschijnt
        delay: Hoeveel seconden de mentions zichtbaar blijven (standaard 2.0)
        show_button: Of de "Stem nu" knop getoond moet worden
        dag: De dag voor de Stem Nu knop
        leading_time: De leidende tijd voor de Stem Nu knop
    """
    # Stap 1: Update notificatiebericht met mentions (en optioneel knop)
    await update_notification_message(
        channel,
        mentions=mentions,
        text=text,
        show_button=show_button,
        dag=dag,
        leading_time=leading_time,
    )

    # Stap 2: Wacht de delay periode
    await asyncio.sleep(delay)

    # Stap 3: Verwijder mentions (tekst en knop blijven)
    await update_notification_message(
        channel,
        mentions="",
        text=text,
        show_button=show_button,
        dag=dag,
        leading_time=leading_time,
    )


async def send_persistent_mention(channel: Any, message: str) -> Optional[Any]:
    """
    Stuur een "doorgaan" notificatie met mentions die blijven tot 23:00.

    Deze functie stuurt een normaal bericht (niet via notificatie-bericht)
    en plant automatisch de cleanup om 23:00 uur.

    Args:
        channel: Het Discord kanaal object
        message: Het volledige bericht inclusief mentions

    Returns:
        Het verzonden bericht object, of None bij fout
    """
    send_func = getattr(channel, "send", None)
    if send_func is None:
        return None

    try:
        # Stuur het bericht
        msg = await safe_call(send_func, message)

        if msg is not None:
            # Bereken tijd tot 23:00
            now = datetime.now(TZ)
            cleanup_time = now.replace(hour=23, minute=0, second=0, microsecond=0)

            # Als 23:00 al geweest is vandaag, niet plannen
            if now >= cleanup_time:
                return msg

            delay_seconds = (cleanup_time - now).total_seconds()

            # Plan de cleanup
            asyncio.create_task(_cleanup_mentions_at_23(msg, delay_seconds))

        return msg
    except Exception as e:  # pragma: no cover
        print(f"❌ Fout bij versturen persistent mention: {e}")
        return None


async def _cleanup_mentions_at_23(message: Any, delay_seconds: float) -> None:
    """
    Interne helper: verwijder mentions uit een bericht om 23:00.

    Args:
        message: Het Discord message object
        delay_seconds: Hoeveel seconden te wachten
    """
    try:
        await asyncio.sleep(delay_seconds)

        # Edit het bericht: verwijder alle mentions
        content = getattr(message, "content", "")
        if not content:
            return

        # Verwijder alle Discord mentions (<@123>, <@&456>, @everyone, @here)
        import re

        cleaned = re.sub(r"<@!?\d+>|<@&\d+>|@everyone|@here", "", content)

        # Probeer te editen
        if hasattr(message, "edit"):
            await safe_call(message.edit, content=cleaned.strip())
    except Exception:  # pragma: no cover
        # Stil falen (bericht kan verwijderd zijn, bot heeft geen rechten, etc.)
        pass
