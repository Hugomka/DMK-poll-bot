# apps/ui/poll_buttons.py

from datetime import datetime
from zoneinfo import ZoneInfo
import discord
from discord.ui import View, Button
from discord import Interaction, ButtonStyle
from apps.logic.visibility import is_vote_button_visible
from apps.utils.poll_settings import is_paused
from apps.utils.poll_storage import toggle_vote, get_user_votes
from apps.utils.poll_message import update_poll_message
from apps.entities.poll_option import get_poll_options, list_days


class PollButton(Button):
    def __init__(self, dag: str, tijd: str, label: str, stijl: ButtonStyle):
        super().__init__(label=label, style=stijl, custom_id=f"{dag}:{tijd}")
        self.dag = dag
        self.tijd = tijd

    async def callback(self, interaction: Interaction):
        if is_paused(interaction.channel.id):
            await interaction.response.send_message("⏸️ Stemmen is gepauzeerd.", ephemeral=True)
            return

        user_id = str(interaction.user.id)

        # ✅ Check of stem nog klopt met votes.json (bijvoorbeeld na reset)
        user_votes = await get_user_votes(user_id)
        dag_opties = user_votes.get(self.dag, [])
        if self.tijd not in dag_opties and dag_opties != []:
            # oude knop zichtbaar, maar stem niet meer geldig → view is verouderd
            new_view = await create_poll_button_view(user_id, interaction.channel.id)
            await interaction.response.send_message(
                "🔄 De stemknoppen zijn opnieuw geladen, bijvoorbeeld na een reset.",
                view=new_view,
                ephemeral=True
            )
            return

        # ✅ Toggle stem
        await toggle_vote(user_id, self.dag, self.tijd)

        # ✅ Vervang eigen view (ephemeral)
        new_view = await create_poll_button_view(user_id, interaction.channel.id)
        if interaction.response.is_done():
            await interaction.edit_original_response(view=new_view)
        else:
            await interaction.response.edit_message(view=new_view)

        # ✅ Update publieke poll
        await update_poll_message(interaction.channel)


class PollButtonView(View):
    """Ephemeral stemknoppen voor 1 gebruiker (optioneel gefilterd op dag)."""
    def __init__(self, votes: dict, channel_id: int, filter_dag: str | None = None, now: datetime | None = None):
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

async def create_poll_button_views_per_day(user_id: str, channel_id: int) -> list[tuple[str, PollButtonView]]:
    votes = await get_user_votes(user_id)
    now = datetime.now(ZoneInfo("Europe/Amsterdam"))
    views = []

    for dag in list_days():
        view = PollButtonView(votes, channel_id, filter_dag=dag, now=now)
        if view.children:  # alleen tonen als er knoppen zijn
            views.append((dag, view))
    return views

class OpenStemmenButton(Button):
    def __init__(self, paused: bool = False):
        label = "🗳️ Stemmen (gepauzeerd)" if paused else "🗳️ Stemmen"
        style = ButtonStyle.secondary if paused else ButtonStyle.primary
        super().__init__(label=label, style=style, custom_id="open_stemmen", disabled=paused)

    async def callback(self, interaction: Interaction):
        if is_paused(interaction.channel.id):
            await interaction.response.send_message("⏸️ Stemmen is tijdelijk gepauzeerd.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        channel_id = interaction.channel.id
        views_per_dag = await create_poll_button_views_per_day(user_id, channel_id)

        if not views_per_dag:
            await interaction.response.send_message(
                "Stemmen is gesloten voor alle dagen. Kom later terug.",
                ephemeral=True
            )
            return

        # Hoofdbericht met uitleg
        await interaction.response.send_message(
            "Kies jouw tijden hieronder 👇 per dag (alleen jij ziet dit).",
            ephemeral=True
        )

        for dag, view in views_per_dag:
            await interaction.followup.send(
                f"📅 **{dag.capitalize()}** — kies jouw tijden 👇",
                view=view,
                ephemeral=True
            )

class OneStemButtonView(View):
    """De vaste stemknop onderaan het pollbericht."""
    def __init__(self, paused: bool = False):
        super().__init__(timeout=None)
        self.add_item(OpenStemmenButton(paused))

    @classmethod
    def is_persistent(cls) -> bool:
        return True
