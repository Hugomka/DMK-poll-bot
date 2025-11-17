# apps/commands/poll_lifecycle.py
#
# Poll levenscyclus: aanmaken, reset, pauze, verwijderen

from __future__ import annotations

import os
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
    update_poll_message,
)
from apps.utils.poll_settings import (
    clear_scheduled_activation,
    is_paused,
    set_scheduled_activation,
    should_hide_counts,
    toggle_paused,
)
from apps.utils.poll_storage import reset_votes, reset_votes_scoped


def _load_opening_message() -> str:
    """Laad het opening bericht uit config/opening_message.txt."""
    OPENING_MESSAGE = "opening_message.txt"
    DEFAULT_MESSAGE = "@everyone \n# 🎮 **Welkom bij de Deaf Mario Kart-poll!**"
    if not (os.path.exists(OPENING_MESSAGE)):
        return DEFAULT_MESSAGE
    try:
        with open(OPENING_MESSAGE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:  # pragma: no cover
        # Fallback als het bestand niet bestaat of niet gelezen kan worden
        return DEFAULT_MESSAGE


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
    ) -> str | None:
        """
        Valideer de scheduling parameters.
        Retourneert een foutmelding als de parameters ongeldig zijn, anders None.
        """
        # Als geen parameters, dan handmatig activeren (standaard gedrag)
        if not tijd and not dag and not datum and not frequentie:
            return None

        # tijd is verplicht met dag of datum
        if (dag or datum) and not tijd:
            return "De parameter 'tijd' is verplicht samen met 'dag' of 'datum'."

        # dag en datum kunnen niet samen
        if dag and datum:
            return "Je kunt niet zowel 'dag' als 'datum' opgeven. Kies één van beide."

        # tijd kan niet zonder dag of datum
        if tijd and not dag and not datum:
            return "De parameter 'tijd' kan niet zonder 'dag' of 'datum'."

        # Valideer tijd formaat (HH:mm)
        if tijd:
            try:
                parts = tijd.split(":")
                if len(parts) != 2:
                    return "Tijd moet in HH:mm formaat zijn (bijv. 20:00)."
                uur, minuut = int(parts[0]), int(parts[1])
                if not (0 <= uur <= 23 and 0 <= minuut <= 59):
                    return "Ongeldige tijd. Uur moet 0-23 zijn, minuut moet 0-59 zijn."
            except ValueError:
                return "Tijd moet in HH:mm formaat zijn (bijv. 20:00)."

        # Valideer datum formaat (DD-MM-YYYY)
        if datum:
            try:
                datetime.strptime(datum, "%d-%m-%Y")
            except ValueError:
                return "Datum moet in DD-MM-YYYY formaat zijn (bijv. 31-12-2025)."

        # frequentie validatie
        if frequentie:
            if frequentie == "eenmalig" and not datum:
                return "Frequentie 'eenmalig' vereist een 'datum' parameter."
            if frequentie == "wekelijks" and not dag:
                return "Frequentie 'wekelijks' vereist een 'dag' parameter."

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
            if is_recurrent:
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
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        # Valideer parameters
        validation_error = self._validate_scheduling_params(
            dag, datum, tijd, frequentie
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
                    interaction, channel, non_bot_berichten, schedule_message=None
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

        # Stap 3: Plaats de polls (handmatige activatie zonder scheduling)
        await self._plaats_polls(interaction, channel, schedule_message=None)

    async def _toon_opschoon_bevestiging(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        channel: Any,
        non_bot_berichten: list,
        schedule_message: str | None = None,
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
                await self._delete_all_bot_messages(channel, also_delete=non_bot_berichten)

                verwijderd_aantal = len(non_bot_berichten)
                await button_interaction.edit_original_response(
                    content=f"✅ Alle berichten verwijderd (waaronder {verwijderd_aantal} van andere gebruikers/bots). De polls worden nu geplaatst...",
                    view=None,
                )

                # Plaats de polls
                await self._plaats_polls(interaction, channel, schedule_message)

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
                await self._plaats_polls(interaction, channel, schedule_message)
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
                await self._delete_all_bot_messages(channel, also_delete=non_bot_berichten)

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
    ) -> None:
        """
        Plaats of update de poll-berichten in het kanaal.
        """
        # Gebruik enabled dagen op basis van poll-opties settings
        from apps.utils.poll_settings import get_enabled_poll_days

        channel_id = getattr(channel, "id", 0)
        dagen = get_enabled_poll_days(channel_id)

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

            # Eerste bericht: Opening met @everyone
            opening_text = _load_opening_message() + "\n\u200b"

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
                        await safe_call(send, content=opening_text) if send else None
                    )
                    if opening_msg is not None:
                        save_message_id(channel.id, "opening", opening_msg.id)
            else:
                # Maak nieuw opening bericht
                opening_msg = (
                    await safe_call(send, content=opening_text) if send else None
                )
                if opening_msg is not None:
                    save_message_id(channel.id, "opening", opening_msg.id)

            # Tweede t/m vierde berichten: dag-berichten (ALLEEN TEKST, GEEN KNOPPEN)
            guild = _get_attr(channel, "guild")
            for dag in dagen:
                gid_val = getattr(guild, "id", "0") if guild is not None else "0"
                cid_val = getattr(channel, "id", "0") or "0"
                content = await build_poll_message_for_day_async(
                    dag, gid_val, cid_val, guild=guild, channel=channel
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
            key = "stemmen"
            tekst = "Klik op **🗳️ Stemmen** om je keuzes te maken."
            s_mid = get_message_id(channel.id, key)
            paused = is_paused(channel.id)
            view = OneStemButtonView(paused=paused)
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
                confirmation = (
                    "✅ Polls zijn weer ingeschakeld en geplaatst/bijgewerkt."
                )
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
                await interaction.followup.send(
                    f"❌ Fout bij plaatsen: {e}", ephemeral=True
                )
            except Exception:  # pragma: no cover
                # Als interaction al is afgehandeld, print alleen de fout
                print(f"❌ Fout bij plaatsen polls: {e}")

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
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return
        dagen = ["vrijdag", "zaterdag", "zondag"]

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
                    tekst = "Klik op **🗳️ Stemmen** om je keuzes te maken."
                    view = OneStemButtonView(paused=paused)
                    await safe_call(s_msg.edit, content=tekst, view=view)

            # 6) Terugkoppeling
            if gevonden:
                await interaction.followup.send(
                    "🔄 De stemmen zijn gereset voor een nieuwe week.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "⚠️ Geen dag-berichten gevonden om te resetten.", ephemeral=True
                )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Reset mislukt: {e}", ephemeral=True)

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
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        try:
            # 1) Toggle pauze-status
            paused = toggle_paused(channel.id)  # True = nu gepauzeerd

            # 2) Stemmen-bericht updaten (knop disabled + tekst)
            key = "stemmen"
            mid = get_message_id(channel.id, key)
            tekst = (
                "⏸️ Stemmen is tijdelijk gepauzeerd."
                if paused
                else "Klik op **🗳️ Stemmen** om je keuzes te maken."
            )
            view = OneStemButtonView(paused=paused)

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

            status_txt = "gepauzeerd" if paused else "hervat"
            await interaction.followup.send(
                f"⏯️ Stemmen is {status_txt}.", ephemeral=True
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

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
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        # Valideer parameters
        validation_error = self._validate_scheduling_params(
            dag, datum, tijd, frequentie
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
        message_keys = ["opening", "vrijdag", "zaterdag", "zondag", "stemmen",
                      "notification_temp", "notification_persistent", "notification",
                      "celebration"]
        for key in message_keys:
            try:
                clear_message_id(channel_id, key)
            except Exception:  # pragma: no cover
                pass

    async def _execute_poll_off(  # pragma: no cover
        self, interaction: discord.Interaction, channel: Any
    ) -> None:
        """
        Voer poll-off uit: verwijder alle bot-berichten + scheduler uitschakelen.
        """
        try:
            # 1) Verwijder alle bot-berichten en wis message IDs
            await self._delete_all_bot_messages(channel)

            # 2) Kanaal permanent uitzetten voor scheduler
            channel_id = getattr(channel, "id", 0)
            try:
                set_channel_disabled(channel_id, True)
            except Exception:  # pragma: no cover
                pass

            # 3) Wis geplande activatie (voor /dmk-poll-on)
            try:
                clear_scheduled_activation(channel_id)
            except Exception:  # pragma: no cover
                pass

            # 4) Terugkoppeling
            await interaction.followup.send(
                "✅ Alle bot-berichten zijn verwijderd. Scheduler voor dit kanaal is uitgezet. Gebruik /dmk-poll-on om later opnieuw te starten.",
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    # -----------------------------
    # /dmk-poll-verwijderen (nieuw: eenvoudig)
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-verwijderen",
        description=with_default_suffix(
            "Verwijder pollberichten en plaats sluitingsbericht"
        ),
    )
    async def verwijderbericht(
        self, interaction: discord.Interaction
    ) -> None:  # pragma: no cover
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        # Stap 1: Controleer op non-bot berichten in het kanaal
        try:
            non_bot_berichten = await self._scan_non_bot_messages(channel)
            if non_bot_berichten:
                # Er zijn non-bot berichten - vraag om bevestiging
                await self._toon_cleanup_bevestiging_verwijderen(
                    interaction, channel, non_bot_berichten
                )
                return  # De bevestigingsview handelt de rest af
        except Exception as e:
            # Als scannen faalt, ga gewoon door
            print(f"⚠️ Kon niet scannen naar oude berichten: {e}")

        # Stap 2: Voer verwijderen uit (geen non-bot berichten, dus geen bevestiging nodig)
        await self._execute_verwijderen(interaction, channel)

    async def _toon_cleanup_bevestiging_verwijderen(  # pragma: no cover
        self,
        interaction: discord.Interaction,
        channel: Any,
        non_bot_berichten: list,
    ) -> None:
        """
        Toon een bevestigingsdialoog voor /dmk-poll-verwijderen.
        Als bevestigd: verwijder non-bot berichten + bot-berichten, dan sluitingsbericht plaatsen.
        Als geannuleerd: verwijder alleen bot-berichten, dan sluitingsbericht plaatsen.
        """
        from apps.ui.cleanup_confirmation import CleanupConfirmationView

        aantal_berichten = len(non_bot_berichten)

        async def bij_bevestiging(button_interaction: discord.Interaction):
            """Verwijder alle berichten en plaats sluitingsbericht."""
            try:
                # Verwijder alle berichten (bot + non-bot)
                await self._delete_all_bot_messages(channel, also_delete=non_bot_berichten)

                await button_interaction.edit_original_response(
                    content=f"✅ Alle berichten verwijderd (waaronder {len(non_bot_berichten)} van andere gebruikers/bots). Sluitingsbericht wordt geplaatst...",
                    view=None,
                )

                # Plaats sluitingsbericht
                await self._execute_verwijderen(interaction, channel, skip_delete=True)

            except Exception as e:  # pragma: no cover
                await button_interaction.followup.send(
                    f"❌ Fout bij verwijderen: {e}",
                    ephemeral=True,
                )

        async def bij_annulering(button_interaction: discord.Interaction):
            """Verwijder alleen bot-berichten en plaats sluitingsbericht."""
            try:
                await button_interaction.edit_original_response(
                    content="✅ Bot-berichten verwijderd. Sluitingsbericht wordt geplaatst...",
                    view=None,
                )

                # Plaats sluitingsbericht (delete wordt gedaan door _execute_verwijderen)
                await self._execute_verwijderen(interaction, channel)

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

    async def _execute_verwijderen(  # pragma: no cover
        self, interaction: discord.Interaction, channel: Any, skip_delete: bool = False
    ) -> None:
        """
        Voer verwijderen uit: verwijder bot-berichten en plaats sluitingsbericht.
        Scheduler blijft actief.

        Args:
            skip_delete: Als True, skip het verwijderen van berichten (al gedaan)
        """
        try:
            # Bepaal de sluitingstijd op basis van /dmk-poll-on instellingen
            from apps.utils.poll_settings import get_scheduled_activation

            schedule = get_scheduled_activation(channel.id)
            closing_time = "dinsdag om 20:00 uur"  # Standaard

            if schedule:
                tijd = schedule.get("tijd", "20:00")
                if schedule.get("type") == "wekelijks":
                    dag_naam = schedule.get("dag", "dinsdag")
                    closing_time = f"{dag_naam} om {tijd} uur"
                elif schedule.get("type") == "datum":
                    datum = schedule.get("datum", "")
                    if datum:
                        from datetime import datetime

                        # Convert from internal YYYY-MM-DD to display DD-MM-YYYY
                        datum_obj = datetime.strptime(datum, "%Y-%m-%d")
                        datum_display = datum_obj.strftime("%d-%m-%Y")
                        dag_naam = [
                            "maandag",
                            "dinsdag",
                            "woensdag",
                            "donderdag",
                            "vrijdag",
                            "zaterdag",
                            "zondag",
                        ][datum_obj.weekday()]
                        closing_time = f"{dag_naam} {datum_display} om {tijd} uur"

            sluitingsbericht = (
                f"Deze poll is gesloten en gaat pas **{closing_time}** weer open. "
                "Dank voor je deelname."
            )

            # 1) Verwijder alle bot-berichten en wis message IDs (alleen als niet al gedaan)
            if not skip_delete:
                await self._delete_all_bot_messages(channel)

            # 2) Plaats het sluitingsbericht
            send = _get_attr(channel, "send")
            if send:
                try:
                    await safe_call(send, content=sluitingsbericht)
                except Exception:  # pragma: no cover
                    pass

            # 3) Scheduler blijft actief - NIET uitschakelen!
            # (Dat is het verschil met /dmk-poll-off)

            # 4) Terugkoppeling
            await interaction.followup.send(
                f"✅ Alle bot-berichten zijn verwijderd en sluitingsbericht geplaatst. De scheduler blijft actief en zal de polls automatisch weer activeren op {closing_time}.",
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollLifecycle(bot))
