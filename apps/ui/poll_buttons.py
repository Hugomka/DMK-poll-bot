# apps/ui/poll_buttons.py

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from discord import ButtonStyle, Interaction
from discord.ui import Button, View

from apps.entities.poll_option import get_poll_options
from apps.logic.visibility import is_vote_button_visible
from apps.utils.discord_client import safe_call
from apps.utils.poll_message import (
    check_all_voted_celebration,
    clear_message_id,
    update_poll_messages_for_category,
)
from apps.utils.poll_settings import (
    get_enabled_rolling_window_days,
    get_poll_option_state,
    is_paused,
)
from apps.utils.poll_storage import get_user_votes, toggle_vote
from apps.utils.time_zone_helper import TimeZoneHelper

def _get_header_tmpl(channel_id: int, dag: str) -> str:
    """Get localized header template for voting interface."""
    from apps.utils.i18n import get_day_name, t

    dag_display = get_day_name(channel_id, dag)
    return t(channel_id, "UI.choose_times_header", dag=dag_display)


async def _cleanup_outdated_messages_for_channel(channel, channel_id: int) -> None:
    """
    Verwijder ALLE bot-berichten in kanaal en recreate alles opnieuw.

    ALLEEN als er outdated berichten zijn! Als alles up-to-date is, skip cleanup.

    Strategie: Check of er bot-berichten bestaan van vóór de laatste reset threshold.
    - Reset threshold = zondag 20:30 (begin van nieuwe week)
    - Als ALLE bot-berichten zijn van ná de threshold: skip cleanup
    - Als ÉÉN of meer bot-berichten zijn van vóór de threshold: cleanup nodig
    """
    from datetime import datetime, timedelta
    import pytz
    from apps.utils.constants import DAG_NAMEN
    from apps.utils.discord_client import fetch_message_or_none
    from apps.utils.message_builder import build_poll_message_for_day_async
    from apps.utils.poll_message import (
        create_notification_message,
        get_message_id,
        save_message_id,
    )

    # STAP 0: Check of cleanup nodig is (vermijd onnodige deletes/recreates)
    try:
        # Bereken reset threshold (zondag 20:30 van huidige week)
        TZ = pytz.timezone("Europe/Amsterdam")
        now = datetime.now(TZ)
        # 6 = zondag; bereken aantal dagen sinds zondag
        days_since_sun = (now.weekday() - 6) % 7
        last_sunday = now.replace(hour=20, minute=30, second=0, microsecond=0) - timedelta(days=days_since_sun)

        # Als we vóór zondag 20:30 zitten, pak zondag van vorige week
        if now < last_sunday:
            last_sunday -= timedelta(days=7)

        reset_threshold = last_sunday
        print(f"Reset threshold (begin huidige week): {reset_threshold.strftime('%Y-%m-%d %H:%M')}", flush=True)

        # Check of alle opgeslagen poll-berichten van ná de threshold zijn
        needs_cleanup = False
        for dag_naam in DAG_NAMEN:
            mid = get_message_id(channel_id, dag_naam)
            if mid:
                msg = await fetch_message_or_none(channel, mid)
                if msg is None:
                    # Bericht bestaat niet meer - cleanup nodig
                    print(f"WARNING: Bericht voor {dag_naam} bestaat niet meer (ID: {mid})")
                    needs_cleanup = True
                    break
                # Check of bericht van vóór reset threshold is
                msg_created = msg.created_at
                if msg_created < reset_threshold:
                    # Outdated bericht gevonden
                    print(f"WARNING: Outdated bericht voor {dag_naam}: {msg_created.strftime('%Y-%m-%d %H:%M')} < {reset_threshold.strftime('%Y-%m-%d %H:%M')}")
                    needs_cleanup = True
                    break

        if not needs_cleanup:
            print(f"INFO: Cleanup overgeslagen: alle poll-berichten zijn van na reset threshold in kanaal {channel_id}")
            return

        print(f"INFO: Cleanup nodig: outdated berichten gevonden in kanaal {channel_id}")

    except Exception as e:  # pragma: no cover
        # Bij twijfel, voer cleanup uit
        print(f"WARNING: Check mislukt, voer cleanup uit: {e}")
        needs_cleanup = True

    # STAP 1: Verwijder ALLE bot-berichten in kanaal (simpel en betrouwbaar)
    try:
        if not hasattr(channel, "history"):
            return

        bot_user = channel.guild.me if hasattr(channel, "guild") else None
        if not bot_user:
            return

        # Verzamel ALLE berichten van de bot (geen markers checken)
        messages_to_delete = []
        async for message in channel.history(limit=100):  # type: ignore[attr-defined]
            if message.author.id == bot_user.id:
                messages_to_delete.append(message)

        print(f"INFO: Cleanup: Gevonden {len(messages_to_delete)} bot-berichten om te verwijderen")

        # Verwijder alle bot-berichten
        for msg in messages_to_delete:
            await safe_call(msg.delete)

        # Clear alle opgeslagen message IDs
        for dag_naam in DAG_NAMEN:
            clear_message_id(channel_id, dag_naam)
        clear_message_id(channel_id, "stemmen")
        clear_message_id(channel_id, "opening")
        clear_message_id(channel_id, "notification_persistent")
        clear_message_id(channel_id, "notification")

        print(f"INFO: Cleanup voltooid: {len(messages_to_delete)} berichten verwijderd")

    except Exception as e:  # pragma: no cover
        print(f"WARNING: Cleanup fout in kanaal {channel_id}: {e}")
        import traceback
        traceback.print_exc()  # Print volledige error voor debugging

    # STAP 2: Recreate ALLE berichten (net zoals /dmk-poll-on)
    try:
        dagen_info = get_enabled_rolling_window_days(channel_id, dag_als_vandaag=None)
        guild = channel.guild if hasattr(channel, "guild") else None
        gid_val = getattr(guild, "id", "0") if guild is not None else "0"

        # 1. Opening message (Welkom bij de DMK-poll)
        from apps.commands.poll_lifecycle import _load_opening_message

        opening_text = _load_opening_message(channel_id=channel_id)
        opening_msg = await safe_call(channel.send, content=opening_text)
        if opening_msg is not None:
            save_message_id(channel_id, "opening", opening_msg.id)

        # 2. Day poll messages (DMK-poll voor Maandag, etc.)
        for day_info in dagen_info:
            dag = day_info["dag"]
            datum_iso = day_info["datum_iso"]
            content = await build_poll_message_for_day_async(
                dag, gid_val, channel_id, guild=guild, channel=channel, datum_iso=datum_iso
            )
            msg = await safe_call(channel.send, content=content, view=None)
            if msg is not None:
                save_message_id(channel_id, dag, msg.id)

        # 3. Stemmen button message
        from apps.ui.poll_buttons import OneStemButtonView
        from apps.utils.i18n import t

        tekst = t(channel_id, "UI.click_vote_button")
        paused = is_paused(channel_id)
        view = OneStemButtonView(paused=paused, channel_id=channel_id)
        s_msg = await safe_call(channel.send, content=tekst, view=view)
        if s_msg is not None:
            save_message_id(channel_id, "stemmen", s_msg.id)

        # 4. Notification message (persistent)
        await create_notification_message(channel, activation_hammertime=None)

    except Exception as e:  # pragma: no cover
        print(f"WARNING: Fout bij recreaten berichten in kanaal {channel_id}: {e}")


def _get_timezone_legend(dag: str, channel_id: int) -> str:
    """Genereer compacte tijdzone legenda voor ephemeral stem-interface.

    Toont alleen de tijden die enabled zijn voor deze dag.
    """
    from apps.utils.poll_settings import get_poll_option_state

    # Haal emoji's uit poll_options.json (centrale bron)
    all_options = get_poll_options()
    emoji_1900 = next(
        (opt.emoji for opt in all_options if opt.dag == dag.lower() and opt.tijd == "om 19:00 uur"),
        "🔴"
    )
    emoji_2030 = next(
        (opt.emoji for opt in all_options if opt.dag == dag.lower() and opt.tijd == "om 20:30 uur"),
        "🟠"
    )

    # Gebruik rolling window om de correcte datum te krijgen (consistent met poll messages)
    from apps.utils.message_builder import get_rolling_window_days
    dagen_info = get_rolling_window_days(dag_als_vandaag=None)

    # Zoek de datum voor deze dag in de rolling window
    datum_iso = None
    for day_info in dagen_info:
        if day_info["dag"] == dag.lower():
            datum_iso = day_info["datum"].strftime("%Y-%m-%d")
            break

    # Dag moet altijd in rolling window zitten - als niet, dan is er een bug
    if datum_iso is None:
        raise ValueError(
            f"Dag '{dag}' niet gevonden in rolling window. "
            f"Dit zou niet moeten gebeuren - bug in get_rolling_window_days()."
        )

    # Check welke tijden enabled zijn voor deze dag
    has_1900 = get_poll_option_state(channel_id, dag.lower(), "19:00")
    has_2030 = get_poll_option_state(channel_id, dag.lower(), "20:30")

    # Bouw legenda op basis van enabled tijden
    from apps.utils.i18n import get_time_label

    parts = []
    if has_1900:
        tijd_1900 = TimeZoneHelper.nl_tijd_naar_hammertime(datum_iso, "19:00", style="F")
        label_1900 = get_time_label(channel_id, "19:00")
        parts.append(f"{emoji_1900} {label_1900} = {tijd_1900}")
    if has_2030:
        tijd_2030 = TimeZoneHelper.nl_tijd_naar_hammertime(datum_iso, "20:30", style="F")
        label_2030 = get_time_label(channel_id, "20:30")
        parts.append(f"{emoji_2030} {label_2030} = {tijd_2030}")

    return " | ".join(parts)


class PollButton(Button):
    def __init__(self, dag: str, tijd: str, label: str, stijl: ButtonStyle):
        super().__init__(label=label, style=stijl, custom_id=f"{dag}:{tijd}")
        self.dag = dag
        self.tijd = tijd

    async def callback(self, interaction: Interaction):
        try:
            channel_id = interaction.channel_id
            if channel_id is None:
                # Alleen in serverkanaal te gebruiken
                msg = "⚠️ This button only works in a server channel."
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                return

            from apps.utils.i18n import t

            if is_paused(channel_id):
                msg = f"⏸️ {t(channel_id, 'UI.voting_paused')}"
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                return

            user_id = str(interaction.user.id)
            guild_id: int = int(
                interaction.guild_id or getattr(interaction.guild, "id", 0) or 0
            )
            now = datetime.now(ZoneInfo("Europe/Amsterdam"))

            # ✅ Snelle ACK: bewerk meteen hetzelfde ephemere bericht (geen nieuw bericht)
            header = _get_header_tmpl(channel_id, self.dag)
            legenda = _get_timezone_legend(self.dag, channel_id)
            header_volledig = f"{header}\n{legenda}"
            if not interaction.response.is_done():
                try:
                    await interaction.response.edit_message(
                        content=f"{header_volledig}\n🔄 {t(channel_id, 'UI.vote_processing')}"
                    )
                except Exception:  # pragma: no cover
                    # Als het niet lukt, val later terug op message.edit
                    pass

            # ✅ Check zichtbaarheid
            if not is_vote_button_visible(channel_id, self.dag, self.tijd, now):
                # Bewerk hetzelfde bericht en stop
                closed_msg = f"❌ {t(channel_id, 'UI.vote_closed')}"
                try:
                    if interaction.message is not None:
                        await interaction.message.edit(
                            content=f"{header_volledig}\n{closed_msg}",
                            view=None,
                        )
                    else:
                        await interaction.edit_original_response(
                            content=f"{header_volledig}\n{closed_msg}",
                            view=None,
                        )
                except Exception:  # pragma: no cover
                    pass
                return

            # ✅ Toggle stem (onder lock in poll_storage)
            # Pass channel for category-based vote syncing
            await toggle_vote(
                user_id,
                self.dag,
                self.tijd,
                (interaction.guild_id or 0),
                channel_id,
                channel=interaction.channel,
            )

            # ✅ Vernieuw eigen ephemeral view (zelfde bericht)
            new_view = await create_poll_button_view(
                user_id, guild_id, channel_id, dag=self.dag
            )

            # Toon korte status in hetzelfde bericht (geen followup-spam)
            status = f"✅ {t(channel_id, 'UI.vote_success')}"
            try:
                if interaction.message is not None:
                    await interaction.message.edit(
                        content=f"{header_volledig}\n{status}",
                        view=new_view,
                    )
                else:
                    await interaction.edit_original_response(
                        content=f"{header_volledig}\n{status}",
                        view=new_view,
                    )
            except Exception:  # pragma: no cover
                # Als bewerken mislukt, probeer nog één keer via edit_original_response
                try:
                    await interaction.edit_original_response(
                        content=f"{header_volledig}\n{status}",
                        view=new_view,
                    )
                except Exception:  # pragma: no cover
                    pass

            # ✅ Update publieke poll (achtergrond, alleen deze dag)
            # Uses category-wide update for dual language support
            if interaction.channel is not None:
                asyncio.create_task(update_poll_messages_for_category(interaction.channel, self.dag))

                # ✅ Update non-voter notification real-time (als die actief is)
                from apps.utils.mention_utils import update_non_voter_notification
                asyncio.create_task(
                    update_non_voter_notification(interaction.channel, self.dag, guild_id)
                )

                # Check celebration (iedereen gestemd?)
                asyncio.create_task(
                    check_all_voted_celebration(
                        interaction.channel, guild_id, channel_id
                    )
                )

        except Exception:  # pragma: no cover
            # Probeer alsnog knoppen te herstellen in hetzelfde bericht
            try:
                user_id = str(interaction.user.id)
                guild_id: int = int(
                    interaction.guild_id or getattr(interaction.guild, "id", 0) or 0
                )
                channel_id = int(interaction.channel_id or 0)
                new_view = await create_poll_button_view(
                    user_id, guild_id, channel_id, dag=self.dag
                )
                header = _get_header_tmpl(channel_id, self.dag)
                legenda = _get_timezone_legend(self.dag, channel_id)
                header_volledig = f"{header}\n{legenda}"
                from apps.utils.i18n import t
                msg = f"⚠️ {t(channel_id, 'UI.vote_error')}"
                if interaction.message is not None:
                    await interaction.message.edit(
                        content=f"{header_volledig}\n{msg}",
                        view=new_view,
                    )
                else:
                    await interaction.edit_original_response(
                        content=f"{header_volledig}\n{msg}",
                        view=new_view,
                    )
            except Exception as inner:  # pragma: no cover
                print(f"❌ Kon geen terugvaloptie tonen: {inner}")


class PollButtonView(View):
    """Ephemeral stemknoppen voor 1 gebruiker (optioneel gefilterd op dag)."""

    def __init__(
        self,
        votes: dict,
        channel_id: int,
        filter_dag: str | None = None,
        now: datetime | None = None,
    ):
        super().__init__(timeout=180)  # Iets ruimer
        now = now or datetime.now(ZoneInfo("Europe/Amsterdam"))

        for option in get_poll_options(channel_id):
            if filter_dag and option.dag != filter_dag:
                continue

            # Check of deze tijd-optie enabled is in settings
            if option.tijd in ["om 19:00 uur", "om 20:30 uur"]:
                tijd_short = "19:00" if "19:00" in option.tijd else "20:30"
                if not get_poll_option_state(channel_id, option.dag, tijd_short):
                    continue  # Skip disabled opties

            if not is_vote_button_visible(channel_id, option.dag, option.tijd, now):
                continue

            selected = option.tijd in votes.get(option.dag, [])
            stijl = ButtonStyle.success if selected else ButtonStyle.secondary
            label = f"✅ {option.label}" if selected else option.label
            self.add_item(PollButton(option.dag, option.tijd, label, stijl))


async def create_poll_button_view(
    user_id: str, guild_id: int, channel_id: int, dag: str | None = None
) -> PollButtonView:
    votes = await get_user_votes(user_id, guild_id, channel_id)
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    return PollButtonView(votes, channel_id, filter_dag=dag, now=now)


async def create_poll_button_views_per_day(
    user_id: str, guild_id: int, channel_id: int
) -> list[tuple[str, str, PollButtonView]]:
    from apps.utils.poll_settings import get_enabled_rolling_window_days

    votes = await get_user_votes(user_id, guild_id, channel_id)
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    views: list[tuple[str, str, PollButtonView]] = []

    # Gebruik rolling window om alleen future + today dagen beschikbaar te maken
    dagen_info = get_enabled_rolling_window_days(channel_id, dag_als_vandaag=None)

    for day_info in dagen_info:
        dag = day_info["dag"]
        is_past = day_info["is_past"]

        # Skip dagen in het verleden - die zijn alleen zichtbaar, niet stembaar
        if is_past:
            continue

        view = PollButtonView(votes, channel_id, filter_dag=dag, now=now)
        if view.children:  # Alleen tonen als er knoppen zijn
            header = _get_header_tmpl(channel_id, dag)
            # Voeg tijdzone legenda toe
            legenda = _get_timezone_legend(dag, channel_id)
            header_met_legenda = f"{header}\n{legenda}"
            views.append((dag, header_met_legenda, view))
    return views


class OpenStemmenButton(Button):
    def __init__(self, paused: bool = False, channel_id: int | None = None):
        # Note: Labels are set at creation time, so we use a simple approach
        # For full i18n, the view would need to be recreated when language changes
        label = "🗳️ Vote (paused)" if paused else "🗳️ Vote"
        if channel_id:
            from apps.utils.i18n import t
            label = f"🗳️ {t(channel_id, 'UI.vote_button_paused' if paused else 'UI.vote_button')}"
        style = ButtonStyle.secondary if paused else ButtonStyle.primary
        super().__init__(
            label=label, style=style, custom_id="open_stemmen", disabled=paused
        )

    async def callback(self, interaction: Interaction):
        channel_id = interaction.channel_id
        if channel_id is None:
            msg = "⚠️ This button only works in a server channel."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        from apps.utils.i18n import t

        if is_paused(channel_id):
            await interaction.response.send_message(
                f"⏸️ {t(channel_id, 'UI.paused_message')}", ephemeral=True
            )
            return

        # EERST: Acknowledge interaction (binnen 3 sec) om timeout te voorkomen
        await interaction.response.send_message(
            f"🔄 {t(channel_id, 'UI.poll_updating')}",
            ephemeral=True,
        )

        # TWEEDE: Cleanup oude poll-berichten in background (kan lang duren)
        await _cleanup_outdated_messages_for_channel(interaction.channel, channel_id)

        # DERDE: Toon voting interface
        user_id = str(interaction.user.id)
        views_per_dag = await create_poll_button_views_per_day(
            user_id, (interaction.guild_id or 0), channel_id
        )

        if not views_per_dag:
            await interaction.edit_original_response(
                content=t(channel_id, "UI.voting_closed_all_days")
            )
            return

        # Update bericht en toon voting knoppen
        await interaction.edit_original_response(
            content=t(channel_id, "UI.choose_times_instruction")
        )

        for dag, header, view in views_per_dag:
            await interaction.followup.send(header, view=view, ephemeral=True)


class OneStemButtonView(View):
    """De vaste stemknop onderaan het pollbericht."""

    def __init__(self, paused: bool = False, channel_id: int | None = None):
        super().__init__(timeout=None)
        self.add_item(OpenStemmenButton(paused, channel_id))
