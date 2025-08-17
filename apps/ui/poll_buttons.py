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
from apps.entities.poll_option import get_poll_options


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
    """Ephemeral stemknoppen voor 1 gebruiker."""
    def __init__(self, votes: dict, channel_id: int):
        super().__init__(timeout=60)
        now = datetime.now(ZoneInfo("Europe/Amsterdam"))

        for option in get_poll_options():
            # 🔒 Verberg knop als deze niet meer geldig is
            if not is_vote_button_visible(channel_id, option.dag, option.tijd, now):
                continue

            selected = option.tijd in votes.get(option.dag, [])
            stijl = ButtonStyle.success if selected else ButtonStyle.secondary
            label = f"✅ {option.label}" if selected else option.label
            self.add_item(PollButton(option.dag, option.tijd, label, stijl))

async def create_poll_button_view(user_id: str, channel_id: int) -> PollButtonView:
    votes = await get_user_votes(user_id)
    return PollButtonView(votes, channel_id)

class OpenStemmenButton(Button):
    def __init__(self, paused: bool = False):
        label = "🗳️ Stemmen (gepauzeerd)" if paused else "🗳️ Stemmen"
        style = ButtonStyle.secondary if paused else ButtonStyle.primary
        super().__init__(label=label, style=style, custom_id="open_stemmen", disabled=paused)

    async def callback(self, interaction: Interaction):
        if is_paused(interaction.channel.id):
            await interaction.response.send_message("⏸️ Stemmen is tijdelijk gepauzeerd.", ephemeral=True)
            return

        view = await create_poll_button_view(str(interaction.user.id), interaction.channel.id)
        message_text = (
            "Kies jouw tijden hieronder 👇 (alleen jij ziet dit)."
            if view.children
            else "Stemmen is gesloten voor alle dagen. Kom later terug."
        )
        await interaction.response.send_message(
            message_text,
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
