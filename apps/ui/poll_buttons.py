# apps/ui/poll_buttons.py

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from discord import ButtonStyle, Interaction
from discord.ui import Button, View

from apps.entities.poll_option import get_poll_options
from apps.logic.visibility import is_vote_button_visible
from apps.utils.poll_message import check_all_voted_celebration, update_poll_message
from apps.utils.poll_settings import (
    get_poll_option_state,
    is_paused,
)
from apps.utils.poll_storage import get_user_votes, toggle_vote
from apps.utils.time_zone_helper import TimeZoneHelper
from apps.utils.message_builder import _get_next_weekday_date_iso

HEADER_TMPL = "📅 **{dag}** — kies jouw tijden 👇"


def _get_timezone_legend(dag: str) -> str:
    """Genereer compacte tijdzone legenda voor ephemeral stem-interface."""
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

    # Fallback als dag niet gevonden (zou niet moeten gebeuren)
    if datum_iso is None:
        datum_iso = _get_next_weekday_date_iso(dag)

    tijd_1900 = TimeZoneHelper.nl_tijd_naar_hammertime(datum_iso, "19:00", style="F")
    tijd_2030 = TimeZoneHelper.nl_tijd_naar_hammertime(datum_iso, "20:30", style="F")
    return f"{emoji_1900} 19:00 = {tijd_1900} | {emoji_2030} 20:30 = {tijd_2030}"


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
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "⚠️ Deze knop werkt alleen in een serverkanaal.", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "⚠️ Deze knop werkt alleen in een serverkanaal.", ephemeral=True
                    )
                return

            if is_paused(channel_id):
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "⏸️ Stemmen is gepauzeerd.", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "⏸️ Stemmen is gepauzeerd.", ephemeral=True
                    )
                return

            user_id = str(interaction.user.id)
            guild_id: int = int(
                interaction.guild_id or getattr(interaction.guild, "id", 0) or 0
            )
            now = datetime.now(ZoneInfo("Europe/Amsterdam"))

            # ✅ Snelle ACK: bewerk meteen hetzelfde ephemere bericht (geen nieuw bericht)
            header = HEADER_TMPL.format(dag=self.dag.capitalize())
            legenda = _get_timezone_legend(self.dag)
            header_volledig = f"{header}\n{legenda}"
            if not interaction.response.is_done():
                try:
                    await interaction.response.edit_message(
                        content=f"{header_volledig}\n🔄 Je stem wordt verwerkt…"
                    )
                except Exception:  # pragma: no cover
                    # Als het niet lukt, val later terug op message.edit
                    pass

            # ✅ Check zichtbaarheid
            if not is_vote_button_visible(channel_id, self.dag, self.tijd, now):
                # Bewerk hetzelfde bericht en stop
                try:
                    if interaction.message is not None:
                        await interaction.message.edit(
                            content=f"{header_volledig}\n❌ De stemmogelijkheid is gesloten.",
                            view=None,
                        )
                    else:
                        await interaction.edit_original_response(
                            content=f"{header_volledig}\n❌ De stemmogelijkheid is gesloten.",
                            view=None,
                        )
                except Exception:  # pragma: no cover
                    pass
                return

            # ✅ Toggle stem (onder lock in poll_storage)
            await toggle_vote(
                user_id, self.dag, self.tijd, (interaction.guild_id or 0), channel_id
            )

            # ✅ Vernieuw eigen ephemeral view (zelfde bericht)
            new_view = await create_poll_button_view(
                user_id, guild_id, channel_id, dag=self.dag
            )

            # Toon korte status in hetzelfde bericht (geen followup-spam)
            status = "✅ Je stem is verwerkt."
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
            if interaction.channel is not None:
                asyncio.create_task(update_poll_message(interaction.channel, self.dag))
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
                header = HEADER_TMPL.format(dag=self.dag.capitalize())
                legenda = _get_timezone_legend(self.dag)
                header_volledig = f"{header}\n{legenda}"
                msg = "⚠️ Er ging iets mis, probeer opnieuw."
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

        for option in get_poll_options():
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
            header = HEADER_TMPL.format(dag=dag.capitalize())
            # Voeg tijdzone legenda toe
            legenda = _get_timezone_legend(dag)
            header_met_legenda = f"{header}\n{legenda}"
            views.append((dag, header_met_legenda, view))
    return views


class OpenStemmenButton(Button):
    def __init__(self, paused: bool = False):
        label = "🗳️ Stemmen (gepauzeerd)" if paused else "🗳️ Stemmen"
        style = ButtonStyle.secondary if paused else ButtonStyle.primary
        super().__init__(
            label=label, style=style, custom_id="open_stemmen", disabled=paused
        )

    async def callback(self, interaction: Interaction):
        channel_id = interaction.channel_id
        if channel_id is None:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "⚠️ Deze knop werkt alleen in een serverkanaal.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "⚠️ Deze knop werkt alleen in een serverkanaal.", ephemeral=True
                )
            return

        if is_paused(channel_id):
            await interaction.response.send_message(
                "⏸️ Stemmen is tijdelijk gepauzeerd.", ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        views_per_dag = await create_poll_button_views_per_day(
            user_id, (interaction.guild_id or 0), channel_id
        )

        if not views_per_dag:
            await interaction.response.send_message(
                "Stemmen is gesloten voor alle dagen. Kom later terug.", ephemeral=True
            )
            return

        # ✅ Eén ephemere instructie en per dag één bericht (latere klikken bewerken *ditzelfde* bericht)
        await interaction.response.send_message(
            "Kies jouw tijden hieronder 👇 per dag (alleen jij ziet dit).",
            ephemeral=True,
        )

        for dag, header, view in views_per_dag:
            await interaction.followup.send(header, view=view, ephemeral=True)


class OneStemButtonView(View):
    """De vaste stemknop onderaan het pollbericht."""

    def __init__(self, paused: bool = False):
        super().__init__(timeout=None)
        self.add_item(OpenStemmenButton(paused))
