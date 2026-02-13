# apps/commands/poll_lifecycle.py
#
# Poll levenscyclus: aanmaken, reset, pauze, verwijderen

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from apps import scheduler
from apps.commands import with_default_suffix
from apps.ui.poll_buttons import OneStemButtonView
from apps.utils.discord_client import fetch_message_or_none, safe_call
from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_message import (
    clear_message_id,
    create_notification_message,
    get_message_id,
    save_message_id,
    set_channel_disabled,
    set_dag_als_vandaag,
    update_poll_message,
)
from apps.utils.poll_settings import (
    WEEK_DAYS,
    clear_scheduled_activation,
    is_paused,
    set_scheduled_activation,
    should_hide_counts,
    toggle_paused,
)
from apps.utils.time_zone_helper import TimeZoneHelper
from apps.utils.poll_storage import reset_votes, reset_votes_scoped


def _load_opening_message(channel_id: int | None = None) -> str:
    """
    Genereer dynamisch opening bericht op basis van channel settings.

    Args:
        channel_id: Het kanaal ID (optioneel). Als None, gebruik fallback met generieke tekst.

    Returns:
        Opening message string met accurate channel-specifieke informatie
    """
    from apps.utils.i18n import get_day_name, t
    from apps.utils.poll_settings import (
        get_enabled_poll_days,
        get_setting,
        is_notification_enabled,
    )
    from apps.utils.time_zone_helper import TimeZoneHelper
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    cid = channel_id or 0

    # Basis header (altijd hetzelfde)
    header = t(cid, "OPENING.header")

    # Als geen channel_id, gebruik generieke fallback
    if channel_id is None:
        return header + t(cid, "OPENING.fallback")

    # Haal enabled dagen op
    enabled_days = get_enabled_poll_days(channel_id)
    if not enabled_days:
        enabled_days = ["vrijdag", "zaterdag", "zondag"]  # Fallback

    # Format dagen lijst (localized)
    localized_days = [get_day_name(cid, dag) for dag in enabled_days]
    and_word = t(cid, "COMMON.and")
    if len(localized_days) == 1:
        dagen_tekst = localized_days[0]
    elif len(localized_days) == 2:
        dagen_tekst = f"{localized_days[0]} {and_word} {localized_days[1]}"
    else:
        dagen_tekst = ", ".join(localized_days[:-1]) + f" {and_word} {localized_days[-1]}"

    # Bepaal deadline tijd (gebruik eerste enabled dag als referentie)
    eerste_dag = enabled_days[0] if enabled_days else "vrijdag"
    setting = get_setting(channel_id, eerste_dag)
    deadline_tijd = setting.get("tijd", "18:00")

    # Bereken HammerTime voor deadline (gebruik morgen als voorbeeld datum)
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    morgen = (now + timedelta(days=1)).date()
    deadline_hammertime = TimeZoneHelper.nl_tijd_naar_hammertime(
        morgen.strftime("%Y-%m-%d"), deadline_tijd, style="t"
    )

    # Basis intro
    intro = t(cid, "OPENING.intro", dagen=dagen_tekst, deadline=deadline_hammertime)

    # Check welke notificaties enabled zijn
    reminders_enabled = is_notification_enabled(channel_id, "reminders")
    misschien_enabled = is_notification_enabled(channel_id, "misschien")

    # Build notification text
    notification_parts = []
    if reminders_enabled:
        notification_parts.append(t(cid, "OPENING.reminder_note"))
    if misschien_enabled:
        notification_parts.append(t(cid, "OPENING.maybe_note"))

    notification_text = " ".join(notification_parts) if notification_parts else ""

    # Append call to action
    if notification_text:
        notification_text += " " + t(cid, "OPENING.notification_cta")

    # Build complete message
    message_parts = [header, intro]
    if notification_text:
        message_parts.append(notification_text)

    message_parts.extend([
        "\n" + t(cid, "OPENING.vote_info"),
        "\n" + t(cid, "OPENING.how_it_works"),
        "• " + t(cid, "OPENING.how_click"),
        "• " + t(cid, "OPENING.how_multiple"),
        "• " + t(cid, "OPENING.how_change"),
        "\n" + t(cid, "OPENING.guests_title"),
        t(cid, "OPENING.guests_instruction"),
        "\n" + t(cid, "OPENING.have_fun"),
    ])

    return "\n".join(message_parts)


def _get_attr(obj: Any, name: str) -> Any:
    """Helper om attribute access type-veilig te doen richting Pylance."""
    return getattr(obj, name, None)


class PollLifecycle(commands.Cog):
    """Poll levenscyclus: aanmaken, reset, pauze, verwijderen"""

    def __init__(self, bot):
        self.bot = bot

    def _validate_scheduling_params(
        self,
        dag: str | None,
        datum: str | None,
        tijd: str | None,
        frequentie: str | None,
        channel_id: int = 0,
    ) -> str | None:
        """
        Valideer de scheduling parameters.
        Retourneert een foutmelding als de parameters ongeldig zijn, anders None.
        """
        from apps.utils.i18n import t

        # Als geen parameters, dan handmatig activeren (standaard gedrag)
        if not tijd and not dag and not datum and not frequentie:
            return None

        # tijd is verplicht met dag of datum
        if (dag or datum) and not tijd:
            return t(channel_id, "ERRORS.time_required")

        # dag en datum kunnen niet samen
        if dag and datum:
            return t(channel_id, "ERRORS.dag_datum_conflict")

        # tijd kan niet zonder dag of datum
        if tijd and not dag and not datum:
            return t(channel_id, "ERRORS.time_without_dag_datum")

        # Valideer tijd formaat (HH:mm)
        if tijd:
            try:
                parts = tijd.split(":")
                if len(parts) != 2:
                    return t(channel_id, "ERRORS.invalid_time")
                uur, minuut = int(parts[0]), int(parts[1])
                if not (0 <= uur <= 23 and 0 <= minuut <= 59):
                    return t(channel_id, "ERRORS.invalid_time")
            except ValueError:
                return t(channel_id, "ERRORS.invalid_time")

        # Valideer datum formaat (DD-MM-YYYY)
        if datum:
            try:
                datetime.strptime(datum, "%d-%m-%Y")
            except ValueError:
                return t(channel_id, "ERRORS.invalid_date")

        # frequentie validatie
        if frequentie:
            if frequentie == "eenmalig" and not datum:
                return t(channel_id, "ERRORS.frequentie_eenmalig_requires_datum")
            if frequentie == "wekelijks" and not dag:
                return t(channel_id, "ERRORS.frequentie_wekelijks_requires_dag")

        return None

    async def _save_schedule(
        self,
        channel_id: int,
        dag: str | None,
        datum: str | None,
        tijd: str,
        frequentie: str | None,
    ) -> str:
        """
        Sla het schema op en retourneer een bevestigingsbericht.
        """
        # Bepaal activatie type op basis van parameters
        if datum:
            activation_type = "datum"
            # Convert DD-MM-YYYY input to YYYY-MM-DD for internal storage
            datum_obj = datetime.strptime(datum, "%d-%m-%Y")
            datum_internal = datum_obj.strftime("%Y-%m-%d")
            set_scheduled_activation(
                channel_id, activation_type, tijd, datum=datum_internal
            )
            dag_naam = [
                "maandag",
                "dinsdag",
                "woensdag",
                "donderdag",
                "vrijdag",
                "zaterdag",
                "zondag",
            ][datum_obj.weekday()]
            # Display in DD-MM-YYYY format
            return f"📅 De poll wordt automatisch geactiveerd op **{dag_naam} {datum}** om **{tijd}** uur."
        elif dag:
            # Wekelijks als frequentie=wekelijks, of als default bij dag
            activation_type = "wekelijks"
            set_scheduled_activation(channel_id, activation_type, tijd, dag=dag)
            is_recurrent = frequentie == "wekelijks" or frequentie is None

            # Bij wekelijks: stel dag_als_vandaag in op de scheduler dag
            # Dit zorgt ervoor dat de rolling window meteen correct is
            if is_recurrent:
                set_dag_als_vandaag(channel_id, dag)
                return f"📅 De poll wordt elke **{dag}** om **{tijd}** uur automatisch geactiveerd."
            else:
                return f"📅 De poll wordt eenmalig op aanstaande **{dag}** om **{tijd}** uur geactiveerd."
        else:
            # Fallback: wis schedule (handmatige activatie)
            clear_scheduled_activation(channel_id)
            return ""

    # -----------------------------
    # /dmk-poll-on
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-on",
        description=with_default_suffix("Plaats of update de polls per avond"),
    )
    @app_commands.describe(
        dag="Weekdag (maandag t/m zondag) - verplicht met tijd",
        datum="Specifieke datum (DD-MM-YYYY) - verplicht met tijd",
        tijd="Tijd in HH:mm formaat - verplicht met dag of datum",
        frequentie="Eenmalig (op datum) of wekelijks (elke week op deze dag)",
        dag_als_vandaag="Welke dag als 'vandaag' beschouwen voor rolling window (optioneel)",
    )
    async def on(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        dag: (
            Literal[
                "maandag",
                "dinsdag",
                "woensdag",
                "donderdag",
                "vrijdag",
                "zaterdag",
                "zondag",
            ]
            | None
        ) = None,
        datum: str | None = None,
        tijd: str | None = None,
        frequentie: Literal["eenmalig", "wekelijks"] | None = None,
        dag_als_vandaag: (
            Literal[
                "maandag",
                "dinsdag",
                "woensdag",
                "donderdag",
                "vrijdag",
                "zaterdag",
                "zondag",
            ]
            | None
        ) = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            from apps.utils.i18n import t
            await interaction.followup.send(f"❌ {t(0, 'ERRORS.no_channel')}", ephemeral=True)
            return

        from apps.utils.i18n import t
        cid = channel.id

        # Valideer parameters
        validation_error = self._validate_scheduling_params(
            dag, datum, tijd, frequentie, cid
        )
        if validation_error:
            await interaction.followup.send(f"❌ {validation_error}", ephemeral=True)
            return

        # Als er scheduling parameters zijn, sla ze op en toon alleen bevestiging
        if tijd and (dag or datum):
            schedule_message = await self._save_schedule(
                channel.id, dag, datum, tijd, frequentie
            )
            # Alleen bevestigingsbericht tonen, poll niet plaatsen
            await interaction.followup.send(schedule_message, ephemeral=True)
            return

        # Handmatige activatie (geen scheduling parameters)
        # Stap 1: Controleer op non-bot berichten in het kanaal
        try:
            non_bot_berichten = await self._scan_non_bot_messages(channel)
            if non_bot_berichten:
                # Er zijn non-bot berichten - vraag om bevestiging
                await self._toon_opschoon_bevestiging(
                    interaction, channel, non_bot_berichten, schedule_message=None, dag_als_vandaag=dag_als_vandaag
                )
                return  # De bevestigingsview handelt de rest af
        except Exception as e:
            # Als scannen faalt, ga gewoon door
            print(f"⚠️ Kon niet scannen naar oude berichten: {e}")

        # Stap 2: Verwijder bot-berichten (geen bevestiging nodig)
        try:
            await self._delete_all_bot_messages(channel)
        except Exception as e:
            print(f"⚠️ Kon bot-berichten niet verwijderen: {e}")

        # Stap 2.5: Bepaal welke dag als "vandaag" te gebruiken
        # Als dag_als_vandaag None is, gebruik echte huidige dag (zodat rolling window correct werkt)
        if dag_als_vandaag is None:
            from apps.utils.constants import DAG_NAMEN
            from datetime import datetime
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo("Europe/Amsterdam"))
            effective_dag_als_vandaag = DAG_NAMEN[now.weekday()]
        else:
            effective_dag_als_vandaag = dag_als_vandaag

        # NIET opslaan in state - we gebruiken altijd de huidige dag bij updates

        # Stap 3: Plaats de polls (handmatige activatie zonder scheduling)
        await self._plaats_polls(interaction, channel, schedule_message=None, dag_als_vandaag=effective_dag_als_vandaag)

    async def _toon_opschoon_bevestiging(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        channel: Any,
        non_bot_berichten: list,
        schedule_message: str | None = None,
        dag_als_vandaag: str | None = None,
    ) -> None:
        """
        Toon een bevestigingsdialoog voor het opschonen van non-bot berichten.
        Als bevestigd: verwijder non-bot berichten + bot-berichten.
        Als geannuleerd: verwijder alleen bot-berichten.
        """
        from apps.ui.cleanup_confirmation import CleanupConfirmationView

        aantal_berichten = len(non_bot_berichten)

        async def bij_bevestiging(button_interaction: discord.Interaction):
            """Verwijder non-bot berichten + bot-berichten en plaats polls."""
            try:
                # Verwijder alle berichten (bot + non-bot)
                await self._delete_all_bot_messages(
                    channel, also_delete=non_bot_berichten
                )

                verwijderd_aantal = len(non_bot_berichten)
                await button_interaction.edit_original_response(
                    content=f"✅ Alle berichten verwijderd (waaronder {verwijderd_aantal} van andere gebruikers/bots). De polls worden nu geplaatst...",
                    view=None,
                )

                # Plaats de polls
                await self._plaats_polls(interaction, channel, schedule_message, dag_als_vandaag)

            except Exception as e:  # pragma: no cover
                await button_interaction.followup.send(
                    f"❌ Fout bij verwijderen: {e}",
                    ephemeral=True,
                )

        async def bij_annulering(button_interaction: discord.Interaction):
            """Verwijder alleen bot-berichten en plaats polls."""
            try:
                # Verwijder alleen bot-berichten
                await self._delete_all_bot_messages(channel)

                await button_interaction.edit_original_response(
                    content="✅ Bot-berichten verwijderd. De polls worden nu geplaatst...",
                    view=None,
                )

                # Plaats de polls
                await self._plaats_polls(interaction, channel, schedule_message, dag_als_vandaag)
            except Exception as e:  # pragma: no cover
                await button_interaction.followup.send(
                    f"❌ Fout bij plaatsen: {e}",
                    ephemeral=True,
                )

        view = CleanupConfirmationView(
            on_confirm=bij_bevestiging,
            on_cancel=bij_annulering,
            message_count=aantal_berichten,
        )

        await interaction.followup.send(
            f"⚠️ Er staan **{aantal_berichten}** bericht(en) van andere gebruikers/bots in dit kanaal.\n"
            f"Wil je deze verwijderen voor een schone start? (Bot-berichten worden altijd verwijderd)",
            view=view,
            ephemeral=True,
        )

    async def _toon_cleanup_bevestiging_off(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        channel: Any,
        non_bot_berichten: list,
    ) -> None:
        """
        Toon een bevestigingsdialoog voor /dmk-poll-off.
        Als bevestigd: verwijder non-bot berichten + bot-berichten, dan poll-off uitvoeren.
        Als geannuleerd: verwijder alleen bot-berichten, dan poll-off uitvoeren.
        """
        from apps.ui.cleanup_confirmation import CleanupConfirmationView

        aantal_berichten = len(non_bot_berichten)

        async def bij_bevestiging(button_interaction: discord.Interaction):
            """Verwijder alle berichten en voer poll-off uit."""
            try:
                # Verwijder alle berichten (bot + non-bot)
                await self._delete_all_bot_messages(
                    channel, also_delete=non_bot_berichten
                )

                await button_interaction.edit_original_response(
                    content=f"✅ Alle berichten verwijderd (waaronder {len(non_bot_berichten)} van andere gebruikers/bots). Polls worden uitgezet...",
                    view=None,
                )

                # Voer poll-off uit (scheduler uitschakelen)
                await self._execute_poll_off(interaction, channel)

            except Exception as e:  # pragma: no cover
                await button_interaction.followup.send(
                    f"❌ Fout bij verwijderen: {e}",
                    ephemeral=True,
                )

        async def bij_annulering(button_interaction: discord.Interaction):
            """Verwijder alleen bot-berichten en voer poll-off uit."""
            try:
                # Verwijder alleen bot-berichten (already done by _execute_poll_off)
                await button_interaction.edit_original_response(
                    content="✅ Bot-berichten verwijderd. Polls worden uitgezet...",
                    view=None,
                )

                # Voer poll-off uit (scheduler uitschakelen)
                await self._execute_poll_off(interaction, channel)

            except Exception as e:  # pragma: no cover
                await button_interaction.followup.send(
                    f"❌ Fout bij uitvoeren: {e}",
                    ephemeral=True,
                )

        view = CleanupConfirmationView(
            on_confirm=bij_bevestiging,
            on_cancel=bij_annulering,
            message_count=aantal_berichten,
        )

        await interaction.followup.send(
            f"⚠️ Er staan **{aantal_berichten}** bericht(en) van andere gebruikers/bots in dit kanaal.\n"
            f"Wil je deze verwijderen? (Bot-berichten worden altijd verwijderd)",
            view=view,
            ephemeral=True,
        )

    async def _plaats_polls(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        channel: Any,
        schedule_message: str | None = None,
        dag_als_vandaag: str | None = None,
    ) -> None:
        """
        Plaats of update de poll-berichten in het kanaal.

        Args:
            interaction: Discord interaction
            channel: Het kanaal waar polls geplaatst worden
            schedule_message: Optioneel schedule bericht
            dag_als_vandaag: Optioneel, welke dag als "vandaag" beschouwen voor rolling window
        """
        # Gebruik enabled dagen op basis van rolling window + poll-opties settings
        from apps.utils.poll_settings import get_enabled_rolling_window_days

        channel_id = getattr(channel, "id", 0)
        dagen_info = get_enabled_rolling_window_days(channel_id, dag_als_vandaag)

        try:
            # Kanaal opnieuw activeren voor de scheduler
            try:
                set_channel_disabled(channel_id, False)
            except Exception:  # pragma: no cover
                # Niet hard falen als togglen mislukt; we gaan verder met plaatsen
                pass

            # Unpause if currently paused
            try:
                from apps.utils.poll_settings import set_paused

                set_paused(channel_id, False)
            except Exception:  # pragma: no cover
                pass

            # Eerste bericht: Opening (dynamisch gegenereerd)
            # De opening tekst bevat @everyone als header (i18n), maar die
            # is puur decoratief — de echte @everyone-ping gebeurt via
            # send_temporary_mention / create_notification_message.
            # allowed_mentions.none() voorkomt een dubbele ping.
            no_mentions = discord.AllowedMentions.none()
            opening_text = _load_opening_message(channel_id=channel.id)

            send = _get_attr(channel, "send")
            opening_mid = get_message_id(channel.id, "opening")

            if opening_mid:
                # Update bestaand opening bericht
                opening_msg = await fetch_message_or_none(channel, opening_mid)
                if opening_msg is not None:
                    await safe_call(opening_msg.edit, content=opening_text)
                else:
                    # Bericht bestaat niet meer, maak nieuw aan
                    opening_msg = (
                        await safe_call(send, content=opening_text, allowed_mentions=no_mentions) if send else None
                    )
                    if opening_msg is not None:
                        save_message_id(channel.id, "opening", opening_msg.id)
            else:
                # Maak nieuw opening bericht
                opening_msg = (
                    await safe_call(send, content=opening_text, allowed_mentions=no_mentions) if send else None
                )
                if opening_msg is not None:
                    save_message_id(channel.id, "opening", opening_msg.id)

            # Verwijder oude dag-berichten die niet meer in de rolling window zitten
            from apps.utils.constants import DAG_NAMEN
            enabled_dagen_set = {day_info["dag"] for day_info in dagen_info}
            for dag_naam in DAG_NAMEN:
                if dag_naam not in enabled_dagen_set:
                    # Deze dag zit niet meer in de rolling window - verwijder het bericht
                    mid = get_message_id(channel.id, dag_naam)
                    if mid:
                        msg = await fetch_message_or_none(channel, mid)
                        if msg is not None:
                            await safe_call(msg.delete)
                        clear_message_id(channel.id, dag_naam)

            # Tweede t/m vierde berichten: dag-berichten (ALLEEN TEKST, GEEN KNOPPEN)
            guild = _get_attr(channel, "guild")
            for day_info in dagen_info:
                dag = day_info["dag"]
                datum_iso = day_info["datum_iso"]
                gid_val = getattr(guild, "id", "0") if guild is not None else "0"
                cid_val = getattr(channel, "id", "0") or "0"
                content = await build_poll_message_for_day_async(
                    dag, gid_val, cid_val, guild=guild, channel=channel, datum_iso=datum_iso
                )

                mid = get_message_id(channel.id, dag)
                if mid:
                    msg = await fetch_message_or_none(channel, mid)
                    if msg is not None:
                        await safe_call(msg.edit, content=content, view=None)
                    else:
                        send = _get_attr(channel, "send")
                        newmsg = (
                            await safe_call(send, content=content, view=None)
                            if send
                            else None
                        )
                        if newmsg is not None:
                            save_message_id(channel.id, dag, newmsg.id)
                else:
                    send = _get_attr(channel, "send")
                    msg = (
                        await safe_call(send, content=content, view=None)
                        if send
                        else None
                    )
                    if msg is not None:
                        save_message_id(channel.id, dag, msg.id)

                # Direct updaten volgens zichtbaarheid + beslissingsregel
                await update_poll_message(channel, dag)

            # Vierde bericht: één vaste knop "🗳️ Stemmen"
            from apps.utils.i18n import t as i18n_t

            key = "stemmen"
            tekst = i18n_t(channel_id, "UI.click_vote_button")
            s_mid = get_message_id(channel.id, key)
            paused = is_paused(channel.id)
            view = OneStemButtonView(paused=paused, channel_id=channel_id)
            send = _get_attr(channel, "send")

            if s_mid:
                s_msg = await fetch_message_or_none(channel, s_mid)
                if s_msg is not None:
                    await safe_call(s_msg.edit, content=tekst, view=view)
                else:
                    s_msg = (
                        await safe_call(send, content=tekst, view=view)
                        if send
                        else None
                    )
                    if s_msg is not None:
                        save_message_id(channel.id, key, s_msg.id)
            else:
                s_msg = (
                    await safe_call(send, content=tekst, view=view) if send else None
                )
                if s_msg is not None:
                    save_message_id(channel.id, key, s_msg.id)

            # Zesde bericht: notificatiebericht (leeg, voor later gebruik)
            # Check both old and new notification keys for backward compatibility
            n_mid_persistent = get_message_id(channel.id, "notification_persistent")
            n_mid_old = get_message_id(channel.id, "notification")
            n_mid = n_mid_persistent or n_mid_old

            if n_mid:
                # Check if message still exists
                n_msg = await fetch_message_or_none(channel, n_mid)
                if n_msg is None:
                    # Message is gone, create new one
                    await create_notification_message(channel)
            else:
                # No message ID, create new one
                await create_notification_message(channel)

            # Stuur bevestiging (alleen als we direct vanuit on() komen, niet via opschoon-knoppen)
            try:
                confirmation = i18n_t(channel_id, "COMMANDS.polls_enabled")
                if schedule_message:
                    confirmation += f"\n{schedule_message}"
                await interaction.followup.send(
                    confirmation,
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover
                # Als interaction al is afgehandeld (bijv. via opschoon-knoppen), skip
                pass

        except Exception as e:  # pragma: no cover
            try:
                from apps.utils.i18n import t as i18n_t

                await interaction.followup.send(
                    f"❌ {i18n_t(channel_id, 'ERRORS.place_error', error=str(e))}", ephemeral=True
                )
            except Exception:  # pragma: no cover
                # Als interaction al is afgehandeld, print alleen de fout
                print(f"❌ Place error: {e}")

    # -----------------------------
    # /dmk-poll-reset
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-reset",
        description=with_default_suffix("Reset alle stemmen en data"),
    )
    async def reset(self, interaction: discord.Interaction) -> None:  # pragma: no cover
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            from apps.utils.i18n import t
            await interaction.followup.send(f"❌ {t(0, 'ERRORS.no_channel')}", ephemeral=True)
            return

        from apps.utils.i18n import t
        dagen = WEEK_DAYS

        guild = getattr(interaction, "guild", None) or getattr(channel, "guild", None)
        gid = int(getattr(guild, "id", 0)) if guild else 0
        cid = int(getattr(channel, "id", 0))

        try:
            # 1) Archief bijwerken (per kanaal)
            try:
                from apps.utils.archive import append_week_snapshot_scoped

                await append_week_snapshot_scoped(gid, cid, channel=channel)
            except Exception as e:  # pragma: no cover
                print(f"⚠️ append_week_snapshot_scoped mislukte: {e}")

            # 2) Stemmen wissen (per kanaal)
            try:
                await reset_votes_scoped(gid, cid)
            except Exception:  # pragma: no cover
                await reset_votes()

            # 2.5) Stel dag_als_vandaag in op de huidige dag (voor rolling window)
            from apps.utils.constants import DAG_NAMEN

            now = datetime.now(ZoneInfo("Europe/Amsterdam"))
            huidige_dag = DAG_NAMEN[now.weekday()]
            set_dag_als_vandaag(cid, huidige_dag)

            # 3) Update reset-tijd in scheduler-state
            now = datetime.now(scheduler.TZ)
            try:
                state = scheduler._read_state()
                state["reset_polls"] = now.isoformat()
                scheduler._write_state(state)
            except Exception as e:  # pragma: no cover
                print(f"⚠️ Kon scheduler-state niet bijwerken: {e}")

            # 4) Dag-berichten updaten (zonder knoppen), met huidige zichtbaarheid/pauze
            now = datetime.now(ZoneInfo("Europe/Amsterdam"))
            paused = is_paused(channel.id)
            gevonden = False

            for dag in dagen:
                mid = get_message_id(channel.id, dag)
                if not mid:
                    continue
                gevonden = True
                msg = await fetch_message_or_none(channel, mid)
                if msg is None:
                    continue
                hide = should_hide_counts(channel.id, dag, now)
                gid_val = (
                    getattr(_get_attr(channel, "guild"), "id", "0")
                    if _get_attr(channel, "guild") is not None
                    else "0"
                )
                cid_val = getattr(channel, "id", "0") or "0"
                content = await build_poll_message_for_day_async(
                    dag,
                    gid_val,
                    cid_val,
                    hide_counts=hide,
                    pauze=paused,
                    guild=_get_attr(channel, "guild"),
                    channel=channel,
                )
                await safe_call(
                    msg.edit, content=content, view=None
                )  # Geen knoppen tonen

            # 5) (Optioneel) Stemmen-bericht tekst + knop updaten als het bestaat
            key = "stemmen"
            s_mid = get_message_id(channel.id, key)
            if s_mid:
                s_msg = await fetch_message_or_none(channel, s_mid)
                if s_msg is not None:
                    tekst = t(cid, "UI.click_vote_button")
                    view = OneStemButtonView(paused=paused, channel_id=cid)
                    await safe_call(s_msg.edit, content=tekst, view=view)

            # 6) Terugkoppeling
            if gevonden:
                await interaction.followup.send(
                    t(cid, "COMMANDS.reset_complete"), ephemeral=True
                )
            else:
                await interaction.followup.send(
                    t(cid, "COMMANDS.no_day_messages"), ephemeral=True
                )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ {t(cid, 'ERRORS.reset_failed', error=str(e))}", ephemeral=True)

    # -----------------------------
    # /dmk-poll-pauze
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-pauze",
        description=with_default_suffix("Pauzeer of hervat de poll"),
    )
    async def pauze(self, interaction: discord.Interaction) -> None:  # pragma: no cover
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            from apps.utils.i18n import t
            await interaction.followup.send(f"❌ {t(0, 'ERRORS.no_channel')}", ephemeral=True)
            return

        from apps.utils.i18n import t
        cid = channel.id

        try:
            # 1) Toggle pauze-status
            paused = toggle_paused(channel.id)  # True = nu gepauzeerd

            # 2) Stemmen-bericht updaten (knop disabled + tekst)
            key = "stemmen"
            mid = get_message_id(channel.id, key)
            tekst = (
                t(cid, "UI.paused_message")
                if paused
                else t(cid, "UI.click_vote_button")
            )
            view = OneStemButtonView(paused=paused, channel_id=cid)

            send = _get_attr(channel, "send")
            if mid:
                msg = await fetch_message_or_none(channel, mid)
                if msg is not None:
                    await safe_call(msg.edit, content=tekst, view=view)
                else:
                    newmsg = (
                        await safe_call(send, content=tekst, view=view)
                        if send
                        else None
                    )
                    if newmsg is not None:
                        save_message_id(channel.id, key, newmsg.id)
            else:
                newmsg = (
                    await safe_call(send, content=tekst, view=view) if send else None
                )
                if newmsg is not None:
                    save_message_id(channel.id, key, newmsg.id)

            status_msg = t(cid, "COMMANDS.poll_paused") if paused else t(cid, "COMMANDS.poll_resumed")
            await interaction.followup.send(status_msg, ephemeral=True)

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ {t(cid, 'ERRORS.generic_error', error=str(e))}", ephemeral=True)

    # -----------------------------
    # /dmk-poll-off
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-off",
        description=with_default_suffix("Schakel polls uit en maak kanaal leeg"),
    )
    @app_commands.describe(
        dag="Weekdag (maandag t/m zondag) - verplicht met tijd",
        datum="Specifieke datum (DD-MM-YYYY) - verplicht met tijd",
        tijd="Tijd in HH:mm formaat - verplicht met dag of datum",
        frequentie="Eenmalig (op datum) of wekelijks (elke week op deze dag)",
    )
    async def off(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        dag: (
            Literal[
                "maandag",
                "dinsdag",
                "woensdag",
                "donderdag",
                "vrijdag",
                "zaterdag",
                "zondag",
            ]
            | None
        ) = None,
        datum: str | None = None,
        tijd: str | None = None,
        frequentie: Literal["eenmalig", "wekelijks"] | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            from apps.utils.i18n import t
            await interaction.followup.send(f"❌ {t(0, 'ERRORS.no_channel')}", ephemeral=True)
            return

        from apps.utils.i18n import t
        cid = channel.id

        # Valideer parameters
        validation_error = self._validate_scheduling_params(
            dag, datum, tijd, frequentie, cid
        )
        if validation_error:
            await interaction.followup.send(f"❌ {validation_error}", ephemeral=True)
            return

        # Als er scheduling parameters zijn, sla ze op
        schedule_message = None
        if tijd and (dag or datum):
            schedule_message = await self._save_schedule_off(
                channel.id, dag, datum, tijd, frequentie
            )
            # Alleen schedule opslaan, niet uitvoeren
            await interaction.followup.send(
                f"✅ {schedule_message}",
                ephemeral=True,
            )
            return

        # Direct uitvoeren (handmatig): kanaal leegmaken + scheduler uitschakelen
        # Stap 1: Controleer op non-bot berichten in het kanaal
        try:
            non_bot_berichten = await self._scan_non_bot_messages(channel)
            if non_bot_berichten:
                # Er zijn non-bot berichten - vraag om bevestiging
                await self._toon_cleanup_bevestiging_off(
                    interaction, channel, non_bot_berichten
                )
                return  # De bevestigingsview handelt de rest af
        except Exception as e:
            # Als scannen faalt, ga gewoon door
            print(f"⚠️ Kon niet scannen naar oude berichten: {e}")

        # Stap 2: Voer poll-off uit (geen non-bot berichten, dus geen bevestiging nodig)
        await self._execute_poll_off(interaction, channel)

    async def _save_schedule_off(
        self,
        channel_id: int,
        dag: str | None,
        datum: str | None,
        tijd: str,
        frequentie: str | None,
    ) -> str:
        """
        Sla het off-schema op en retourneer een bevestigingsbericht.
        """
        from apps.utils.poll_settings import set_scheduled_deactivation

        # Bepaal deactivatie type op basis van parameters
        if datum:
            activation_type = "datum"
            # Convert DD-MM-YYYY input to YYYY-MM-DD for internal storage
            datum_obj = datetime.strptime(datum, "%d-%m-%Y")
            datum_internal = datum_obj.strftime("%Y-%m-%d")
            set_scheduled_deactivation(
                channel_id, activation_type, tijd, datum=datum_internal
            )
            dag_naam = [
                "maandag",
                "dinsdag",
                "woensdag",
                "donderdag",
                "vrijdag",
                "zaterdag",
                "zondag",
            ][datum_obj.weekday()]
            # Display in DD-MM-YYYY format
            return f"De poll wordt automatisch uitgeschakeld op **{dag_naam} {datum}** om **{tijd}** uur."
        elif dag:
            # Wekelijks als frequentie=wekelijks, of als default bij dag
            activation_type = "wekelijks"
            set_scheduled_deactivation(channel_id, activation_type, tijd, dag=dag)
            is_recurrent = frequentie == "wekelijks" or frequentie is None
            if is_recurrent:
                return f"De poll wordt elke **{dag}** om **{tijd}** uur automatisch uitgeschakeld."
            else:
                return f"De poll wordt eenmalig op aanstaande **{dag}** om **{tijd}** uur uitgeschakeld."
        else:
            return ""

    async def _scan_non_bot_messages(self, channel: Any) -> list:
        """
        Scan het kanaal voor berichten NIET van de bot.

        Returns:
            Lijst met berichten die niet van de bot zijn (van andere users/bots)
        """
        non_bot_berichten = []
        try:
            bot_user_id = getattr(self.bot.user, "id", None)
            history_method = _get_attr(channel, "history")
            if bot_user_id and history_method:
                async for bericht in history_method(limit=100):
                    # Alleen berichten die NIET van de bot zijn
                    if getattr(bericht.author, "id", None) != bot_user_id:
                        non_bot_berichten.append(bericht)
        except Exception:  # pragma: no cover
            pass
        return non_bot_berichten

    async def _delete_all_bot_messages(
        self, channel: Any, also_delete: list | None = None
    ) -> None:
        """
        Verwijder alle berichten van de bot in dit kanaal en wis alle message IDs.
        Optioneel ook andere berichten verwijderen (bijv. na bevestiging).

        Args:
            channel: Het kanaal om berichten uit te verwijderen
            also_delete: Optionele lijst met extra berichten om te verwijderen (non-bot messages)
        """
        # 1) Verwijder ALLE berichten van de bot in dit kanaal
        try:
            bot_user_id = getattr(self.bot.user, "id", None)
            history_method = _get_attr(channel, "history")
            if bot_user_id and history_method:
                async for bericht in history_method(limit=100):
                    # Check of het bericht van de bot is
                    if getattr(bericht.author, "id", None) == bot_user_id:
                        try:
                            await bericht.delete()
                        except Exception:  # pragma: no cover
                            pass  # Sla berichten over die niet verwijderd kunnen worden
        except Exception:  # pragma: no cover
            pass  # Als history scan faalt, ga gewoon door

        # 2) Verwijder ook non-bot messages als die zijn meegegeven
        if also_delete:
            for bericht in also_delete:
                try:
                    await bericht.delete()
                except Exception:  # pragma: no cover
                    pass

        # 3) Wis alle opgeslagen message IDs voor dit kanaal
        channel_id = getattr(channel, "id", 0)
        message_keys = [
            "opening",
            "maandag",
            "dinsdag",
            "woensdag",
            "donderdag",
            "vrijdag",
            "zaterdag",
            "zondag",
            "stemmen",
            "notification_temp",
            "notification_persistent",
            "notification",
            "celebration",
            "celebration_gif",
        ]
        for key in message_keys:
            try:
                clear_message_id(channel_id, key)
            except Exception:  # pragma: no cover
                pass

    async def _execute_poll_off(  # pragma: no cover
        self, interaction: discord.Interaction, channel: Any
    ) -> None:
        """
        Voer poll-off uit: verwijder alle bot-berichten ZONDER scheduler uit te schakelen.
        Dit is TIJDELIJK sluiten - automatische activering blijft werken.

        Voor PERMANENT uitschakelen, gebruik /dmk-poll-stopzetten.
        """
        try:
            # 1) Verwijder alle bot-berichten en wis message IDs
            await self._delete_all_bot_messages(channel)

            # 2) Plaats sluitingsbericht met informatie over automatische heropening
            from apps.utils.poll_settings import get_effective_activation

            channel_id = getattr(channel, "id", 0)
            schedule, _is_default = get_effective_activation(channel_id)

            # Standaard fallback: dinsdag om 20:00 uur
            now = datetime.now(ZoneInfo("Europe/Amsterdam"))
            current_date_obj = now.date()
            hammertime_str = TimeZoneHelper.nl_tijd_naar_hammertime(
                current_date_obj.strftime("%Y-%m-%d"), "20:00", style="F"
            )

            if schedule:
                tijd = schedule.get("tijd", "20:00")
                if schedule.get("type") == "wekelijks":
                    # Voor wekelijkse activatie: gebruik vandaag als datum voor hammertime
                    hammertime_str = TimeZoneHelper.nl_tijd_naar_hammertime(
                        current_date_obj.strftime("%Y-%m-%d"), tijd, style="F"
                    )
                elif schedule.get("type") == "datum":
                    datum = schedule.get("datum", "")
                    if datum:
                        hammertime_str = TimeZoneHelper.nl_tijd_naar_hammertime(
                            datum, tijd, style="F"
                        )

            sluitingsbericht = (
                f"Deze poll is tijdelijk gesloten en gaat automatisch weer open op {hammertime_str}. "
                "Dank voor je deelname."
            )

            send = _get_attr(channel, "send")
            if send:
                try:
                    await safe_call(send, content=sluitingsbericht)
                except Exception:  # pragma: no cover
                    pass

            # 3) BELANGRIJK: Scheduler blijft actief - NIET uitschakelen!
            # Voor permanent uitschakelen, gebruik /dmk-poll-stopzetten

            # 4) Terugkoppeling
            await interaction.followup.send(
                f"✅ Alle bot-berichten zijn verwijderd. De scheduler blijft actief en zal de polls automatisch weer activeren op {hammertime_str}.",
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            from apps.utils.i18n import t

            cid = getattr(channel, "id", 0) or 0
            await interaction.followup.send(
                t(cid, "ERRORS.generic_error", error=str(e)), ephemeral=True
            )

    # -----------------------------
    # /dmk-poll-stopzetten (permanent uitschakelen)
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-stopzetten",
        description=with_default_suffix(
            "Stop de DMK-poll-bot permanent (verwijder berichten + schakel automatisme uit)"
        ),
    )
    async def stopzetten(
        self, interaction: discord.Interaction
    ) -> None:  # pragma: no cover
        """
        Stop de DMK-poll-bot PERMANENT:
        - Verwijdert alle poll-berichten
        - Schakelt automatisme UIT (disabled = true)
        - Bot moet handmatig weer gestart worden met /dmk-poll-on

        Dit verschilt van /dmk-poll-off (tijdelijk) en /dmk-poll-verwijderen (scheduler blijft actief).
        """
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            from apps.utils.i18n import t
            await interaction.followup.send(f"❌ {t(0, 'ERRORS.no_channel')}", ephemeral=True)
            return

        # Stap 1: Controleer op non-bot berichten in het kanaal
        try:
            non_bot_berichten = await self._scan_non_bot_messages(channel)
            if non_bot_berichten:
                # Er zijn non-bot berichten - vraag om bevestiging
                await self._toon_cleanup_bevestiging_stopzetten(
                    interaction, channel, non_bot_berichten
                )
                return  # De bevestigingsview handelt de rest af
        except Exception as e:
            # Als scannen faalt, ga gewoon door
            print(f"⚠️ Kon niet scannen naar oude berichten: {e}")

        # Stap 2: Voer stopzetten uit (geen non-bot berichten, dus geen bevestiging nodig)
        await self._execute_stopzetten(interaction, channel)

    async def _toon_cleanup_bevestiging_stopzetten(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        channel: Any,
        non_bot_berichten: list,
    ) -> None:
        """
        Toon een bevestigingsdialoog voor /dmk-poll-stopzetten.
        Als bevestigd: verwijder non-bot berichten + bot-berichten, schakel bot uit.
        Als geannuleerd: verwijder alleen bot-berichten, schakel bot uit.
        """
        from apps.ui.cleanup_confirmation import CleanupConfirmationView

        aantal_berichten = len(non_bot_berichten)

        async def bij_bevestiging(button_interaction: discord.Interaction):
            """Verwijder alle berichten en schakel bot permanent uit."""
            try:
                # Verwijder alle berichten (bot + non-bot)
                await self._delete_all_bot_messages(
                    channel, also_delete=non_bot_berichten
                )

                await button_interaction.edit_original_response(
                    content=f"✅ Alle berichten verwijderd (waaronder {len(non_bot_berichten)} van andere gebruikers/bots). Bot wordt permanent uitgeschakeld...",
                    view=None,
                )

                # Schakel bot permanent uit
                await self._execute_stopzetten(interaction, channel, skip_delete=True)

            except Exception as e:  # pragma: no cover
                await button_interaction.followup.send(
                    f"❌ Fout bij stopzetten: {e}",
                    ephemeral=True,
                )

        async def bij_annulering(button_interaction: discord.Interaction):
            """Verwijder alleen bot-berichten en schakel bot permanent uit."""
            try:
                await button_interaction.edit_original_response(
                    content="✅ Bot-berichten verwijderd. Bot wordt permanent uitgeschakeld...",
                    view=None,
                )

                # Schakel bot permanent uit (delete wordt gedaan door _execute_stopzetten)
                await self._execute_stopzetten(interaction, channel)

            except Exception as e:  # pragma: no cover
                await button_interaction.followup.send(
                    f"❌ Fout bij uitvoeren: {e}",
                    ephemeral=True,
                )

        view = CleanupConfirmationView(
            on_confirm=bij_bevestiging,
            on_cancel=bij_annulering,
            message_count=aantal_berichten,
        )

        await interaction.followup.send(
            f"⚠️ Er staan **{aantal_berichten}** bericht(en) van andere gebruikers/bots in dit kanaal.\n"
            f"Wil je deze verwijderen? (Bot-berichten worden altijd verwijderd)\n\n"
            f"**LET OP:** Dit schakelt de bot PERMANENT uit. Automatische activering wordt gestopt.",
            view=view,
            ephemeral=True,
        )

    async def _execute_stopzetten(  # pragma: no cover
        self, interaction: discord.Interaction, channel: Any, skip_delete: bool = False
    ) -> None:
        """
        Voer stopzetten uit: verwijder bot-berichten en schakel scheduler permanent uit.

        Args:
            skip_delete: Als True, skip het verwijderen van berichten (al gedaan)
        """
        try:
            # 1) Verwijder alle bot-berichten en wis message IDs (alleen als niet al gedaan)
            if not skip_delete:
                await self._delete_all_bot_messages(channel)

            # 2) Plaats het sluitingsbericht
            send = _get_attr(channel, "send")
            sluitingsbericht = (
                "🛑 **DMK-poll-bot is permanent uitgeschakeld.**\n\n"
                "De automatische activering is gestopt. "
                "Gebruik `/dmk-poll-on` om de bot weer te starten."
            )
            if send:
                try:
                    await safe_call(send, content=sluitingsbericht)
                except Exception:  # pragma: no cover
                    pass

            # 3) Schakel scheduler PERMANENT uit (disabled = true)
            set_channel_disabled(channel.id, True)

            # 4) Wis geplande activatie
            try:
                clear_scheduled_activation(channel.id)
            except Exception:  # pragma: no cover
                pass

            # 5) Terugkoppeling
            await interaction.followup.send(
                "✅ DMK-poll-bot is permanent uitgeschakeld.\n"
                "- Alle bot-berichten zijn verwijderd\n"
                "- Automatische activering is gestopt\n"
                "- Gebruik `/dmk-poll-on` om de bot weer te starten",
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            from apps.utils.i18n import t

            cid = getattr(channel, "id", 0) or 0
            await interaction.followup.send(
                t(cid, "ERRORS.generic_error", error=str(e)), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollLifecycle(bot))
