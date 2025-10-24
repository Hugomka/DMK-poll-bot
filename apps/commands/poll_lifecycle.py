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

        # Valideer datum formaat (YYYY-MM-DD)
        if datum:
            try:
                datetime.strptime(datum, "%Y-%m-%d")
            except ValueError:
                return "Datum moet in YYYY-MM-DD formaat zijn (bijv. 2025-12-31)."

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
            set_scheduled_activation(channel_id, activation_type, tijd, datum=datum)
            datum_obj = datetime.strptime(datum, "%Y-%m-%d")
            dag_naam = [
                "maandag",
                "dinsdag",
                "woensdag",
                "donderdag",
                "vrijdag",
                "zaterdag",
                "zondag",
            ][datum_obj.weekday()]
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
        description="Plaats of update de polls per avond (standaard: beheerder/moderator)",
    )
    @app_commands.describe(
        dag="Weekdag (maandag t/m zondag) - verplicht met tijd",
        datum="Specifieke datum (YYYY-MM-DD) - verplicht met tijd",
        tijd="Tijd in HH:mm formaat - verplicht met dag of datum",
        frequentie="Eenmalig (op datum) of wekelijks (elke week op deze dag)",
    )
    async def on(
        self,
        interaction: discord.Interaction,
        dag: Literal[
            "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"
        ]
        | None = None,
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
        validation_error = self._validate_scheduling_params(dag, datum, tijd, frequentie)
        if validation_error:
            await interaction.followup.send(f"❌ {validation_error}", ephemeral=True)
            return

        # Als er scheduling parameters zijn, sla ze op
        schedule_message = None
        if tijd and (dag or datum):
            schedule_message = await self._save_schedule(
                channel.id, dag, datum, tijd, frequentie
            )

        # Stap 1: Controleer op oude berichten in het kanaal
        try:
            oude_berichten = await self._scan_oude_berichten(channel)
            if oude_berichten:
                # Er zijn oude berichten - vraag om bevestiging
                await self._toon_opschoon_bevestiging(
                    interaction, channel, oude_berichten, schedule_message
                )
                return  # De bevestigingsview handelt de rest af
        except Exception as e:
            # Als scannen faalt, ga gewoon door
            print(f"⚠️ Kon niet scannen naar oude berichten: {e}")

        # Stap 2: Plaats de polls (indien geen opschoning nodig of na opschoning)
        await self._plaats_polls(interaction, channel, schedule_message)

    async def _scan_oude_berichten(self, channel: Any) -> list:
        """
        Scan het kanaal voor ALLE berichten (inclusief bot's eigen berichten).

        Returns:
            Lijst met alle berichten die verwijderd kunnen worden
        """
        oude_berichten = []
        try:
            # Haal laatste 100 berichten op (ALLE berichten, ook van de bot)
            async for bericht in channel.history(limit=100):
                oude_berichten.append(bericht)
        except Exception:  # pragma: no cover
            pass
        return oude_berichten

    async def _toon_opschoon_bevestiging(
        self,
        interaction: discord.Interaction,
        channel: Any,
        oude_berichten: list,
        schedule_message: str | None = None,
    ) -> None:
        """
        Toon een bevestigingsdialoog voor het opschonen van oude berichten.
        """
        from apps.ui.cleanup_confirmation import CleanupConfirmationView

        aantal_berichten = len(oude_berichten)

        async def bij_bevestiging(button_interaction: discord.Interaction):
            """Verwijder oude berichten en plaats polls."""
            try:
                verwijderd_aantal = 0
                for bericht in oude_berichten:
                    try:
                        await bericht.delete()
                        verwijderd_aantal += 1
                    except Exception:  # pragma: no cover
                        pass  # Sla berichten over die niet verwijderd kunnen worden

                await button_interaction.edit_original_response(
                    content=f"✅ {verwijderd_aantal} bericht(en) verwijderd. De polls worden nu geplaatst...",
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
            """Plaats polls zonder berichten te verwijderen."""
            try:
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
            f"⚠️ Er staan **{aantal_berichten}** bericht(en) in dit kanaal.\n"
            f"Wil je deze verwijderen voor een schone start?",
            view=view,
            ephemeral=True,
        )

    async def _plaats_polls(
        self, interaction: discord.Interaction, channel: Any, schedule_message: str | None = None
    ) -> None:
        """
        Plaats of update de poll-berichten in het kanaal.
        """
        dagen = ["vrijdag", "zaterdag", "zondag"]

        try:
            # Kanaal opnieuw activeren voor de scheduler
            try:
                set_channel_disabled(getattr(channel, "id", 0), False)
            except Exception:  # pragma: no cover
                # Niet hard falen als togglen mislukt; we gaan verder met plaatsen
                pass

            # Unpause if currently paused
            try:
                from apps.utils.poll_settings import set_paused

                set_paused(getattr(channel, "id", 0), False)
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
                    dag, gid_val, cid_val, guild=guild
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
            n_mid = get_message_id(channel.id, "notification")
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
                confirmation = "✅ Polls zijn weer ingeschakeld en geplaatst/bijgewerkt."
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
        description="Reset alle stemmen en data (standaard: beheerder/moderator)",
    )
    async def reset(self, interaction: discord.Interaction) -> None:
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

                await append_week_snapshot_scoped(gid, cid)
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
        description="Pauzeer of hervat de poll (standaard: beheerder/moderator)",
    )
    async def pauze(self, interaction: discord.Interaction) -> None:
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
        description="Schakel polls uit en maak kanaal leeg (standaard: beheerder/moderator)",
    )
    @app_commands.describe(
        dag="Weekdag (maandag t/m zondag) - verplicht met tijd",
        datum="Specifieke datum (YYYY-MM-DD) - verplicht met tijd",
        tijd="Tijd in HH:mm formaat - verplicht met dag of datum",
        frequentie="Eenmalig (op datum) of wekelijks (elke week op deze dag)",
    )
    async def off(
        self,
        interaction: discord.Interaction,
        dag: Literal[
            "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"
        ]
        | None = None,
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
        validation_error = self._validate_scheduling_params(dag, datum, tijd, frequentie)
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
            set_scheduled_deactivation(channel_id, activation_type, tijd, datum=datum)
            datum_obj = datetime.strptime(datum, "%Y-%m-%d")
            dag_naam = [
                "maandag",
                "dinsdag",
                "woensdag",
                "donderdag",
                "vrijdag",
                "zaterdag",
                "zondag",
            ][datum_obj.weekday()]
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

    async def _execute_poll_off(
        self, interaction: discord.Interaction, channel: Any
    ) -> None:
        """
        Voer poll-off uit: kanaal leegmaken + scheduler uitschakelen.
        """
        dagen = ["vrijdag", "zaterdag", "zondag"]

        try:
            gevonden = False

            # 0) Opening bericht verwijderen
            opening_mid = get_message_id(channel.id, "opening")
            if opening_mid:
                opening_msg = await fetch_message_or_none(channel, opening_mid)
                if opening_msg is not None:
                    try:
                        await safe_call(opening_msg.delete)
                    except Exception:  # pragma: no cover
                        await safe_call(
                            opening_msg.edit, content="📴 Poll gesloten.", view=None
                        )
                clear_message_id(channel.id, "opening")
                gevonden = True

            # 1) Dag-berichten verwijderen
            for dag in dagen:
                mid = get_message_id(channel.id, dag)
                if not mid:
                    continue
                gevonden = True
                msg = await fetch_message_or_none(channel, mid)
                if msg is not None:
                    try:
                        await safe_call(msg.delete)
                    except Exception:  # pragma: no cover
                        afsluit_tekst = "📴 Deze poll is gesloten. Dank voor je deelname."
                        await safe_call(msg.edit, content=afsluit_tekst, view=None)
                clear_message_id(channel.id, dag)

            # 2) Stemmen-bericht verwijderen
            s_mid = get_message_id(channel.id, "stemmen")
            if s_mid:
                s_msg = await fetch_message_or_none(channel, s_mid)
                if s_msg is not None:
                    try:
                        await safe_call(s_msg.delete)
                    except Exception:  # pragma: no cover
                        await safe_call(
                            s_msg.edit, content="📴 Stemmen gesloten.", view=None
                        )
                clear_message_id(channel.id, "stemmen")

            # 3) Notificatiebericht verwijderen
            n_mid = get_message_id(channel.id, "notification")
            if n_mid:
                n_msg = await fetch_message_or_none(channel, n_mid)
                if n_msg is not None:
                    try:
                        await safe_call(n_msg.delete)
                    except Exception:  # pragma: no cover
                        await safe_call(
                            n_msg.edit, content="📴 Notificaties gesloten.", view=None
                        )
                clear_message_id(channel.id, "notification")

            # 4) Kanaal permanent uitzetten voor scheduler
            try:
                set_channel_disabled(getattr(channel, "id", 0), True)
            except Exception:  # pragma: no cover
                pass

            # 5) Wis geplande activatie (voor /dmk-poll-on)
            try:
                clear_scheduled_activation(getattr(channel, "id", 0))
            except Exception:  # pragma: no cover
                pass

            # 6) Terugkoppeling
            if gevonden:
                await interaction.followup.send(
                    "✅ Polls uitgeschakeld. Scheduler voor dit kanaal is uitgezet. Gebruik /dmk-poll-on om later opnieuw te starten.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "ℹ️ Er stonden geen poll-berichten meer in dit kanaal. De scheduler is nu uitgezet zodat ze niet terugkomen. Gebruik /dmk-poll-on om later opnieuw te starten.",
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
        description="Verwijder pollberichten en plaats sluitingsbericht - scheduler blijft actief (standaard: beheerder/moderator)",
    )
    async def verwijderbericht(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return
        dagen = ["vrijdag", "zaterdag", "zondag"]

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

                        datum_obj = datetime.strptime(datum, "%Y-%m-%d")
                        dag_naam = [
                            "maandag",
                            "dinsdag",
                            "woensdag",
                            "donderdag",
                            "vrijdag",
                            "zaterdag",
                            "zondag",
                        ][datum_obj.weekday()]
                        closing_time = f"{dag_naam} {datum} om {tijd} uur"

            sluitingsbericht = (
                f"Deze poll is gesloten en gaat pas **{closing_time}** weer open. "
                "Dank voor je deelname."
            )

            gevonden = False

            # 0) Opening bericht verwijderen
            opening_mid = get_message_id(channel.id, "opening")
            if opening_mid:
                opening_msg = await fetch_message_or_none(channel, opening_mid)
                if opening_msg is not None:
                    try:
                        await safe_call(opening_msg.delete)
                    except Exception:  # pragma: no cover
                        pass
                clear_message_id(channel.id, "opening")
                gevonden = True

            # 1) Dag-berichten verwijderen
            for dag in dagen:
                mid = get_message_id(channel.id, dag)
                if not mid:
                    continue
                gevonden = True
                msg = await fetch_message_or_none(channel, mid)
                if msg is not None:
                    try:
                        await safe_call(msg.delete)
                    except Exception:  # pragma: no cover
                        pass
                clear_message_id(channel.id, dag)

            # 2) Stemmen-bericht verwijderen
            s_mid = get_message_id(channel.id, "stemmen")
            if s_mid:
                s_msg = await fetch_message_or_none(channel, s_mid)
                if s_msg is not None:
                    try:
                        await safe_call(s_msg.delete)
                    except Exception:  # pragma: no cover
                        pass
                clear_message_id(channel.id, "stemmen")

            # 3) Notificatiebericht verwijderen
            n_mid = get_message_id(channel.id, "notification")
            if n_mid:
                n_msg = await fetch_message_or_none(channel, n_mid)
                if n_msg is not None:
                    try:
                        await safe_call(n_msg.delete)
                    except Exception:  # pragma: no cover
                        pass
                clear_message_id(channel.id, "notification")

            # 4) Plaats het sluitingsbericht
            send = _get_attr(channel, "send")
            if send:
                try:
                    await safe_call(send, content=sluitingsbericht)
                except Exception:  # pragma: no cover
                    pass

            # 5) Scheduler blijft actief - NIET uitschakelen!
            # (Dat is het verschil met /dmk-poll-off)

            # 6) Terugkoppeling
            if gevonden:
                await interaction.followup.send(
                    f"✅ Polls verwijderd en sluitingsbericht geplaatst. De scheduler blijft actief en zal de polls automatisch weer activeren op {closing_time}.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"ℹ️ Er stonden geen poll-berichten meer in dit kanaal. Sluitingsbericht geplaatst. De scheduler blijft actief en zal de polls automatisch weer activeren op {closing_time}.",
                    ephemeral=True,
                )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollLifecycle(bot))
