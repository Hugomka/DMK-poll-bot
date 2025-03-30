from discord.ui import View, Button
from discord import Interaction, ButtonStyle
from apps.utils.poll_storage import add_vote
from apps.utils.poll_message import update_poll_message
from apps.utils.poll_storage import get_user_votes
from apps.entities.poll_option import POLL_OPTIONS
from discord import ButtonStyle


class PollButtonView(View):
    def __init__(self, user_id=""):
        super().__init__(timeout=None)
        votes = get_user_votes(user_id) if user_id else {}
        for option in POLL_OPTIONS:
            is_selected = False

            if option.dag in ["misschien", "niet_meedoen"]:
                is_selected = votes.get(option.dag) is True
            else:
                is_selected = option.tijd in votes.get(option.dag, [])

            stijl = ButtonStyle.success if is_selected else option.stijl
            self.add_item(PollButton(option.dag, option.tijd, option.label, stijl))

class PollButton(Button):
    def __init__(self, dag, tijd, label, stijl):
        super().__init__(label=label, style=stijl, custom_id=f"{dag}:{tijd}")
        self.dag = dag
        self.tijd = tijd

    async def callback(self, interaction: Interaction):
        try:
            user_id = str(interaction.user.id)
            await interaction.response.defer(ephemeral=True)

            add_vote(user_id, self.dag, self.tijd)
            await update_poll_message(interaction.channel)

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)
