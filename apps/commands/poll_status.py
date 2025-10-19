# apps/commands/poll_status.py
#
# Status en notificaties voor DMK-poll

from __future__ import annotations

import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from apps import scheduler
from apps.entities.poll_option import get_poll_options
from apps.utils.message_builder import build_grouped_names_for
from apps.utils.poll_message import is_channel_disabled
from apps.utils.poll_settings import get_setting, is_paused
from apps.utils.poll_storage import load_votes


# Hergebruik constants en helpers uit dmk_poll
RESET_TEXT = (
    "@everyone De poll is zojuist gereset voor het nieuwe weekend. "
    "Je kunt weer stemmen. Veel plezier!"
)


def _is_poll_channel(channel) -> bool:
    """Alleen toestaan in een kanaal waar de bot actief is (heeft poll-IDs)."""
    from apps.utils.poll_message import get_message_id

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

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none()
            )

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

            # Geen dag → algemene melding via notificatiebericht
            from apps.utils.mention_utils import send_temporary_mention

            await send_temporary_mention(channel, mentions="@everyone", text=RESET_TEXT.replace("@everyone ", ""))
            await interaction.followup.send(
                "Algemene melding is verstuurd.", ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"Er ging iets mis: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollStatus(bot))
