# apps/commands/poll_status.py
#
# Status en notificaties voor DMK-poll

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apps.commands import with_default_suffix
from apps.entities.poll_option import get_poll_options
from apps.utils.celebration_gif import get_celebration_gif_url
from apps.utils.message_builder import build_grouped_names_for, get_non_voters_for_day
from apps.utils.poll_message import (
    LOCAL_CELEBRATION_IMAGE,
    create_celebration_embed,
    is_channel_disabled,
)
from apps.utils.poll_settings import (
    WEEKEND_DAYS,
    get_setting,
    is_paused,
    get_effective_activation,
    get_effective_deactivation,
)
from apps.utils.poll_storage import get_was_misschien_count, load_votes
from apps.utils.notification_texts import (
    NOTIFICATION_TEXTS,
    format_opening_time_from_schedule,
    get_notification_by_name,
    get_text_herinnering_dag,
    get_text_poll_gesloten,
)


def _is_denied_channel(channel) -> bool:
    names = set(
        n.strip().lower()
        for n in os.getenv("DENY_CHANNEL_NAMES", "").split(",")
        if n.strip()
    )
    ch_name = (getattr(channel, "name", "") or "").lower()
    return ch_name in names


class PollStatus(commands.Cog):
    """Status en notificaties"""

    def __init__(self, bot):
        self.bot = bot

    # -----------------------------
    # /dmk-poll-status
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-status",
        description=with_default_suffix("Toon pauze, zichtbaarheid en alle stemmen per dag"),
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
        except Exception:  # pragma: no cover
            gid_val = 0

        cid_raw = getattr(channel, "id", 0)
        try:
            cid_val: int = int(cid_raw)
        except Exception:  # pragma: no cover
            cid_val = 0

        # Helper function to format schedule information
        def format_schedule(schedule: Optional[dict], is_default: bool) -> str:
            """Format a schedule dict into a readable Dutch string with default label."""
            if not schedule:
                return "Geen"

            day_names = ["maandag", "dinsdag", "woensdag", "donderdag",
                        "vrijdag", "zaterdag", "zondag"]

            typ = schedule.get("type")
            tijd = schedule.get("tijd", "??:??")

            if typ == "datum":
                datum = schedule.get("datum", "")
                try:
                    # Convert from internal YYYY-MM-DD to display DD-MM-YYYY
                    datum_obj = datetime.strptime(datum, "%Y-%m-%d")
                    datum_display = datum_obj.strftime("%d-%m-%Y")
                    dag_naam = day_names[datum_obj.weekday()]
                    result = f"{dag_naam} {datum_display} om {tijd}"
                except Exception:  # pragma: no cover
                    result = f"{datum} om {tijd}"
            elif typ == "wekelijks":
                dag = schedule.get("dag", "?")
                result = f"elke {dag} om {tijd}"
            else:  # pragma: no cover
                result = "Onbekend"

            # Add default label if this is a default schedule
            if is_default and result != "Geen":
                result += "  *(default)*"

            return result

        try:
            pauze_txt = "Ja" if is_paused(cid_val) else "Nee"

            # Retrieve effective schedule information (with fallback to defaults)
            act_sched, act_is_default = get_effective_activation(cid_val)
            deact_sched, deact_is_default = get_effective_deactivation(cid_val)

            embed = discord.Embed(
                title="📊 DMK-poll status",
                description=f"⏸️ Pauze: **{pauze_txt}**",
                color=discord.Color.blurple(),
            )

            # Add schedule fields with default labels
            embed.add_field(
                name="🗓️ Geplande activatie",
                value=format_schedule(act_sched, act_is_default),
                inline=False,
            )
            embed.add_field(
                name="🗑️ Geplande deactivatie",
                value=format_schedule(deact_sched, deact_is_default),
                inline=False,
            )

            # Gescopeerde stemmen voor dit guild en kanaal
            scoped = await load_votes(gid_val, cid_val)

            for dag in WEEKEND_DAYS:
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

                    # Insert was_misschien after misschien option
                    if opt.tijd == "misschien":
                        was_misschien = await get_was_misschien_count(dag, gid_val, cid_val)
                        regel = f"💤 was misschien — **{was_misschien}** stemmen"
                        regels.append(regel)

                # Voeg niet-stemmers toe (altijd tonen) - at the end
                non_voter_count, non_voter_text = await get_non_voters_for_day(
                    dag, guild, channel, scoped
                )
                regel = f"👻 niet gestemd — **{non_voter_count}** stemmen"
                if non_voter_text:
                    regel += f":  {non_voter_text}"
                regels.append(regel)

                value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
                embed.add_field(
                    name=f"{dag.capitalize()} ({zicht_txt})",
                    value=value,
                    inline=False,
                )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none()
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    # -----------------------------
    # /dmk-poll-notify
    # -----------------------------
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.command(
        name="dmk-poll-notify",
        description="Stuur handmatig een notificatie voor DMK-poll.",
    )
    @app_commands.describe(
        notificatie="Kies een standaard notificatietekst.",
        eigen_tekst="Optioneel: eigen notificatietekst (overschrijft standaard keuze).",
        ping="Kies welke ping te gebruiken (default: everyone)."
    )
    @app_commands.choices(
        notificatie=[
            app_commands.Choice(name=notif.name, value=notif.name)
            for notif in NOTIFICATION_TEXTS
        ],
        ping=[
            app_commands.Choice(name="everyone", value="everyone"),
            app_commands.Choice(name="here", value="here"),
            app_commands.Choice(name="none", value="none")
        ]
    )
    async def notify_fallback(
        self,
        interaction: discord.Interaction,
        notificatie: Optional[str] = None,
        eigen_tekst: Optional[str] = None,
        ping: Optional[str] = "everyone",
    ):
        await interaction.response.defer(ephemeral=True)
        channel = getattr(interaction, "channel", None)
        if channel is None:
            await interaction.followup.send("❌ Geen kanaal gevonden.", ephemeral=True)
            return

        cid = getattr(channel, "id", 0)

        # 1) Kanaal is uitgeschakeld → toon sluitingsbericht met heropening tijd
        if is_channel_disabled(cid):
            try:
                act_schedule, _ = get_effective_activation(cid)
                opening_time = format_opening_time_from_schedule(act_schedule)
                sluitingsbericht = get_text_poll_gesloten(opening_time)

                send = getattr(channel, "send", None)
                if send:
                    from apps.utils.discord_client import safe_call
                    await safe_call(send, content=sluitingsbericht)

                await interaction.followup.send(
                    f"Sluitingsbericht verstuurd (poll gaat open: **{opening_time}**).", ephemeral=True
                )
            except Exception as e:  # pragma: no cover
                await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)
            return

        # 2) Kanaal is denied → stil terug
        if _is_denied_channel(channel):
            await interaction.followup.send("❌ Dit kanaal is uitgesloten van notificaties.", ephemeral=True)
            return

        # 3) Zet scheduler aan (enable channel voor scheduler)
        from apps.utils.poll_message import set_channel_disabled
        set_channel_disabled(cid, False)

        # 4) Bepaal de te versturen tekst
        try:
            # Eigen tekst heeft prioriteit
            if eigen_tekst:
                notification_text = eigen_tekst
                notification_name = "Eigen tekst"
            elif notificatie:
                notification_name = notificatie

                # Dag-specifieke herinneringen gebruiken helper functie
                if notificatie == "Herinnering vrijdag":
                    notification_text = get_text_herinnering_dag("vrijdag")
                elif notificatie == "Herinnering zaterdag":
                    notification_text = get_text_herinnering_dag("zaterdag")
                elif notificatie == "Herinnering zondag":
                    notification_text = get_text_herinnering_dag("zondag")
                elif notificatie == "Poll gesloten":
                    # Poll gesloten moet dynamisch opening time gebruiken
                    act_schedule, _ = get_effective_activation(cid)
                    opening_time = format_opening_time_from_schedule(act_schedule)
                    notification_text = get_text_poll_gesloten(opening_time)
                else:
                    # Zoek standaard notificatie op naam
                    notif = get_notification_by_name(notificatie)
                    if notif:
                        notification_text = notif.content
                    else:
                        await interaction.followup.send("❌ Onbekende notificatie geselecteerd.", ephemeral=True)
                        return
            else:
                await interaction.followup.send(
                    "❌ Geef een notificatie of eigen tekst op.",
                    ephemeral=True
                )
                return

            # Verstuur notificatie
            # Felicitatie is speciaal: stuurt embed + los GIF bericht
            if notificatie == "Felicitatie (iedereen gestemd)":
                from apps.utils.discord_client import fetch_message_or_none, safe_call
                from apps.utils.poll_message import (
                    clear_message_id,
                    get_message_id,
                    save_message_id,
                )

                # Verwijder eerst oude celebration berichten (indien aanwezig)
                celebration_id = get_message_id(cid, "celebration")
                if celebration_id:
                    msg = await fetch_message_or_none(channel, celebration_id)
                    if msg:
                        await safe_call(msg.delete)
                    clear_message_id(cid, "celebration")

                celebration_gif_id = get_message_id(cid, "celebration_gif")
                if celebration_gif_id:
                    gif_msg = await fetch_message_or_none(channel, celebration_gif_id)
                    if gif_msg:
                        await safe_call(gif_msg.delete)
                    clear_message_id(cid, "celebration_gif")

                # Nu celebration berichten sturen
                embed = create_celebration_embed()

                send = getattr(channel, "send", None)
                if send:
                    # Stuur eerst embed met tekst
                    new_msg = await safe_call(send, embed=embed)
                    if new_msg:
                        save_message_id(cid, "celebration", new_msg.id)

                    # Selecteer random Tenor URL met gewogen selectie
                    tenor_url = get_celebration_gif_url()

                    # Probeer eerst Tenor URL, fallback naar lokale afbeelding
                    gif_msg = None
                    if tenor_url:
                        gif_msg = await safe_call(send, content=tenor_url)

                    # Sla GIF message ID op (Tenor of fallback)
                    if gif_msg:
                        save_message_id(cid, "celebration_gif", gif_msg.id)
                    elif os.path.exists(LOCAL_CELEBRATION_IMAGE):
                        # Als Tenor niet werkt, stuur lokale afbeelding
                        with open(LOCAL_CELEBRATION_IMAGE, "rb") as f:
                            file = discord.File(f, filename="bedankt.jpg")
                            fallback_msg = await safe_call(send, file=file)
                            if fallback_msg:
                                save_message_id(cid, "celebration_gif", fallback_msg.id)
            else:
                # Normale notificatie met tekst
                from apps.utils.mention_utils import send_temporary_mention

                # Convert ping parameter to mention string
                if ping == "none":
                    mention_str = None
                elif ping == "here":
                    mention_str = "@here"
                else:  # everyone (default)
                    mention_str = "@everyone"

                await send_temporary_mention(channel, mentions=mention_str, text=notification_text)

            # Include ping type in confirmation message
            ping_info = f" (ping: {ping})" if ping != "everyone" else ""
            await interaction.followup.send(
                f"✅ Notificatie verstuurd: **{notification_name}**{ping_info}", ephemeral=True
            )

        except Exception as e:  # pragma: no cover
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollStatus(bot))
