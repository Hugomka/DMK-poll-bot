# apps/commands/dmk_poll.py
#
# Richtlijn:
# - Standaard mogen *alle leden* commands gebruiken (geen decorator nodig).
# - Voor admin en moderator als default gebruik je @app_commands.default_permissions(moderate_members=True).
# - Alle DMK-commands zijn server-only (geen DM's): @app_commands.guild_only()
#
# Beheerders kunnen deze defaults later aanpassen per server via:
# Server Settings → Integrations → [jouw bot] → Commands.
# (Daar kun je per command rollen/leden/kanalen aan- of uitzetten.)

from __future__ import annotations

import io
import os
import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import discord
from discord import File, app_commands
from discord.ext import commands

from apps import scheduler
from apps.entities.poll_option import get_poll_options
from apps.ui.poll_buttons import OneStemButtonView
from apps.utils.archive import (
    append_week_snapshot_scoped,
    archive_exists_scoped,
    delete_archive_scoped,
    open_archive_bytes_scoped,
)
from apps.utils.discord_client import fetch_message_or_none, safe_call
from apps.utils.message_builder import (
    build_grouped_names_for,
    build_poll_message_for_day_async,
)
from apps.utils.poll_message import (
    clear_message_id,
    create_notification_message,
    get_message_id,
    is_channel_disabled,
    save_message_id,
    set_channel_disabled,
    update_poll_message,
)
from apps.utils.poll_settings import (
    get_setting,
    is_paused,
    set_visibility,
    should_hide_counts,
    toggle_paused,
)
from apps.utils.poll_storage import (
    add_guest_votes,
    load_votes,
    remove_guest_votes,
    reset_votes,
    reset_votes_scoped,
)

try:
    from apps.ui.archive_view import ArchiveDeleteView
except Exception:  # pragma: no cover
    ArchiveDeleteView = None


RESET_TEXT = (
    "@everyone De poll is zojuist gereset voor het nieuwe weekend. "
    "Je kunt weer stemmen. Veel plezier!"
)


def _load_opening_message() -> str:
    """Laad het opening bericht uit config/opening_message.txt."""
    OPENING_MESSAGE = "opening_message.txt"
    DEFAULT_MESSAGE = "@everyone \n# 🎮 **Welkom bij de Deaf Mario Kart-poll!**"
    if not (os.path.exists(OPENING_MESSAGE)):
        return DEFAULT_MESSAGE
    try:
        with open(OPENING_MESSAGE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        # Fallback als het bestand niet bestaat of niet gelezen kan worden
        return DEFAULT_MESSAGE


def _is_poll_channel(channel) -> bool:
    """Alleen toestaan in een kanaal waar de bot actief is (heeft poll-IDs)."""
    try:
        cid = int(getattr(channel, "id", 0))
    except Exception:
        return False
    if not cid:
        return False
    for key in ("opening", "vrijdag", "zaterdag", "zondag", "stemmen", "notification"):
        try:
            if get_message_id(cid, key):
                return True
        except Exception:
            # defensief: negeer kapotte opslag
            continue
    return False


def _is_denied_channel(channel) -> bool:
    names = set(
        n.strip().lower()
        for n in os.getenv("DENY_CHANNEL_NAMES", "").split(",")
        if n.strip()
    )
    ch_name = (getattr(channel, "name", "") or "").lower()
    return ch_name in names


def _get_attr(obj: Any, name: str) -> Any:
    """Helper om attribute access type-veilig te doen richting Pylance."""
    return getattr(obj, name, None)


class DMKPoll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(
            error, (app_commands.MissingPermissions, app_commands.CheckFailure)
        ):
            await interaction.response.send_message(
                "🚫 Sorry, je bent geen beheerder of moderator. Je kunt dit commando niet gebruiken.",
                ephemeral=True,
            )
        else:
            raise error

    # -----------------------------
    # /dmk-poll-on
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-on",
        description="Plaats of update de polls per avond (standaard: beheerder/moderator)",
    )
    async def on(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        dagen = ["vrijdag", "zaterdag", "zondag"]

        try:
            # Kanaal opnieuw activeren voor de scheduler
            try:
                set_channel_disabled(getattr(channel, "id", 0), False)
            except Exception:
                # Niet hard falen als togglen mislukt; we gaan verder met plaatsen
                pass

            # Unpause if currently paused
            try:
                from apps.utils.poll_settings import set_paused

                set_paused(getattr(channel, "id", 0), False)
            except Exception:
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

            # Vijfde bericht: notificatiebericht (leeg, voor later gebruik)
            n_mid = get_message_id(channel.id, "notification")
            if not n_mid:
                # Alleen aanmaken als het nog niet bestaat
                await create_notification_message(channel)

            await interaction.followup.send(
                "✅ Polls zijn weer ingeschakeld en geplaatst/bijgewerkt.",
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(
                f"❌ Fout bij plaatsen: {e}", ephemeral=True
            )

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
                await append_week_snapshot_scoped(gid, cid)
            except Exception as e:  # pragma: no cover
                print(f"⚠️ append_week_snapshot_scoped mislukte: {e}")

            # 2) Stemmen wissen (per kanaal)
            try:
                await reset_votes_scoped(gid, cid)
            except Exception:
                await reset_votes()

            # 3) Update reset-tijd in scheduler-state
            now = datetime.now(scheduler.TZ)
            try:
                state = scheduler._read_state()
                state["reset_polls"] = now.isoformat()
                scheduler._write_state(state)
            except Exception as e:
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
    # /dmk-poll-verwijderen
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-verwijderen",
        description="Verwijder de pollberichten uit huidige kanaal (standaard: beheerder/moderator)",
    )
    async def verwijderbericht(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return
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
                    except Exception:
                        # Als delete niet mag, dan in elk geval neutraliseren
                        await safe_call(
                            opening_msg.edit, content="📴 Poll gesloten.", view=None
                        )
                clear_message_id(channel.id, "opening")
                gevonden = True

            # 1) Dag-berichten afsluiten (knop-vrij) en keys wissen
            for dag in dagen:
                mid = get_message_id(channel.id, dag)
                if not mid:
                    continue
                gevonden = True
                msg = await fetch_message_or_none(channel, mid)
                if msg is not None:
                    afsluit_tekst = "📴 Deze poll is gesloten. Dank voor je deelname."
                    await safe_call(msg.edit, content=afsluit_tekst, view=None)
                # Key altijd opschonen
                clear_message_id(channel.id, dag)

            # 2) Losse "Stemmen"-bericht ook opruimen
            s_mid = get_message_id(channel.id, "stemmen")
            if s_mid:
                s_msg = await fetch_message_or_none(channel, s_mid)
                if s_msg is not None:
                    try:
                        await safe_call(s_msg.delete)
                    except Exception:
                        # Als delete niet mag, dan in elk geval neutraliseren
                        await safe_call(
                            s_msg.edit, content="📴 Stemmen gesloten.", view=None
                        )
                clear_message_id(channel.id, "stemmen")

            # 3) Notificatiebericht ook opruimen
            n_mid = get_message_id(channel.id, "notification")
            if n_mid:
                n_msg = await fetch_message_or_none(channel, n_mid)
                if n_msg is not None:
                    try:
                        await safe_call(n_msg.delete)
                    except Exception:
                        # Als delete niet mag, dan in elk geval neutraliseren
                        await safe_call(
                            n_msg.edit, content="📴 Notificaties gesloten.", view=None
                        )
                clear_message_id(channel.id, "notification")

            # 4) Kanaal permanent uitzetten voor scheduler (altijd doen)
            try:
                set_channel_disabled(getattr(channel, "id", 0), True)
            except Exception:
                pass

            # 5) Terugkoppeling
            if gevonden:
                await interaction.followup.send(
                    "✅ Polls verwijderd. Scheduler voor dit kanaal is uitgezet. Gebruik /dmk-poll-on om later opnieuw te starten.",
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
    # /dmk-poll-stemmen
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-stemmen",
        description="Toon of verberg stemmenaantallen tot de deadline. (standaard: beheerder/moderator)",
    )
    @app_commands.choices(
        actie=[
            app_commands.Choice(name="Zichtbaar maken", value="zichtbaar"),
            app_commands.Choice(name="Verbergen tot deadline", value="verborgen"),
        ],
        dag=[
            app_commands.Choice(name="Vrijdag", value="vrijdag"),
            app_commands.Choice(name="Zaterdag", value="zaterdag"),
            app_commands.Choice(name="Zondag", value="zondag"),
        ],
    )
    @app_commands.describe(tijd="Tijdstip in uu:mm (alleen nodig bij verborgen modus)")
    async def stemmen(
        self,
        interaction: discord.Interaction,
        actie: app_commands.Choice[str],
        dag: Optional[app_commands.Choice[str]] = None,
        tijd: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        try:
            if dag and dag.value:
                doel_dagen = [dag.value]
            else:
                doel_dagen = ["vrijdag", "zaterdag", "zondag"]

            laatste: Optional[dict] = None
            for d in doel_dagen:
                if actie.value == "zichtbaar":
                    laatste = set_visibility(channel.id, d, modus="altijd")
                else:
                    laatste = set_visibility(
                        channel.id, d, modus="deadline", tijd=(tijd or "18:00")
                    )
                await update_poll_message(channel, d)

            tijd_txt = (laatste or {}).get("tijd", "18:00")
            modus_txt = (
                "altijd zichtbaar"
                if (laatste or {}).get("modus") == "altijd"
                else f"verborgen tot {tijd_txt}"
            )

            if dag and dag.value:
                await interaction.followup.send(
                    f"⚙️ Instelling voor {dag.value} gewijzigd naar: **{modus_txt}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"⚙️ Instellingen voor alle dagen gewijzigd naar: **{modus_txt}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
                    ephemeral=True,
                )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    # -----------------------------
    # Archief
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-archief-download",
        description="Download het CSV-archief met weekresultaten. (standaard: beheerder/moderator)",
    )
    async def archief_download(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=False)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        guild = getattr(interaction, "guild", None) or getattr(channel, "guild", None)
        gid = int(getattr(guild, "id", 0)) if guild else 0
        cid = int(getattr(channel, "id", 0))

        try:
            if not archive_exists_scoped(gid, cid):
                await interaction.followup.send(
                    "Er is nog geen archief voor dit kanaal.", ephemeral=True
                )
                return

            filename, data = open_archive_bytes_scoped(gid, cid)
            if not data:
                await interaction.followup.send(
                    "Archief kon niet worden gelezen.", ephemeral=True
                )
                return

            if ArchiveDeleteView is None:
                await interaction.followup.send(
                    content="CSV-archief met weekresultaten voor dit kanaal.",
                    file=File(io.BytesIO(data), filename=filename),
                )
                return

            view = ArchiveDeleteView(gid, cid)
            await interaction.followup.send(
                "CSV-archief met weekresultaten voor dit kanaal. Wil je het hierna verwijderen?",
                file=File(io.BytesIO(data), filename=filename),
                view=view,
            )
        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-archief-verwijderen",
        description="Verwijder het volledige archief. (standaard: beheerder/moderator)",
    )
    async def archief_verwijderen(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        guild = getattr(interaction, "guild", None) or getattr(channel, "guild", None)
        gid = int(getattr(guild, "id", 0)) if guild else 0
        cid = int(getattr(channel, "id", 0))

        try:
            ok = delete_archive_scoped(gid, cid)
            msg = (
                "Archief voor dit kanaal verwijderd. ✅"
                if ok
                else "Er was geen archief om te verwijderen voor dit kanaal."
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    # -----------------------------
    # /dmk-poll-status
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-status",
        description="Toon pauze, zichtbaarheid en alle stemmen per dag. (standaard: beheerder/moderator)",
    )
    async def status(self, interaction: discord.Interaction) -> None:
        # Alleen defer hier, de echte logica staat in _status_impl
        await interaction.response.defer(ephemeral=True)
        await self._status_impl(interaction)

    async def _status_impl(self, interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        # Guild ophalen (uit interaction of uit channel), en IDs veilig casten naar int
        guild = getattr(interaction, "guild", None) or getattr(channel, "guild", None)

        gid_raw = getattr(guild, "id", 0) if guild is not None else 0
        try:
            gid_val: int = int(gid_raw)
        except Exception:
            gid_val = 0

        cid_raw = getattr(channel, "id", 0)
        try:
            cid_val: int = int(cid_raw)
        except Exception:
            cid_val = 0

        try:
            pauze_txt = "Ja" if is_paused(cid_val) else "Nee"

            embed = discord.Embed(
                title="📊 DMK-poll status",
                description=f"⏸️ Pauze: **{pauze_txt}**",
                color=discord.Color.blurple(),
            )

            # Gescopeerde stemmen voor dit guild en kanaal
            scoped = await load_votes(gid_val, cid_val)

            for dag in ["vrijdag", "zaterdag", "zondag"]:
                instelling = get_setting(cid_val, dag)
                zicht_txt = (
                    "altijd zichtbaar"
                    if (instelling or {}).get("modus") == "altijd"
                    else f"deadline {(instelling or {}).get('tijd', '18:00')}"
                )

                regels: list[str] = []
                for opt in get_poll_options():
                    if opt.dag != dag:
                        continue

                    totaal, groepen_txt = await build_grouped_names_for(
                        dag, opt.tijd, guild, scoped
                    )

                    regel = f"{opt.emoji} {opt.tijd} — **{totaal}** stemmen"
                    if groepen_txt:
                        regel += f":  {groepen_txt}"
                    regels.append(regel)

                value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
                embed.add_field(
                    name=f"{dag.capitalize()} ({zicht_txt})",
                    value=value,
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    # -----------------------------
    # /dmk-poll-notify (fallback)
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-notify",
        description="Stuur handmatig een notificatie voor DMK-poll.",
    )
    @app_commands.describe(
        dag="Optioneel: vrijdag, zaterdag of zondag. Zonder dag wordt de algemene resetmelding gestuurd."
    )
    @app_commands.choices(
        dag=[
            app_commands.Choice(name="vrijdag", value="vrijdag"),
            app_commands.Choice(name="zaterdag", value="zaterdag"),
            app_commands.Choice(name="zondag", value="zondag"),
        ]
    )
    async def notify_fallback(
        self,
        interaction: discord.Interaction,
        dag: Optional[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        channel = getattr(interaction, "channel", None)
        if channel is None:
            return

        # 1) kanaal is uitgeschakeld → stil terug
        if is_channel_disabled(getattr(channel, "id", 0)):
            return

        # 2) kanaal is denied → stil terug
        if _is_denied_channel(channel):
            return

        # 3) alleen in actieve poll-kanalen → stil terug
        allow_from_per_channel_only = os.getenv(
            "ALLOW_FROM_PER_CHANNEL_ONLY", "true"
        ).lower() in {"1", "true", "yes", "y"}
        if allow_from_per_channel_only and not _is_poll_channel(channel):
            return

        try:
            if dag:
                dag_str = dag.lower()
                handled = await scheduler.notify_non_voters(
                    self.bot, dag=dag_str, channel=channel
                )
                if handled:
                    await interaction.followup.send(
                        f"Notificatie voor **{dag_str}** is verstuurd.", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"Geen notificatie verstuurd voor **{dag_str}** (geen niet-stemmers gevonden).",
                        ephemeral=True,
                    )
                return

            # Geen dag → algemene melding
            await safe_call(channel.send, RESET_TEXT)
            await interaction.followup.send(
                "Algemene melding is verstuurd.", ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"Er ging iets mis: {e}", ephemeral=True)

    # -----------------------------
    # Gast-commando's
    # -----------------------------
    # Iedereen mag gasten toevoegen
    @app_commands.guild_only()
    @app_commands.command(
        name="gast-add",
        description="Voeg gaststemmen toe voor een dag+tijd. Meerdere namen scheiden met , of ;",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name="Vrijdag 19:00", value="vrijdag|om 19:00 uur"),
            app_commands.Choice(name="Vrijdag 20:30", value="vrijdag|om 20:30 uur"),
            app_commands.Choice(name="Zaterdag 19:00", value="zaterdag|om 19:00 uur"),
            app_commands.Choice(name="Zaterdag 20:30", value="zaterdag|om 20:30 uur"),
            app_commands.Choice(name="Zondag 19:00", value="zondag|om 19:00 uur"),
            app_commands.Choice(name="Zondag 20:30", value="zondag|om 20:30 uur"),
        ],
    )
    @app_commands.describe(namen="Meerdere namen met komma, bv: Mario, Luigi, Peach")
    async def gast_add(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        namen: str,
    ) -> None:
        """Voorbeeld: /gast-add slot:'Vrijdag 20:30' namen:'Mario, Luigi, Peach'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)

            # Split op komma of puntkomma
            ruwe = [p.strip() for p in re.split(r"[;,]", namen or "") if p.strip()]
            if not ruwe:
                await interaction.followup.send(
                    "⚠️ Geen geldige namen opgegeven.", ephemeral=True
                )
                return

            toegevoegd, overgeslagen = await add_guest_votes(
                interaction.user.id,
                dag,
                tijd,
                ruwe,
                (
                    getattr(interaction.guild, "id", "0")
                    if interaction.guild is not None
                    else "0"
                ),
                getattr(interaction.channel, "id", "0") or "0",
            )

            # Publieke pollbericht voor díe dag even updaten
            await update_poll_message(channel=interaction.channel, dag=dag)

            parts: list[str] = []
            if toegevoegd:
                parts.append(f"✅ Toegevoegd: {', '.join(toegevoegd)}")
            if overgeslagen:
                parts.append(f"ℹ️ Overgeslagen (bestond al): {', '.join(overgeslagen)}")
            if not parts:
                parts = ["(niets gewijzigd)"]

            await interaction.followup.send(
                f"👥 Gaststemmen voor **{dag} {tijd}**\n" + "\n".join(parts),
                ephemeral=True,
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(
        name="gast-remove",
        description="Verwijder gaststemmen voor een dag+tijd. Meerdere namen scheiden met , of ;",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name="Vrijdag 19:00", value="vrijdag|om 19:00 uur"),
            app_commands.Choice(name="Vrijdag 20:30", value="vrijdag|om 20:30 uur"),
            app_commands.Choice(name="Zaterdag 19:00", value="zaterdag|om 19:00 uur"),
            app_commands.Choice(name="Zaterdag 20:30", value="zaterdag|om 20:30 uur"),
            app_commands.Choice(name="Zondag 19:00", value="zondag|om 19:00 uur"),
            app_commands.Choice(name="Zondag 20:30", value="zondag|om 20:30 uur"),
        ],
    )
    @app_commands.describe(namen="Meerdere namen met komma, bv: Mario, Luigi, Peach")
    async def gast_remove(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        namen: str,
    ) -> None:
        """Voorbeeld: /gast-remove slot:'Vrijdag 20:30' namen:'Mario, Luigi'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)
            ruwe = [p.strip() for p in re.split(r"[;,]", namen or "") if p.strip()]
            if not ruwe:
                await interaction.followup.send(
                    "⚠️ Geen geldige namen opgegeven.", ephemeral=True
                )
                return

            verwijderd, nietgevonden = await remove_guest_votes(
                interaction.user.id,
                dag,
                tijd,
                ruwe,
                (
                    getattr(interaction.guild, "id", "0")
                    if interaction.guild is not None
                    else "0"
                ),
                getattr(interaction.channel, "id", "0") or "0",
            )

            # Publieke pollbericht voor díe dag updaten
            await update_poll_message(channel=interaction.channel, dag=dag)

            parts: list[str] = []
            if verwijderd:
                parts.append(f"✅ Verwijderd: {', '.join(verwijderd)}")
            if nietgevonden:
                parts.append(f"ℹ️ Niet gevonden: {', '.join(nietgevonden)}")
            if not parts:
                parts = ["(niets gewijzigd)"]

            await interaction.followup.send(
                f"👥 Gaststemmen verwijderd voor **{dag} {tijd}**\n" + "\n".join(parts),
                ephemeral=True,
            )
        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    c = DMKPoll(bot)
    bot.tree.on_error = c.on_app_command_error
    await bot.add_cog(c)
