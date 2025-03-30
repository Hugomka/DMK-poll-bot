from discord.ui import View, Button
from discord import Interaction, ButtonStyle
from apps.utils.poll_storage import add_vote
from apps.utils.poll_message import update_poll_message

class PollButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)  # timeout=None = blijft altijd actief

        dagen = ["vrijdag", "zaterdag", "zondag"]
        tijden = ["19:00", "20:30"]

        for dag in dagen:
            for tijd in tijden:
                label = f"{dag.capitalize()} {tijd}"
                self.add_item(PollButton(dag, tijd, label))

        self.add_item(PollButton("misschien", "misschien", "Ⓜ️ Misschien", style=ButtonStyle.secondary))
        self.add_item(PollButton("niet", "niet", "❌ Niet meedoen", style=ButtonStyle.danger))

class PollButton(Button):
    def __init__(self, dag, tijd, label, style=ButtonStyle.primary):
        super().__init__(label=label, style=style, custom_id=f"{dag}:{tijd}")
        self.dag = dag
        self.tijd = tijd

    async def callback(self, interaction: Interaction):
        try:
            user_id = str(interaction.user.id)
            await interaction.response.defer(ephemeral=True)

            add_vote(user_id, self.dag, self.tijd)
            await update_poll_message(interaction.channel)
            await interaction.followup.send(f"✅ Je hebt gestemd op **{self.label}**", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)
