# apps/ui/poll_buttons.py

from datetime import datetime
from zoneinfo import ZoneInfo

from discord import ButtonStyle, Interaction
from discord.ui import Button, View

from apps.entities.poll_option import get_poll_options, list_days
from apps.logic.visibility import is_vote_button_visible
from apps.utils.poll_message import update_poll_message
from apps.utils.poll_settings import is_paused
from apps.utils.poll_storage import get_user_votes, toggle_vote


class PollButton(Button):
    def __init__(self, dag: str, tijd: str, label: str, stijl: ButtonStyle):
        super().__init__(label=label, style=stijl, custom_id=f"{dag}:{tijd}")
        self.dag = dag
        self.tijd = tijd

    async def callback(self, interaction: Interaction):
        try:
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
                    "⏸️ Stemmen is gepauzeerd.", ephemeral=True
                )
                return

            user_id = str(interaction.user.id)
            guild_id: int = int(
                interaction.guild_id or getattr(interaction.guild, "id", 0) or 0
            )

            # ✅ Check of stemmen nog open is
            now = datetime.now(ZoneInfo("Europe/Amsterdam"))
            if not is_vote_button_visible(channel_id, self.dag, self.tijd, now):
                await interaction.response.send_message(
                    f"❌ De stemmogelijkheid voor **{self.dag} {self.tijd}** is gesloten.",
                    ephemeral=True,
                )
                return

            # ✅ Toggle stem
            await toggle_vote(
                user_id, self.dag, self.tijd, (interaction.guild_id or 0), channel_id
            )

            # ✅ Vernieuw eigen ephemeral view (alleen voor deze gebruiker)
            new_view = await create_poll_button_view(
                user_id, guild_id, channel_id, dag=self.dag
            )
            if interaction.response.is_done():
                await interaction.edit_original_response(view=new_view)
            else:
                await interaction.response.edit_message(view=new_view)

            # ✅ Update publieke poll (als er een kanaal is)
            if interaction.channel is not None:
                await update_poll_message(interaction.channel)

        except Exception as e:
            print(f"⚠️ Fout bij verwerken stemknop: {e}")
            # Probeer alsnog nieuwe knoppen te tonen
            try:
                channel_id = interaction.channel_id
                if channel_id is None:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            "⚠️ Geen geldig kanaal.", ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "⚠️ Geen geldig kanaal.", ephemeral=True
                        )
                    return

                views_per_dag = await create_poll_button_views_per_day(
                    str(interaction.user.id), guild_id, channel_id
                )

                if not views_per_dag:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            "🔄 De stemknoppen zijn verlopen en alle dagen zijn gesloten.",
                            ephemeral=True,
                        )
                    else:
                        await interaction.response.send_message(
                            "🔄 De stemknoppen zijn verlopen en alle dagen zijn gesloten.",
                            ephemeral=True,
                        )
                    return

                # Begin met uitlegbericht
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "🔄 De stemknoppen zijn opnieuw geladen, bijvoorbeeld na een reset.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "🔄 De stemknoppen zijn opnieuw geladen, bijvoorbeeld na een reset.",
                        ephemeral=True,
                    )

                # Toon aparte views per dag
                for dag, view in views_per_dag:
                    await interaction.followup.send(
                        f"📅 **{dag.capitalize()}** — kies jouw tijden 👇",
                        view=view,
                        ephemeral=True,
                    )
            except Exception as inner:
                print(f"❌ Kon geen nieuwe view tonen: {inner}")


class PollButtonView(View):
    """Ephemeral stemknoppen voor 1 gebruiker (optioneel gefilterd op dag)."""

    def __init__(
        self,
        votes: dict,
        channel_id: int,
        filter_dag: str | None = None,
        now: datetime | None = None,
    ):
        super().__init__(timeout=60)
        now = now or datetime.now(ZoneInfo("Europe/Amsterdam"))

        for option in get_poll_options():
            if filter_dag and option.dag != filter_dag:
                continue

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
) -> list[tuple[str, PollButtonView]]:
    votes = await get_user_votes(user_id, guild_id, channel_id)
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    views: list[tuple[str, PollButtonView]] = []

    for dag in list_days():
        view = PollButtonView(votes, channel_id, filter_dag=dag, now=now)
        if view.children:  # alleen tonen als er knoppen zijn
            views.append((dag, view))
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

        # ✅ Start met uitleg
        await interaction.response.send_message(
            "Kies jouw tijden hieronder 👇 per dag (alleen jij ziet dit).",
            ephemeral=True,
        )

        # ✅ Toon stemknoppen per dag
        for dag, view in views_per_dag:
            await interaction.followup.send(
                f"📅 **{dag.capitalize()}** — kies jouw tijden 👇",
                view=view,
                ephemeral=True,
            )


class OneStemButtonView(View):
    """De vaste stemknop onderaan het pollbericht."""

    def __init__(self, paused: bool = False):
        super().__init__(timeout=None)
        self.add_item(OpenStemmenButton(paused))

    @classmethod
    def is_persistent(cls) -> bool:
        return True
